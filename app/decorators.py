from functools import wraps
from flask import flash, redirect, url_for, request, jsonify, abort
from flask_login import current_user


def admin_required(f):
    """Restricts access to Admin users only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Authentication required.'}), 401
            flash('Please log in as an administrator to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if not current_user.is_admin:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Administrator access required.'}), 403
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def teacher_required(f):
    """Restricts access to Teacher or Admin users."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Authentication required.'}), 401
            flash('Please log in as a teacher or administrator to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if not (current_user.is_teacher or current_user.is_admin):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Teacher access required.'}), 403
            flash('Access denied. Teacher privileges required.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def student_required(f):
    """Restricts access to Student users only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Authentication required.'}), 401
            flash('Please log in as a student to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if not current_user.is_student:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Student access required.'}), 403
            flash('Access denied. Student portal only.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def roles_required(*roles):
    """Restricts access to users matching one of the specified roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'success': False, 'message': 'Authentication required.'}), 401
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            if current_user.role not in roles and not current_user.is_admin:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'success': False, 'message': 'Insufficient permissions.'}), 403
                flash('Access denied. Insufficient permissions.', 'danger')
                return redirect(url_for('auth.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
