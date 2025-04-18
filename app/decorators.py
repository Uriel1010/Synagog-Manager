# File: app/decorators.py
from functools import wraps
from flask import flash, redirect, url_for, request, jsonify, current_app
from flask_login import login_required, current_user

# --- Admin check for web sessions ---
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

# --- NEW: API Key check decorator ---
def api_key_required(f):
    @wraps(f)
    def decorated_api_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') # Check for a custom header
        expected_key = current_app.config.get('ADMIN_API_KEY')

        # Check if ADMIN_API_KEY is configured and matches the request
        if not expected_key:
             current_app.logger.error("ADMIN_API_KEY is not configured in the application.")
             return jsonify({"error": "API access is not configured on the server."}), 500 # Internal Server Error

        if not api_key or api_key != expected_key:
            current_app.logger.warning(f"API Key missing or invalid. Provided: '{api_key}'")
            return jsonify({"error": "Unauthorized: Invalid or missing API Key"}), 401 # Unauthorized

        # Key is valid, proceed with the decorated function
        return f(*args, **kwargs)
    return decorated_api_function

# You could add other decorators here later