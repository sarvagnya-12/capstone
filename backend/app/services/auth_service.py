from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User, UserRole


class EmailAlreadyRegisteredError(Exception):
    pass


def register_user(db: Session, org_name: str, email: str, password: str) -> User:
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise EmailAlreadyRegisteredError(email)

    user = User(
        org_name=org_name,
        email=email,
        hashed_password=hash_password(password),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
