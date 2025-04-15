# file: app/__init__.py
from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt # Using Flask-Bcrypt wrapper

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login' # Route function name for login page
login_manager.login_message_category = 'info' # Flash message category
bcrypt = Bcrypt()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    # Register Blueprints (routes)
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp) # Main routes, no prefix needed usually

    from app.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from app.routes.scanning import bp as scanning_bp
    app.register_blueprint(scanning_bp, url_prefix='/scan')

    from app.routes.reports import bp as reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')

    # Create database tables if they don't exist (useful for initial setup/simple cases)
    # For production/complex changes, use Flask-Migrate: flask db init, flask db migrate, flask db upgrade
    with app.app_context():
        # db.create_all() # Uncomment for simple setup, but prefer migrations
        pass # Migrations are preferred

    return app

# Import models at the bottom to avoid circular imports with blueprints
from app import models