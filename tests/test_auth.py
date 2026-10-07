from tests.conftest import login_client
from app.models import User


def test_admin_login_success(client):
    res = login_client(client, 'admin@test.edu', 'Admin@123')
    assert res.status_code == 200
    assert b"Admin Control Center" in res.data or b"Dashboard" in res.data


def test_teacher_login_success(client):
    res = login_client(client, 'teacher@test.edu', 'Teacher@123')
    assert res.status_code == 200
    assert b"Teacher Workspace" in res.data or b"Today's Class Schedule" in res.data


def test_student_login_success(client):
    res = login_client(client, 'student@test.edu', 'Student@123')
    assert res.status_code == 200
    assert b"My Attendance Overview" in res.data or b"Overall Rate" in res.data


def test_login_invalid_password(client):
    res = login_client(client, 'admin@test.edu', 'WrongPassword123')
    assert res.status_code == 200
    assert b"Invalid email address or password" in res.data


def test_login_nonexistent_user(client):
    res = login_client(client, 'ghost@test.edu', 'SomePass@123')
    assert res.status_code == 200
    assert b"Invalid email address or password" in res.data


def test_login_deactivated_account(client):
    res = login_client(client, 'inactive@test.edu', 'Teacher@123')
    assert res.status_code == 200
    assert b"deactivated" in res.data


def test_logout(client):
    login_client(client, 'admin@test.edu', 'Admin@123')
    res = client.get('/logout', follow_redirects=True)
    assert res.status_code == 200
    assert b"logged out successfully" in res.data


def test_password_hashing():
    u = User(name="Hash Test", email="hash@test.edu", role="student")
    u.set_password("SecretPass@99")
    assert u.password_hash != "SecretPass@99"
    assert u.check_password("SecretPass@99") is True
    assert u.check_password("WrongPass") is False


def test_change_password_flow(client):
    login_client(client, 'admin@test.edu', 'Admin@123')
    res = client.post('/change-password', data={
        'current_password': 'Admin@123',
        'new_password': 'NewAdminPassword@456',
        'confirm_password': 'NewAdminPassword@456'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"changed successfully" in res.data
