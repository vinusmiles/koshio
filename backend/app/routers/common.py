from fastapi import HTTPException, status
from sqlalchemy.orm import Session


def get_owned(db: Session, model, obj_id: int | None, user_id: int, label: str):
    """Fetch a row only if it belongs to this user. Other users' rows look
    exactly like missing rows, so their existence is never revealed."""
    if obj_id is None:
        return None
    obj = db.get(model, obj_id)
    if obj is None or obj.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} not found.")
    return obj
