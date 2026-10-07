import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from flask import Flask, jsonify
from flask_cors import CORS
from app.config import config
from app.extensions import db, migrate, login_manager, csrf
from app.error_handlers import register_error_handlers
from app.services.face_service import get_face_engine


def create_app(config_name: str = 'default') -> Flask:
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}, r"/attendance/api/*": {"origins": "*"}}, supports_credentials=True)
    app.config.from_object(config[config_name])

    # Ensure required data directories exist
    for dir_path in [app.config['DATA_DIR'], app.config['FACES_DIR'], 
                     app.config['EXPORTS_DIR'], app.config['BACKUPS_DIR'], 
                     app.config['LOGS_DIR']]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    # Configure structured logging
    log_file = Path(app.config['LOGS_DIR']) / 'smart_attendance.log'
    file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s (%(funcName)s:%(lineno)d): %(message)s'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("Smart Attendance System initializing...")

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Exclude live webcam frame API endpoint from CSRF validation (handled by session cookie & rate limiting)
    # Note: We can exempt specific API blueprints or paths if needed:
    # csrf.exempt(attendance_bp) or exempt route

    # Register Blueprints
    from app.auth import bp as auth_bp
    from app.admin import bp as admin_bp
    from app.attendance import bp as attendance_bp
    from app.reports import bp as reports_bp
    from app.analytics import bp as analytics_bp
    from app.student import bp as student_bp

    # Exempt internal live camera frame API and enroll frame API from CSRF form token requirement
    csrf.exempt(attendance_bp)
    csrf.exempt(analytics_bp)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(student_bp)

    # Register error handlers
    register_error_handlers(app)

    # Health check endpoint
    @app.route('/health')
    def health_check():
        db_status = "ok"
        try:
            db.session.execute(db.text('SELECT 1'))
        except Exception as e:
            db_status = f"degraded: {str(e)}"

        engine = get_face_engine()
        return jsonify({
            'status': 'ok' if db_status == 'ok' else 'degraded',
            'database': db_status,
            'face_engine': engine.engine_name,
            'version': app.config.get('APP_VERSION', '1.0.0')
        })

    # Global context processor
    @app.context_processor
    def inject_globals():
        return {
            'app_version': app.config.get('APP_VERSION', '1.0.0'),
            'app_name': 'Smart Attendance System'
        }

    engine = get_face_engine(app.config.get('FACE_ENGINE', 'auto'))
    app.logger.info(f"Active Face Recognition Engine: {engine.engine_name}")

    return app


