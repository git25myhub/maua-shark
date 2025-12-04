Deployment Guide
================

This guide covers local, staging, and production deployment for MAUA SACCO.


Local development
-----------------

1) Set up Python and dependencies

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

2) Configure environment

```bash
copy env_template.txt .env
# Edit .env with DATABASE_URL, M-Pesa, and Mail credentials
```

3) Initialize database

```bash
flask db upgrade
python scripts/create_admin.py
```

4) Run server

```bash
python app.py
```


Production (Gunicorn)
---------------------

1) Set environment variables (never commit secrets). Required:

- `DATABASE_URL`
- `SECRET_KEY`
- `BASE_URL`
- `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET`, `MPESA_BUSINESS_SHORT_CODE`, `MPESA_PASSKEY`, `MPESA_ENVIRONMENT`
- `MAIL_*` settings

2) Run migrations

```bash
flask db upgrade
```

3) Start via Gunicorn

```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

4) Reverse proxy with Nginx (example)

- Proxy `location /` to `http://127.0.0.1:8000`
- Serve static files at `/static` from the project `maua/static` directory or let Flask serve them


Render.com deployment
---------------------

- `render.yaml` describes a web service with build and start commands
- Ensure environment variables are set in the Render dashboard
- Typical start: `gunicorn -c gunicorn.conf.py wsgi:app`


Database migrations CI hint
---------------------------

- On deploy hook, run `flask db upgrade`
- Maintain migration scripts in `migrations/versions`


Monitoring and health
---------------------

- Health endpoint: `GET /health`
- Optional HEAD on `/staff/parcels/<id>/tracking` returns 200 and can be used for monitors


Security and operations
-----------------------

- Use per-environment secrets; rotate regularly
- Configure TLS termination at the reverse proxy or platform edge
- Set `ProductionConfig` to enforce secure cookies and logging to stdout/stderr


