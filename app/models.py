from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager


def utc_now():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student', index=True)  # admin, teacher, student
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_default_password = db.Column(db.Boolean, default=False, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    student_profile = db.relationship('Student', back_populates='user', uselist=False)
    taught_subjects = db.relationship('Subject', back_populates='teacher', lazy='dynamic')
    conducted_sessions = db.relationship('AttendanceSession', back_populates='teacher', lazy='dynamic')
    timetable_entries = db.relationship('Timetable', back_populates='teacher', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', back_populates='user', lazy='dynamic')
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'

    @property
    def is_teacher(self) -> bool:
        return self.role == 'teacher'

    @property
    def is_student(self) -> bool:
        return self.role == 'student'

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class ClassRoom(db.Model):
    __tablename__ = 'classrooms'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    department = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(10), nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    students = db.relationship('Student', back_populates='classroom', lazy='dynamic')
    subjects = db.relationship('Subject', back_populates='classroom', lazy='dynamic')
    sessions = db.relationship('AttendanceSession', back_populates='classroom', lazy='dynamic')
    timetable_entries = db.relationship('Timetable', back_populates='classroom', lazy='dynamic')

    def __repr__(self):
        return f"<ClassRoom {self.name} ({self.department})>"


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    department = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(10), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, unique=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    face_enrolled = db.Column(db.Boolean, default=False, nullable=False)
    biometric_consent = db.Column(db.Boolean, default=False, nullable=False)
    biometric_consent_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    classroom = db.relationship('ClassRoom', back_populates='students')
    user = db.relationship('User', back_populates='student_profile')
    face_encodings = db.relationship('FaceEncoding', back_populates='student', cascade='all, delete-orphan', lazy='dynamic')
    attendance_records = db.relationship('AttendanceRecord', back_populates='student', lazy='dynamic')
    notifications = db.relationship('Notification', back_populates='student', lazy='dynamic')

    def __repr__(self):
        return f"<Student {self.roll_no} - {self.name}>"


class FaceEncoding(db.Model):
    __tablename__ = 'face_encodings'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False, index=True)
    encoding = db.Column(db.Text, nullable=False)  # JSON-encoded list of floats or serialized base64
    image_path = db.Column(db.String(255), nullable=True)
    quality_score = db.Column(db.Float, default=1.0, nullable=False)
    engine = db.Column(db.String(20), default='lbph', nullable=False)  # 'dlib', 'lbph'
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    student = db.relationship('Student', back_populates='face_encodings')

    def __repr__(self):
        return f"<FaceEncoding student_id={self.student_id} engine={self.engine}>"


class Subject(db.Model):
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    classroom = db.relationship('ClassRoom', back_populates='subjects')
    teacher = db.relationship('User', back_populates='taught_subjects')
    sessions = db.relationship('AttendanceSession', back_populates='subject', lazy='dynamic')
    timetable_entries = db.relationship('Timetable', back_populates='subject', lazy='dynamic')

    def __repr__(self):
        return f"<Subject {self.code} - {self.name}>"


class AttendanceSession(db.Model):
    __tablename__ = 'attendance_sessions'

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    period = db.Column(db.Integer, nullable=False)
    session_name = db.Column(db.String(100), nullable=False)
    started_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, default=60, nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False, index=True)  # scheduled, active, ended, cancelled
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    classroom = db.relationship('ClassRoom', back_populates='sessions')
    subject = db.relationship('Subject', back_populates='sessions')
    teacher = db.relationship('User', back_populates='conducted_sessions')
    records = db.relationship('AttendanceRecord', back_populates='session', cascade='all, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return f"<AttendanceSession {self.id} {self.session_name} ({self.status})>"


class AttendanceRecord(db.Model):
    __tablename__ = 'attendance_records'
    __table_args__ = (
        db.UniqueConstraint('session_id', 'student_id', name='uq_session_student'),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('attendance_sessions.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='Present', index=True)  # Present, Absent, Late, Excused
    marked_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    method = db.Column(db.String(20), nullable=False, default='face')  # face, manual, override, system
    confidence = db.Column(db.Float, nullable=True)
    note = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    session = db.relationship('AttendanceSession', back_populates='records')
    student = db.relationship('Student', back_populates='attendance_records')
    adjustments = db.relationship('AttendanceAdjustment', back_populates='record', cascade='all, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return f"<AttendanceRecord session={self.session_id} student={self.student_id} status={self.status}>"


class AttendanceAdjustment(db.Model):
    __tablename__ = 'attendance_adjustments'

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey('attendance_records.id'), nullable=False, index=True)
    previous_status = db.Column(db.String(20), nullable=False)
    new_status = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    adjusted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    record = db.relationship('AttendanceRecord', back_populates='adjustments')
    adjusted_by = db.relationship('User')

    def __repr__(self):
        return f"<AttendanceAdjustment record={self.record_id} {self.previous_status}->{self.new_status}>"


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    # Relationships
    user = db.relationship('User', back_populates='audit_logs')

    def __repr__(self):
        return f"<AuditLog {self.action} on {self.entity_type}:{self.entity_id}>"


class Setting(db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def __repr__(self):
        return f"<Setting {self.key}={self.value}>"


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    type = db.Column(db.String(50), default='info', nullable=False)  # info, warning, success, shortage, password
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    # Relationships
    student = db.relationship('Student', back_populates='notifications')
    user = db.relationship('User', back_populates='notifications')

    def __repr__(self):
        return f"<Notification {self.title}>"


class Holiday(db.Model):
    __tablename__ = 'holidays'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<Holiday {self.date}: {self.name}>"


class Timetable(db.Model):
    __tablename__ = 'timetables'

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    weekday = db.Column(db.Integer, nullable=False, index=True)  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    period = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    room = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    classroom = db.relationship('ClassRoom', back_populates='timetable_entries')
    subject = db.relationship('Subject', back_populates='timetable_entries')
    teacher = db.relationship('User', back_populates='timetable_entries')

    def __repr__(self):
        return f"<Timetable class={self.class_id} sub={self.subject_id} day={self.weekday} p={self.period}>"
