from datetime import date
from tests.conftest import login_client
from app.models import AttendanceSession, AttendanceRecord, AttendanceAdjustment, Student, ClassRoom, Subject, User
from app.services.attendance_service import (
    start_attendance_session, mark_manual_attendance, override_attendance_record, end_attendance_session
)
from app.extensions import db


def test_start_session_success(client):
    login_client(client, 'teacher@test.edu', 'Teacher@123')
    cls = ClassRoom.query.first()
    sub = Subject.query.first()
    teacher = User.query.filter_by(role='teacher').first()

    success, msg, session = start_attendance_session(
        class_id=cls.id,
        subject_id=sub.id,
        teacher_id=teacher.id,
        period=1,
        session_date=date.today()
    )
    assert success is True
    assert session is not None
    assert session.status == 'active'


def test_duplicate_active_session_prevented(client):
    cls = ClassRoom.query.first()
    sub = Subject.query.first()
    teacher = User.query.filter_by(role='teacher').first()

    success1, _, s1 = start_attendance_session(cls.id, sub.id, teacher.id, 2, date.today())
    assert success1 is True

    # Attempt second session with same parameters
    success2, msg2, s2 = start_attendance_session(cls.id, sub.id, teacher.id, 2, date.today())
    assert success2 is False
    assert "already exists" in msg2


def test_manual_attendance_and_end_session(client):
    cls = ClassRoom.query.first()
    sub = Subject.query.first()
    teacher = User.query.filter_by(role='teacher').first()
    stu = Student.query.first()

    # Add a second student to verify absent marking on session end
    stu2 = Student(
        roll_no="TEST002",
        name="Second Student",
        email="second@test.edu",
        department="Computer Science",
        year=1,
        section="A",
        class_id=cls.id,
        is_active=True
    )
    db.session.add(stu2)
    db.session.commit()

    success, _, session = start_attendance_session(cls.id, sub.id, teacher.id, 3, date.today())
    assert success is True

    # Mark stu1 present manually
    success_mark, msg_mark, count = mark_manual_attendance(
        session.id,
        [{'student_id': stu.id, 'status': 'Present', 'note': 'Manual check'}],
        user_id=teacher.id
    )
    assert success_mark is True
    assert count == 1

    # End session -> stu2 should become Absent automatically
    success_end, msg_end = end_attendance_session(session.id, user_id=teacher.id)
    assert success_end is True

    db.session.refresh(session)
    assert session.status == 'ended'

    rec1 = AttendanceRecord.query.filter_by(session_id=session.id, student_id=stu.id).first()
    rec2 = AttendanceRecord.query.filter_by(session_id=session.id, student_id=stu2.id).first()

    assert rec1 is not None and rec1.status == 'Present'
    assert rec2 is not None and rec2.status == 'Absent'


def test_override_attendance_creates_audit_record(client):
    cls = ClassRoom.query.first()
    sub = Subject.query.first()
    teacher = User.query.filter_by(role='teacher').first()
    stu = Student.query.first()

    _, _, session = start_attendance_session(cls.id, sub.id, teacher.id, 4, date.today())
    mark_manual_attendance(session.id, [{'student_id': stu.id, 'status': 'Absent'}], user_id=teacher.id)

    record = AttendanceRecord.query.filter_by(session_id=session.id, student_id=stu.id).first()
    assert record.status == 'Absent'

    # Override status from Absent to Present
    success, msg = override_attendance_record(
        record_id=record.id,
        new_status='Present',
        reason='Approved bus delay excuse',
        user_id=teacher.id
    )
    assert success is True

    db.session.refresh(record)
    assert record.status == 'Present'
    assert record.method == 'override'

    adj = AttendanceAdjustment.query.filter_by(record_id=record.id).first()
    assert adj is not None
    assert adj.previous_status == 'Absent'
    assert adj.new_status == 'Present'
    assert 'Approved bus delay' in adj.reason
