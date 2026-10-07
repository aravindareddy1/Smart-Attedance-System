import os
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
from app import create_app, db
from app.models import User, Student, ClassRoom, Subject, Timetable, Holiday, Setting
from app.utils import set_setting


@pytest.fixture(scope='session')
def app():
    """Create testing application context."""
    test_app = create_app('testing')
    return test_app


@pytest.fixture(scope='function')
def client(app):
    """Test client per test with clean database isolation."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        # Populate base test seed
        set_setting('attendance_threshold', '75.0')
        set_setting('face_distance_threshold', '0.50')
        set_setting('late_threshold_minutes', '10')

        admin = User(name="Admin User", email="admin@test.edu", role="admin", is_active=True, is_default_password=True)
        admin.set_password("Admin@123")
        db.session.add(admin)

        teacher = User(name="Prof. Teacher", email="teacher@test.edu", role="teacher", is_active=True, is_default_password=False)
        teacher.set_password("Teacher@123")
        db.session.add(teacher)

        inactive_user = User(name="Inactive User", email="inactive@test.edu", role="teacher", is_active=False, is_default_password=False)
        inactive_user.set_password("Teacher@123")
        db.session.add(inactive_user)

        cls = ClassRoom(name="TEST-101", department="Computer Science", year=1, section="A", academic_year="2025-2026", is_active=True)
        db.session.add(cls)
        db.session.flush()

        sub = Subject(name="Intro to CS", code="CS101", class_id=cls.id, teacher_id=teacher.id, is_active=True)
        db.session.add(sub)
        db.session.flush()

        student_user = User(name="Test Student", email="student@test.edu", role="student", is_active=True, is_default_password=False)
        student_user.set_password("Student@123")
        db.session.add(student_user)
        db.session.flush()

        student = Student(
            roll_no="TEST001",
            name="Test Student",
            email="student@test.edu",
            department="Computer Science",
            year=1,
            section="A",
            class_id=cls.id,
            user_id=student_user.id,
            is_active=True,
            face_enrolled=False
        )
        db.session.add(student)
        db.session.commit()

        yield app.test_client()

        db.session.remove()
        db.drop_all()


def login_client(client, email, password):
    """Helper to authenticate a client session."""
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)
