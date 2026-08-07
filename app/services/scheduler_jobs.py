"""
Registers periodic background jobs.

Only one job today: sweep for repair orders that have been sitting in
WAITING_ON_CUSTOMER longer than the shop's configured timeout and move them
to EXPIRED. Runs inside the same process via APScheduler, which is fine for
a single-shop deployment; if you ever run multiple app instances behind a
load balancer, move this to a proper cron/worker process instead so it
doesn't fire once per instance (see docs/DEPLOYMENT.md).
"""
import logging

logger = logging.getLogger("autoshop.scheduler")


def register_jobs(app, scheduler):
    from app.services.approval_workflow import expire_stale_waiting_jobs

    def sweep_expired_jobs():
        with app.app_context():
            expired_ids = expire_stale_waiting_jobs()
            if expired_ids:
                logger.info("Expired stale waiting-on-customer jobs: %s", expired_ids)

    scheduler.add_job(
        sweep_expired_jobs,
        trigger="interval",
        minutes=15,
        id="sweep_expired_waiting_jobs",
        replace_existing=True,
    )
