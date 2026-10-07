from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, IntegerField, TextAreaField, DateField, TimeField, FloatField
from wtforms.validators import DataRequired, InputRequired, Email, Length, EqualTo, ValidationError, NumberRange, Optional
from app.models import User, Student, ClassRoom, Subject, Timetable, Holiday


class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Sign In')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long.')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match.')
    ])
    submit = SubmitField('Update Password')


class ForgotPasswordForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Password Reset Link')


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long.')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match.')
    ])
    submit = SubmitField('Reset Password')


class TeacherForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Initial Password', validators=[
        Optional(),
        Length(min=6, message='Password must be at least 6 characters long.')
    ])
    is_active = BooleanField('Active Account', default=True)
    submit = SubmitField('Save Teacher')

    def __init__(self, original_email=None, *args, **kwargs):
        super(TeacherForm, self).__init__(*args, **kwargs)
        self.original_email = original_email

    def validate_email(self, field):
        if field.data != self.original_email:
            user = User.query.filter_by(email=field.data).first()
            if user:
                raise ValidationError('This email address is already registered.')


class StudentForm(FlaskForm):
    roll_no = StringField('Roll Number', validators=[DataRequired(), Length(max=50)])
    name = StringField('Student Name', validators=[DataRequired(), Length(max=100)])
    email = StringField('Student Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    department = StringField('Department', validators=[DataRequired(), Length(max=100)])
    year = IntegerField('Year of Study', validators=[DataRequired(), NumberRange(min=1, max=6)])
    section = StringField('Section', validators=[DataRequired(), Length(max=10)])
    class_id = SelectField('Classroom', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active Student', default=True)
    create_login = BooleanField('Create Student Portal Login', default=True)
    submit = SubmitField('Save Student')

    def __init__(self, original_roll_no=None, *args, **kwargs):
        super(StudentForm, self).__init__(*args, **kwargs)
        self.original_roll_no = original_roll_no
        self.class_id.choices = [(c.id, f"{c.name} ({c.department})") for c in ClassRoom.query.filter_by(is_active=True).all()]

    def validate_roll_no(self, field):
        if field.data != self.original_roll_no:
            student = Student.query.filter_by(roll_no=field.data).first()
            if student:
                raise ValidationError('A student with this Roll Number already exists.')


class ClassRoomForm(FlaskForm):
    name = StringField('Class Identifier (e.g. CSE-3A)', validators=[DataRequired(), Length(max=100)])
    department = StringField('Department', validators=[DataRequired(), Length(max=100)])
    year = IntegerField('Year', validators=[DataRequired(), NumberRange(min=1, max=6)])
    section = StringField('Section', validators=[DataRequired(), Length(max=10)])
    academic_year = StringField('Academic Year (e.g. 2025-2026)', validators=[DataRequired(), Length(max=20)])
    is_active = BooleanField('Active Class', default=True)
    submit = SubmitField('Save Class')


class SubjectForm(FlaskForm):
    name = StringField('Subject Name', validators=[DataRequired(), Length(max=100)])
    code = StringField('Subject Code', validators=[DataRequired(), Length(max=20)])
    class_id = SelectField('Classroom', coerce=int, validators=[DataRequired()])
    teacher_id = SelectField('Assigned Teacher', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active Subject', default=True)
    submit = SubmitField('Save Subject')

    def __init__(self, *args, **kwargs):
        super(SubjectForm, self).__init__(*args, **kwargs)
        self.class_id.choices = [(c.id, f"{c.name} ({c.department})") for c in ClassRoom.query.filter_by(is_active=True).all()]
        self.teacher_id.choices = [(t.id, f"{t.name} ({t.email})") for t in User.query.filter(User.role.in_(['teacher', 'admin']), User.is_active==True).all()]


class TimetableForm(FlaskForm):
    class_id = SelectField('Classroom', coerce=int, validators=[DataRequired()])
    subject_id = SelectField('Subject', coerce=int, validators=[DataRequired()])
    teacher_id = SelectField('Teacher', coerce=int, validators=[DataRequired()])
    weekday = SelectField('Day of Week', coerce=int, choices=[
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
    ], validators=[InputRequired()])
    period = IntegerField('Period Number', validators=[DataRequired(), NumberRange(min=1, max=12)])
    start_time = TimeField('Start Time', validators=[DataRequired()])
    end_time = TimeField('End Time', validators=[DataRequired()])
    room = StringField('Room / Hall', validators=[Optional(), Length(max=50)])
    is_active = BooleanField('Active Slot', default=True)
    submit = SubmitField('Save Schedule')

    def __init__(self, *args, **kwargs):
        super(TimetableForm, self).__init__(*args, **kwargs)
        self.class_id.choices = [(c.id, c.name) for c in ClassRoom.query.filter_by(is_active=True).all()]
        self.subject_id.choices = [(s.id, f"{s.code} - {s.name}") for s in Subject.query.filter_by(is_active=True).all()]
        self.teacher_id.choices = [(t.id, t.name) for t in User.query.filter(User.role.in_(['teacher', 'admin']), User.is_active==True).all()]


class HolidayForm(FlaskForm):
    date = DateField('Holiday Date', validators=[DataRequired()])
    name = StringField('Holiday Title', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=255)])
    submit = SubmitField('Save Holiday')


class CSVImportForm(FlaskForm):
    file = FileField('CSV File', validators=[
        FileRequired(),
        FileAllowed(['csv', 'txt'], 'CSV files only!')
    ])
    default_class_id = SelectField('Default Class (Optional fallback)', coerce=int, validators=[Optional()])
    submit = SubmitField('Upload and Import')

    def __init__(self, *args, **kwargs):
        super(CSVImportForm, self).__init__(*args, **kwargs)
        classes = [(0, '-- None (Match from CSV) --')] + [(c.id, c.name) for c in ClassRoom.query.filter_by(is_active=True).all()]
        self.default_class_id.choices = classes


class FaceEnrollmentForm(FlaskForm):
    biometric_consent = BooleanField('I explicitly agree to capture and store biometric face encodings for attendance verification.', validators=[DataRequired()])
    submit = SubmitField('Confirm and Enroll Faces')


class AttendanceOverrideForm(FlaskForm):
    status = SelectField('New Status', choices=[
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late'),
        ('Excused', 'Excused')
    ], validators=[DataRequired()])
    reason = TextAreaField('Reason for Override', validators=[DataRequired(), Length(min=5, max=500)])
    submit = SubmitField('Apply Override')


class SettingsForm(FlaskForm):
    attendance_threshold = FloatField('Minimum Attendance Threshold (%)', validators=[DataRequired(), NumberRange(min=1, max=100)])
    face_distance_threshold = FloatField('Face Distance Threshold (Lower is stricter, Default 0.50)', validators=[DataRequired(), NumberRange(min=0.1, max=1.0)])
    min_session_length = IntegerField('Minimum Session Length (Minutes)', validators=[DataRequired(), NumberRange(min=5, max=180)])
    session_timeout_minutes = IntegerField('Session Auto-Expiration (Minutes)', validators=[DataRequired(), NumberRange(min=10, max=300)])
    late_threshold_minutes = IntegerField('Late Marking Threshold (Minutes)', validators=[DataRequired(), NumberRange(min=1, max=60)])
    submit = SubmitField('Save Settings')
