MAUA SACCO
=================================

All-in-one bus booking and parcel management system built with Flask. It provides:

- Passenger trip discovery, booking, seat selection, and payments
- Parcel creation, tracking, assignment to vehicles, and delivery updates
- Admin and staff dashboards for managing routes, vehicles, trips, bookings, and parcels
- M-Pesa STK integration and SMS/email notifications


Quick start
-----------

Prerequisites:

- Python 3.13 (or 3.10+)
- PostgreSQL 13+
- Git (optional)

1) Clone and set up environment

```bash
python -m venv venv
venv\Scripts\activate  # Windows PowerShell
pip install -r requirements.txt
copy env_template.txt .env
```

2) Configure database

- Create a PostgreSQL database `maua-db` and update `DATABASE_URL` in `.env` if needed.

3) Initialize database and seed admin

```bash
set FLASK_APP=app.py
flask db upgrade
python scripts/create_admin.py
```

4) Run the app

```bash
python app.py
# or
flask run --host=0.0.0.0 --port=5000
```

The app will be available at http://localhost:5000


Project structure
-----------------

```
maua_sacco/
  app.py                # Entry point (loads factory from maua/__init__.py)
  config.py             # Config classes (Dev/Testing/Prod)
  manage.py             # Optional CLI helpers
  migrations/           # Alembic migrations
  scripts/create_admin.py
  maua/
    __init__.py         # Flask app factory, blueprint registration
    extensions.py       # db, login_manager, migrate, bcrypt, etc.
    admin/              # Admin models + routes
    auth/               # User auth (forms/models/routes)
    booking/            # Booking forms/models/routes/services
    catalog/            # Public catalog (routes, trips, vehicles)
    main/               # Home, health check, static pages
    notifications/      # SMS integration
    parcels/            # Parcel forms/models/routes
    payment/            # Payment models, M-Pesa integration
    staff/              # Staff dashboard and operations
    static/             # CSS, JS, uploads
    templates/          # Jinja2 templates (admin, staff, booking, parcels, etc.)
```


Key features
------------

- Authentication (register/login) with Flask-Login + Bcrypt
- Catalog of routes, trips, and vehicles
- Booking flow: select trip → seats → passenger details → payment
- Parcel flow: create → assign vehicle/driver → track → deliver
- Staff tools: manage trips, bookings, parcels, vehicles, customers
- PDF export of completed trips for record-keeping
- SMS notifications for bookings and parcels
- M-Pesa STK push payments integration


Configuration
-------------

- Copy `env_template.txt` to `.env` and set values.
- The application reads config via `config.py` and the app factory in `maua/__init__.py`.
- Important variables:
  - `DATABASE_URL` (PostgreSQL)
  - `SECRET_KEY`
  - `BASE_URL`
  - M-Pesa: `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET`, `MPESA_BUSINESS_SHORT_CODE`, `MPESA_PASSKEY`, `MPESA_ENVIRONMENT`
  - Mail: `MAIL_*` settings (used for notifications)


Development workflow
--------------------

- Create and activate a virtualenv and install dependencies
- Apply migrations with `flask db upgrade`
- Run locally with `python app.py`
- Use `pytest` to run tests in `tests/`

```bash
pytest -q
```


Blueprints and modules (high level)
-----------------------------------

- `auth`: authentication routes, forms, user model
- `catalog`: read-only browsing of routes and trips
- `booking`: booking flow, seat map, payment state
- `parcels`: parcel CRUD, tracking, payments, receipts
- `payment`: M-Pesa integration, payment models and callbacks
- `admin`: CRUD for depots, routes, vehicles, settings
- `staff`: staff console to manage trips, bookings, parcels
- `main`: landing pages and health check


Database and migrations
-----------------------

- SQLAlchemy models reside under `maua/*/models.py`
- Alembic migrations live in `migrations/versions/`
- Common commands:

```bash
flask db migrate -m "change summary"
flask db upgrade
flask db downgrade
```


Payments and notifications
--------------------------

- M-Pesa credentials are read from environment variables
- SMS sending is abstracted under `maua/notifications/sms.py`
- Payment flows and callbacks live under `maua/payment/`


Deployment
----------

- Example process files: `Procfile`, `gunicorn.conf.py`, `render.yaml`, `runtime.txt`
- For production, run via Gunicorn WSGI using `wsgi.py`

```bash
gunicorn -c gunicorn.conf.py wsgi:app
```


Documentation
-------------

- See `docs/ARCHITECTURE.md` for module, model, and flow details
- See `docs/API.md` for key endpoints and payloads
- See `docs/DEPLOYMENT.md` for local and production deployment steps
- See `MPESA_SETUP_GUIDE.md` for Daraja setup


Security notes
--------------

- Do not commit real secrets. Use `.env` locally and provider secrets in production
- Rotate credentials regularly and use per-environment config


License
-------

Proprietary — internal use for MAUA SACCO unless otherwise agreed.


