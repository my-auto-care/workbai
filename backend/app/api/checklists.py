from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import uuid

from app.db.session import get_db
from app.db.models import ChecklistTemplate

router = APIRouter()

class ChecklistCreate(BaseModel):
    name: str
    vehicle_filter: Optional[dict] = {}
    items: dict

class ChecklistUpdate(BaseModel):
    name: Optional[str] = None
    vehicle_filter: Optional[dict] = None
    items: Optional[dict] = None

@router.get("/checklists")
def list_checklists(db: Session = Depends(get_db)):
    templates = db.query(ChecklistTemplate).all()
    return [{"id": str(t.id), "name": t.name, "version": t.version, "vehicle_filter": t.vehicle_filter} for t in templates]

@router.get("/checklists/{checklist_id}")
def get_checklist(checklist_id: uuid.UUID, db: Session = Depends(get_db)):
    template = db.get(ChecklistTemplate, checklist_id)
    if not template:
        raise HTTPException(status_code=404, detail="Checklist not found")
    return {"id": str(template.id), "name": template.name, "version": template.version, "vehicle_filter": template.vehicle_filter, "items": template.items}

@router.post("/checklists", status_code=201)
def create_checklist(body: ChecklistCreate, db: Session = Depends(get_db)):
    template = ChecklistTemplate(name=body.name, vehicle_filter=body.vehicle_filter, items=body.items)
    db.add(template)
    db.commit()
    db.refresh(template)
    return {"id": str(template.id), "name": template.name, "version": template.version}

@router.patch("/checklists/{checklist_id}")
def update_checklist(checklist_id: uuid.UUID, body: ChecklistUpdate, db: Session = Depends(get_db)):
    template = db.get(ChecklistTemplate, checklist_id)
    if not template:
        raise HTTPException(status_code=404, detail="Checklist not found")
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
