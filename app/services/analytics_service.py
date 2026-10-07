from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import func, case
from app.extensions import db
from app.models import (
    AttendanceRecord, AttendanceSession, Student, ClassRoom, Subject, User
)
from app.utils import calculate_attendance_percentage, get_setting


def get_analytics_summary(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Computes top-level KPI metrics.
    """
    today = date.today()
    threshold = float(get_setting('attendance_threshold', '75.0'))

    # Total counts
    total_students = Student.query.filter_by(is_active=True).count()
    total_teachers = User.query.filter(User.role.in_(['teacher', 'admin']), User.is_active==True).count()
    active_classes = ClassRoom.query.filter_by(is_active=True).count()

    # Enrolled face coverage
    enrolled_faces_count = Student.query.filter_by(is_active=True, face_enrolled=True).count()
    face_coverage_pct = round((enrolled_faces_count / total_students * 100.0) if total_students > 0 else 0.0, 1)

    # Today's sessions & attendance
    today_sessions = AttendanceSession.query.filter_by(date=today).all()
    sessions_today_count = len(today_sessions)

    today_present = 0
    today_total_marks = 0
    if today_sessions:
        session_ids = [s.id for s in today_sessions]
        today_records = AttendanceRecord.query.filter(AttendanceRecord.session_id.in_(session_ids)).all()
        today_total_marks = len(today_records)
        today_present = sum(1 for r in today_records if r.status in ('Present', 'Late'))

    today_present_pct = round((today_present / today_total_marks * 100.0) if today_total_marks > 0 else 0.0, 1)

    # Overall average attendance percentage (filtered if applicable)
    base_query = db.session.query(
        func.count(AttendanceRecord.id).label('total'),
        func.sum(case((AttendanceRecord.status.in_(['Present', 'Late']), 1), else_=0)).label('attended')
    ).join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)

    if date_from:
        base_query = base_query.filter(AttendanceSession.date >= date_from)
    if date_to:
        base_query = base_query.filter(AttendanceSession.date <= date_to)
    if class_id:
        base_query = base_query.filter(AttendanceSession.class_id == class_id)
    if subject_id:
        base_query = base_query.filter(AttendanceSession.subject_id == subject_id)

    total_rec, attended_rec = base_query.first() or (0, 0)
    total_rec = total_rec or 0
    attended_rec = attended_rec or 0
    avg_attendance_pct = round((attended_rec / total_rec * 100.0) if total_rec > 0 else 0.0, 1)

    # Students below threshold
    students = Student.query.filter_by(is_active=True).all()
    below_threshold_count = 0
    for s in students:
        s_total = AttendanceRecord.query.join(AttendanceSession).filter(
            AttendanceRecord.student_id == s.id,
            AttendanceSession.status == 'ended'
        ).count()
        if s_total > 0:
            s_attended = AttendanceRecord.query.join(AttendanceSession).filter(
                AttendanceRecord.student_id == s.id,
                AttendanceSession.status == 'ended',
                AttendanceRecord.status.in_(['Present', 'Late'])
            ).count()
            s_pct = (s_attended / float(s_total)) * 100.0
            if s_pct < threshold:
                below_threshold_count += 1

    return {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'active_classes': active_classes,
        'today_present_pct': today_present_pct,
        'avg_attendance_pct': avg_attendance_pct,
        'students_below_threshold': below_threshold_count,
        'sessions_today': sessions_today_count,
        'face_coverage_pct': face_coverage_pct,
        'threshold': threshold
    }


def get_trend_analytics(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Computes daily attendance percentage trend over the given range.
    """
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=30)

    query = db.session.query(
        AttendanceSession.date,
        func.count(AttendanceRecord.id).label('total'),
        func.sum(case((AttendanceRecord.status.in_(['Present', 'Late']), 1), else_=0)).label('attended'),
        func.sum(case((AttendanceRecord.status == 'Present', 1), else_=0)).label('present'),
        func.sum(case((AttendanceRecord.status == 'Late', 1), else_=0)).label('late'),
        func.sum(case((AttendanceRecord.status == 'Absent', 1), else_=0)).label('absent')
    ).join(
        AttendanceRecord, AttendanceSession.id == AttendanceRecord.session_id
    ).filter(
        AttendanceSession.date >= date_from,
        AttendanceSession.date <= date_to,
        AttendanceSession.status == 'ended'
    )

    if class_id:
        query = query.filter(AttendanceSession.class_id == class_id)
    if subject_id:
        query = query.filter(AttendanceSession.subject_id == subject_id)

    query = query.group_by(AttendanceSession.date).order_by(AttendanceSession.date.asc())
    results = query.all()

    labels = []
    percentages = []
    present_counts = []
    absent_counts = []

    for row in results:
        labels.append(row.date.strftime('%b %d'))
        tot = row.total or 0
        att = row.attended or 0
        pct = round((att / tot * 100.0) if tot > 0 else 0.0, 1)
        percentages.append(pct)
        present_counts.append(row.present or 0)
        absent_counts.append(row.absent or 0)

    return {
        'labels': labels,
        'percentages': percentages,
        'present_counts': present_counts,
        'absent_counts': absent_counts
    }


