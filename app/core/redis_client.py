import time
from redis import Redis
from app.core.config import settings

redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

# Sliding-window rate limiter using a Redis sorted set as a log of timestamps.
# Old entries get trimmed on every check, so the window actually slides instead
# of resetting on a fixed clock boundary that's easy to burst through.
_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)

if count < limit then
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, window)
    return 1
else
    return 0
end
"""
_sliding_window = redis_client.register_script(_SLIDING_WINDOW_SCRIPT)


def check_login_rate_limit(identifier: str) -> bool:
    # True if this attempt is allowed, False if they've hit the limit.
    key = f"login_attempts:{identifier}"
    now = time.time()
    member = f"{now}:{id(object())}"
    allowed = _sliding_window(
        keys=[key],
        args=[now, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS, settings.LOGIN_RATE_LIMIT_ATTEMPTS, member],
    )
    return bool(allowed)


def reset_login_rate_limit(identifier: str) -> None:
    redis_client.delete(f"login_attempts:{identifier}")


def check_signup_rate_limit(identifier: str) -> bool:
    # Same idea as login, just for signup - stops spam accounts and probing.
    key = f"signup_attempts:{identifier}"
    now = time.time()
    member = f"{now}:{id(object())}"
    allowed = _sliding_window(
        keys=[key],
        args=[now, settings.SIGNUP_RATE_LIMIT_WINDOW_SECONDS, settings.SIGNUP_RATE_LIMIT_ATTEMPTS, member],
    )
    return bool(allowed)


def reset_signup_rate_limit(identifier: str) -> None:
    redis_client.delete(f"signup_attempts:{identifier}")


def mark_reset_token_used(token: str, ttl_seconds: int) -> None:
    redis_client.setex(f"used_reset_token:{token}", ttl_seconds, "1")


def is_reset_token_used(token: str) -> bool:
    return redis_client.exists(f"used_reset_token:{token}") == 1


def store_refresh_jti(user_id: str, jti: str, ttl_seconds: int) -> None:
    redis_client.setex(f"refresh_jti:{user_id}:{jti}", ttl_seconds, "1")


def is_refresh_jti_valid(user_id: str, jti: str) -> bool:
    return redis_client.exists(f"refresh_jti:{user_id}:{jti}") == 1


def revoke_refresh_jti(user_id: str, jti: str) -> None:
    redis_client.delete(f"refresh_jti:{user_id}:{jti}")


def revoke_all_refresh_tokens(user_id: str) -> None:
    for key in redis_client.scan_iter(f"refresh_jti:{user_id}:*"):
        redis_client.delete(key)


def mark_refresh_jti_used(user_id: str, jti: str, ttl_seconds: int) -> None:
    # Keeps track of tokens that were rotated out properly, so if one shows up
    # again later we know it was reused, not just expired or invalid.
    redis_client.setex(f"used_refresh_jti:{user_id}:{jti}", ttl_seconds, "1")


def was_refresh_jti_used(user_id: str, jti: str) -> bool:
    return redis_client.exists(f"used_refresh_jti:{user_id}:{jti}") == 1