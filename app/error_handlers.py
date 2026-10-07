import logging
from flask import render_template, request, jsonify

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    
    def wants_json():
        return (
            request.is_json
            or request.path.startswith('/api/')
            or request.accept_mimetypes.accept_json > request.accept_mimetypes.accept_html
        )

    @app.errorhandler(400)
    def bad_request(error):
        if wants_json():
            return jsonify({'success': False, 'message': 'Bad Request: ' + str(getattr(error, 'description', 'Invalid request'))}), 400
        return render_template('errors/400.html', error=error), 400

    @app.errorhandler(401)
    def unauthorized(error):
        if wants_json():
            return jsonify({'success': False, 'message': 'Unauthorized. Please log in.'}), 401
        return render_template('errors/401.html', error=error), 401

    @app.errorhandler(403)
    def forbidden(error):
        if wants_json():
            return jsonify({'success': False, 'message': 'Forbidden: You do not have permission to access this resource.'}), 403
        return render_template('errors/403.html', error=error), 403

    @app.errorhandler(404)
    def page_not_found(error):
        if wants_json():
            return jsonify({'success': False, 'message': 'Resource not found.'}), 404
        return render_template('errors/404.html', error=error), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        if wants_json():
            return jsonify({'success': False, 'message': 'Method not allowed.'}), 405
        return render_template('errors/405.html', error=error), 405

    @app.errorhandler(413)
    def request_entity_too_large(error):
        if wants_json():
            return jsonify({'success': False, 'message': 'Uploaded file is too large. Maximum size is 5MB.'}), 413
        return render_template('errors/413.html', error=error), 413

    @app.errorhandler(422)
    def unprocessable_entity(error):
        if wants_json():
            return jsonify({'success': False, 'message': 'Unprocessable Entity: Validation failed.'}), 422
        return render_template('errors/422.html', error=error), 422

    @app.errorhandler(429)
    def ratelimit_handler(error):
        if wants_json():
            return jsonify({'success': False, 'message': 'Too many requests. Please slow down.'}), 429
        return render_template('errors/429.html', error=error), 429

    @app.errorhandler(500)
    def internal_server_error(error):
        logger.error(f"Internal Server Error on {request.path}: {str(error)}", exc_info=True)
        if wants_json():
            return jsonify({'success': False, 'message': 'An internal server error occurred. Please contact support.'}), 500
        return render_template('errors/500.html', error=error), 500
