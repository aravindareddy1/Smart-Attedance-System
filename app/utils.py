import json
from datetime import datetime, timezone
from flask import request
from flask_login import current_user
from app.extensions import db
from app.models import AuditLog, Setting, Notification


def get_client_ip() -> str:
    """Extract client IP address from request headers."""
    if request:
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        return request.remote_addr or '127.0.0.1'
    return '127.0.0.1'


def log_audit(action: str, entity_type: str, entity_id: int = None, details: dict | str = None, user_id: int = None):
    """Create an audit log record safely."""
    try:
        active_user_id = user_id
        if active_user_id is None and current_user and current_user.is_authenticated:
            active_user_id = current_user.id
            
        details_str = json.dumps(details) if isinstance(details, (dict, list)) else (str(details) if details else None)
        
        audit_entry = AuditLog(
            user_id=active_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details_str,
            ip_address=get_client_ip(),
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(audit_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Non-fatal audit logging error


def get_setting(key: str, default: str = None) -> str:
    """Retrieve application setting value from database or fallback to default."""
    try:
        setting = Setting.query.filter_by(key=key).first()
        if setting:
            return setting.value
    except Exception:
        pass
    return default


def set_setting(key: str, value: str, description: str = None):
    """Create or update application setting in database."""
    try:
        setting = Setting.query.filter_by(key=key).first()
        if not setting:
            setting = Setting(key=key, value=str(value), description=description)
            db.session.add(setting)
        else:
            setting.value = str(value)
            if description:
                setting.description = description
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def create_notification(title: str, message: str, type: str = 'info', student_id: int = None, user_id: int = None):
    """Create a notification in the database."""
    try:
        notif = Notification(
            title=title,
            message=message,
            type=type,
            student_id=student_id,
            user_id=user_id,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(notif)
        db.session.commit()
    except Exception:
        db.session.rollback()


def calculate_attendance_percentage(present_count: int, late_count: int, total_eligible_sessions: int) -> float:
    """
    Standard percentage calculation:
    Attendance Percentage = (Present + Late) / (Eligible Sessions) * 100
    """
    if total_eligible_sessions <= 0:
        return 0.0
    percentage = ((present_count + late_count) / float(total_eligible_sessions)) * 100.0
    return round(min(100.0, max(0.0, percentage)), 2)


def calculate_required_future_classes(present_late_count: int, total_sessions: int, target_percentage: float = 75.0) -> int:
    """
    Calculate how many consecutive upcoming classes a student must attend to reach target percentage.
    Formula: (present_late + x) / (total_sessions + x) >= target_percentage / 100
    x * (1 - p) >= p * total_sessions - present_late
    x >= (p * total_sessions - present_late) / (1 - p)
    """
    if target_percentage >= 100.0:
        return -1  # Mathematically impossible if already missed a single class
    p = target_percentage / 100.0
    current_percentage = (present_late_count / total_sessions * 100.0) if total_sessions > 0 else 0.0
    if current_percentage >= target_percentage:
        return 0
    
    needed = (p * total_sessions - present_late_count) / (1.0 - p)
    import math
    return max(0, math.ceil(needed))
