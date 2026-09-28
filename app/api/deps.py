from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.core.security import decode_token
from app.core.exceptions import InvalidTokenError

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except ValueError:
        raise InvalidTokenError()

    user = UserRepository(db).get_by_id(payload["sub"])
    if not user or not user.is_active:
        raise InvalidTokenError()
    return user