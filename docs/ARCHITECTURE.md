Architecture Overview
=====================

This document explains the overall architecture, modules, data models, and key flows of the MAUA SACCO system.


Application core
----------------

- Flask application factory in `maua/__init__.py` initializes extensions and registers blueprints:
  - `db`, `migrate`, `login_manager`, `bcrypt`, `Mail`
  - Blueprints: `auth`, `main`, `health`, `booking`, `parcels`, `admin`, `payment`, `catalog`, `staff`


Modules and responsibilities
----------------------------

- `auth`
  - User model and authentication (register, login, session management)
  - Forms and validation using Flask-WTF and Email Validator

- `catalog`
  - Public browsing of `Route`, `Trip`, and `Vehicle`
  - Read-only, supports discovery of available trips

- `booking`
  - Models: `Booking` with passenger details, seat number, status, timestamps
  - Forms and services to select seats, capture passenger info, and update status
  - Integrates with `payment` for booking payments

- `parcels`
  - Models: `Parcel` with sender/receiver details, origin/destination, pricing and status
  - Create, list, track, and receipt views; integrates with payments

- `payment`
  - Models for transactions and payment status
  - M-Pesa STK push logic in `mpesa_service.py`; caching helpers in `cache.py`
  - Routes for initiating and receiving payment callbacks

- `admin`
  - CRUD over depots, routes, vehicles, and application settings
  - Views under `templates/admin` with layout `_layout.html`

- `staff`
  - Back-office operations: manage trips, bookings, parcels, vehicles, and customers
  - PDF export for completed trips and batch operations

- `main`
  - Home page, contact/help/legal pages, and health check blueprint

- `notifications`
  - SMS sending utilities (`sms.py`) used across staff operations and status updates


Key data models (high level)
----------------------------

- `Route` (in `catalog.models`): `code`, `origin`, `destination`
- `Vehicle` (in `catalog.models`): `plate_no`, `make`, `model`, `seat_layout`, `seat_count`
- `Trip` (in `catalog.models`): `route_id`, `vehicle_id`, `depart_at`, `base_fare`, `driver_name`, `driver_phone`, `status`
- `Booking` (in `booking.models`): `trip_id`, `user_id`, `seat_number`, `passenger_*`, `status`, `created_at`
- `Parcel` (in `parcels.models`): `ref_code`, `sender_*`, `receiver_*`, `origin_name`, `destination_name`, `amount`, `status`, `tracking_number`, `vehicle_plate`, `driver_phone`, `created_by`
- `Payment`/`Transaction` (in `payment.models`): fields for M-Pesa reference, status, amounts, timestamps


Important flows
---------------

Booking flow:
1. User browses routes and trips in `catalog`
2. Selects a trip and seat; submits passenger details
3. Payment initiated via `payment.routes` → M-Pesa STK
4. On callback success, booking status becomes `confirmed`
5. Staff can change status to `checked_in` and trip completion autocompletes bookings

Parcel flow:
1. Create parcel with sender/receiver and route details
2. Optional payment via M-Pesa
3. Staff assign vehicle/driver or tracking number; SMS updates sent
4. Status transitions: `pending` → `in_transit` → `delivered`

Staff operations:
- Manage trips (create, schedule, complete), bookings (status updates, check-in), vehicles (seat layout), customers (aggregate from bookings), and parcels (status, assignments)
- Export completed trips to PDF and optionally clear records


Templates and static assets
---------------------------

- `templates/` structured by module: `admin`, `auth`, `booking`, `catalog`, `parcels`, `staff`, etc.
- Shared layout in `templates/base.html` and module-specific `_layout.html`
- Static assets under `maua/static` with CSS and JS


Configuration and environments
------------------------------

- `config.py` provides `Development`, `Testing`, and `Production` configs
- `.env` used for local secret management via `python-dotenv`
- Production runs behind WSGI server (Gunicorn) using `wsgi.py`


Migrations
----------

- Alembic migrations in `migrations/versions`
- Use `flask db migrate/upgrade/downgrade`


Observability and logging
-------------------------

- Development config writes rotating logs to `logs/maua.log`
- Production config logs to stdout/stderr for platform capture


