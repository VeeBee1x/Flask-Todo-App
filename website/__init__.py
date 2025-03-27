from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from os import environ
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

db = SQLAlchemy()
DB_NAME = "database.db"
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app():
    app = Flask(__name__)
    
    # Get DATABASE_URL from environment or use SQLite as fallback
    DATABASE_URL = environ.get('DATABASE_URL', f'sqlite:///{DB_NAME}')
    
    # Fix Postgres URL format if needed
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    app.config['SECRET_KEY'] = environ.get('SECRET_KEY', 'your-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # Register blueprints
    from .views import views
    from .auth import auth
    
    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    
    # Create database
    from .models import User, Todo
    with app.app_context():
        db.create_all()
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))
    
    return app