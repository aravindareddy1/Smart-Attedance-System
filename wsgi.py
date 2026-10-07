"""
Production WSGI Entrypoint for Smart Attendance System (Render / Gunicorn / PostgreSQL)
"""
import os
import logging
from app import create_app, db

env_name = os.getenv('FLASK_ENV', 'production')
app = create_app(env_name)

# Auto-initialize database tables and demo seed data on cloud startup
with app.app_context():
    try:
        db.create_all()
        from app.models import User
        if not User.query.filter_by(role='admin').first():
            app.logger.info("Initializing production database with initial seed data...")
            from seed import run_seed
            run_seed()
    except Exception as e:
        app.logger.warning(f"Database auto-setup notice: {e}")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
