import uuid
from sqlalchemy import Column, Numeric, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class CentreTest(Base):
    """Pivot: which tests a centre offers, and at what price/turnaround."""
    __tablename__ = "centre_tests"
    __table_args__ = (UniqueConstraint("centre_id", "test_id", name="uq_centre_test"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    centre_id = Column(UUID(as_uuid=True), ForeignKey("diagnostic_centres.id"), nullable=False)
    test_id = Column(UUID(as_uuid=True), ForeignKey("tests.id"), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    turnaround_hours = Column(Integer, nullable=False, default=24)

    centre = relationship("DiagnosticCentre", back_populates="centre_tests")
    test = relationship("Test")