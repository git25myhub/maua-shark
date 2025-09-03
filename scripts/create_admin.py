import argparse
from maua import create_app
from maua.extensions import db
from maua.auth.models import User


def create_or_update_admin(email: str, password: str, username: str, phone: str) -> None:
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(username=username, email=email, phone=phone)
        user.set_password(password)
        user.is_admin = True
        db.session.add(user)
        db.session.commit()
        print(f"Admin ready: {user.email} username={user.username} is_admin={user.is_admin}")


def main():
    parser = argparse.ArgumentParser(description="Create or update an admin user")
    parser.add_argument("email", help="Admin email")
    parser.add_argument("password", help="Admin password")
    parser.add_argument("--username", default="admin", help="Username to use if user is created")
    parser.add_argument("--phone", default="0700000000", help="Phone to use if user is created")
    args = parser.parse_args()

    create_or_update_admin(args.email, args.password, args.username, args.phone)


if __name__ == "__main__":
    main()


