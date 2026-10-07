from tests.conftest import login_client


def test_unauthenticated_access_redirects(client):
    res = client.get('/admin/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/login' in res.location


def test_student_cannot_access_admin_portal(client):
    login_client(client, 'student@test.edu', 'Student@123')
    res = client.get('/admin/dashboard', follow_redirects=True)
    assert res.status_code == 200
    assert b"Access denied" in res.data or b"My Attendance Overview" in res.data


def test_student_cannot_start_attendance_session(client):
    login_client(client, 'student@test.edu', 'Student@123')
    res = client.get('/attendance/start', follow_redirects=True)
    assert res.status_code == 200
    assert b"Access denied" in res.data or b"My Attendance Overview" in res.data


def test_teacher_cannot_access_admin_settings(client):
    login_client(client, 'teacher@test.edu', 'Teacher@123')
    res = client.get('/admin/settings', follow_redirects=True)
    assert res.status_code == 200
    assert b"Access denied" in res.data or b"Teacher Workspace" in res.data


def test_admin_has_full_access(client):
    login_client(client, 'admin@test.edu', 'Admin@123')
    res = client.get('/admin/settings')
    assert res.status_code == 200
    assert b"System Settings" in res.data
