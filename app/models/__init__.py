# Import every model here so anywhere Base.metadata is used, all tables are registered together.
# This matters because SQLAlchemy resolves foreign keys by table name lookup in Base.metadata -
# if a model class is never imported, its table silently doesn't exist for FK resolution,
# even though the class file is right there on disk.
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