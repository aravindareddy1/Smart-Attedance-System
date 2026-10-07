import os
import sys
import platform
import cv2
from datetime import datetime, timezone, date
from pathlib import Path
from flask import render_template, redirect, url_for, flash, request, jsonify, send_file, Response, current_app
from flask_login import login_required, current_user
from app.admin import bp
from app.extensions import db, csrf
from app.decorators import admin_required
from app.models import (
    User, Student, ClassRoom, Subject, Timetable, Holiday,
    AttendanceSession, AttendanceRecord, FaceEncoding, AuditLog, Setting
)
from app.forms import (
    TeacherForm, StudentForm, ClassRoomForm, SubjectForm,
    TimetableForm, HolidayForm, CSVImportForm, SettingsForm, FaceEnrollmentForm
)
from app.services.face_service import get_face_engine, decode_base64_image
from app.services.import_service import process_student_csv_import, generate_import_template_csv
from app.services.backup_service import create_database_backup, list_backups
from app.services.analytics_service import get_analytics_summary
from app.utils import log_audit, get_setting, set_setting


@bp.route('/dashboard')
@admin_required
def dashboard():
    summary = get_analytics_summary()
    recent_sessions = AttendanceSession.query.order_by(AttendanceSession.started_at.desc()).limit(5).all()
    recent_audits = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all()
    
    return render_template(
        'admin/dashboard.html',
        summary=summary,
        recent_sessions=recent_sessions,
        recent_audits=recent_audits
    )


# ==========================================
# TEACHER MANAGEMENT
# ==========================================

