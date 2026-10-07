from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from flask import current_app
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import (
    AttendanceSession, AttendanceRecord, AttendanceAdjustment,
    Student, ClassRoom, Subject, User, FaceEncoding
)
from app.services.face_service import (
    get_face_engine, decode_base64_image, ConsecutiveMatchTracker
)
from app.utils import log_audit, get_setting


# In-memory consecutive match trackers per session_id: {session_id: ConsecutiveMatchTracker}
_session_trackers: Dict[int, ConsecutiveMatchTracker] = {}
# In-memory cached frames for liveness detection: {session_id: last_frame_bgr}
_session_last_frames: Dict[int, Any] = {}


def get_or_create_tracker(session_id: int) -> ConsecutiveMatchTracker:
    if session_id not in _session_trackers:
        _session_trackers[session_id] = ConsecutiveMatchTracker(required_matches=2)
    return _session_trackers[session_id]


def start_attendance_session(
    class_id: int,
    subject_id: int,
    teacher_id: int,
    period: int,
    session_date: datetime.date,
    duration_minutes: int = 60,
    session_name: Optional[str] = None
) -> Tuple[bool, str, Optional[AttendanceSession]]:
    """
    Creates and starts a new attendance session after validating constraints.
    """
    classroom = ClassRoom.query.get(class_id)
    subject = Subject.query.get(subject_id)
    teacher = User.query.get(teacher_id)

    if not classroom or not classroom.is_active:
        return False, "Classroom not found or inactive.", None
    if not subject or not subject.is_active:
        return False, "Subject not found or inactive.", None
    if not teacher or not teacher.is_active:
        return False, "Teacher not found or inactive.", None

    if subject.class_id != class_id:
        return False, "Subject does not belong to the selected classroom.", None

    # Check for existing active session for same class/subject/period/date
    existing_active = AttendanceSession.query.filter_by(
        class_id=class_id,
        subject_id=subject_id,
        period=period,
        date=session_date,
        status='active'
    ).first()

    if existing_active:
        return False, f"An active session (#{existing_active.id}) already exists for this class, subject, and period.", None

    if not session_name:
        session_name = f"{subject.name} - Period {period}"

    now = datetime.now(timezone.utc)
    session = AttendanceSession(
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=teacher_id,
        date=session_date,
        period=period,
        session_name=session_name,
        started_at=now,
        duration_minutes=duration_minutes,
        status='active'
    )

    try:
        db.session.add(session)
        db.session.commit()
        log_audit('SESSION_START', 'AttendanceSession', session.id, {
            'class_id': class_id,
            'subject_id': subject_id,
            'teacher_id': teacher_id,
            'date': str(session_date),
            'period': period
        }, user_id=teacher_id)
        return True, "Session started successfully.", session
    except Exception as e:
        db.session.rollback()
        return False, f"Database error starting session: {str(e)}", None


def check_and_expire_session(session: AttendanceSession) -> bool:
    """
    Checks if an active session has exceeded duration and automatically closes it.
    """
    if session.status != 'active':
        return False

    now = datetime.now(timezone.utc)
    started = session.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
        
    elapsed = (now - started).total_seconds() / 60.0
    if elapsed >= session.duration_minutes:
        end_attendance_session(session.id, user_id=session.teacher_id, reason="Auto-expired due to time limit")
        return True
    return False


