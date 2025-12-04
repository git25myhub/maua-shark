from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from maua.extensions import db, bcrypt
from maua.catalog.models import Route, Depot, Vehicle
from maua.auth.models import User
from datetime import datetime

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
        origin = request.form.get('origin', '').strip()
        destination = request.form.get('destination', '').strip()
        
        if not all([code, origin, destination]):
            flash('All fields are required.', 'danger')
        else:
            try:
                # Create new depots if they don't exist
                origin_depot = Depot.query.filter_by(name=origin).first()
                if not origin_depot:
                    # Extract town and name from the format "Town - Name"
                    parts = [p.strip() for p in origin.split('-', 1)]
                    town = parts[0] if len(parts) > 0 else 'Unknown'
                    name = parts[1] if len(parts) > 1 else origin
                    origin_depot = Depot(town=town, name=name, address=origin)
                    db.session.add(origin_depot)
                    db.session.flush()  # Get the ID for the new depot
                
                destination_depot = Depot.query.filter_by(name=destination).first()
                if not destination_depot:
                    parts = [p.strip() for p in destination.split('-', 1)]
                    town = parts[0] if len(parts) > 0 else 'Unknown'
                    name = parts[1] if len(parts) > 1 else destination
                    destination_depot = Depot(town=town, name=name, address=destination)
                    db.session.add(destination_depot)
                    db.session.flush()
                
                # Create the route
                route = Route(
                    code=code,
                    origin_depot_id=origin_depot.id,
                    destination_depot_id=destination_depot.id,
                    active=True
                )
                db.session.add(route)
                db.session.commit()
                flash('Route created successfully!', 'success')
                return redirect(url_for('admin.routes_manage'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating route: {str(e)}', 'danger')
    
    # For GET requests or if there was an error in POST
    routes = Route.query.order_by(Route.id.desc()).all()
    return render_template('admin/routes_manage.html', routes=routes)


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


# ============================================================================
# STAFF MANAGEMENT - Admin creates and manages staff accounts
# ============================================================================

@admin_bp.route('/staff', methods=['GET'])
@login_required
@admin_required
def staff_manage():
    """List all staff members"""
    staff_members = User.query.filter(
        (User.is_staff == True) | (User.is_admin == True)
    ).order_by(User.created_at.desc()).all()
    return render_template('admin/staff_manage.html', staff_members=staff_members)


@admin_bp.route('/staff/create', methods=['GET', 'POST'])
@login_required
@admin_required
def staff_create():
    """Create a new staff account"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        role = request.form.get('role', 'staff')  # staff or admin
        
        # Validation
        if not all([username, email, phone, password]):
            flash('All fields are required.', 'danger')
            return render_template('admin/staff_create.html')
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('admin/staff_create.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return render_template('admin/staff_create.html')
        
        try:
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            staff = User(
                username=username,
                email=email,
                phone=phone,
                password_hash=hashed_password,
                is_staff=(role == 'staff'),
                is_admin=(role == 'admin'),
                is_active=True,
                date_joined=datetime.utcnow()
            )
            db.session.add(staff)
            db.session.commit()
            flash(f'Staff account for {username} created successfully!', 'success')
            return redirect(url_for('admin.staff_manage'))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to create staff account: {str(e)}', 'danger')
    
    return render_template('admin/staff_create.html')


@admin_bp.route('/staff/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def staff_edit(user_id: int):
    """Edit staff account"""
    user = User.query.get_or_404(user_id)
    
    # Prevent editing yourself or other admins (except by super admin)
    if user.id == current_user.id:
        flash('You cannot edit your own account here. Use profile settings.', 'warning')
        return redirect(url_for('admin.staff_manage'))
    
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.phone = request.form.get('phone')
        user.is_active = request.form.get('is_active') == 'on'
        
        role = request.form.get('role', 'staff')
        user.is_staff = (role == 'staff')
        user.is_admin = (role == 'admin')
        
        # Update password if provided
        new_password = request.form.get('password')
        if new_password:
            user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        
        try:
            db.session.commit()
            flash('Staff account updated successfully!', 'success')
            return redirect(url_for('admin.staff_manage'))
        except Exception:
            db.session.rollback()
            flash('Failed to update staff account.', 'danger')
    
    return render_template('admin/staff_edit.html', user=user)


@admin_bp.route('/staff/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def staff_toggle(user_id: int):
    """Toggle staff account active status"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('admin.staff_manage'))
    
    try:
        user.is_active = not user.is_active
        db.session.commit()
        status = 'activated' if user.is_active else 'deactivated'
        flash(f'Account {user.username} has been {status}.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to update account status.', 'danger')
    
    return redirect(url_for('admin.staff_manage'))


@admin_bp.route('/staff/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def staff_delete(user_id: int):
    """Delete staff account"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin.staff_manage'))
    
    if user.is_admin:
        flash('Cannot delete admin accounts. Demote to staff first.', 'warning')
        return redirect(url_for('admin.staff_manage'))
    
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f'Staff account {user.username} deleted.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to delete staff account. They may have associated records.', 'danger')
    
    return redirect(url_for('admin.staff_manage'))