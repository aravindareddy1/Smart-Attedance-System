from datetime import datetime, date, timezone
from flask import render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app.attendance import bp
from app.extensions import db
from app.decorators import teacher_required
from app.models import (
    AttendanceSession, AttendanceRecord, AttendanceAdjustment,
    ClassRoom, Subject, Student, Timetable, User
)
from app.forms import AttendanceOverrideForm
from app.services.attendance_service import (
    start_attendance_session, process_live_frame,
    mark_manual_attendance, override_attendance_record, end_attendance_session
)
from app.services.report_service import get_filtered_attendance_query, get_shortage_report
from app.services.face_service import get_face_engine
from app.utils import log_audit, get_setting


@bp.route('/dashboard')
@teacher_required
def teacher_dashboard():
    # If admin, show all assigned or general view; if teacher, filter to their classes
    teacher_id = current_user.id
    
    # Timetable for today (0=Monday ... 6=Sunday)
    today_weekday = date.today().weekday()
    
    if current_user.is_admin:
        assigned_subjects = Subject.query.filter_by(is_active=True).all()
        today_schedules = Timetable.query.filter_by(weekday=today_weekday, is_active=True).order_by(Timetable.period.asc()).all()
        recent_sessions = AttendanceSession.query.order_by(AttendanceSession.started_at.desc()).limit(10).all()
    else:
        assigned_subjects = Subject.query.filter_by(teacher_id=teacher_id, is_active=True).all()
        today_schedules = Timetable.query.filter_by(teacher_id=teacher_id, weekday=today_weekday, is_active=True).order_by(Timetable.period.asc()).all()
        recent_sessions = AttendanceSession.query.filter_by(teacher_id=teacher_id).order_by(AttendanceSession.started_at.desc()).limit(10).all()

    # Active session if any
    active_session = AttendanceSession.query.filter_by(
        teacher_id=teacher_id,
        status='active'
    ).first()

    shortages = get_shortage_report(threshold=float(get_setting('attendance_threshold', '75.0')))
    
    return render_template(
        'attendance/teacher_dashboard.html',
        assigned_subjects=assigned_subjects,
        today_schedules=today_schedules,
        recent_sessions=recent_sessions,
        active_session=active_session,
        shortages=shortages[:5]
    )


@bp.route('/start', methods=['GET', 'POST'])
@teacher_required
def start_session():
    # Pre-populate from query parameters if launched from Timetable
    initial_class_id = request.args.get('class_id', type=int)
    initial_subject_id = request.args.get('subject_id', type=int)
    initial_period = request.args.get('period', default=1, type=int)

    if request.method == 'POST':
        class_id = request.form.get('class_id', type=int)
        subject_id = request.form.get('subject_id', type=int)
        period = request.form.get('period', type=int)
        date_str = request.form.get('date')
        session_type = request.form.get('session_type', 'live')  # 'live' or 'manual'

        session_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()

        success, msg, session = start_attendance_session(
            class_id=class_id,
            subject_id=subject_id,
            teacher_id=current_user.id,
            period=period,
            session_date=session_date
        )

        if not success:
            flash(msg, 'danger')
            return redirect(url_for('attendance.start_session', class_id=class_id, subject_id=subject_id, period=period))

        flash(msg, 'success')
        if session_type == 'manual':
            return redirect(url_for('attendance.manual_attendance', session_id=session.id))
        return redirect(url_for('attendance.live_attendance', session_id=session.id))

    # GET: Prepare classes and subjects permitted for this user
    if current_user.is_admin:
        classes = ClassRoom.query.filter_by(is_active=True).all()
        subjects = Subject.query.filter_by(is_active=True).all()
    else:
        subjects = Subject.query.filter_by(teacher_id=current_user.id, is_active=True).all()
        class_ids = set(s.class_id for s in subjects)
        classes = ClassRoom.query.filter(ClassRoom.id.in_(class_ids), ClassRoom.is_active==True).all() if class_ids else []

    # Selected class student inspection for confirmation
    selected_class = ClassRoom.query.get(initial_class_id) if initial_class_id else (classes[0] if classes else None)
    total_students = 0
    enrolled_students = 0
    if selected_class:
        students = selected_class.students.filter_by(is_active=True).all()
        total_students = len(students)
        enrolled_students = sum(1 for s in students if s.face_enrolled)

    return render_template(
        'attendance/start_session.html',
        classes=classes,
        subjects=subjects,
        initial_class_id=initial_class_id,
        initial_subject_id=initial_subject_id,
        initial_period=initial_period,
        today_date=date.today().strftime('%Y-%m-%d'),
        selected_class=selected_class,
        total_students=total_students,
        enrolled_students=enrolled_students
    )


@bp.route('/live/<int:session_id>')
@teacher_required
def live_attendance(session_id):
    session = AttendanceSession.query.get_or_404(session_id)
    if not current_user.is_admin and session.teacher_id != current_user.id:
        flash('Unauthorized to access this session.', 'danger')
        return redirect(url_for('attendance.teacher_dashboard'))

    if session.status != 'active':
        flash(f"Session is already {session.status}.", 'warning')
        return redirect(url_for('attendance.session_summary', session_id=session.id))

    class_students = Student.query.filter_by(class_id=session.class_id, is_active=True).order_by(Student.roll_no.asc()).all()
    records = AttendanceRecord.query.filter_by(session_id=session.id).all()
    marked_map = {r.student_id: r for r in records}

    engine = get_face_engine()

    return render_template(
        'attendance/live_session.html',
        session=session,
        students=class_students,
        marked_map=marked_map,
        engine_name=engine.engine_name
    )


