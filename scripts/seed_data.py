from datetime import datetime, timedelta, timezone
from app.db.session import SessionLocal
from app.models.centre import DiagnosticCentre
from app.models.test import Test
from app.models.centre_test import CentreTest
from app.models.slot import Slot

TESTS = {
    "CBC": "Complete Blood Count",
    "Lipid Profile": "Cholesterol and triglycerides panel",
    "HbA1c": "Three-month average blood sugar",
    "Thyroid Profile": "TSH, T3 and T4 levels",
}

# centre name -> (location, {test name: (price, turnaround hours)})
CENTRES = {
    "Apollo Diagnostics": ("Mumbai", {"CBC": (500, 24), "Lipid Profile": (900, 24), "HbA1c": (650, 24)}),
    "Lal PathLabs": ("Delhi", {"CBC": (450, 12), "Thyroid Profile": (800, 36)}),
    "Metropolis Healthcare": ("Bengaluru", {"CBC": (550, 24), "Lipid Profile": (850, 24), "Thyroid Profile": (750, 24)}),
}

SLOT_HOURS = [9, 10, 11, 14]
SLOT_DAYS_AHEAD = 3
SLOT_CAPACITY = 2


def seed() -> None:
    db = SessionLocal()
    created = {"centres": 0, "tests": 0, "offerings": 0, "slots": 0}
    try:
        tests = {}
        for name, description in TESTS.items():
            test = db.query(Test).filter(Test.name == name).first()
            if not test:
                test = Test(name=name, description=description)
                db.add(test)
                db.flush()
                created["tests"] += 1
            tests[name] = test

        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        for centre_name, (location, offered) in CENTRES.items():
            centre = db.query(DiagnosticCentre).filter(
                DiagnosticCentre.name == centre_name, DiagnosticCentre.location == location
            ).first()
            if not centre:
                centre = DiagnosticCentre(name=centre_name, location=location)
                db.add(centre)
                db.flush()
                created["centres"] += 1

            for test_name, (price, turnaround) in offered.items():
                offering = db.query(CentreTest).filter(
                    CentreTest.centre_id == centre.id, CentreTest.test_id == tests[test_name].id
                ).first()
                if not offering:
                    offering = CentreTest(
                        centre_id=centre.id, test_id=tests[test_name].id,
                        price=price, turnaround_hours=turnaround,
                    )
                    db.add(offering)
                    db.flush()
                    created["offerings"] += 1

                for day in range(1, SLOT_DAYS_AHEAD + 1):
                    for hour in SLOT_HOURS:
                        start = today + timedelta(days=day, hours=hour)
                        exists = db.query(Slot).filter(
                            Slot.centre_test_id == offering.id, Slot.start_time == start
                        ).first()
                        if not exists:
                            db.add(Slot(
                                centre_test_id=offering.id, start_time=start,
                                end_time=start + timedelta(minutes=30), capacity=SLOT_CAPACITY,
                            ))
                            created["slots"] += 1

        db.commit()
        print(f"Seed complete: {created}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()