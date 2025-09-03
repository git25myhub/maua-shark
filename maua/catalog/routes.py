from flask import render_template, abort
from maua.catalog import bp
from maua.catalog.models import Trip
from datetime import datetime


@bp.route('/routes')
def routes():
    trips = Trip.query.order_by(Trip.depart_at.asc()).limit(50).all()
    return render_template('catalog/routes.html', title='Routes', trips=trips)


@bp.route('/trips/<int:trip_id>')
def trip_detail(trip_id: int):
    trip = Trip.query.get(trip_id)
    if trip is None:
        abort(404)

    # Build seat status map
    seat_layout = trip.vehicle.seat_layout or []
    # default red (available)
    seat_status = {seat['seat']: 'red' for seat in seat_layout}

    # Mark booked seats, respecting hold expiry
    for booking in trip.bookings:
        if booking.status in ['checked_in', 'completed']:
            seat_status[booking.seat_number] = 'green'  # passenger on board
        elif booking.status in ['confirmed']:
            seat_status[booking.seat_number] = 'blue'  # booked

    return render_template('catalog/trip_detail.html', trip=trip, seat_layout=seat_layout, seat_status=seat_status)