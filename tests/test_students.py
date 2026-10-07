from tests.conftest import login_client
from app.models import Student, ClassRoom, AttendanceSession, AttendanceRecord
from app.extensions import db
from datetime import date


def test_create_student_success(client):
    login_client(client, 'admin@test.edu', 'Admin@123')
    cls = ClassRoom.query.first()
    res = client.post('/admin/students/add', data={
        'roll_no': 'CS9999',
        'name': 'New Student Alex',
        'email': 'alex.new@test.edu',
        'phone': '555-1234',
        'department': 'Computer Science',
        'year': 1,
        'section': 'A',
        'class_id': cls.id,
        'is_active': True,
        'create_login': True
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"added successfully" in res.data
    assert Student.query.filter_by(roll_no='CS9999').first() is not None


def test_duplicate_roll_number_rejected(client):
    login_client(client, 'admin@test.edu', 'Admin@123')
    cls = ClassRoom.query.first()
    res = client.post('/admin/students/add', data={
        'roll_no': 'TEST001',  # Already exists from fixture
        'name': 'Duplicate Roll',
        'email': 'dup@test.edu',
        'department': 'Computer Science',
        'year': 1,
        'section': 'A',
        'class_id': cls.id,
        'is_active': True
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"already exists" in res.data


def test_student_status_toggle(client):
    login_client(client, 'admin@test.edu', 'Admin@123')
    stu = Student.query.filter_by(roll_no='TEST001').first()
    assert stu.is_active is True

    res = client.post(f'/admin/students/{stu.id}/toggle-status', follow_redirects=True)
    assert res.status_code == 200
    assert b"deactivated" in res.data
    
    db.session.refresh(stu)
    assert stu.is_active is False


def test_student_delete_with_attendance_is_soft_deleted(client):
    login_client(client, 'admin@test.edu', 'Admin@123')
    stu = Student.query.filter_by(roll_no='TEST001').first()
    
    # Create attendance session & record
    session = AttendanceSession(
        class_id=stu.class_id,
        subject_id=stu.classroom.subjects.first().id,
        teacher_id=stu.classroom.subjects.first().teacher_id,
        date=date.today(),
        period=1,
        session_name="Test Session",
        status='ended'
    )
    db.session.add(session)
    db.session.flush()

    record = AttendanceRecord(
        session_id=session.id,
        student_id=stu.id,
        status='Present',
        method='manual'
    )
    db.session.add(record)
    db.session.commit()

    # Attempt deletion
    res = client.post(f'/admin/students/{stu.id}/delete', follow_redirects=True)
    assert res.status_code == 200
    assert b"deactivated instead of permanently deleted" in res.data
    
    db.session.refresh(stu)
    assert stu.is_active is False
    assert Student.query.get(stu.id) is not None
