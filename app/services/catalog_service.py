from sqlalchemy.orm import Session
from app.repositories.centre_repository import CentreRepository, TestRepository
from app.repositories.slot_repository import SlotRepository
from app.models.centre import DiagnosticCentre
from app.models.test import Test
from app.models.centre_test import CentreTest
from app.models.slot import Slot
from app.core.exceptions import AppException


class DuplicateOfferingError(AppException):
    status_code = 400
    detail = "This centre already offers this test"


class DuplicateSlotError(AppException):
    status_code = 400
    detail = "A slot already exists at this exact time for this offering"


class CentreNotFoundError(AppException):
    status_code = 404
    detail = "Diagnostic centre not found"


class CentreTestNotFoundError(AppException):
    status_code = 404
    detail = "This test is not offered at this centre"


class TestNotFoundError(AppException):
    status_code = 404
    detail = "Test not found"


class CatalogService:
    def __init__(self, db: Session):
        self.db = db
        self.centres = CentreRepository(db)
        self.tests = TestRepository(db)
        self.slots = SlotRepository(db)

    def create_centre(self, name: str, location: str) -> DiagnosticCentre:
        return self.centres.create(DiagnosticCentre(name=name, location=location))

    def list_centres(self, skip: int = 0, limit: int = 20) -> list[DiagnosticCentre]:
        return self.centres.list(skip=skip, limit=limit)

    def get_centre(self, centre_id: str) -> DiagnosticCentre:
        centre = self.centres.get_by_id(centre_id)
        if not centre:
            raise CentreNotFoundError()
        return centre

    def create_test(self, name: str, description: str | None) -> Test:
        return self.tests.create(Test(name=name, description=description))

    def list_tests(self, skip: int = 0, limit: int = 20) -> list[Test]:
        return self.tests.list(skip=skip, limit=limit)

    def add_test_to_centre(self, centre_id: str, test_id: str, price, turnaround_hours: int) -> CentreTest:
        self.get_centre(centre_id)  # 404s if centre missing
        if not self.tests.get_by_id(test_id):
            raise TestNotFoundError()
        if self.centres.get_existing_offering(centre_id, test_id):
            raise DuplicateOfferingError()
        offering = CentreTest(centre_id=centre_id, test_id=test_id, price=price, turnaround_hours=turnaround_hours)
        self.db.add(offering)
        self.db.commit()
        self.db.refresh(offering)
        return offering

    def list_tests_for_centre(self, centre_id: str) -> list[CentreTest]:
        self.get_centre(centre_id)
        return self.centres.list_tests_for_centre(centre_id)

    def create_slot(self, centre_test_id: str, start_time, end_time, capacity: int) -> Slot:
        offering = self.centres.get_centre_test(centre_test_id)
        if not offering:
            raise CentreTestNotFoundError()
        if self.slots.find_existing(centre_test_id, start_time):
            raise DuplicateSlotError()
        slot = Slot(centre_test_id=centre_test_id, start_time=start_time, end_time=end_time, capacity=capacity)
        return self.slots.create(slot)

    def list_available_slots(self, centre_test_id: str) -> list[Slot]:
        if not self.centres.get_centre_test(centre_test_id):
            raise CentreTestNotFoundError()
        return self.slots.list_available_for_centre_test(centre_test_id)