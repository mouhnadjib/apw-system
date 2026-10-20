from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas, services
from ..db import get_db

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/info", response_model=schemas.PublicInfoOut)
def info(db: Session = Depends(get_db)):
    """معلومات عامة غير حساسة تظهر في شاشة التفعيل (اسم الولاية اختياري)."""
    return schemas.PublicInfoOut(wilaya_name=services.get_setting(db, "wilaya_name"))
