from sqlalchemy.orm import Session, joinedload
from app.models.centre import DiagnosticCentre
from app.models.test import Test
from app.models.centre_test import CentreTest
from app.repositories.base_repository import BaseRepository


class CentreRepository(BaseRepository[DiagnosticCentre]):
    def __init__(self, db: Session):
        super().__init__(db, DiagnosticCentre)

    def list_tests_for_centre(self, centre_id: str) -> list[CentreTest]:
        return (
            self.db.query(CentreTest)
            .options(joinedload(CentreTest.test))
            .filter(CentreTest.centre_id == centre_id)
            .all()
        )

    def get_centre_test(self, centre_test_id: str) -> CentreTest | None:
        return (
            self.db.query(CentreTest)
            .options(joinedload(CentreTest.test), joinedload(CentreTest.centre))
            .filter(CentreTest.id == centre_test_id)
            .first()
        )

    def get_existing_offering(self, centre_id: str, test_id: str) -> CentreTest | None:
        return (
            self.db.query(CentreTest)
            .filter(CentreTest.centre_id == centre_id, CentreTest.test_id == test_id)
            .first()
        )


class TestRepository(BaseRepository[Test]):
    def __init__(self, db: Session):
        super().__init__(db, Test)

    def get_by_name(self, name: str) -> Test | None:
        return self.db.query(Test).filter(Test.name == name).first()