@bp.route('/teachers')
@admin_required
def teachers():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    query = User.query.filter_by(role='teacher')
    
    if search:
        query = query.filter((User.name.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%")))
        
    pagination = query.order_by(User.name.asc()).paginate(page=page, per_page=15, error_out=False)
    return render_template('admin/teachers.html', pagination=pagination, search=search)


@bp.route('/teachers/add', methods=['GET', 'POST'])
@admin_required
def add_teacher():
    form = TeacherForm()
    if form.validate_on_submit():
        teacher = User(
            name=form.name.data.strip(),
            email=form.email.data.strip().lower(),
            role='teacher',
            is_active=form.is_active.data,
            is_default_password=True
        )
        pwd = form.password.data if form.password.data else 'Teacher@123'
        teacher.set_password(pwd)
        db.session.add(teacher)
        db.session.commit()

        log_audit('TEACHER_CREATE', 'User', teacher.id, {'name': teacher.name, 'email': teacher.email})
        flash(f"Teacher '{teacher.name}' added successfully.", 'success')
        return redirect(url_for('admin.teachers'))

    return render_template('admin/teacher_form.html', form=form, title='Add New Teacher')


@bp.route('/teachers/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_teacher(id):
    teacher = User.query.get_or_404(id)
    form = TeacherForm(original_email=teacher.email, obj=teacher)
    if form.validate_on_submit():
        teacher.name = form.name.data.strip()
        teacher.email = form.email.data.strip().lower()
        teacher.is_active = form.is_active.data
        if form.password.data:
            teacher.set_password(form.password.data)
            teacher.is_default_password = False
        db.session.commit()

        log_audit('TEACHER_UPDATE', 'User', teacher.id, {'name': teacher.name, 'email': teacher.email})
        flash(f"Teacher '{teacher.name}' updated successfully.", 'success')
        return redirect(url_for('admin.teachers'))

    return render_template('admin/teacher_form.html', form=form, title=f"Edit Teacher: {teacher.name}")


@bp.route('/teachers/<int:id>/toggle-status', methods=['POST'])
@admin_required
def toggle_teacher_status(id):
    teacher = User.query.get_or_404(id)
    teacher.is_active = not teacher.is_active
    db.session.commit()
    status_str = "activated" if teacher.is_active else "deactivated"
    log_audit('TEACHER_STATUS_TOGGLE', 'User', teacher.id, {'is_active': teacher.is_active})
    flash(f"Teacher '{teacher.name}' has been {status_str}.", 'info')
    return redirect(url_for('admin.teachers'))


# ==========================================
# STUDENT MANAGEMENT
# ==========================================

@bp.route('/students')
@admin_required
def students():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    class_id = request.args.get('class_id', type=int)
    enrolled_filter = request.args.get('enrolled', '').strip()

    query = Student.query
    if search:
        query = query.filter((Student.name.ilike(f"%{search}%")) | (Student.roll_no.ilike(f"%{search}%")) | (Student.email.ilike(f"%{search}%")))
    if class_id:
        query = query.filter_by(class_id=class_id)
    if enrolled_filter == 'yes':
        query = query.filter_by(face_enrolled=True)
    elif enrolled_filter == 'no':
        query = query.filter_by(face_enrolled=False)

    pagination = query.order_by(Student.roll_no.asc()).paginate(page=page, per_page=20, error_out=False)
    classes = ClassRoom.query.filter_by(is_active=True).all()

    return render_template(
        'admin/students.html',
        pagination=pagination,
        classes=classes,
        search=search,
        selected_class_id=class_id,
        enrolled_filter=enrolled_filter
    )


@bp.route('/students/add', methods=['GET', 'POST'])
@admin_required
def add_student():
    form = StudentForm()
    if form.validate_on_submit():
        user_account = None
        if form.create_login.data:
            existing_user = User.query.filter_by(email=form.email.data.strip().lower()).first()
            if not existing_user:
                user_account = User(
                    name=form.name.data.strip(),
                    email=form.email.data.strip().lower(),
                    role='student',
                    is_active=form.is_active.data,
                    is_default_password=True
                )
                user_account.set_password('Student@123')
                db.session.add(user_account)
                db.session.flush()

        student = Student(
            roll_no=form.roll_no.data.strip().upper(),
            name=form.name.data.strip(),
            email=form.email.data.strip(),
            phone=form.phone.data.strip() if form.phone.data else None,
            department=form.department.data.strip(),
            year=form.year.data,
            section=form.section.data.strip().upper(),
            class_id=form.class_id.data,
            user_id=user_account.id if user_account else None,
            is_active=form.is_active.data,
            face_enrolled=False
        )
        db.session.add(student)
        db.session.commit()

        log_audit('STUDENT_CREATE', 'Student', student.id, {'roll_no': student.roll_no, 'name': student.name})
        flash(f"Student '{student.name}' ({student.roll_no}) added successfully.", 'success')
        return redirect(url_for('admin.students'))

    return render_template('admin/student_form.html', form=form, title='Add New Student')


@bp.route('/students/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_student(id):
    student = Student.query.get_or_404(id)
    form = StudentForm(original_roll_no=student.roll_no, obj=student)
    if form.validate_on_submit():
        student.roll_no = form.roll_no.data.strip().upper()
        student.name = form.name.data.strip()
        student.email = form.email.data.strip()
        student.phone = form.phone.data.strip() if form.phone.data else None
        student.department = form.department.data.strip()
        student.year = form.year.data
        student.section = form.section.data.strip().upper()
        student.class_id = form.class_id.data
        student.is_active = form.is_active.data
        db.session.commit()

        log_audit('STUDENT_UPDATE', 'Student', student.id, {'roll_no': student.roll_no, 'name': student.name})
        flash(f"Student '{student.name}' updated successfully.", 'success')
        return redirect(url_for('admin.students'))

    return render_template('admin/student_form.html', form=form, title=f"Edit Student: {student.name}")


@bp.route('/students/<int:id>/toggle-status', methods=['POST'])
@admin_required
def toggle_student_status(id):
    student = Student.query.get_or_404(id)
    student.is_active = not student.is_active
    db.session.commit()
    status_str = "activated" if student.is_active else "deactivated"
    log_audit('STUDENT_STATUS_TOGGLE', 'Student', student.id, {'is_active': student.is_active})
    flash(f"Student '{student.name}' ({student.roll_no}) has been {status_str}.", 'info')
    return redirect(url_for('admin.students'))


@bp.route('/students/<int:id>/delete', methods=['POST'])
@admin_required
def delete_student(id):
    student = Student.query.get_or_404(id)
    # Check if student has attendance records
    record_count = student.attendance_records.count()
    if record_count > 0:
        student.is_active = False
        db.session.commit()
        log_audit('STUDENT_SOFT_DELETE', 'Student', student.id, {'reason': 'Deactivated due to existing attendance history'})
        flash(f"Student '{student.name}' has historical attendance records and was deactivated instead of permanently deleted.", 'warning')
    else:
        # Safe to delete face encodings and student
        name = student.name
        roll_no = student.roll_no
        db.session.delete(student)
        db.session.commit()
        log_audit('STUDENT_DELETE', 'Student', id, {'roll_no': roll_no, 'name': name})
        flash(f"Student '{name}' ({roll_no}) deleted successfully.", 'success')

    return redirect(url_for('admin.students'))


# ==========================================
# FACE ENROLLMENT & BIOMETRIC PRIVACY
# ==========================================

@bp.route('/students/<int:id>/enroll-face', methods=['GET', 'POST'])
@login_required
def enroll_student_face(id):
    # Only Admin or Teacher can enroll student faces
    if not (current_user.is_admin or current_user.is_teacher):
        flash('Unauthorized to manage face biometrics.', 'danger')
        return redirect(url_for('auth.dashboard'))

    student = Student.query.get_or_404(id)
    form = FaceEnrollmentForm()
    encodings = FaceEncoding.query.filter_by(student_id=student.id).all()

    return render_template(
        'admin/face_enrollment.html',
        student=student,
        form=form,
        encodings=encodings,
        samples_count=len(encodings)
    )


@bp.route('/api/students/<int:id>/enroll-frame', methods=['POST'])
@login_required
@csrf.exempt
def api_enroll_student_frame(id):
    if not (current_user.is_admin or current_user.is_teacher):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    student = Student.query.get_or_404(id)
    data = request.get_json() or {}
    frame_base64 = data.get('image')
    has_consent = data.get('consent', False)

    if not frame_base64:
        return jsonify({'success': False, 'message': 'No image data provided.'}), 400

    try:
        image_bgr = decode_base64_image(frame_base64)
    except Exception as e:
        return jsonify({'success': False, 'message': f'Image decoding failed: {str(e)}'}), 400

    engine = get_face_engine()
    is_valid, error_msg, metadata = engine.validate_face_image(image_bgr)

    if not is_valid:
        return jsonify({'success': False, 'message': error_msg}), 422

    # Extract encoding
    box = metadata.get('box') if metadata else None
    encoding_data = engine.extract_encoding(image_bgr, box=box)
    if not encoding_data:
        return jsonify({'success': False, 'message': 'Failed to extract face features from the image.'}), 422

    # Save encoding record
    now = datetime.now(timezone.utc)
    encoding_record = FaceEncoding(
        student_id=student.id,
        encoding=encoding_data,
        quality_score=metadata.get('quality_score', 1.0) if metadata else 1.0,
        engine=engine.engine_name,
        created_at=now
    )
    db.session.add(encoding_record)

    student.face_enrolled = True
    student.biometric_consent = bool(has_consent or student.biometric_consent)
    if student.biometric_consent and not student.biometric_consent_date:
        student.biometric_consent_date = now

    db.session.commit()

    total_samples = FaceEncoding.query.filter_by(student_id=student.id).count()
    log_audit('FACE_SAMPLE_ENROLLED', 'Student', student.id, {
        'total_samples': total_samples,
        'engine': engine.engine_name
    }, user_id=current_user.id)

    return jsonify({
        'success': True,
        'message': f'Face sample #{total_samples} captured and validated successfully!',
        'total_samples': total_samples,
        'quality_score': metadata.get('quality_score', 1.0) if metadata else 1.0
    })


@bp.route('/students/<int:id>/delete-face', methods=['POST'])
@login_required
def delete_student_face(id):
    student = Student.query.get_or_404(id)
    # Check authorization: Admin, Teacher, or the Student themselves
    is_owner_student = current_user.is_student and student.user_id == current_user.id
    if not (current_user.is_admin or current_user.is_teacher or is_owner_student):
        flash('Unauthorized to delete face biometrics.', 'danger')
        return redirect(url_for('auth.dashboard'))

    # Delete all face encodings
    sample_count = FaceEncoding.query.filter_by(student_id=student.id).count()
    FaceEncoding.query.filter_by(student_id=student.id).delete()
    student.face_enrolled = False
    student.biometric_consent = False
    student.biometric_consent_date = None
    db.session.commit()

    log_audit('FACE_DATA_DELETED', 'Student', student.id, {'deleted_samples': sample_count}, user_id=current_user.id)
    flash(f"Biometric face data ({sample_count} samples) permanently deleted for student '{student.name}'.", 'info')

    if is_owner_student:
        return redirect(url_for('student.dashboard'))
    return redirect(url_for('admin.enroll_student_face', id=student.id))


# ==========================================
# BULK CSV IMPORT
# ==========================================

@bp.route('/students/import', methods=['GET', 'POST'])
@admin_required
def import_students():
    form = CSVImportForm()
    import_result = None

    if form.validate_on_submit():
        file = form.file.data
        default_class = form.default_class_id.data if form.default_class_id.data != 0 else None
        import_result = process_student_csv_import(file.stream, default_class_id=default_class, user_id=current_user.id)
        if import_result['success']:
            flash(import_result['message'], 'success')
        else:
            flash(import_result['message'], 'danger')

    return render_template('admin/import_students.html', form=form, result=import_result)


@bp.route('/students/import/template')
@admin_required
def download_import_template():
    csv_data = generate_import_template_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=student_import_template.csv"}
    )


# ==========================================
# CLASSES & SUBJECTS MANAGEMENT
# ==========================================

@bp.route('/classes', methods=['GET', 'POST'])
@admin_required
def classes():
    form = ClassRoomForm()
    if form.validate_on_submit():
        cls = ClassRoom(
            name=form.name.data.strip(),
            department=form.department.data.strip(),
            year=form.year.data,
            section=form.section.data.strip().upper(),
            academic_year=form.academic_year.data.strip(),
            is_active=form.is_active.data
        )
        db.session.add(cls)
        db.session.commit()
        log_audit('CLASS_CREATE', 'ClassRoom', cls.id, {'name': cls.name})
        flash(f"Class '{cls.name}' created successfully.", 'success')
        return redirect(url_for('admin.classes'))

    all_classes = ClassRoom.query.order_by(ClassRoom.name.asc()).all()
    return render_template('admin/classes.html', form=form, classes=all_classes)


@bp.route('/classes/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_class(id):
    cls = ClassRoom.query.get_or_404(id)
    form = ClassRoomForm(obj=cls)
    if form.validate_on_submit():
        cls.name = form.name.data.strip()
        cls.department = form.department.data.strip()
        cls.year = form.year.data
        cls.section = form.section.data.strip().upper()
        cls.academic_year = form.academic_year.data.strip()
        cls.is_active = form.is_active.data
        db.session.commit()
        log_audit('CLASS_UPDATE', 'ClassRoom', cls.id, {'name': cls.name})
        flash(f"Class '{cls.name}' updated successfully.", 'success')
        return redirect(url_for('admin.classes'))
    return render_template('admin/class_edit.html', form=form, cls=cls)


@bp.route('/classes/<int:id>/toggle-status', methods=['POST'])
@admin_required
def toggle_class_status(id):
    cls = ClassRoom.query.get_or_404(id)
    cls.is_active = not cls.is_active
    db.session.commit()
    status_label = 'activated' if cls.is_active else 'deactivated'
    log_audit('CLASS_STATUS_TOGGLE', 'ClassRoom', cls.id, {'is_active': cls.is_active})
    flash(f"Class '{cls.name}' has been {status_label}.", 'info')
    return redirect(url_for('admin.classes'))


@bp.route('/subjects', methods=['GET', 'POST'])
@admin_required
def subjects():
    form = SubjectForm()
    if form.validate_on_submit():
        sub = Subject(
            name=form.name.data.strip(),
            code=form.code.data.strip().upper(),
            class_id=form.class_id.data,
            teacher_id=form.teacher_id.data,
            is_active=form.is_active.data
        )
        db.session.add(sub)
        db.session.commit()
        log_audit('SUBJECT_CREATE', 'Subject', sub.id, {'code': sub.code, 'name': sub.name})
        flash(f"Subject '{sub.name}' ({sub.code}) created successfully.", 'success')
        return redirect(url_for('admin.subjects'))

    all_subjects = Subject.query.order_by(Subject.code.asc()).all()
    return render_template('admin/subjects.html', form=form, subjects=all_subjects)


@bp.route('/subjects/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_subject(id):
    sub = Subject.query.get_or_404(id)
    form = SubjectForm(obj=sub)
    if form.validate_on_submit():
        sub.name = form.name.data.strip()
        sub.code = form.code.data.strip().upper()
        sub.class_id = form.class_id.data
        sub.teacher_id = form.teacher_id.data
        sub.is_active = form.is_active.data
        db.session.commit()
        log_audit('SUBJECT_UPDATE', 'Subject', sub.id, {'code': sub.code, 'name': sub.name})
        flash(f"Subject '{sub.name}' updated successfully.", 'success')
        return redirect(url_for('admin.subjects'))
    return render_template('admin/subject_edit.html', form=form, sub=sub)


@bp.route('/subjects/<int:id>/toggle-status', methods=['POST'])
@admin_required
def toggle_subject_status(id):
    sub = Subject.query.get_or_404(id)
    sub.is_active = not sub.is_active
    db.session.commit()
    status_label = 'activated' if sub.is_active else 'deactivated'
    log_audit('SUBJECT_STATUS_TOGGLE', 'Subject', sub.id, {'is_active': sub.is_active})
    flash(f"Subject '{sub.name}' has been {status_label}.", 'info')
    return redirect(url_for('admin.subjects'))


# ==========================================
# TIMETABLE & HOLIDAYS
# ==========================================

@bp.route('/timetable', methods=['GET', 'POST'])
@admin_required
def timetable():
    form = TimetableForm()
    if form.validate_on_submit():
        entry = Timetable(
            class_id=form.class_id.data,
            subject_id=form.subject_id.data,
            teacher_id=form.teacher_id.data,
            weekday=form.weekday.data,
            period=form.period.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            room=form.room.data.strip() if form.room.data else None,
            is_active=form.is_active.data
        )
        db.session.add(entry)
        db.session.commit()
        log_audit('TIMETABLE_CREATE', 'Timetable', entry.id, {'weekday': entry.weekday, 'period': entry.period})
        flash('Timetable slot added successfully.', 'success')
        return redirect(url_for('admin.timetable'))

    entries = Timetable.query.order_by(Timetable.weekday.asc(), Timetable.period.asc()).all()
    return render_template('admin/timetable.html', form=form, entries=entries)


@bp.route('/timetable/<int:id>/delete', methods=['POST'])
@admin_required
def delete_timetable(id):
    entry = Timetable.query.get_or_404(id)
    db.session.delete(entry)
    db.session.commit()
    log_audit('TIMETABLE_DELETE', 'Timetable', id)
    flash('Timetable slot removed successfully.', 'info')
    return redirect(url_for('admin.timetable'))


@bp.route('/holidays', methods=['GET', 'POST'])
@admin_required
def holidays():
    form = HolidayForm()
    if form.validate_on_submit():
        holiday = Holiday(
            date=form.date.data,
            name=form.name.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            is_active=True
        )
        db.session.add(holiday)
        db.session.commit()
        log_audit('HOLIDAY_CREATE', 'Holiday', holiday.id, {'date': str(holiday.date), 'name': holiday.name})
        flash(f"Holiday '{holiday.name}' scheduled for {holiday.date}.", 'success')
        return redirect(url_for('admin.holidays'))

    all_holidays = Holiday.query.order_by(Holiday.date.asc()).all()
    return render_template('admin/holidays.html', form=form, holidays=all_holidays)


@bp.route('/holidays/<int:id>/delete', methods=['POST'])
@admin_required
def delete_holiday(id):
    holiday = Holiday.query.get_or_404(id)
    db.session.delete(holiday)
    db.session.commit()
    log_audit('HOLIDAY_DELETE', 'Holiday', id, {'date': str(holiday.date)})
    flash('Holiday removed.', 'info')
    return redirect(url_for('admin.holidays'))


# ==========================================
# AUDIT LOGS, SETTINGS, BACKUPS & DIAGNOSTICS
# ==========================================

@bp.route('/audit-logs')
@admin_required
def audit_logs():
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action', '').strip()
    entity_filter = request.args.get('entity', '').strip()
    
    query = AuditLog.query
    if action_filter:
        query = query.filter(AuditLog.action.ilike(f"%{action_filter}%"))
    if entity_filter:
        query = query.filter(AuditLog.entity_type.ilike(f"%{entity_filter}%"))

    pagination = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    return render_template('admin/audit_logs.html', pagination=pagination, action_filter=action_filter, entity_filter=entity_filter)


@bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    form = SettingsForm()
    if request.method == 'GET':
        form.attendance_threshold.data = float(get_setting('attendance_threshold', '75.0'))
        form.face_distance_threshold.data = float(get_setting('face_distance_threshold', '0.50'))
        form.min_session_length.data = int(get_setting('min_session_length', '30'))
        form.session_timeout_minutes.data = int(get_setting('session_timeout_minutes', '60'))
        form.late_threshold_minutes.data = int(get_setting('late_threshold_minutes', '10'))

    if form.validate_on_submit():
        set_setting('attendance_threshold', str(form.attendance_threshold.data), 'Minimum attendance percentage')
        set_setting('face_distance_threshold', str(form.face_distance_threshold.data), 'Face recognition matching tolerance')
        set_setting('min_session_length', str(form.min_session_length.data), 'Minimum length in minutes')
        set_setting('session_timeout_minutes', str(form.session_timeout_minutes.data), 'Auto-expiration period in minutes')
        set_setting('late_threshold_minutes', str(form.late_threshold_minutes.data), 'Grace period before marking late')

        log_audit('SETTINGS_UPDATE', 'System', None, {
            'threshold': form.attendance_threshold.data,
            'tolerance': form.face_distance_threshold.data
        })
        flash('System configuration settings updated successfully.', 'success')
        return redirect(url_for('admin.settings'))

    return render_template('admin/settings.html', form=form)


@bp.route('/backups', methods=['GET', 'POST'])
@admin_required
def backups():
    if request.method == 'POST':
        success, message, filename = create_database_backup(user_id=current_user.id)
        if success:
            flash(message, 'success')
        else:
            flash(message, 'danger')
        return redirect(url_for('admin.backups'))

    backup_list = list_backups()
    return render_template('admin/backups.html', backups=backup_list)


@bp.route('/diagnostics')
@admin_required
def diagnostics():
    engine = get_face_engine()
    
    # Check dlib availability
    dlib_available = False
    try:
        import dlib
        dlib_available = True
    except Exception:
        pass

    info = {
        'app_status': 'Operational',
        'app_version': current_app.config.get('APP_VERSION', '1.0.0'),
        'python_version': sys.version.split(' ')[0],
        'os_info': f"{platform.system()} {platform.release()}",
        'database': current_app.config['SQLALCHEMY_DATABASE_URI'].split('///')[0],
        'active_face_engine': engine.engine_name,
        'opencv_version': cv2.__version__,
        'dlib_available': dlib_available,
        'attendance_threshold': get_setting('attendance_threshold', '75.0') + '%',
        'face_distance_threshold': get_setting('face_distance_threshold', '0.50'),
        'timezone': current_app.config.get('TIMEZONE', 'Asia/Kolkata')
    }
    return render_template('admin/diagnostics.html', info=info)
