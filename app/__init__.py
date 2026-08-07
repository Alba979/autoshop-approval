import logging
import os

from flask import Flask

from config import CONFIG_BY_NAME
from app.extensions import db, migrate, login_manager, scheduler


def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True)

    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app.config.from_object(CONFIG_BY_NAME[config_name])

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app.models.user import StaffUser

    @login_manager.user_loader
    def load_user(user_id):
        return StaffUser.query.get(int(user_id))

    from app.routes.staff import staff_bp
    from app.routes.customer import customer_bp
    from app.routes.api import api_bp
    from app.routes.analytics import analytics_bp

    app.register_blueprint(staff_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(analytics_bp)

    from app.utils.filters import register_filters

    register_filters(app)

    if app.config.get("SCHEDULER_ENABLED") and not app.config.get("TESTING"):
        from app.services.scheduler_jobs import register_jobs

        register_jobs(app, scheduler)
        if not scheduler.running:
            scheduler.start()

    if not app.debug:
        logging.basicConfig(level=logging.INFO)

    @app.cli.command("init-db")
    def init_db_command():
        """Create all tables (no sample data). Use seed-db instead for a
        fully populated demo/dev database."""
        db.create_all()
        print("Database tables created.")

    @app.cli.command("seed-db")
    def seed_db_command():
        """Wipe and reseed the database with realistic sample data."""
        from scripts.seed_data import run_seed

        run_seed()

    @app.shell_context_processor
    def make_shell_context():
        from app.models.customer import Customer
        from app.models.vehicle import Vehicle
        from app.models.job import RepairJob
        from app.models.estimate import Estimate, EstimateLineItem
        from app.models.approval import ApprovalRequest
        from app.models.technician import Technician
        from app.models.diagnostic import DiagnosticFinding, DiagnosticPhoto

        return dict(
            db=db,
            Customer=Customer,
            Vehicle=Vehicle,
            RepairJob=RepairJob,
            Estimate=Estimate,
            EstimateLineItem=EstimateLineItem,
            ApprovalRequest=ApprovalRequest,
            Technician=Technician,
            DiagnosticFinding=DiagnosticFinding,
            DiagnosticPhoto=DiagnosticPhoto,
        )

    return app
