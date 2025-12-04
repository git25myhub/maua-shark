API Overview
============

This document lists key HTTP endpoints exposed by the application. Many routes return HTML for server-rendered pages; JSON endpoints are marked.


Auth
----

- GET `/auth/login` — Login form
- POST `/auth/login` — Authenticate user
- GET `/auth/register` — Registration form
- POST `/auth/register` — Create account
- GET `/auth/logout` — Logout


Main and health
---------------

- GET `/` — Home page
- GET `/health` — Health probe (200 OK)


Catalog
-------

- GET `/catalog/routes` — List routes
- GET `/catalog/trip/<id>` — Trip details


Booking
-------

- GET `/booking/` — Booking landing
- GET `/booking/select_seat?trip_id=<id>` — Seat selection
- POST `/booking/passenger_details` — Submit passenger info
- GET `/booking/payment` — Payment page for booking
- GET `/booking/payment_status` — Poll/display status
- GET `/booking/confirmation` — Confirmation page


Parcels
-------

- GET `/parcels/` — Parcel landing
- GET `/parcels/create` — New parcel form
- POST `/parcels/create` — Create parcel
- GET `/parcels/list` — List user parcels
- GET `/parcels/track` — Track by reference
- GET `/parcels/receipt` — View receipt
- GET `/parcels/payment` — Payment page for parcel
- GET `/parcels/payment_status` — Payment status page


Payments (M-Pesa)
-----------------

- POST `/stkpush` — Initiate STK push for booking/parcel
- POST `/mpesa/callback` — Daraja callback endpoint
- GET `/payment/status?ref=<ref>` — Query payment status (HTML)


Admin
-----

- GET `/admin/` — Admin dashboard
- GET `/admin/routes` — Manage routes
- GET `/admin/vehicles` — Manage vehicles
- GET `/admin/depots` — Manage depots
- GET `/admin/settings` — Settings


Staff
-----

- GET `/staff/` — Staff dashboard

Bookings:
- GET `/staff/bookings/routes` — Choose a route
- GET `/staff/bookings/routes/<route_id>/trips` — Trips for a route
- GET `/staff/bookings?trip_id=<id>&status=<optional>` — List bookings for a trip
- POST `/staff/bookings/<booking_id>/status` — Update booking status
- JSON GET `/staff/trips/<trip_id>/seats/<seat>/booking.json` — Booking details for seat

Parcels:
- GET `/staff/parcels?status=<optional>` — List parcels
- POST `/staff/parcels/<parcel_id>/status` — Update parcel status
- POST `/staff/parcels/<parcel_id>/tracking` — Assign tracking/vehicle/driver (HEAD returns 200 for monitoring)

Trips and vehicles:
- GET `/staff/trips?status=<optional>` — List trips
- GET `/staff/trips/completed` — Completed trips list
- POST `/staff/trips/completed/export_pdf` — Export completed trips to PDF and clear
- POST `/staff/trips/<trip_id>/status` — Update trip status
- GET/POST `/staff/trips/create` — Create a trip
- GET `/staff/vehicles` — List vehicles
- GET/POST `/staff/vehicles/<vehicle_id>/seats` — Edit seat layout
- GET `/staff/trips/<trip_id>/seats` — Visualize trip seat map
- POST `/staff/trips/<trip_id>/seats/<seat>/checkin` — Check in passenger

Customers:
- GET `/staff/customers` — Aggregated passengers from bookings


Notes
-----

- Most staff/admin endpoints require authentication and staff/admin roles.
- JSON contract example: `/staff/trips/<trip_id>/seats/<seat>/booking.json`

Response 200 (found):

```json
{
  "found": true,
  "booking": {
    "id": 1,
    "seat_number": "1A",
    "status": "confirmed",
    "route": "Nairobi → Mombasa",
    "depart_at": "2025-01-05T10:00:00",
    "vehicle_plate": "KAA123A",
    "vehicle_make": "Isuzu",
    "vehicle_model": "NQR",
    "driver_name": "John Doe",
    "driver_phone": "+254700000000"
  }
}
```

Response 404 (not found):

```json
{ "found": false }
```


