from app.services.import_service import process_student_csv_import, generate_import_template_csv
from app.models import Student, User


def test_import_template_generator():
    csv_text = generate_import_template_csv()
    assert "roll_no,name,email,phone,department,year,section,class_name" in csv_text
    assert "CS2026001" in csv_text


def test_csv_import_valid_data(client):
    csv_data = (
        "roll_no,name,email,phone,department,year,section,class_name\n"
        "IMP001,Alice Wonder,alice.w@test.edu,555-001,Computer Science,1,A,TEST-101\n"
        "IMP002,Bob Builder,bob.b@test.edu,555-002,Computer Science,1,A,TEST-101\n"
    )
    result = process_student_csv_import(csv_data)
    assert result['success'] is True
    assert result['imported_count'] == 2
    assert result['failed_count'] == 0
    assert Student.query.filter_by(roll_no='IMP001').first() is not None
    assert User.query.filter_by(email='alice.w@test.edu').first() is not None


def test_csv_import_partial_failure_with_diagnostics(client):
    csv_data = (
        "roll_no,name,email,phone,department,year,section,class_name\n"
        "IMP003,Charlie Chaplin,charlie@test.edu,555-003,Computer Science,1,A,TEST-101\n"
        ",Missing Roll,noroll@test.edu,555-004,Computer Science,1,A,TEST-101\n"  # Missing roll_no
        "IMP004,Invalid Email,not-an-email,555-005,Computer Science,1,A,TEST-101\n"  # Bad email
        "TEST001,Duplicate Student,dup@test.edu,555-006,Computer Science,1,A,TEST-101\n"  # Duplicate roll
    )
    result = process_student_csv_import(csv_data)
    assert result['total_rows'] == 4
    assert result['imported_count'] == 1  # IMP003 succeeded
    assert result['failed_count'] == 3
    assert len(result['errors']) >= 3
    
    # Verify valid row was not lost
    assert Student.query.filter_by(roll_no='IMP003').first() is not None
