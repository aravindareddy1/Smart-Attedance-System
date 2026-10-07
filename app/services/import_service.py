import csv
import io
import re
from typing import Dict, Any, List, Tuple, Optional
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import Student, ClassRoom, User
from app.utils import log_audit


def validate_email(email_str: str) -> bool:
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email_str.strip()))


def process_student_csv_import(
    file_stream,
    default_class_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Parses and validates a CSV file for student enrollment row by row.
    Columns expected:
    roll_no, name, email, phone, department, year, section, class_name

    Returns a detailed summary report containing:
    - total_rows
    - imported_count
    - failed_count
    - errors: list of {row, field, value, error, suggestion}
    - imported_students: list of student roll numbers
    """
    if isinstance(file_stream, bytes):
        file_content = file_stream.decode('utf-8-sig', errors='replace')
    elif hasattr(file_stream, 'read'):
        raw = file_stream.read()
        file_content = raw.decode('utf-8-sig', errors='replace') if isinstance(raw, bytes) else raw
    else:
        file_content = str(file_stream)

    csv_reader = csv.DictReader(io.StringIO(file_content))
    if not csv_reader.fieldnames:
        return {
            'success': False,
            'message': 'The CSV file is empty or headers could not be parsed.',
            'total_rows': 0,
            'imported_count': 0,
            'failed_count': 0,
            'errors': []
        }

    # Normalize column names
    field_map = {name.strip().lower().replace(' ', '_'): name for name in csv_reader.fieldnames}
    required_cols = ['roll_no', 'name', 'email', 'department', 'year', 'section']
    missing_cols = [col for col in required_cols if col not in field_map]

    if missing_cols:
        return {
            'success': False,
            'message': f"CSV is missing mandatory columns: {', '.join(missing_cols)}. Expected format: roll_no, name, email, phone, department, year, section, class_name",
            'total_rows': 0,
            'imported_count': 0,
            'failed_count': 0,
            'errors': []
        }

    total_rows = 0
    imported_count = 0
    failed_count = 0
    errors = []
    imported_students = []

    # Cache classrooms for lookup
    classrooms_by_name = {c.name.strip().lower(): c.id for c in ClassRoom.query.all()}
    existing_roll_nos = set(r[0].strip().lower() for r in db.session.query(Student.roll_no).all())
    existing_emails = set(e[0].strip().lower() for e in db.session.query(User.email).all())

    row_num = 1  # 1-indexed (header is 1, data starts row 2)

    for row in csv_reader:
        row_num += 1
        total_rows += 1
        row_errors = []

        roll_no = row.get(field_map.get('roll_no', ''), '').strip()
        name = row.get(field_map.get('name', ''), '').strip()
        email = row.get(field_map.get('email', ''), '').strip()
        phone = row.get(field_map.get('phone', ''), '').strip()
        dept = row.get(field_map.get('department', ''), '').strip()
        year_str = row.get(field_map.get('year', ''), '').strip()
        section = row.get(field_map.get('section', ''), '').strip()
        class_name = row.get(field_map.get('class_name', ''), '').strip() if 'class_name' in field_map else ''

        # Validation rules
        if not roll_no:
            row_errors.append({'field': 'roll_no', 'value': '', 'error': 'Roll number is required', 'suggestion': 'Provide a unique alphanumeric roll number'})
        elif roll_no.lower() in existing_roll_nos:
            row_errors.append({'field': 'roll_no', 'value': roll_no, 'error': 'Roll number already exists in database', 'suggestion': 'Check for duplicate student records'})

        if not name:
            row_errors.append({'field': 'name', 'value': '', 'error': 'Name is required', 'suggestion': 'Enter student full name'})

        if not email:
            row_errors.append({'field': 'email', 'value': '', 'error': 'Email is required', 'suggestion': 'Provide a valid student email'})
        elif not validate_email(email):
            row_errors.append({'field': 'email', 'value': email, 'error': 'Invalid email format', 'suggestion': 'Use standard email format e.g. student@institution.edu'})

        if not dept:
            row_errors.append({'field': 'department', 'value': '', 'error': 'Department is required', 'suggestion': 'e.g. Computer Science'})

        year = 1
        try:
            year = int(year_str)
            if year < 1 or year > 6:
                row_errors.append({'field': 'year', 'value': year_str, 'error': 'Year must be between 1 and 6', 'suggestion': 'Enter a valid year number'})
        except ValueError:
            row_errors.append({'field': 'year', 'value': year_str, 'error': 'Year must be an integer', 'suggestion': 'Enter 1, 2, 3, or 4'})

        if not section:
            row_errors.append({'field': 'section', 'value': '', 'error': 'Section is required', 'suggestion': 'e.g. A, B, C'})

        target_class_id = default_class_id
        if class_name and class_name.lower() in classrooms_by_name:
            target_class_id = classrooms_by_name[class_name.lower()]
        elif not target_class_id:
            # Try to find class matching name, department, year, and section
            matched_cls = ClassRoom.query.filter(
                (ClassRoom.name.ilike(class_name)) |
                ((ClassRoom.department.ilike(dept)) & (ClassRoom.year == year) & (ClassRoom.section.ilike(section)))
            ).first()
            if matched_cls:
                target_class_id = matched_cls.id
            else:
                row_errors.append({
                    'field': 'class_name',
                    'value': class_name or f"{dept} Y{year} Sec-{section}",
                    'error': 'No matching classroom found',
                    'suggestion': 'Create the classroom first or specify an existing class name'
                })

        if row_errors:
            failed_count += 1
            for err in row_errors:
                errors.append({
                    'row': row_num,
                    'field': err['field'],
                    'value': err['value'],
                    'error': err['error'],
                    'suggestion': err['suggestion']
                })
            continue

        # If valid row, create Student and Student User login
        try:
            # Create user login account if email not already used
            user_account = None
            if email.lower() not in existing_emails:
                user_account = User(
                    name=name,
                    email=email.lower(),
                    role='student',
                    is_active=True,
                    is_default_password=True
                )
                user_account.set_password('Student@123')
                db.session.add(user_account)
                db.session.flush()
                existing_emails.add(email.lower())

            student = Student(
                roll_no=roll_no,
                name=name,
                email=email,
                phone=phone,
                department=dept,
                year=year,
                section=section,
                class_id=target_class_id,
                user_id=user_account.id if user_account else None,
                is_active=True,
                face_enrolled=False
            )
            db.session.add(student)
            db.session.flush()

            existing_roll_nos.add(roll_no.lower())
            imported_students.append(roll_no)
            imported_count += 1

        except Exception as e:
            db.session.rollback()
            failed_count += 1
            errors.append({
                'row': row_num,
                'field': 'Database',
                'value': roll_no,
                'error': str(e),
                'suggestion': 'Retry importing this specific row'
            })
            continue

    try:
        db.session.commit()
        log_audit('STUDENT_BULK_IMPORT', 'Student', None, {
            'total_rows': total_rows,
            'imported': imported_count,
            'failed': failed_count
        }, user_id=user_id)
    except Exception as e:
        db.session.rollback()
        return {
            'success': False,
            'message': f'Database error committing imported rows: {str(e)}',
            'total_rows': total_rows,
            'imported_count': 0,
            'failed_count': total_rows,
            'errors': [{'row': 'ALL', 'field': 'commit', 'value': '', 'error': str(e), 'suggestion': 'Check database connection'}]
        }

    return {
        'success': True,
        'message': f"{total_rows} rows processed: {imported_count} imported, {failed_count} failed.",
        'total_rows': total_rows,
        'imported_count': imported_count,
        'failed_count': failed_count,
        'errors': errors,
        'imported_students': imported_students
    }


def generate_import_template_csv() -> str:
    """Generates standard CSV template headers with sample rows."""
    headers = ['roll_no', 'name', 'email', 'phone', 'department', 'year', 'section', 'class_name']
    samples = [
        ['CS2026001', 'Alice Johnson', 'alice.johnson@example.edu', '9876543210', 'Computer Science', '3', 'A', 'CSE-3A'],
        ['CS2026002', 'Bob Smith', 'bob.smith@example.edu', '9876543211', 'Computer Science', '3', 'A', 'CSE-3A'],
        ['EC2026001', 'Charlie Brown', 'charlie.brown@example.edu', '9876543212', 'Electronics', '2', 'B', 'ECE-2B']
    ]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(samples)
    return output.getvalue()
