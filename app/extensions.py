"""Shared extension instances, created here to avoid circular imports."""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from apscheduler.schedulers.background import BackgroundScheduler

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "staff.login"
login_manager.login_message_category = "warning"

scheduler = BackgroundScheduler(daemon=True)
