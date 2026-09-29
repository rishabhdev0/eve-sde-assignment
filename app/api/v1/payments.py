from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_current_user
from app.schemas.payment import PaymentCreate, PaymentOut
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/", response_model=PaymentOut, status_code=status.HTTP_202_ACCEPTED)
def create_payment(payload: PaymentCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # 202, not 201 - the payment is still PENDING, worker picks it up async
    return PaymentService(db).create_payment(str(user.id), str(payload.booking_id))


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return PaymentService(db).get_payment(payment_id, str(user.id))