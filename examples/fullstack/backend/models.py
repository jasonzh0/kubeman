"""Pydantic models for request/response validation."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TodoCreate(BaseModel):
    """Model for creating a new todo."""

    title: str


class TodoResponse(BaseModel):
    """Model for todo response."""

    id: int
    title: str
    completed: bool
    created_at: datetime

    class Config:
        from_attributes = True
