from datetime import datetime, timezone
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from app.auth import bp
from app.extensions import db
from app.models import User
from app.forms import LoginForm, ChangePasswordForm, ForgotPasswordForm
from app.utils import log_audit


@bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    return redirect(url_for('auth.login'))


@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin.dashboard'))
    elif current_user.is_teacher:
        return redirect(url_for('attendance.teacher_dashboard'))
    elif current_user.is_student:
        return redirect(url_for('student.dashboard'))
    return render_template('auth/profile.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data

        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            log_audit('LOGIN_FAILED', 'User', None, {'email': email})
            flash('Invalid email address or password. Please try again.', 'danger')
            return render_template('auth/login.html', form=form)

        if not user.is_active:
            log_audit('LOGIN_DEACTIVATED', 'User', user.id, {'email': email})
            flash('This account has been deactivated. Please contact the administrator.', 'danger')
            return render_template('auth/login.html', form=form)

        login_user(user, remember=form.remember_me.data)
        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()

        log_audit('LOGIN_SUCCESS', 'User', user.id, {'role': user.role})

        flash(f'Welcome back, {user.name}!', 'success')

        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('auth.dashboard')
        return redirect(next_page)

    return render_template('auth/login.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    user_id = current_user.id
    email = current_user.email
    logout_user()
    log_audit('LOGOUT', 'User', user_id, {'email': email})
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Incorrect current password.', 'danger')
            return render_template('auth/change_password.html', form=form)

        current_user.set_password(form.new_password.data)
        current_user.is_default_password = False
        db.session.commit()

        log_audit('PASSWORD_CHANGE', 'User', current_user.id, {'action': 'self_password_update'})
        flash('Your password has been changed successfully.', 'success')
        return redirect(url_for('auth.dashboard'))

    return render_template('auth/change_password.html', form=form)


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        log_audit('FORGOT_PASSWORD_REQUEST', 'User', user.id if user else None, {'email': email})
        # Always display the same safe message regardless of whether user exists
        flash('If an account exists with that email, instructions have been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html', form=form)


@bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html', user=current_user)
