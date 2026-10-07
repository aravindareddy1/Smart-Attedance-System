import calendar
from datetime import datetime, date, timedelta, timezone
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.student import bp
from app.decorators import student_required
from app.models import (
    Student, AttendanceRecord, AttendanceSession, Subject, Holiday,
    Notification, FaceEncoding
)
from app.utils import calculate_attendance_percentage, get_setting, log_audit
from app.extensions import db


def get_current_student() -> Student:
    """Helper to get student record linked to current user."""
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        # Fallback by email match
        student = Student.query.filter_by(email=current_user.email).first()
    return student


@bp.route('/dashboard')
@student_required
def dashboard():
    student = get_current_student()
    if not student:
        flash('Student record not found for your account. Please contact administrator.', 'warning')
        return render_template('student/no_profile.html')

    threshold = float(get_setting('attendance_threshold', '75.0'))

    # All sessions for student's classroom
    total_sessions = AttendanceSession.query.filter_by(
        class_id=student.class_id,
        status='ended'
    ).count()

    records = AttendanceRecord.query.join(AttendanceSession).filter(
        AttendanceRecord.student_id == student.id,
        AttendanceSession.status == 'ended'
    ).all()

    present_count = sum(1 for r in records if r.status == 'Present')
    late_count = sum(1 for r in records if r.status == 'Late')
    absent_count = sum(1 for r in records if r.status == 'Absent')
    excused_count = sum(1 for r in records if r.status == 'Excused')

    overall_pct = calculate_attendance_percentage(present_count, late_count, total_sessions)
    is_shortage = overall_pct < threshold

    # Subject-wise attendance breakdown
    subjects = Subject.query.filter_by(class_id=student.class_id, is_active=True).all()
    subject_stats = []

    for sub in subjects:
        sub_total = AttendanceSession.query.filter_by(
            class_id=student.class_id,
            subject_id=sub.id,
            status='ended'
        ).count()

        sub_records = [r for r in records if r.session.subject_id == sub.id]
        sub_present = sum(1 for r in sub_records if r.status == 'Present')
        sub_late = sum(1 for r in sub_records if r.status == 'Late')
        sub_absent = sum(1 for r in sub_records if r.status == 'Absent')
        sub_pct = calculate_attendance_percentage(sub_present, sub_late, sub_total)

        subject_stats.append({
            'code': sub.code,
            'name': sub.name,
            'teacher': sub.teacher.name if sub.teacher else 'N/A',
            'total': sub_total,
            'attended': sub_present + sub_late,
            'absent': sub_absent,
            'percentage': sub_pct,
            'is_shortage': sub_pct < threshold
        })

    # Recent attendance activity (last 10 records)
    recent_records = AttendanceRecord.query.filter_by(
        student_id=student.id
    ).join(AttendanceSession).order_by(AttendanceSession.date.desc(), AttendanceSession.period.desc()).limit(10).all()

    return render_template(
        'student/dashboard.html',
        student=student,
        overall_pct=overall_pct,
        present_count=present_count,
        late_count=late_count,
        absent_count=absent_count,
        excused_count=excused_count,
        total_sessions=total_sessions,
        threshold=threshold,
        is_shortage=is_shortage,
        subject_stats=subject_stats,
        recent_records=recent_records
    )


@bp.route('/calendar')
@student_required
def attendance_calendar():
    student = get_current_student()
    if not student:
        return redirect(url_for('student.dashboard'))

    today = date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)

    # Validate year & month
    if month < 1 or month > 12:
        month = today.month

    # Generate days matrix for calendar
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]

    # Prev and Next month navigation
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    # Query attendance records for this month
    start_date = date(year, month, 1)
    num_days = calendar.monthrange(year, month)[1]
    end_date = date(year, month, num_days)

    records = AttendanceRecord.query.join(AttendanceSession).filter(
        AttendanceRecord.student_id == student.id,
        AttendanceSession.date >= start_date,
        AttendanceSession.date <= end_date
    ).all()

    # Map by day of month: day -> list of session records
    daily_records = {}
    for r in records:
        day_num = r.session.date.day
        if day_num not in daily_records:
            daily_records[day_num] = []
        daily_records[day_num].append(r)

    # Holidays in this month
    holidays = Holiday.query.filter(
        Holiday.date >= start_date,
        Holiday.date <= end_date,
        Holiday.is_active == True
    ).all()
    holiday_map = {h.date.day: h.name for h in holidays}

    return render_template(
        'student/calendar.html',
        student=student,
        cal=cal,
        year=year,
        month=month,
        month_name=month_name,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        daily_records=daily_records,
        holiday_map=holiday_map,
        today=today
    )


@bp.route('/history')
@student_required
def history():
    student = get_current_student()
    if not student:
        return redirect(url_for('student.dashboard'))

    page = request.args.get('page', 1, type=int)
    subject_id = request.args.get('subject_id', type=int)
    status = request.args.get('status', '').strip()

    query = AttendanceRecord.query.join(AttendanceSession).filter(
        AttendanceRecord.student_id == student.id
    )

    if subject_id:
        query = query.filter(AttendanceSession.subject_id == subject_id)
    if status:
        query = query.filter(AttendanceRecord.status == status)

    pagination = query.order_by(AttendanceSession.date.desc(), AttendanceSession.period.desc()).paginate(page=page, per_page=20, error_out=False)
    subjects = Subject.query.filter_by(class_id=student.class_id, is_active=True).all()

    return render_template(
        'student/history.html',
        student=student,
        pagination=pagination,
        subjects=subjects,
        selected_subject_id=subject_id,
        selected_status=status
    )


@bp.route('/profile')
@student_required
def profile():
    student = get_current_student()
    if not student:
        return redirect(url_for('student.dashboard'))

    samples_count = FaceEncoding.query.filter_by(student_id=student.id).count()

    return render_template(
        'student/profile.html',
        student=student,
        user=current_user,
        samples_count=samples_count
    )


@bp.route('/delete-my-face', methods=['POST'])
@student_required
def delete_my_face():
    student = get_current_student()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('student.dashboard'))

    samples_count = FaceEncoding.query.filter_by(student_id=student.id).count()
    FaceEncoding.query.filter_by(student_id=student.id).delete()
    student.face_enrolled = False
    student.biometric_consent = False
    student.biometric_consent_date = None
    db.session.commit()

    log_audit('STUDENT_SELF_DELETE_FACE', 'Student', student.id, {'deleted_samples': samples_count}, user_id=current_user.id)
    flash(f"Your biometric face data ({samples_count} samples) has been permanently removed from the system.", 'info')
    return redirect(url_for('student.profile'))
