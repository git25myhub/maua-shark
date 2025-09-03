from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from maua.extensions import db
from maua.catalog.models import Route, Depot, Vehicle

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    return render_template('admin/dashboard.html')


@admin_bp.route('/routes', methods=['GET', 'POST'])
@login_required
@admin_required
def routes_manage():
    if request.method == 'POST':
        code = request.form.get('code')
        origin_id = request.form.get('origin_id', type=int)
        destination_id = request.form.get('destination_id', type=int)
        try:
            r = Route(code=code, origin_depot_id=origin_id, destination_depot_id=destination_id, active=True)
            db.session.add(r)
            db.session.commit()
            flash('Route created.', 'success')
        except Exception:
            db.session.rollback()
            flash('Failed to create route.', 'danger')
        return redirect(url_for('admin.routes_manage'))
    routes = Route.query.order_by(Route.id.desc()).all()
    depots = Depot.query.order_by(Depot.town.asc()).all()
    return render_template('admin/routes_manage.html', routes=routes, depots=depots)


@admin_bp.route('/routes/<int:route_id>/delete', methods=['POST'])
@login_required
@admin_required
def routes_delete(route_id: int):
    r = Route.query.get_or_404(route_id)
    try:
        db.session.delete(r)
        db.session.commit()
        flash('Route deleted.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to delete route.', 'danger')
    return redirect(url_for('admin.routes_manage'))


@admin_bp.route('/routes/<int:route_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def routes_edit(route_id: int):
    r = Route.query.get_or_404(route_id)
    if request.method == 'POST':
        r.code = request.form.get('code')
        r.origin_depot_id = request.form.get('origin_id', type=int)
        r.destination_depot_id = request.form.get('destination_id', type=int)
        try:
            db.session.commit()
            flash('Route updated.', 'success')
            return redirect(url_for('admin.routes_manage'))
        except Exception:
            db.session.rollback()
            flash('Failed to update route.', 'danger')
    depots = Depot.query.order_by(Depot.town.asc()).all()
    return render_template('admin/route_edit.html', route=r, depots=depots)


@admin_bp.route('/vehicles', methods=['GET', 'POST'])
@login_required
@admin_required
def vehicles_manage():
    if request.method == 'POST':
        plate_no = request.form.get('plate_no')
        make = request.form.get('make')
        model = request.form.get('model')
        seats_text = request.form.get('seats', '').strip()
        layout = [{'seat': token} for token in seats_text.split()] if seats_text else []
        try:
            v = Vehicle(plate_no=plate_no, make=make, model=model, seat_count=len(layout), seat_layout=layout, active=True)
            db.session.add(v)
            db.session.commit()
            flash('Vehicle created.', 'success')
        except Exception:
            db.session.rollback()
            flash('Failed to create vehicle.', 'danger')
        return redirect(url_for('admin.vehicles_manage'))
    vehicles = Vehicle.query.order_by(Vehicle.plate_no.asc()).all()
    return render_template('admin/vehicles_manage.html', vehicles=vehicles)


@admin_bp.route('/vehicles/<int:vehicle_id>/delete', methods=['POST'])
@login_required
@admin_required
def vehicles_delete(vehicle_id: int):
    v = Vehicle.query.get_or_404(vehicle_id)
    try:
        db.session.delete(v)
        db.session.commit()
        flash('Vehicle deleted.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to delete vehicle.', 'danger')
    return redirect(url_for('admin.vehicles_manage'))


@admin_bp.route('/vehicles/<int:vehicle_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def vehicles_edit(vehicle_id: int):
    v = Vehicle.query.get_or_404(vehicle_id)
    if request.method == 'POST':
        v.plate_no = request.form.get('plate_no')
        v.make = request.form.get('make')
        v.model = request.form.get('model')
        seats_text = request.form.get('seats', '').strip()
        layout = [{'seat': t} for t in seats_text.split()] if seats_text else []
        v.seat_layout = layout
        v.seat_count = len(layout)
        try:
            db.session.commit()
            flash('Vehicle updated.', 'success')
            return redirect(url_for('admin.vehicles_manage'))
        except Exception:
            db.session.rollback()
            flash('Failed to update vehicle.', 'danger')
    seats_text = ' '.join([s['seat'] for s in (v.seat_layout or [])])
    return render_template('admin/vehicle_edit.html', vehicle=v, seats_text=seats_text)


@admin_bp.route('/depots', methods=['GET', 'POST'])
@login_required
@admin_required
def depots_manage():
    if request.method == 'POST':
        name = request.form.get('name')
        town = request.form.get('town')
        address = request.form.get('address')
        phone = request.form.get('phone')
        try:
            d = Depot(name=name, town=town, address=address, phone=phone)
            db.session.add(d)
            db.session.commit()
            flash('Depot created.', 'success')
        except Exception:
            db.session.rollback()
            flash('Failed to create depot.', 'danger')
        return redirect(url_for('admin.depots_manage'))
    depots = Depot.query.order_by(Depot.town.asc()).all()
    return render_template('admin/depots_manage.html', depots=depots)


@admin_bp.route('/depots/<int:depot_id>/delete', methods=['POST'])
@login_required
@admin_required
def depots_delete(depot_id: int):
    d = Depot.query.get_or_404(depot_id)
    try:
        db.session.delete(d)
        db.session.commit()
        flash('Depot deleted.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to delete depot.', 'danger')
    return redirect(url_for('admin.depots_manage'))


@admin_bp.route('/depots/<int:depot_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def depots_edit(depot_id: int):
    d = Depot.query.get_or_404(depot_id)
    if request.method == 'POST':
        d.name = request.form.get('name')
        d.town = request.form.get('town')
        d.address = request.form.get('address')
        d.phone = request.form.get('phone')
        try:
            db.session.commit()
            flash('Depot updated.', 'success')
            return redirect(url_for('admin.depots_manage'))
        except Exception:
            db.session.rollback()
            flash('Failed to update depot.', 'danger')
    return render_template('admin/depot_edit.html', depot=d)