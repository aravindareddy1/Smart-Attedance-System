import pytest
from app import db
from app.models import ClassRoom, Subject, Timetable, User
from tests.conftest import login_client


def test_create_and_manage_class(client):
    """Test admin creating and listing classrooms."""
    login_client(client, "admin@test.edu", "Admin@123")
    
    # Create new class
    resp = client.post('/admin/classes', data={
        'name': 'CS-2026-B',
        'department': 'Computer Science',
        'year': 2,
        'section': 'B',
        'academic_year': '2025-2026',
        'is_active': 'y'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'CS-2026-B' in resp.data

    with client.application.app_context():
        cls = ClassRoom.query.filter_by(name='CS-2026-B').first()
        assert cls is not None
        assert cls.section == 'B'
        assert cls.is_active is True

    # Edit class
    resp = client.post(f'/admin/classes/{cls.id}/edit', data={
        'name': 'CS-2026-B-Updated',
        'department': 'Computer Science',
        'year': 2,
        'section': 'B',
        'academic_year': '2025-2026',
        'is_active': 'y'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'CS-2026-B-Updated' in resp.data

    # Toggle status
    resp = client.post(f'/admin/classes/{cls.id}/toggle-status', follow_redirects=True)
    assert resp.status_code == 200
    with client.application.app_context():
        cls = db.session.get(ClassRoom, cls.id)
        assert cls.is_active is False


def test_create_and_manage_subject(client):
    """Test admin creating, assigning, and toggling subject status."""
    login_client(client, "admin@test.edu", "Admin@123")

    with client.application.app_context():
        cls = ClassRoom.query.filter_by(name="TEST-101").first()
        teacher = User.query.filter_by(email="teacher@test.edu").first()
        cls_id = cls.id
        teacher_id = teacher.id

    resp = client.post('/admin/subjects', data={
        'name': 'Data Structures',
        'code': 'CS201',
        'class_id': cls_id,
        'teacher_id': teacher_id,
        'is_active': 'y'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Data Structures' in resp.data

    with client.application.app_context():
        sub = Subject.query.filter_by(code='CS201').first()
        assert sub is not None
        assert sub.teacher_id == teacher_id

    # Toggle subject
    resp = client.post(f'/admin/subjects/{sub.id}/toggle-status', follow_redirects=True)
    assert resp.status_code == 200
    with client.application.app_context():
        sub = db.session.get(Subject, sub.id)
        assert sub.is_active is False


def test_timetable_creation(client):
    """Test timetable slot creation and retrieval."""
    login_client(client, "admin@test.edu", "Admin@123")

    with client.application.app_context():
        cls = ClassRoom.query.filter_by(name="TEST-101").first()
        sub = Subject.query.filter_by(code="CS101").first()
        teacher = User.query.filter_by(email="teacher@test.edu").first()
        cls_id = cls.id
        sub_id = sub.id
        teacher_id = teacher.id

    resp = client.post('/admin/timetable', data={
        'class_id': cls_id,
        'subject_id': sub_id,
        'teacher_id': teacher_id,
        'weekday': 0,
        'period': 1,
        'start_time': '09:00',
        'end_time': '10:00',
        'room': 'Lab 1',
        'is_active': 'y'
    }, follow_redirects=True)
    assert resp.status_code == 200

    with client.application.app_context():
        tt = Timetable.query.filter_by(class_id=cls_id, period=1, weekday=0).first()
        assert tt is not None
        assert tt.room == 'Lab 1'
