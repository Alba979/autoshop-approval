# Deployment Notes

This app is intentionally simple to operate: one process, SQLite by
default, photos on local disk. That's a reasonable production setup for a
single-location shop. This doc covers running it that way with Docker, and
what to change as the shop grows.

## 1. Running with Docker (single server)

```bash
cp .env.example .env
# edit .env: set SECRET_KEY, PUBLIC_BASE_URL, SHOP_NAME, SHOP_PHONE,
# and Twilio credentials if you're sending real texts.

docker compose build
docker compose run --rm web flask --app wsgi.py init-db
docker compose up -d
```

The `shop_data` named volume (see `docker-compose.yml`) holds
`instance/shop.db` (SQLite) and `instance/uploads/diagnostic_photos/` - back
this volume up regularly (see §4).

Put this behind a reverse proxy (Caddy, nginx, or your host's built-in TLS
termination) so customers hit `https://` links from their texts. Whatever
that public hostname is, set it as `PUBLIC_BASE_URL` in `.env`.

## 2. Environment variables that matter in production

| Variable | Notes |
|---|---|
| `SECRET_KEY` | Generate a long random value (`python -c "import secrets; print(secrets.token_hex(32))"`). Approval links are cryptographically signed with this - rotating it invalidates all outstanding approval links. |
| `PUBLIC_BASE_URL` | Must be the externally reachable HTTPS URL customers' phones can open. |
| `SMS_PROVIDER=twilio` | Plus `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`. |
| `WAITING_ON_CUSTOMER_TIMEOUT_HOURS` | How long before an unanswered estimate auto-expires. |
| `APPROVAL_LINK_TTL_HOURS` | How long the approve/decline link itself stays valid. Should be >= the timeout above. |

## 3. Moving diagnostic photos to S3

Local disk is fine for one shop location. If you want offsite redundancy
(or run more than one app instance), set:

```
PHOTO_STORAGE_BACKEND=s3
S3_BUCKET_NAME=your-bucket
AWS_REGION=us-east-1
```

and provide AWS credentials the normal way (environment variables, an
attached IAM role, etc. - `boto3` picks these up automatically). Add
`boto3` to `requirements.txt` when you do this; it's left out by default to
keep the base install lean for shops that don't need it.

Note: photos already saved locally are **not** automatically migrated when
you flip this switch - write a one-off script to walk existing
`DiagnosticPhoto` rows with `storage_backend="local"` and upload them, then
update the rows, if you switch backends after going live.

## 4. Backups

Whatever you do, back up two things on a schedule:

1. `instance/shop.db` (or your Postgres database, see §5)
2. `instance/uploads/diagnostic_photos/`

These are your warranty-dispute evidence - treat them like financial
records, not like disposable cache.

## 5. Growing past SQLite

SQLite comfortably handles a single shop's write volume. If you open a
second location sharing one system, or want managed backups/HA, switch to
Postgres:

1. Provision a Postgres instance.
2. Set `DATABASE_URL=postgresql://user:pass@host:5432/dbname`.
3. Run `flask --app wsgi.py db init && flask --app wsgi.py db migrate -m "initial" && flask --app wsgi.py db upgrade` against the new database (or just `init-db` for a fresh one with no history to preserve).
4. If migrating existing data, dump/restore or write a one-off ETL script -
   don't try to copy the raw SQLite file into Postgres.

All the datetime columns in this codebase are naive UTC (see the comment in
`app/models/base.py`) specifically so this migration doesn't require
touching every timestamp - Postgres stores naive UTC just as consistently
as SQLite does, and you can move to timezone-aware columns later at your
convenience.

## 6. Running the timeout sweep at scale

The "waiting on customer" expiry check runs inside the web process via
APScheduler on a 15-minute interval (`app/services/scheduler_jobs.py`).
That's correct for one process. If you ever run multiple web replicas
behind a load balancer, either:

- Set `SCHEDULER_ENABLED=false` (via `Config.SCHEDULER_ENABLED`, currently
  read from code defaults - expose it as an env var if you need this) on
  all but one replica, or
- Move the sweep to a separate scheduled job (cron, a lightweight worker,
  your platform's scheduled-task feature) that calls
  `app.services.approval_workflow.expire_stale_waiting_jobs()` directly.

Either avoids the same job firing once per replica.
