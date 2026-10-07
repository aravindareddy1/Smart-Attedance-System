"""
Production WSGI Entrypoint for Smart Attendance System (Gunicorn / Render / Docker)
"""
import os
from app import create_app

env_name = os.getenv('FLASK_ENV', 'production')
app = create_app(env_name)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
