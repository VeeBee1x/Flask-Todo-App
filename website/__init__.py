from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from os import environ
import pytz


db = SQLAlchemy()
DB_NAME = "database.db"
login_manager = LoginManager()
login_manager.login_view = 'auth.login'


def create_app():
    app = Flask(__name__)
    
    DATABASE_URL = environ.get('DATABASE_URL', f'sqlite:///{DB_NAME}')
    
    app.config['SECRET_KEY'] = environ.get('SECRET_KEY', 'your-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
    
    # Starta databasen och inloggningshanteraren
    db.init_app(app)
    login_manager.init_app(app)
    
    # Registrera sidor och autentisering
    from .views import views
    from .auth import auth
    
    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    
    # Skapa databasen om den inte finns
    from .models import User, Todo
    with app.app_context():
        db.create_all()
    
    # Ladda användaren
    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))
    

    @app.template_filter('localtime')
    def localtime_filter(utc_dt):
        local_tz = pytz.timezone('Europe/Stockholm')  # Byter till svensk tid
        return utc_dt.replace(tzinfo=pytz.utc).astimezone(local_tz).strftime('%Y-%m-%d %H:%M')
    return app