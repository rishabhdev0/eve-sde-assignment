from sqlalchemy.orm import Session
from datetime import timedelta
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.core.security import (
    hash_password, verify_password, create_access_token, create_token,
    decode_token, generate_reset_token, verify_reset_token,
    generate_verify_token, verify_verify_token,
)
from app.core.redis_client import (
    check_login_rate_limit, reset_login_rate_limit, check_signup_rate_limit,
    mark_reset_token_used, is_reset_token_used,
    store_refresh_jti, is_refresh_jti_valid, revoke_refresh_jti, revoke_all_refresh_tokens,
    mark_refresh_jti_used, was_refresh_jti_used,
)
from app.core.config import settings
from app.core.exceptions import (
    InvalidCredentialsError, AccountDisabledError, EmailNotVerifiedError,
    DuplicateEmailError, InvalidTokenError, RateLimitedError, ReusedResetTokenError,
    RefreshTokenReuseDetectedError,
)
from app.services.email import send_reset_email, send_verification_email


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def _issue_tokens(self, user: User) -> tuple[str, str]:
        access = create_access_token(str(user.id))
        refresh, jti = create_token(str(user.id), timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh")
        store_refresh_jti(str(user.id), jti, settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)
        return access, refresh

    def signup(self, email: str, password: str, client_ip: str) -> tuple[str, str]:
        if not check_signup_rate_limit(client_ip):
            raise RateLimitedError("Too many signup attempts from this IP. Try again later.")

        if self.users.get_by_email(email):
            raise DuplicateEmailError()

        user = User(
            email=email,
            hashed_password=hash_password(password),
            is_email_verified=not settings.REQUIRE_EMAIL_VERIFICATION,
        )
        user = self.users.create(user)

        if settings.REQUIRE_EMAIL_VERIFICATION:
            token = generate_verify_token(user.email)
            send_verification_email(user.email, f"https://your-frontend.com/verify-email?token={token}")

        return self._issue_tokens(user)

    def verify_email(self, token: str) -> None:
        try:
            email = verify_verify_token(token)
        except Exception:
            raise InvalidTokenError("Invalid or expired verification token")
        user = self.users.get_by_email(email)
        if not user:
            raise InvalidTokenError("Invalid or expired verification token")
        user.is_email_verified = True
        self.db.commit()

    def login(self, email: str, password: str, client_ip: str) -> tuple[str, str]:
        rate_key = f"{email}:{client_ip}"
        if not check_login_rate_limit(rate_key):
            raise RateLimitedError()

        user = self.users.get_by_email(email)
        if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()
        if not user.is_active:
            raise AccountDisabledError()
        if settings.REQUIRE_EMAIL_VERIFICATION and not user.is_email_verified:
            raise EmailNotVerifiedError()

        reset_login_rate_limit(rate_key)
        return self._issue_tokens(user)

    def refresh(self, refresh_token: str) -> tuple[str, str]:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except ValueError:
            raise InvalidTokenError("Invalid or expired refresh token")

        user_id, jti = payload["sub"], payload["jti"]

        if not is_refresh_jti_valid(user_id, jti):
            if was_refresh_jti_used(user_id, jti):
                # This token was already used once - if it shows up again, it was
                # copied. Kill every session for this user to be safe.
                revoke_all_refresh_tokens(user_id)
                raise RefreshTokenReuseDetectedError()
            raise InvalidTokenError("Invalid or expired refresh token")

        user = self.users.get_by_id(user_id)
        if not user or not user.is_active:
            raise InvalidTokenError("Invalid or expired refresh token")

        revoke_refresh_jti(user_id, jti)
        mark_refresh_jti_used(user_id, jti, settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)

        return self._issue_tokens(user)

    def forgot_password(self, email: str) -> None:
        user = self.users.get_by_email(email)
        if user and user.hashed_password:
            token = generate_reset_token(user.email)
            send_reset_email(user.email, f"https://your-frontend.com/reset-password?token={token}")

    def reset_password(self, token: str, new_password: str) -> None:
        if is_reset_token_used(token):
            raise ReusedResetTokenError()
        try:
            email = verify_reset_token(token)
        except Exception:
            raise ReusedResetTokenError()

        user = self.users.get_by_email(email)
        if not user:
            raise ReusedResetTokenError()

        user.hashed_password = hash_password(new_password)
        self.db.commit()
        mark_reset_token_used(token, settings.RESET_TOKEN_EXPIRE_MINUTES * 60)

    def get_or_create_google_user(self, email: str) -> User:
        user = self.users.get_by_email(email)
        if not user:
            user = self.users.create(User(
                email=email, hashed_password=None,
                is_google_account=True, is_email_verified=True,
            ))
        return user