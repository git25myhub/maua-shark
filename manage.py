from flask_migrate import Migrate
from maua import create_app, db
from maua.auth.models import User
from maua.booking.models import Booking, Ticket
from maua.catalog.models import Depot, Route, Vehicle, Trip, Parcel
from maua.payment.models import Payment
import click

app = create_app()
migrate = Migrate(app, db)


@app.cli.command("create-admin")
@click.option("--email", required=True, help="Admin email")
@click.option("--password", required=True, help="Admin password")
@click.option("--username", default="admin", help="Username if creating new user")
@click.option("--phone", default="0745629494", help="Phone if creating new user")
def create_admin(email: str, password: str, username: str, phone: str) -> None:
    """Create or update an admin user."""
    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(username=username, email=email, phone=phone)
    user.set_password(password)
    user.is_admin = True
    db.session.add(user)
    db.session.commit()
    click.echo(f"Admin ready: {user.email} username={user.username} is_admin={user.is_admin}")


if __name__ == '__main__':
    app.run(debug=True)