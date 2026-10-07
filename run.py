import os
from app import create_app, db
from app.models import User, Student, ClassRoom, Subject, AttendanceSession, AttendanceRecord

env = os.getenv('FLASK_ENV', 'development')
app = create_app(env)


@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Student': Student,
        'ClassRoom': ClassRoom,
        'Subject': Subject,
        'AttendanceSession': AttendanceSession,
        'AttendanceRecord': AttendanceRecord
    }


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', True))
