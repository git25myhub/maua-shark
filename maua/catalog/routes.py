from flask import render_template, abort, redirect, url_for
from maua.catalog import bp
from maua.catalog.models import Trip
from datetime import datetime
from collections import defaultdict


@bp.route('/routes')
def routes():
    # Only show scheduled trips that are not marked as full
    trips_all = Trip.query.filter(
        Trip.status == 'scheduled',
        Trip.is_full == False
    ).order_by(Trip.depart_at.asc(), Trip.id.asc()).limit(500).all()

    # Group by route_id and pick the first trip (earliest) that still has available seats
    route_to_active_trip = {}
    routes_groups = defaultdict(list)
    for t in trips_all:
        routes_groups[t.route_id].append(t)

    for route_id, group in routes_groups.items():
        chosen = None
        for t in group:  # already sorted by depart_at asc
            try:
                if hasattr(t, 'available_seats') and len(t.available_seats) > 0:
                    chosen = t
                    break
            except Exception:
                continue
        if chosen:
            route_to_active_trip[route_id] = chosen
        # If no trips for this route have seats, do not surface the route

    trips = list(route_to_active_trip.values())
    trips.sort(key=lambda t: (t.depart_at, t.id))

    return render_template('catalog/routes.html', title='Routes', trips=trips)


@bp.route('/trips/<int:trip_id>')
def trip_detail(trip_id: int):
    trip = Trip.query.get(trip_id)
    if trip is None:
        abort(404)

    # If trip is marked as full, redirect to routes page
    if trip.is_full:
        return redirect(url_for('catalog.routes'))

    # Enforce one car at a time per route: if another trip (earliest) on this route has seats
    # and it is not this one, redirect to that one
    try:
        siblings = Trip.query.filter(
            Trip.status == 'scheduled',
            Trip.route_id == trip.route_id,
            Trip.is_full == False,
        ).order_by(Trip.depart_at.asc(), Trip.id.asc()).all()
        if siblings:
            active = None
            for s in siblings:
                if hasattr(s, 'available_seats') and len(s.available_seats) > 0:
                    active = s
                    break
            if active and active.id != trip.id:
                return redirect(url_for('catalog.trip_detail', trip_id=active.id))
    except Exception:
        pass

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