def process_live_frame(session_id: int, base64_frame: str, current_user_id: int) -> Dict[str, Any]:
    """
    Processes incoming video frame from browser:
    - Verifies session is active
    - Decodes JPEG frame
    - Performs basic anti-spoofing heuristic
    - Detects faces and extracts encodings
    - Matches against enrolled students of this session's class
    - Buffers consecutive matches (requiring 2 consecutive matches)
    - Concurrency-safe attendance record insertion
    """
    session = AttendanceSession.query.get(session_id)
    if not session:
        return {'success': False, 'message': 'Session not found.', 'session_status': 'invalid'}

    # Verify authorization
    user = User.query.get(current_user_id)
    if not user or (not user.is_admin and user.id != session.teacher_id):
        return {'success': False, 'message': 'Unauthorized to conduct this session.', 'session_status': session.status}

    # Check auto expiration
    if check_and_expire_session(session):
        return {'success': False, 'message': 'Session has expired and was automatically closed.', 'session_status': 'ended'}

    if session.status != 'active':
        return {'success': False, 'message': f'Session is {session.status}.', 'session_status': session.status}

    try:
        image_bgr = decode_base64_image(base64_frame)
    except Exception as e:
        return {'success': False, 'message': f'Invalid image frame data: {str(e)}', 'session_status': 'active'}

    engine = get_face_engine()
    tracker = get_or_create_tracker(session_id)

    # Liveness check against previous frame
    prev_frame = _session_last_frames.get(session_id)
    is_live, liveness_msg = engine.check_liveness(image_bgr, prev_frame)
    _session_last_frames[session_id] = image_bgr

    # Detect faces
    detected_faces = engine.detect_faces(image_bgr)
    if not detected_faces:
        return {
            'success': True,
            'faces': [],
            'marked': [],
            'unknown_count': 0,
            'session_status': 'active',
            'liveness': liveness_msg
        }

    # Load enrolled encodings for students enrolled in this session's class
    enrolled_records = db.session.query(FaceEncoding, Student).join(Student).filter(
        Student.class_id == session.class_id,
        Student.is_active == True,
        Student.face_enrolled == True
    ).all()

    enrolled_items = []
    for enc, stu in enrolled_records:
        enrolled_items.append({
            'student_id': stu.id,
            'name': stu.name,
            'roll_no': stu.roll_no,
            'encoding': enc.encoding,
            'engine': enc.engine
        })

    # Already marked student IDs in this session
    already_marked_ids = set(
        r.student_id for r in AttendanceRecord.query.filter_by(session_id=session.id).all()
    )

    face_results = []
    newly_marked = []
    unknown_count = 0

    now = datetime.now(timezone.utc)
    started = session.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    elapsed_minutes = (now - started).total_seconds() / 60.0
    late_threshold = int(get_setting('late_threshold_minutes', '10'))
    attendance_status = 'Late' if elapsed_minutes > late_threshold else 'Present'

    for face in detected_faces:
        box = face['box']
        candidate_encoding = engine.extract_encoding(image_bgr, box=box)
        match = engine.match_candidate(candidate_encoding, enrolled_items)

        if match:
            student_id = match['student_id']
            face_results.append({
                'box': box,
                'name': match['name'],
                'roll_no': match['roll_no'],
                'confidence': match['confidence'],
                'matched': True
            })

            # Check consecutive match rule
            is_confirmed = tracker.register_match(student_id)

            if is_confirmed and student_id not in already_marked_ids:
                # Attempt concurrency-safe insert
                try:
                    record = AttendanceRecord(
                        session_id=session.id,
                        student_id=student_id,
                        status=attendance_status,
                        method='face',
                        confidence=match['confidence'],
                        note=f"Recognized via {engine.engine_name}",
                        marked_at=now
                    )
                    db.session.add(record)
                    db.session.commit()
                    already_marked_ids.add(student_id)
                    newly_marked.append({
                        'student_id': student_id,
                        'name': match['name'],
                        'roll_no': match['roll_no'],
                        'status': attendance_status,
                        'confidence': match['confidence'],
                        'time': now.strftime('%H:%M:%S')
                    })
                    log_audit('ATTENDANCE_FACE_MARK', 'AttendanceRecord', record.id, {
                        'student_id': student_id,
                        'session_id': session.id,
                        'status': attendance_status,
                        'confidence': match['confidence']
                    }, user_id=current_user_id)
                except IntegrityError:
                    db.session.rollback()
                    # Handled duplicate safely
                    already_marked_ids.add(student_id)
        else:
            unknown_count += 1
            face_results.append({
                'box': box,
                'name': 'Unknown',
                'roll_no': '',
                'confidence': 0.0,
                'matched': False
            })

    return {
        'success': True,
        'faces': face_results,
        'marked': newly_marked,
        'unknown_count': unknown_count,
        'session_status': 'active',
        'liveness': liveness_msg
    }


