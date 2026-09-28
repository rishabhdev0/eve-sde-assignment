import logging
logger = logging.getLogger("email_service")

def send_reset_email(to_email: str, reset_link: str) -> None:
    logger.info(f"[MOCK EMAIL] Password reset for {to_email}: {reset_link}")

def send_verification_email(to_email: str, verify_link: str) -> None:
    logger.info(f"[MOCK EMAIL] Verify email for {to_email}: {verify_link}")