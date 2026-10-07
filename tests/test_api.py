import pytest
from app.models import User, Student, ClassRoom, Subject


def test_api_login_success(client, app):
    response = client.post('/api/auth/login', json={
        'email': 'admin@test.edu',
        'password': 'Admin@123'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'token' in data
    assert data['user']['role'] == 'admin'


def test_api_login_invalid(client, app):
    response = client.post('/api/auth/login', json={
        'email': 'admin@test.edu',
        'password': 'WrongPassword'
    })
    assert response.status_code == 401
    data = response.get_json()
    assert data['success'] is False


def test_api_dashboard_stats(client, app):
    response = client.get('/api/dashboard/stats')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'stats' in data
    assert 'total_students' in data['stats']


def test_api_students_crud(client, app):
    # List students
    res = client.get('/api/students')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    initial_count = data['count']

    # Create new student
    res = client.post('/api/students', json={
        'roll_no': 'TEST-API-001',
        'name': 'API Test Student',
        'email': 'api_student@example.com',
        'department': 'Computer Science',
        'year': 2,
        'section': 'A'
    })
    assert res.status_code == 201
    stu_id = res.get_json()['id']

    # Update student
    res = client.put(f'/api/students/{stu_id}', json={
        'name': 'API Test Student Updated'
    })
    assert res.status_code == 200
    assert res.get_json()['success'] is True

    # Toggle status
    res = client.post(f'/api/students/{stu_id}/toggle-status')
    assert res.status_code == 200
    assert res.get_json()['is_active'] is False

    # Delete student
    res = client.delete(f'/api/students/{stu_id}')
    assert res.status_code == 200


def test_api_teachers_list(client, app):
    res = client.get('/api/teachers')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert isinstance(data['teachers'], list)


def test_api_classes_and_subjects(client, app):
    # Classes
    res = client.get('/api/classes')
    assert res.status_code == 200
    assert res.get_json()['success'] is True

    # Subjects
    res = client.get('/api/subjects')
    assert res.status_code == 200
    assert res.get_json()['success'] is True


def test_api_timetable(client, app):
    res = client.get('/api/timetable')
    assert res.status_code == 200
    assert res.get_json()['success'] is True


def test_api_shortage_report(client, app):
    res = client.get('/api/reports/shortage?threshold=75.0')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'shortages' in data


def test_api_diagnostics_and_audit(client, app):
    # Diagnostics
    res = client.get('/api/diagnostics')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'face_engine' in data
    assert 'opencv_version' in data

    # Audit Logs
    res = client.get('/api/audit-logs')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'logs' in data


def test_api_holidays_settings_backups_profile(client, app):
    # Profile
    res = client.get('/api/user/profile')
    assert res.status_code == 200
    assert 'user' in res.get_json()

    # Settings
    res = client.get('/api/settings')
    assert res.status_code == 200
    assert res.get_json()['success'] is True

    # Save Settings
    res = client.post('/api/settings', json={'attendance_threshold': '80.0'})
    assert res.status_code == 200

    # Holidays
    res = client.get('/api/holidays')
    assert res.status_code == 200

    res = client.post('/api/holidays', json={'name': 'Founder Day', 'date': '2026-11-15', 'description': 'Holiday'})
    assert res.status_code == 201

    # Backups
    res = client.get('/api/backups')
    assert res.status_code == 200
    assert res.get_json()['success'] is True

    res = client.post('/api/backups')
    assert res.status_code == 200

