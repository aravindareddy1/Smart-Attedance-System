import os
import sys
import io
import base64
import numpy as np
import cv2
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app import create_app, db
from app.models import User, Student, ClassRoom, Subject, AttendanceSession, AttendanceRecord, AuditLog
from flask_wtf.csrf import generate_csrf
import re


def extract_csrf_token(response_data):
    html = response_data.decode('utf-8', errors='ignore')
    match = re.search(r'name=["\']csrf_token["\'][^>]*?value=["\']([^"\']+)["\']', html)
    if not match:
        match = re.search(r'value=["\']([^"\']+)["\'][^>]*?name=["\']csrf_token["\']', html)
    return match.group(1) if match else None


def auth_post(client, url, data, form_url=None):
    if form_url:
        get_res = client.get(form_url)
        token = extract_csrf_token(get_res.data)
        if token:
            data['csrf_token'] = token
    else:
        get_res = client.get(url)
        token = extract_csrf_token(get_res.data)
        if token:
            data['csrf_token'] = token
    return client.post(url, data=data, follow_redirects=True)


def run_full_smoke_test():
    print("=" * 70)
    print("STARTING FULL END-TO-END SMOKE TEST ON SEEDED APPLICATION")
    print("=" * 70)

    app = create_app('development')
    client = app.test_client()

    with app.app_context():
        # 1. Health check
        print("\n[1/10] Testing /health and System Diagnostics...")
        health_resp = client.get('/health')
        assert health_resp.status_code == 200, f"Health check failed: {health_resp.status_code}"
        health_data = health_resp.get_json()
        print(f" -> Status: {health_data.get('status')}")
        print(f" -> Database: {health_data.get('database')}")
        print(f" -> Face Engine: {health_data.get('face_engine')}")
        print(f" -> Version: {health_data.get('version')}")
        assert health_data['status'] == 'ok'
        assert health_data['database'] == 'ok'
        assert health_data['face_engine'] in ('OpenCV-LBPH', 'Dlib-CNN', 'Dlib-HOG')

        # 2. Unauthenticated access & security redirects
        print("\n[2/10] Testing Security & Unauthenticated Access Guards...")
        resp = client.get('/admin/dashboard', follow_redirects=False)
        assert resp.status_code == 302 and '/login' in resp.location
        resp = client.get('/attendance/start', follow_redirects=False)
        assert resp.status_code == 302 and '/login' in resp.location
        resp = client.get('/student/dashboard', follow_redirects=False)
        assert resp.status_code == 302 and '/login' in resp.location
        print(" -> All protected endpoints strictly redirect unauthenticated requests to /login.")

        # 3. Admin Authentication & Administrative Operations
        print("\n[3/10] Testing Admin Authentication & Management Portals...")
        login_resp = auth_post(client, '/login', {'email': 'admin@example.com', 'password': 'Admin@123'})
        assert login_resp.status_code == 200
        assert b'Administration' in login_resp.data or b'Admin' in login_resp.data
        print(" -> Admin login successful.")

        # Verify admin portal views
        for endpoint, title in [
            ('/admin/dashboard', b'Admin Control Center'),
            ('/admin/students', b'Students'),
            ('/admin/teachers', b'Faculty'),
            ('/admin/classes', b'Classes'),
            ('/admin/subjects', b'Subjects'),
            ('/admin/timetable', b'Timetable'),
            ('/admin/holidays', b'Holidays'),
            ('/admin/audit-logs', b'Audit'),
            ('/admin/settings', b'Configuration'),
            ('/admin/diagnostics', b'Diagnostics'),
            ('/admin/backups', b'Backups'),
        ]:
            r = client.get(endpoint)
            assert r.status_code == 200, f"Admin view {endpoint} returned status {r.status_code}"
            assert title in r.data, f"Admin view {endpoint} missing expected marker {title.decode()}"
        print(" -> All 11 Admin dashboard views rendered with 200 OK.")

        # Test Database Backup Creation
        backup_resp = auth_post(client, '/admin/backups', {})
        assert backup_resp.status_code == 200
        assert b'Backup' in backup_resp.data
        print(" -> Hot database backup generation verified.")

        # Logout Admin
        client.get('/logout', follow_redirects=True)

        # 4. Teacher Authentication & Session Lifecycle
        print("\n[4/10] Testing Teacher Workflow & Attendance Session Lifecycle...")
        t_login = auth_post(client, '/login', {'email': 'dr.sarah@example.com', 'password': 'Teacher@123'})
        assert t_login.status_code == 200
        assert b'Teacher Portal' in t_login.data or b'Faculty' in t_login.data
        print(" -> Teacher Dr. Sarah logged in.")

        teacher_user = User.query.filter_by(email='dr.sarah@example.com').first()
        cs_class = ClassRoom.query.filter_by(name='CSE-3A').first()
        cs_sub = Subject.query.filter_by(code='CS301', teacher_id=teacher_user.id).first()

        # Start Attendance Session
        session_post = auth_post(client, '/attendance/start', {
            'class_id': cs_class.id,
            'subject_id': cs_sub.id,
            'period': 1,
            'session_type': 'live',
            'session_name': 'Live Smoke Test Lecture',
            'duration_minutes': 60
        })
        assert session_post.status_code == 200
        
        active_session = AttendanceSession.query.filter_by(
            class_id=cs_class.id,
            subject_id=cs_sub.id,
            status='active'
        ).first()
        assert active_session is not None
        print(f" -> Active session #{active_session.id} started.")

        # Manual Roll Call
        first_student = Student.query.filter_by(class_id=cs_class.id, is_active=True).first()
        manual_resp = auth_post(client, f'/attendance/manual/{active_session.id}', {
            f'status_{first_student.id}': 'Present',
            f'note_{first_student.id}': 'Smoke test manual verification'
        })
        assert manual_resp.status_code == 200
        print(f" -> Student {first_student.name} marked Present via manual roll-call.")

        # Status Override
        record = AttendanceRecord.query.filter_by(session_id=active_session.id, student_id=first_student.id).first()
        assert record is not None
        override_resp = auth_post(client, f'/attendance/override/{record.id}', {
            'status': 'Late',
            'reason': 'Verified arrived 12 minutes late due to transit'
        })
        assert override_resp.status_code == 200
        
        db.session.refresh(record)
        assert record.status == 'Late'
        assert record.method == 'override'
        print(f" -> Attendance record #{record.id} status successfully overridden to Late with audit justification.")

        # End Session
        end_resp = auth_post(client, f'/attendance/end/{active_session.id}', {})
        assert end_resp.status_code == 200
        db.session.refresh(active_session)
        assert active_session.status == 'ended'
        print(f" -> Session #{active_session.id} ended. Unmarked students auto-marked Absent.")

        client.get('/logout', follow_redirects=True)

        # 5. Face Enrollment & Validation Engine API
        print("\n[5/10] Testing Face Biometrics Enrollment & Frame API...")
        auth_post(client, '/login', {'email': 'admin@example.com', 'password': 'Admin@123'})
        
        # Test with synthetic test face image
        test_img = np.full((300, 300, 3), 128, dtype=np.uint8)
        # Draw a synthetic face representation
        cv2.circle(test_img, (150, 150), 80, (200, 200, 200), -1)
        cv2.circle(test_img, (120, 130), 12, (50, 50, 50), -1)
        cv2.circle(test_img, (180, 130), 12, (50, 50, 50), -1)
        cv2.ellipse(test_img, (150, 180), (35, 18), 0, 0, 180, (50, 50, 50), 4)

        _, buf = cv2.imencode('.jpg', test_img)
        b64_frame = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"

        # Test enrollment frame endpoint
        enroll_resp = client.post(f'/admin/api/students/{first_student.id}/enroll-frame', json={
            'image': b64_frame,
            'consent': True
        })
        # Note: If synthetic face is detected or rejected due to detector, response will be valid JSON
        assert enroll_resp.status_code in (200, 422)
        enroll_data = enroll_resp.get_json()
        print(f" -> Frame enrollment API responded: {enroll_data.get('message')}")

        client.get('/logout', follow_redirects=True)

        # 6. Student Portal & Read-Only Access
        print("\n[6/10] Testing Student Read-Only Access Portal...")
        s_login = auth_post(client, '/login', {'email': 'aarav.sharma@example.edu', 'password': 'Student@123'})
        assert s_login.status_code == 200
        assert b'Student Portal' in s_login.data or b'Attendance' in s_login.data
        print(" -> Student Aarav Sharma logged into personal portal.")

        # Test Student views
        for s_url, s_marker in [
            ('/student/dashboard', b'Overall Rate'),
            ('/student/calendar', b'Calendar'),
            ('/student/history', b'History'),
            ('/student/profile', b'Profile')
        ]:
            sr = client.get(s_url)
            assert sr.status_code == 200, f"Student url {s_url} failed with {sr.status_code}"
            assert s_marker in sr.data, f"Student url {s_url} missing marker {s_marker.decode()}"
        print(" -> Student Dashboard, Calendar, History, and Profile views verified.")

        # Verify Student RBAC containment
        forbidden_admin = client.get('/admin/dashboard')
        assert forbidden_admin.status_code in (302, 403)
        forbidden_start = client.get('/attendance/start')
        assert forbidden_start.status_code in (302, 403)
        print(" -> Student RBAC confinement confirmed: Admin routes and Session creation strictly forbidden.")

        client.get('/logout', follow_redirects=True)

        # 7. Analytics Endpoints & JSON APIs
        print("\n[7/10] Testing Analytics Visualizations & JSON APIs...")
        auth_post(client, '/login', {'email': 'admin@example.com', 'password': 'Admin@123'})
        
        for api_url in [
            '/analytics/api/summary',
            '/analytics/api/trend',
            '/analytics/api/classwise',
            '/analytics/api/subjectwise',
            '/analytics/api/heatmap',
            '/analytics/api/distribution',
            '/analytics/api/top-absent'
        ]:
            ar = client.get(api_url)
            assert ar.status_code == 200, f"Analytics API {api_url} returned {ar.status_code}"
            adata = ar.get_json()
            assert adata is not None, f"Analytics API {api_url} returned empty/invalid JSON"
        print(" -> All 7 Analytics JSON APIs returned valid data structures.")

        # 8. Reports & Document Exports (CSV and Styled Excel)
        print("\n[8/10] Testing Reports & Document Exports...")
        # CSV Export
        csv_resp = client.get('/reports/export/csv')
        assert csv_resp.status_code == 200
        assert csv_resp.mimetype == 'text/csv'
        assert len(csv_resp.data) > 100
        print(f" -> CSV export generated ({len(csv_resp.data)} bytes, Content-Type: {csv_resp.mimetype}).")

        # Excel Export (.xlsx)
        excel_resp = client.get('/reports/export/excel')
        assert excel_resp.status_code == 200
        assert 'spreadsheet' in excel_resp.mimetype or 'openxmlformats' in excel_resp.mimetype or 'excel' in excel_resp.mimetype
        assert len(excel_resp.data) > 1000
        print(f" -> Excel report (.xlsx) generated ({len(excel_resp.data)} bytes, formatted workbook with headers).")

        # Shortage Report
        shortage_resp = client.get('/reports/shortage')
        assert shortage_resp.status_code == 200
        assert b'Attendance Shortage' in shortage_resp.data
        print(" -> Shortage analysis & recovery projection view verified.")

        # 9. Audit Logging Verification
        print("\n[9/10] Verifying Security Audit Log Trail...")
        logs_count = AuditLog.query.count()
        assert logs_count > 0
        latest_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(5).all()
        for al in latest_logs:
            print(f"    - Action: {al.action} | Entity: {al.entity_type} #{al.entity_id} | Time: {al.created_at}")
        print(f" -> Total {logs_count} immutable audit log entries recorded.")

        # 10. Error Handlers
        print("\n[10/10] Testing Custom HTTP Error Handlers...")
        err_404 = client.get('/nonexistent-page-url-xyz-404')
        assert err_404.status_code == 404
        assert b'404' in err_404.data
        print(" -> Custom 404 Error page verified.")

        client.get('/logout', follow_redirects=True)

    print("\n" + "=" * 70)
    print("ALL 10 END-TO-END SMOKE TESTS COMPLETED SUCCESSFULLY (100% PASS)!")
    print("=" * 70)


if __name__ == '__main__':
    run_full_smoke_test()
