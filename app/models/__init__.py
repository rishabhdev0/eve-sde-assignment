# Import every model so its table actually gets registered - miss one and its
# foreign keys just quietly don't work, even though the file's right there.
from app.models.user import User  # noqa
from app.models.centre import DiagnosticCentre  # noqa
from app.models.test import Test  # noqa
from app.models.centre_test import CentreTest  # noqa
from app.models.slot import Slot  # noqa
from app.models.booking import Booking  # noqa
from app.models.booking_event import BookingEvent  # noqa
from app.models.payment import Payment  # noqa
from app.models.payment_event import PaymentEvent  # noqa
from app.models.webhook_event import WebhookEvent  # noqa