def get_classwise_analytics(date_from: Optional[date] = None, date_to: Optional[date] = None) -> Dict[str, Any]:
    """
    Calculates average attendance percentage for each active class.
    """
    classes = ClassRoom.query.filter_by(is_active=True).all()
    labels = []
    percentages = []

    for c in classes:
        query = db.session.query(
            func.count(AttendanceRecord.id).label('total'),
            func.sum(case((AttendanceRecord.status.in_(['Present', 'Late']), 1), else_=0)).label('attended')
        ).join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id).filter(
            AttendanceSession.class_id == c.id,
            AttendanceSession.status == 'ended'
        )

        if date_from:
            query = query.filter(AttendanceSession.date >= date_from)
        if date_to:
            query = query.filter(AttendanceSession.date <= date_to)

        tot, att = query.first() or (0, 0)
        tot = tot or 0
        att = att or 0
        pct = round((att / tot * 100.0) if tot > 0 else 0.0, 1)
        labels.append(c.name)
        percentages.append(pct)

    return {
        'labels': labels,
        'percentages': percentages
    }


def get_subjectwise_analytics(class_id: Optional[int] = None, date_from: Optional[date] = None, date_to: Optional[date] = None) -> Dict[str, Any]:
    """
    Calculates average attendance percentage for each active subject.
    """
    sub_query = Subject.query.filter_by(is_active=True)
    if class_id:
        sub_query = sub_query.filter_by(class_id=class_id)
    subjects = sub_query.all()

    labels = []
    percentages = []

    for s in subjects:
        query = db.session.query(
            func.count(AttendanceRecord.id).label('total'),
            func.sum(case((AttendanceRecord.status.in_(['Present', 'Late']), 1), else_=0)).label('attended')
        ).join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id).filter(
            AttendanceSession.subject_id == s.id,
            AttendanceSession.status == 'ended'
        )

        if date_from:
            query = query.filter(AttendanceSession.date >= date_from)
        if date_to:
            query = query.filter(AttendanceSession.date <= date_to)

        tot, att = query.first() or (0, 0)
        tot = tot or 0
        att = att or 0
        pct = round((att / tot * 100.0) if tot > 0 else 0.0, 1)
        labels.append(f"{s.code} ({s.name})")
        percentages.append(pct)

    return {
        'labels': labels,
        'percentages': percentages
    }


def get_heatmap_analytics(class_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Calculates attendance percentage by (Weekday, Period) for heatmap visualization.
    """
    weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    periods = list(range(1, 7))  # Periods 1 to 6

    # Matrix: row=weekday (0 to 5), col=period (1 to 6)
    matrix = []
    for day_idx in range(6):
        row = []
        for p in periods:
            # Query attendance records matching sessions on this weekday & period
            # In SQLite: strftime('%w', date) -> 0=Sunday, 1=Monday...
            # We filter python-side or via query
            sessions = AttendanceSession.query.filter(
                AttendanceSession.period == p,
                AttendanceSession.status == 'ended'
            )
            if class_id:
                sessions = sessions.filter(AttendanceSession.class_id == class_id)
            all_sess = sessions.all()
            matching_sess_ids = [s.id for s in all_sess if s.date.weekday() == day_idx]

            if matching_sess_ids:
                tot, att = db.session.query(
                    func.count(AttendanceRecord.id),
                    func.sum(case((AttendanceRecord.status.in_(['Present', 'Late']), 1), else_=0))
                ).filter(AttendanceRecord.session_id.in_(matching_sess_ids)).first()
                tot = tot or 0
                att = att or 0
                pct = round((att / tot * 100.0) if tot > 0 else 0.0, 1)
            else:
                pct = 0.0
            row.append(pct)
        matrix.append(row)

    return {
        'weekdays': weekdays,
        'periods': [f"Period {p}" for p in periods],
        'data': matrix
    }


def get_top_absent_analytics(limit: int = 10, class_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Returns top N students with the highest number of absences.
    """
    query = db.session.query(
        Student.roll_no,
        Student.name,
        ClassRoom.name.label('class_name'),
        func.count(AttendanceRecord.id).label('absent_count')
    ).join(
        AttendanceRecord, Student.id == AttendanceRecord.student_id
    ).join(
        AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id
    ).join(
        ClassRoom, Student.class_id == ClassRoom.id
    ).filter(
        AttendanceRecord.status == 'Absent',
        AttendanceSession.status == 'ended',
        Student.is_active == True
    )

    if class_id:
        query = query.filter(Student.class_id == class_id)

    query = query.group_by(Student.id, Student.roll_no, Student.name, ClassRoom.name)\
                 .order_by(func.count(AttendanceRecord.id).desc())\
                 .limit(limit)

    results = query.all()
    labels = [f"{r.roll_no} - {r.name}" for r in results]
    counts = [r.absent_count for r in results]

    return {
        'labels': labels,
        'counts': counts
    }


def get_attendance_distribution(class_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Categorizes active students into attendance percentage tiers.
    """
    students_query = Student.query.filter_by(is_active=True)
    if class_id:
        students_query = students_query.filter_by(class_id=class_id)
    students = students_query.all()

    buckets = {
        '90-100%': 0,
        '80-89%': 0,
        '75-79%': 0,
        '60-74%': 0,
        'Below 60%': 0
    }

    for s in students:
        tot = AttendanceRecord.query.join(AttendanceSession).filter(
            AttendanceRecord.student_id == s.id,
            AttendanceSession.status == 'ended'
        ).count()
        if tot == 0:
            continue
        att = AttendanceRecord.query.join(AttendanceSession).filter(
            AttendanceRecord.student_id == s.id,
            AttendanceSession.status == 'ended',
            AttendanceRecord.status.in_(['Present', 'Late'])
        ).count()
        pct = (att / float(tot)) * 100.0

        if pct >= 90.0:
            buckets['90-100%'] += 1
        elif pct >= 80.0:
            buckets['80-89%'] += 1
        elif pct >= 75.0:
            buckets['75-79%'] += 1
        elif pct >= 60.0:
            buckets['60-74%'] += 1
        else:
            buckets['Below 60%'] += 1

    return {
        'labels': list(buckets.keys()),
        'counts': list(buckets.values())
    }
