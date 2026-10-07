import os
import io
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import func
from app.extensions import db
from app.models import (
    AttendanceRecord, AttendanceSession, Student, ClassRoom, Subject, User, Holiday
)
from app.utils import calculate_attendance_percentage, get_setting


def get_filtered_attendance_query(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    class_id: Optional[int] = None,
    section: Optional[str] = None,
    subject_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    student_id: Optional[int] = None,
    roll_no: Optional[str] = None,
    status: Optional[str] = None,
    method: Optional[str] = None
):
    """
    Constructs a SQLAlchemy query joining AttendanceRecord with Session, Student, Class, Subject, Teacher.
    """
    query = db.session.query(
        AttendanceRecord.id.label('record_id'),
        AttendanceSession.date.label('session_date'),
        AttendanceSession.period.label('period'),
        AttendanceSession.session_name.label('session_name'),
        ClassRoom.name.label('class_name'),
        ClassRoom.department.label('department'),
        ClassRoom.section.label('section'),
        Subject.name.label('subject_name'),
        Subject.code.label('subject_code'),
        User.name.label('teacher_name'),
        Student.roll_no.label('roll_no'),
        Student.name.label('student_name'),
        AttendanceRecord.status.label('status'),
        AttendanceRecord.method.label('method'),
        AttendanceRecord.confidence.label('confidence'),
        AttendanceRecord.note.label('note'),
        AttendanceRecord.marked_at.label('marked_at'),
        AttendanceRecord.updated_at.label('updated_at')
    ).join(
        AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id
    ).join(
        Student, AttendanceRecord.student_id == Student.id
    ).join(
        ClassRoom, AttendanceSession.class_id == ClassRoom.id
    ).join(
        Subject, AttendanceSession.subject_id == Subject.id
    ).join(
        User, AttendanceSession.teacher_id == User.id
    )

    if date_from:
        query = query.filter(AttendanceSession.date >= date_from)
    if date_to:
        query = query.filter(AttendanceSession.date <= date_to)
    if class_id:
        query = query.filter(AttendanceSession.class_id == class_id)
    if section:
        query = query.filter(ClassRoom.section == section)
    if subject_id:
        query = query.filter(AttendanceSession.subject_id == subject_id)
    if teacher_id:
        query = query.filter(AttendanceSession.teacher_id == teacher_id)
    if student_id:
        query = query.filter(AttendanceRecord.student_id == student_id)
    if roll_no:
        query = query.filter(Student.roll_no.ilike(f"%{roll_no}%"))
    if status:
        query = query.filter(AttendanceRecord.status == status)
    if method:
        query = query.filter(AttendanceRecord.method == method)

    return query.order_by(AttendanceSession.date.desc(), AttendanceSession.period.asc(), Student.roll_no.asc())


def generate_attendance_csv(query) -> str:
    """Generates CSV content from query results."""
    records = query.all()
    data = []
    for r in records:
        data.append({
            'Record ID': r.record_id,
            'Date': r.session_date.strftime('%Y-%m-%d') if r.session_date else '',
            'Period': r.period,
            'Class': r.class_name,
            'Section': r.section,
            'Subject Code': r.subject_code,
            'Subject Name': r.subject_name,
            'Teacher': r.teacher_name,
            'Roll Number': r.roll_no,
            'Student Name': r.student_name,
            'Status': r.status,
            'Method': r.method,
            'Confidence': f"{r.confidence:.2f}" if r.confidence is not None else 'N/A',
            'Marked At': r.marked_at.strftime('%Y-%m-%d %H:%M:%S') if r.marked_at else '',
            'Note': r.note or ''
        })
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=[
            'Record ID', 'Date', 'Period', 'Class', 'Section', 'Subject Code',
            'Subject Name', 'Teacher', 'Roll Number', 'Student Name', 'Status',
            'Method', 'Confidence', 'Marked At', 'Note'
        ])
    return df.to_csv(index=False)