def mark_manual_attendance(
    session_id: int,
    student_records: List[Dict[str, Any]],
    user_id: int
) -> Tuple[bool, str, int]:
    """
    Saves manual attendance for multiple students.
    student_records: list of {'student_id': int, 'status': str, 'note': Optional[str]}
    """
    session = AttendanceSession.query.get(session_id)
    if not session:
        return False, "Session not found.", 0

    if session.status != 'active':
        return False, f"Cannot mark attendance in {session.status} session.", 0

    count = 0
    now = datetime.now(timezone.utc)

    for item in student_records:
        student_id = item.get('student_id')
        status = item.get('status', 'Present')
        note = item.get('note', 'Manual roll call')

        if not student_id or status not in ('Present', 'Absent', 'Late', 'Excused'):
            continue

        existing = AttendanceRecord.query.filter_by(session_id=session.id, student_id=student_id).first()
        if existing:
            existing.status = status
            existing.method = 'manual'
            existing.note = note
            existing.updated_at = now
        else:
            record = AttendanceRecord(
                session_id=session.id,
                student_id=student_id,
                status=status,
                method='manual',
                note=note,
                marked_at=now
            )
            db.session.add(record)
        count += 1

    try:
        db.session.commit()
        log_audit('ATTENDANCE_MANUAL_MARK', 'AttendanceSession', session.id, {
            'records_updated': count
        }, user_id=user_id)
        return True, f"Successfully recorded {count} attendance entries.", count
    except Exception as e:
        db.session.rollback()
        return False, f"Database error during manual marking: {str(e)}", 0


def override_attendance_record(
    record_id: int,
    new_status: str,
    reason: str,
    user_id: int
) -> Tuple[bool, str]:
    """
    Teacher/Admin overrides an existing attendance record status with an audit record.
    """
    if new_status not in ('Present', 'Absent', 'Late', 'Excused'):
        return False, "Invalid attendance status."

    record = AttendanceRecord.query.get(record_id)
    if not record:
        return False, "Attendance record not found."

    old_status = record.status
    if old_status == new_status:
        return False, "New status is identical to current status."

    now = datetime.now(timezone.utc)
    try:
        adjustment = AttendanceAdjustment(
            record_id=record.id,
            previous_status=old_status,
            new_status=new_status,
            reason=reason,
            adjusted_by_id=user_id,
            created_at=now
        )
        db.session.add(adjustment)

        record.status = new_status
        record.method = 'override'
        record.note = f"Overridden from {old_status}: {reason}"
        record.updated_at = now

        db.session.commit()

        log_audit('ATTENDANCE_OVERRIDE', 'AttendanceRecord', record.id, {
            'previous_status': old_status,
            'new_status': new_status,
            'reason': reason
        }, user_id=user_id)

        return True, f"Attendance status updated from {old_status} to {new_status}."
    except Exception as e:
        db.session.rollback()
        return False, f"Error saving override: {str(e)}"


def end_attendance_session(session_id: int, user_id: int, reason: str = "Completed by teacher") -> Tuple[bool, str]:
    """
    Atomically closes session, identifies unmarked students in the classroom,
    marks them as 'Absent', and marks session as ended.
    """
    session = AttendanceSession.query.get(session_id)
    if not session:
        return False, "Session not found."

    if session.status == 'ended':
        return True, "Session has already ended."

    now = datetime.now(timezone.utc)

    # Get all active students belonging to this classroom
    class_students = Student.query.filter_by(
        class_id=session.class_id,
        is_active=True
    ).all()

    existing_record_map = {
        r.student_id: r for r in AttendanceRecord.query.filter_by(session_id=session.id).all()
    }

    absent_count = 0
    for stu in class_students:
        if stu.id not in existing_record_map:
            absent_record = AttendanceRecord(
                session_id=session.id,
                student_id=stu.id,
                status='Absent',
                method='system',
                note='Unmarked at session end',
                marked_at=now
            )
            db.session.add(absent_record)
            absent_count += 1

    session.status = 'ended'
    session.ended_at = now

    try:
        db.session.commit()
        # Clean up tracker & cache
        _session_trackers.pop(session_id, None)
        _session_last_frames.pop(session_id, None)

        log_audit('SESSION_END', 'AttendanceSession', session.id, {
            'absent_marked_count': absent_count,
            'reason': reason
        }, user_id=user_id)

        return True, f"Session ended. {absent_count} unmarked students recorded as Absent."
    except Exception as e:
        db.session.rollback()
        return False, f"Error ending session: {str(e)}"
