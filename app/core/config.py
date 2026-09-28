from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://eve:eve@postgres:5432/eve_db"
    REDIS_URL: str = "redis://redis:6379/0"

    JWT_SECRET: str
    SESSION_SECRET: str = "change-this-session-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    VERIFY_TOKEN_EXPIRE_HOURS: int = 24
    SIGNUP_RATE_LIMIT_ATTEMPTS: int = 5
    SIGNUP_RATE_LIMIT_WINDOW_SECONDS: int = 3600
    WEBHOOK_SHARED_SECRET: str = "change-this-webhook-secret"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    LOGIN_RATE_LIMIT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300

    REQUIRE_EMAIL_VERIFICATION: bool = True

    class Config:
        env_file = ".env"

settings = Settings()