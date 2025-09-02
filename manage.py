from flask_migrate import Migrate
from maua import create_app, db
from maua.auth.models import User
from maua.booking.models import Booking, Ticket
from maua.catalog.models import Depot, Route, Vehicle, Trip, Parcel
from maua.payment.models import Payment

app = create_app()
migrate = Migrate(app, db)

if __name__ == '__main__':
    app.run(debug=True)