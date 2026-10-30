from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import analytics
from ..db import get_db
from ..models import User
from ..periods import resolve, today_ist
from ..schemas import CategoryPoint, MonthPoint, Period, Summary
from ..security import current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _period(preset: str, start: date | None, end: date | None) -> Period:
    try:
        s, e, label = resolve(preset, start, end)
    except ValueError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err))
    return Period(preset=preset, start=s, end=e, label=label)


@router.get("/summary", response_model=Summary)
def summary(preset: str = "current_month", start: date | None = None, end: date | None = None,
            user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _period(preset, start, end)
    return Summary(period=p, **analytics.summarize(db, user.id, p.start, p.end),
                   credit_card_outstanding=analytics.card_outstanding(db, user.id))


@router.get("/monthly", response_model=list[MonthPoint])
def monthly(months: int = Query(default=12, ge=1, le=36),
            user: User = Depends(current_user), db: Session = Depends(get_db)):
    return analytics.monthly_series(db, user.id, today_ist(), months)


@router.get("/categories", response_model=list[CategoryPoint])
def categories(preset: str = "current_month", start: date | None = None, end: date | None = None,
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _period(preset, start, end)
    return analytics.category_breakdown(db, user.id, p.start, p.end)