@bp.route('/api/frame/<int:session_id>', methods=['POST'])
@login_required
def api_process_frame(session_id):
    data = request.get_json() or {}
    frame_data = data.get('frame')
    if not frame_data:
        return jsonify({'success': False, 'message': 'No frame data provided.'}), 400

    result = process_live_frame(session_id, frame_data, current_user.id)
    return jsonify(result)


@bp.route('/manual/<int:session_id>', methods=['GET', 'POST'])
@teacher_required
def manual_attendance(session_id):
    session = AttendanceSession.query.get_or_404(session_id)
    if not current_user.is_admin and session.teacher_id != current_user.id:
        flash('Unauthorized to manage this session.', 'danger')
        return redirect(url_for('attendance.teacher_dashboard'))

    students = Student.query.filter_by(class_id=session.class_id, is_active=True).order_by(Student.roll_no.asc()).all()

    if request.method == 'POST':
        student_records = []
        for s in students:
            status = request.form.get(f"status_{s.id}", 'Present')
            note = request.form.get(f"note_{s.id}", '')
            student_records.append({
                'student_id': s.id,
                'status': status,
                'note': note or 'Manual attendance'
            })

        success, msg, count = mark_manual_attendance(session_id, student_records, current_user.id)
        if success:
            flash(msg, 'success')
            if request.form.get('action') == 'save_and_end':
                end_attendance_session(session_id, current_user.id, reason="Manual attendance submitted and closed")
                return redirect(url_for('attendance.session_summary', session_id=session.id))
        else:
            flash(msg, 'danger')

    records = AttendanceRecord.query.filter_by(session_id=session.id).all()
    marked_map = {r.student_id: r for r in records}

    return render_template(
        'attendance/manual_attendance.html',
        session=session,
        students=students,
        marked_map=marked_map
    )


@bp.route('/override/<int:record_id>', methods=['GET', 'POST'])
@teacher_required
def override_record(record_id):
    record = AttendanceRecord.query.get_or_404(record_id)
    form = AttendanceOverrideForm(obj=record)

    if form.validate_on_submit():
        new_status = form.status.data
        reason = form.reason.data.strip()
        success, msg = override_attendance_record(record_id, new_status, reason, current_user.id)
        if success:
            flash(msg, 'success')
            return redirect(request.referrer or url_for('attendance.records'))
        else:
            flash(msg, 'danger')

    return render_template('attendance/override_modal.html', form=form, record=record)


@bp.route('/end/<int:session_id>', methods=['POST'])
@teacher_required
def end_session(session_id):
    session = AttendanceSession.query.get_or_404(session_id)
    if not current_user.is_admin and session.teacher_id != current_user.id:
        flash('Unauthorized to end this session.', 'danger')
        return redirect(url_for('attendance.teacher_dashboard'))

    success, msg = end_attendance_session(session_id, current_user.id)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    return redirect(url_for('attendance.session_summary', session_id=session.id))


@bp.route('/session/<int:session_id>/summary')
@teacher_required
def session_summary(session_id):
    session = AttendanceSession.query.get_or_404(session_id)
    records = AttendanceRecord.query.filter_by(session_id=session.id).join(Student).order_by(Student.roll_no.asc()).all()

    stats = {
        'total': len(records),
        'present': sum(1 for r in records if r.status == 'Present'),
        'late': sum(1 for r in records if r.status == 'Late'),
        'absent': sum(1 for r in records if r.status == 'Absent'),
        'excused': sum(1 for r in records if r.status == 'Excused')
    }

    return render_template(
        'attendance/session_summary.html',
        session=session,
        records=records,
        stats=stats
    )


@bp.route('/records')
@teacher_required
def records():
    page = request.args.get('page', 1, type=int)
    date_from_str = request.args.get('date_from', '').strip()
    date_to_str = request.args.get('date_to', '').strip()
    class_id = request.args.get('class_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    student_roll = request.args.get('roll_no', '').strip()
    status = request.args.get('status', '').strip()
    method = request.args.get('method', '').strip()

    date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else None
    date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else None

    # Teacher data scoping
    teacher_id = None if current_user.is_admin else current_user.id

    query = get_filtered_attendance_query(
        date_from=date_from,
        date_to=date_to,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=teacher_id,
        roll_no=student_roll,
        status=status,
        method=method
    )

    pagination = query.paginate(page=page, per_page=25, error_out=False)

    # Filter dropdown choices
    if current_user.is_admin:
        classes = ClassRoom.query.filter_by(is_active=True).all()
        subjects = Subject.query.filter_by(is_active=True).all()
    else:
        subjects = Subject.query.filter_by(teacher_id=current_user.id, is_active=True).all()
        c_ids = set(s.class_id for s in subjects)
        classes = ClassRoom.query.filter(ClassRoom.id.in_(c_ids)).all() if c_ids else []

    return render_template(
        'attendance/records.html',
        pagination=pagination,
        classes=classes,
        subjects=subjects,
        selected_class_id=class_id,
        selected_subject_id=subject_id,
        date_from=date_from_str,
        date_to=date_to_str,
        roll_no=student_roll,
        selected_status=status,
        selected_method=method
    )

import base64
import cv2
