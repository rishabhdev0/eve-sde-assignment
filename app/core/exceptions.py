class AppException(Exception):
    status_code = 400
    detail = "Something went wrong"

    def __init__(self, detail: str | None = None):
        if detail:
            self.detail = detail
        super().__init__(self.detail)


class InvalidCredentialsError(AppException):
    status_code = 401
    detail = "Invalid email or password"


class AccountDisabledError(AppException):
    status_code = 403
    detail = "Account disabled"


class EmailNotVerifiedError(AppException):
    status_code = 403
    detail = "Please verify your email before logging in"


class DuplicateEmailError(AppException):
    status_code = 400
    detail = "Could not create account"


class InvalidTokenError(AppException):
    status_code = 401
    detail = "Invalid or expired token"


class RateLimitedError(AppException):
    status_code = 429
    detail = "Too many attempts. Try again later."


class ReusedResetTokenError(AppException):
    status_code = 400
    detail = "Invalid or expired reset token"


class RefreshTokenReuseDetectedError(AppException):
    status_code = 401
    detail = "Security issue detected - all sessions have been logged out. Please log in again."