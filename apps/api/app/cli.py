import argparse
from getpass import getpass

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User, UserRole, UserStatus


def create_administrator() -> None:
    try:
        email = validate_email(input("Administrator email: ").strip()).normalized.lower()
    except EmailNotValidError as error:
        raise SystemExit(str(error)) from error
    password = getpass("Password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters")

    with SessionLocal.begin() as db:
        existing_admin = db.scalar(
            select(User.id).where(User.role == UserRole.ADMINISTRATOR)
        )
        if existing_admin:
            raise SystemExit("An administrator already exists")
        existing_user = db.scalar(select(User).where(User.email == email))
        if existing_user:
            raise SystemExit("An account already uses that email")
        db.add(
            User(
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMINISTRATOR,
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
        )
    print(f"Administrator created for {email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Staff portal administration")
    parser.add_argument("command", choices=["create-admin"])
    args = parser.parse_args()
    if args.command == "create-admin":
        create_administrator()


if __name__ == "__main__":
    main()
