import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import StaffActor, get_current_actor, require_roles
from app.db.models import ChecklistTemplate, UserRole
from app.db.session import get_db

router = APIRouter()


class ChecklistCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    vehicle_filter: Optional[dict] = {}
    items: dict


class ChecklistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    vehicle_filter: Optional[dict] = None
    items: Optional[dict] = None


def _staff(actor: StaffActor = Depends(get_current_actor)) -> StaffActor:
    if actor.role not in {UserRole.technician, UserRole.advisor, UserRole.admin}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient staff role")
    return actor


@router.get("/checklists")
def list_checklists(actor: StaffActor = Depends(_staff), db: Session = Depends(get_db)):
    templates = db.query(ChecklistTemplate).order_by(ChecklistTemplate.name.asc(), ChecklistTemplate.version.desc()).all()
    return [
        {"id": str(template.id), "name": template.name, "version": template.version, "vehicle_filter": template.vehicle_filter}
        for template in templates
    ]


@router.get("/checklists/{checklist_id}")
def get_checklist(checklist_id: uuid.UUID, actor: StaffActor = Depends(_staff), db: Session = Depends(get_db)):
    template = db.get(ChecklistTemplate, checklist_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist not found")
    return {
        "id": str(template.id),
        "name": template.name,
        "version": template.version,
        "vehicle_filter": template.vehicle_filter,
        "items": template.items,
    }


@router.post("/checklists", status_code=status.HTTP_201_CREATED)
def create_checklist(
    body: ChecklistCreate,
    actor: StaffActor = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    template = ChecklistTemplate(name=body.name, vehicle_filter=body.vehicle_filter, items=body.items)
    db.add(template)
    db.commit()
    db.refresh(template)
    return {"id": str(template.id), "name": template.name, "version": template.version}


@router.patch("/checklists/{checklist_id}")
def update_checklist(
    checklist_id: uuid.UUID,
    body: ChecklistUpdate,
    actor: StaffActor = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    template = db.get(ChecklistTemplate, checklist_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist not found")
    if body.name is not None:
        template.name = body.name
    if body.vehicle_filter is not None:
        template.vehicle_filter = body.vehicle_filter
    if body.items is not None:
        template.items = body.items
        template.version += 1
    db.commit()
    db.refresh(template)
    return {"id": str(template.id), "name": template.name, "version": template.version}
