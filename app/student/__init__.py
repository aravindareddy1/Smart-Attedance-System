from flask import Blueprint

bp = Blueprint('student', __name__, url_prefix='/student')

from app.student import routes
