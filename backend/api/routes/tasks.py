"""
tasks.py — REST API Endpoints for Role-Based Task Management and RBAC Workflows
"""

from datetime import datetime, timezone
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from storage.db import get_db
from storage.models import SystemTask, User, UserRole

router = APIRouter(prefix="/tasks", tags=["Tasks & RBAC Workflows"])


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    assigned_role: str
    priority: str
    status: str
    category: str
    station_code: Optional[str] = None
    assigned_to_name: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    total: int
    pending_count: int
    in_progress_count: int
    completed_count: int
    tasks: List[TaskResponse]


class TaskCreateRequest(BaseModel):
    title: str
    description: str
    assigned_role: str
    priority: str = "medium"
    status: str = "pending"
    category: str = "general"
    station_code: Optional[str] = None
    assigned_to_name: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_role: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    station_code: Optional[str] = None
    assigned_to_name: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None


@router.get("", response_model=TaskListResponse)
def list_tasks(
    role: Optional[str] = Query(None, description="Filter by assigned role: admin, data_quality_officer, field_technician, forecaster"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: pending, in_progress, completed"),
    priority: Optional[str] = Query(None, description="Filter by priority: critical, high, medium, low"),
    station_code: Optional[str] = Query(None, description="Filter by station code"),
    db: Session = Depends(get_db),
):
    """
    List all tasks divided by role with optional status, priority, and station filters.
    """
    query = db.query(SystemTask)

    if role and role != "all":
        query = query.filter(SystemTask.assigned_role == role)
    if status_filter and status_filter != "all":
        query = query.filter(SystemTask.status == status_filter)
    if priority and priority != "all":
        query = query.filter(SystemTask.priority == priority)
    if station_code and station_code != "all":
        query = query.filter(SystemTask.station_code == station_code)

    all_tasks = query.order_by(SystemTask.created_at.desc()).all()

    # Calculate status counts across all matching filter query
    pending_cnt = sum(1 for t in all_tasks if t.status == "pending")
    in_prog_cnt = sum(1 for t in all_tasks if t.status == "in_progress")
    comp_cnt = sum(1 for t in all_tasks if t.status == "completed")

    task_responses = [
        TaskResponse(
            id=str(t.id),
            title=t.title,
            description=t.description,
            assigned_role=t.assigned_role,
            priority=t.priority,
            status=t.status,
            category=t.category,
            station_code=t.station_code,
            assigned_to_name=t.assigned_to_name,
            due_date=t.due_date,
            notes=t.notes,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in all_tasks
    ]

    return TaskListResponse(
        total=len(task_responses),
        pending_count=pending_cnt,
        in_progress_count=in_prog_cnt,
        completed_count=comp_cnt,
        tasks=task_responses,
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new operational task assigned to an RBAC role.
    """
    now = datetime.now(timezone.utc)
    task = SystemTask(
        id=uuid.uuid4(),
        title=payload.title.strip(),
        description=payload.description.strip(),
        assigned_role=payload.assigned_role.strip(),
        priority=payload.priority.lower().strip(),
        status=payload.status.lower().strip(),
        category=payload.category.lower().strip(),
        station_code=payload.station_code.strip() if payload.station_code else None,
        assigned_to_name=payload.assigned_to_name.strip() if payload.assigned_to_name else None,
        due_date=payload.due_date.strip() if payload.due_date else None,
        notes=payload.notes.strip() if payload.notes else None,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return TaskResponse(
        id=str(task.id),
        title=task.title,
        description=task.description,
        assigned_role=task.assigned_role,
        priority=task.priority,
        status=task.status,
        category=task.category,
        station_code=task.station_code,
        assigned_to_name=task.assigned_to_name,
        due_date=task.due_date,
        notes=task.notes,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str,
    payload: TaskUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Update task status (e.g. claim, progress, mark complete) or task details.
    """
    try:
        t_uuid = uuid.UUID(task_id)
        task = db.query(SystemTask).filter(SystemTask.id == t_uuid).first()
    except ValueError:
        task = db.query(SystemTask).filter(SystemTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )

    if payload.title is not None:
        task.title = payload.title.strip()
    if payload.description is not None:
        task.description = payload.description.strip()
    if payload.assigned_role is not None:
        task.assigned_role = payload.assigned_role.strip()
    if payload.priority is not None:
        task.priority = payload.priority.lower().strip()
    if payload.status is not None:
        task.status = payload.status.lower().strip()
    if payload.category is not None:
        task.category = payload.category.lower().strip()
    if payload.station_code is not None:
        task.station_code = payload.station_code.strip() if payload.station_code else None
    if payload.assigned_to_name is not None:
        task.assigned_to_name = payload.assigned_to_name.strip() if payload.assigned_to_name else None
    if payload.due_date is not None:
        task.due_date = payload.due_date.strip() if payload.due_date else None
    if payload.notes is not None:
        task.notes = payload.notes.strip() if payload.notes else None

    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)

    return TaskResponse(
        id=str(task.id),
        title=task.title,
        description=task.description,
        assigned_role=task.assigned_role,
        priority=task.priority,
        status=task.status,
        category=task.category,
        station_code=task.station_code,
        assigned_to_name=task.assigned_to_name,
        due_date=task.due_date,
        notes=task.notes,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
):
    """
    Remove a completed or obsolete operational task.
    """
    try:
        t_uuid = uuid.UUID(task_id)
        task = db.query(SystemTask).filter(SystemTask.id == t_uuid).first()
    except ValueError:
        task = db.query(SystemTask).filter(SystemTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )

    db.delete(task)
    db.commit()
    return None
