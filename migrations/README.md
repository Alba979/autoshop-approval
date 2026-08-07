# Migrations

This folder is intentionally empty in the repository - Flask-Migrate
(Alembic) generates its `env.py` and version scripts here the first time you
run:

```bash
flask --app wsgi.py db init
flask --app wsgi.py db migrate -m "initial schema"
flask --app wsgi.py db upgrade
```

For local development and demos, you don't need migrations at all - `flask
--app wsgi.py init-db` (or `seed-db`) calls `db.create_all()` directly. Reach
for real migrations once you have a production database with data you can't
just recreate.
