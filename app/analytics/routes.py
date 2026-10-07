from datetime import datetime, date
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.analytics import bp
from app.decorators import teacher_required
from app.models import ClassRoom, Subject
from app.services.analytics_service import (
    get_analytics_summary, get_trend_analytics, get_classwise_analytics,
    get_subjectwise_analytics, get_heatmap_analytics,
    get_top_absent_analytics, get_attendance_distribution
)


@bp.route('/dashboard')
@teacher_required
def dashboard():
    classes = ClassRoom.query.filter_by(is_active=True).all()
    subjects = Subject.query.filter_by(is_active=True).all()
    return render_template('analytics/dashboard.html', classes=classes, subjects=subjects)


@bp.route('/api/summary')
@teacher_required
def api_summary():
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    class_id = request.args.get('class_id', type=int)
    subject_id = request.args.get('subject_id', type=int)

    d_from = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else None
    d_to = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else None

    data = get_analytics_summary(date_from=d_from, date_to=d_to, class_id=class_id, subject_id=subject_id)
    return jsonify(data)


@bp.route('/api/trend')
@teacher_required
def api_trend():
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    class_id = request.args.get('class_id', type=int)
    subject_id = request.args.get('subject_id', type=int)

    d_from = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else None
    d_to = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else None

    data = get_trend_analytics(date_from=d_from, date_to=d_to, class_id=class_id, subject_id=subject_id)
    return jsonify(data)


@bp.route('/api/classwise')
@teacher_required
def api_classwise():
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    d_from = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else None
    d_to = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else None

    data = get_classwise_analytics(date_from=d_from, date_to=d_to)
    return jsonify(data)


@bp.route('/api/subjectwise')
@teacher_required
def api_subjectwise():
    class_id = request.args.get('class_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    d_from = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else None
    d_to = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else None

    data = get_subjectwise_analytics(class_id=class_id, date_from=d_from, date_to=d_to)
    return jsonify(data)


@bp.route('/api/heatmap')
@teacher_required
def api_heatmap():
    class_id = request.args.get('class_id', type=int)
    data = get_heatmap_analytics(class_id=class_id)
    return jsonify(data)


@bp.route('/api/top-absent')
@teacher_required
def api_top_absent():
    class_id = request.args.get('class_id', type=int)
    limit = request.args.get('limit', 10, type=int)
    data = get_top_absent_analytics(limit=limit, class_id=class_id)
    return jsonify(data)


@bp.route('/api/distribution')
@teacher_required
def api_distribution():
    class_id = request.args.get('class_id', type=int)
    data = get_attendance_distribution(class_id=class_id)
    return jsonify(data)
