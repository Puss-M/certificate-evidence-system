import getpass

from pwdlib import PasswordHash

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.user import User


def _prompt_value(label: str) -> str:
    value = input(label).strip()
    if not value:
        raise SystemExit("value cannot be empty")
    return value


def main() -> None:
    if engine is None or SessionLocal is None:
        raise SystemExit("DATABASE_URL is not configured")

    Base.metadata.create_all(bind=engine)
    username = _prompt_value("Admin username: ")
    display_name = _prompt_value("Admin display name: ")
    password = getpass.getpass("Admin password: ")
    password_confirm = getpass.getpass("Confirm admin password: ")
    if len(password) < 12:
        raise SystemExit("password must contain at least 12 characters")
    if password != password_confirm:
        raise SystemExit("password confirmation does not match")

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first() is not None:
            raise SystemExit("username already exists")
        db.add(
            User(
                username=username,
                display_name=display_name,
                password_hash=PasswordHash.recommended().hash(password),
                role="ADMIN",
            )
        )
        db.commit()
        print("administrator created")
    finally:
        db.close()


if __name__ == "__main__":
    main()
