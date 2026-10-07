from datetime import datetime, date
from flask import render_template, request, Response, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from app.reports import bp
from app.decorators import teacher_required
from app.models import ClassRoom, Subject, Student, User
from app.services.report_service import (
    get_filtered_attendance_query, generate_attendance_csv,
    generate_attendance_xlsx, get_shortage_report
)
from app.utils import log_audit, get_setting


@bp.route('/')
@teacher_required
def index():
    classes = ClassRoom.query.filter_by(is_active=True).all()
    subjects = Subject.query.filter_by(is_active=True).all()
    return render_template('reports/index.html', classes=classes, subjects=subjects)


@bp.route('/shortage')
@teacher_required
def shortage():
    class_id = request.args.get('class_id', type=int)
    threshold = float(get_setting('attendance_threshold', '75.0'))
    shortage_list = get_shortage_report(threshold=threshold, class_id=class_id)
    classes = ClassRoom.query.filter_by(is_active=True).all()

    return render_template(
        'reports/shortage.html',
        shortages=shortage_list,
        classes=classes,
        threshold=threshold,
        selected_class_id=class_id
    )


@bp.route('/export/csv')
@teacher_required
def export_csv():
    date_from_str = request.args.get('date_from', '').strip()
    date_to_str = request.args.get('date_to', '').strip()
    class_id = request.args.get('class_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    student_roll = request.args.get('roll_no', '').strip()
    status = request.args.get('status', '').strip()
    method = request.args.get('method', '').strip()

    date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else None
    date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else None
    teacher_id = None if current_user.is_admin else current_user.id

    query = get_filtered_attendance_query(
        date_from=date_from,
        date_to=date_to,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=teacher_id,
        roll_no=student_roll,
        status=status,
        method=method
    )

    csv_data = generate_attendance_csv(query)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"attendance_report_{timestamp}.csv"

    log_audit('REPORT_EXPORT_CSV', 'Report', None, {
        'class_id': class_id,
        'subject_id': subject_id,
        'date_from': date_from_str,
        'date_to': date_to_str
    }, user_id=current_user.id)

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )


@bp.route('/export/xlsx')
@bp.route('/export/excel')
@teacher_required
def export_xlsx():
    date_from_str = request.args.get('date_from', '').strip()
    date_to_str = request.args.get('date_to', '').strip()
    class_id = request.args.get('class_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    student_roll = request.args.get('roll_no', '').strip()
    status = request.args.get('status', '').strip()
    method = request.args.get('method', '').strip()

    date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else None
    date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else None
    teacher_id = None if current_user.is_admin else current_user.id

    query = get_filtered_attendance_query(
        date_from=date_from,
        date_to=date_to,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=teacher_id,
        roll_no=student_roll,
        status=status,
        method=method
    )

    excel_stream = generate_attendance_xlsx(query, report_title="Smart Attendance System - Comprehensive Report")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"attendance_report_{timestamp}.xlsx"

    log_audit('REPORT_EXPORT_XLSX', 'Report', None, {
        'class_id': class_id,
        'subject_id': subject_id,
        'date_from': date_from_str,
        'date_to': date_to_str
    }, user_id=current_user.id)

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )
