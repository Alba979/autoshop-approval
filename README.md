# Ridgeline Auto Repair - Diagnostic-to-Repair Approval Workflow

A small-shop web application that enforces one simple rule: **no repair work
starts until the customer has explicitly approved an itemized estimate** -
and every step along the way (diagnosis, photos, the text sent, the tap that
approved it) is timestamped and kept for warranty disputes.

Built for a single independent auto repair shop (one or a few bays, a
handful of technicians) that currently tracks approvals over phone calls and
sticky notes, and wants that turned into an auditable system without buying
into a full dealership-grade shop management suite.

## What it does

- **Technician logs diagnostic findings** per job - system/area, description,
  severity, and photos - directly against a repair order.
- **Parts/labor estimates** are built line-by-line (part or labor, qty, unit
  price) with tax computed automatically.
- **Spending cap enforcement**: every customer has a spending cap. Any
  estimate above that cap requires an explicit, fresh customer approval - a
  technician can't quietly reuse an old approval to cover a bigger number.
- **One-tap SMS approval**: sends the customer an itemized text with a
  signed, expiring link. They tap **Approve** or **Decline** - no login, no
  app to install.
- **"Waiting on customer" holds**: the job sits in a distinct status the
  moment the estimate goes out, and a background sweep automatically expires
  it if nobody responds within a configurable window (default 24h).
- **Permanent audit trail**: diagnostic photos, every status transition, and
  every approval request's sent/responded timestamps are retained
  indefinitely for warranty recordkeeping - nothing in that trail is ever
  overwritten, only appended to.
- **Analytics dashboard**: average approval turnaround time and
  estimate-to-final-cost variance, both broken down per technician, with
  charts.

## Tech stack

- Python 3.12, Flask, SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF
- SQLite by default (drop-in Postgres for a growing/multi-location shop)
- APScheduler for the in-process "waiting on customer" timeout sweep
- Twilio for SMS (a `console` provider is used out of the box so you can
  run everything locally without a Twilio account)
- Server-rendered Jinja templates + Bootstrap 5 (no build step, no Node)
- Chart.js for the analytics dashboard
- pytest for the test suite

This is intentionally a "boring", easy-to-operate stack for a small
business - no separate frontend build, no message queue, no k8s. A single
process handles the web app, the background sweep, and (via SQLite) the
database.

## Project structure

```
app/
  models/        SQLAlchemy models (Customer, Vehicle, RepairJob, Estimate,
                 ApprovalRequest, DiagnosticFinding/Photo, ...)
  routes/        Flask blueprints: staff.py (internal dashboard),
                 customer.py (public approve/decline pages), analytics.py,
                 api.py
  services/      Business logic: approval_workflow.py (the spending-cap /
                 send / respond / expire logic), sms.py, tokens.py,
                 photo_storage.py, analytics.py, scheduler_jobs.py
  templates/     Jinja templates (staff/, customer/)
  static/        CSS
  forms.py       Flask-WTF form definitions
scripts/
  seed_data.py   Realistic sample data (see below)
tests/           pytest suite covering the spending-cap and timeout logic
docs/
  DEPLOYMENT.md  Notes on going from SQLite/local-disk to Postgres/S3
config.py        Environment-driven configuration
wsgi.py          App entrypoint (flask run / gunicorn)
```

## Getting started (local development)

```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then edit values as needed

flask --app wsgi.py init-db        # create empty tables, OR:
flask --app wsgi.py seed-db        # create tables + realistic sample data (recommended)

flask --app wsgi.py run            # http://localhost:5000
```

With `SMS_PROVIDER=console` (the default), approval texts are printed to
the terminal log instead of sent - look for a line like:

```
[console-sms] to=+15555550103 body=Ridgeline Auto Repair: Estimate ready for your 2016 Honda Civic. ...
```

Copy the `/estimate/<token>` link from that log (or from the job detail page
in the dashboard) into a browser to try the customer-facing approve/decline
flow.

### Demo logins (after `seed-db`)

| Role            | Email                              | Password           |
|-----------------|-------------------------------------|---------------------|
| Owner           | owner@ridgelineauto.example         | ShopOwner!2026      |
| Service writer  | frontdesk@ridgelineauto.example     | FrontDesk!2026      |
| Technician      | marcus@ridgelineauto.example        | Technician!2026     |

The seed script also prints two ready-to-open customer approval links (one
under the customer's spending cap, one over it) so you can see both flows
immediately.

## Running tests

```bash
pytest
```

The test suite covers the parts of this system that most need to be
correct and are easiest to get subtly wrong:

- Spending-cap logic - including the "a prior higher approval still covers
  a smaller revised estimate" edge case, and its inverse.
- The send -> approve/decline workflow, including that a customer
  double-tapping (or reloading) a response link can't change their answer.
- One-tap link tokens - valid round-trip, tampering, and expiry.
- The "waiting on customer" timeout sweep.
- Analytics aggregation (turnaround time, cost variance).

## Sending real text messages

Set these in `.env` and switch `SMS_PROVIDER=twilio`:

```
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+1...
```

## Deploying

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for running this with Docker,
moving diagnostic photos to S3, and switching from SQLite to Postgres as the
shop grows. A `Dockerfile` and `docker-compose.yml` are included.

## Design notes / known limitations

- **Job numbering** (`RO-2026-0001`, ...) is generated by counting existing
  rows for the year. That's fine at small-shop volume; if you ever run
  multiple app instances writing concurrently, switch it to a DB sequence.
- **The background timeout sweep** runs inside the web process via
  APScheduler. That's the simplest thing that works for one shop on one
  server. If you scale to multiple app instances behind a load balancer,
  move the sweep to its own scheduled process so it doesn't fire once per
  instance (noted in `docs/DEPLOYMENT.md`).
- **Diagnostic photos** are stored on local disk by default and are never
  deleted by the application. For real disaster-recovery guarantees, switch
  `PHOTO_STORAGE_BACKEND=s3` (see `docs/DEPLOYMENT.md`).
- This project was built from scratch for this brief - it does not use or
  derive from any existing open-source shop-management codebase.

## License

MIT - see [`LICENSE`](LICENSE).