def generate_attendance_xlsx(query, report_title: str = "Attendance Report") -> io.BytesIO:
    """
    Generates a beautifully styled Excel spreadsheet with frozen header, auto column widths,
    status highlighting, and summary metrics.
    """
    records = query.all()
    data = []
    status_counts = {'Present': 0, 'Absent': 0, 'Late': 0, 'Excused': 0}

    for r in records:
        if r.status in status_counts:
            status_counts[r.status] += 1
        data.append({
            'Record ID': r.record_id,
            'Date': r.session_date.strftime('%Y-%m-%d') if r.session_date else '',
            'Period': r.period,
            'Class': r.class_name,
            'Section': r.section,
            'Subject Code': r.subject_code,
            'Subject Name': r.subject_name,
            'Teacher': r.teacher_name,
            'Roll Number': r.roll_no,
            'Student Name': r.student_name,
            'Status': r.status,
            'Method': r.method,
            'Confidence': r.confidence if r.confidence is not None else '',
            'Marked At': r.marked_at.strftime('%Y-%m-%d %H:%M:%S') if r.marked_at else '',
            'Note': r.note or ''
        })

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance Records"

    # Title styling
    ws.merge_cells('A1:O1')
    title_cell = ws['A1']
    title_cell.value = report_title.upper()
    title_cell.font = Font(name='Calibri', size=16, bold=True, color='FFFFFF')
    title_cell.fill = PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid')
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 35

    # Summary Row in Header
    ws.merge_cells('A2:O2')
    sub_cell = ws['A2']
    total_recs = len(records)
    sub_cell.value = (
        f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Total Records: {total_recs} | "
        f"Present: {status_counts['Present']} | Late: {status_counts['Late']} | "
        f"Absent: {status_counts['Absent']} | Excused: {status_counts['Excused']}"
    )
    sub_cell.font = Font(name='Calibri', size=10, italic=True, color='374151')
    sub_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[2].height = 20

    headers = [
        'Record ID', 'Date', 'Period', 'Class', 'Section', 'Subject Code',
        'Subject Name', 'Teacher', 'Roll Number', 'Student Name', 'Status',
        'Method', 'Confidence', 'Marked At', 'Note'
    ]

    header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='3B82F6', end_color='3B82F6', fill_type='solid')
    thin_border = Border(
        left=Side(style='thin', color='D1D5DB'),
        right=Side(style='thin', color='D1D5DB'),
        top=Side(style='thin', color='D1D5DB'),
        bottom=Side(style='thin', color='D1D5DB')
    )

    # Write Headers at row 4
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border
    ws.row_dimensions[4].height = 25

    # Status color formatting
    status_fills = {
        'Present': PatternFill(start_color='DEF7EC', end_color='DEF7EC', fill_type='solid'),
        'Late': PatternFill(start_color='FEF08A', end_color='FEF08A', fill_type='solid'),
        'Absent': PatternFill(start_color='FDE8E8', end_color='FDE8E8', fill_type='solid'),
        'Excused': PatternFill(start_color='E1EFFE', end_color='E1EFFE', fill_type='solid')
    }

    # Data Rows
    row_idx = 5
    for item in data:
        for col_num, key in enumerate(headers, 1):
            cell = ws.cell(row=row_idx, column=col_num)
            val = item.get(key, '')
            cell.value = val
            cell.border = thin_border
            cell.font = Font(name='Calibri', size=10)
            cell.alignment = Alignment(vertical='center')

            if key == 'Status' and val in status_fills:
                cell.fill = status_fills[val]
                cell.alignment = Alignment(horizontal='center', vertical='center')
            elif key in ('Record ID', 'Period', 'Date', 'Roll Number', 'Method'):
                cell.alignment = Alignment(horizontal='center', vertical='center')

        ws.row_dimensions[row_idx].height = 20
        row_idx += 1

    # Freeze panes at data start
    ws.freeze_panes = 'A5'

    # Auto-fit column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def get_shortage_report(threshold: Optional[float] = None, class_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Calculates student attendance shortages below the threshold.
    """
    if threshold is None:
        threshold = float(get_setting('attendance_threshold', '75.0'))

    students_query = Student.query.filter_by(is_active=True)
    if class_id:
        students_query = students_query.filter_by(class_id=class_id)

    students = students_query.all()
    results = []

    for s in students:
        # Total sessions for student's classroom
        total_sessions = AttendanceSession.query.filter(
            AttendanceSession.class_id == s.class_id,
            AttendanceSession.status == 'ended'
        ).count()

        if total_sessions == 0:
            continue

        records = AttendanceRecord.query.join(AttendanceSession).filter(
            AttendanceRecord.student_id == s.id,
            AttendanceSession.status == 'ended'
        ).all()

        present_count = sum(1 for r in records if r.status == 'Present')
        late_count = sum(1 for r in records if r.status == 'Late')
        absent_count = sum(1 for r in records if r.status == 'Absent')
        excused_count = sum(1 for r in records if r.status == 'Excused')

        # Eligible sessions = Total - Excused (or standard eligible)
        pct = calculate_attendance_percentage(present_count, late_count, total_sessions)

        if pct < threshold:
            from app.utils import calculate_required_future_classes
            required_classes = calculate_required_future_classes(
                present_count + late_count, total_sessions, target_percentage=threshold
            )
            results.append({
                'student_id': s.id,
                'roll_no': s.roll_no,
                'name': s.name,
                'email': s.email,
                'class_name': s.classroom.name if s.classroom else 'N/A',
                'department': s.department,
                'percentage': pct,
                'total_sessions': total_sessions,
                'attended_sessions': present_count + late_count,
                'missed_sessions': absent_count,
                'required_percentage': threshold,
                'consecutive_classes_needed': required_classes
            })

    # Sort lowest percentage first
    results.sort(key=lambda x: x['percentage'])
    return results
