from pydantic import BaseModel
from typing import Optional
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class UploadResponse(BaseModel):
    task_id: str
    user_id: str
    filename: str
    status: TaskStatus
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    user_id: str
    status: TaskStatus
    filename: str
    instruction: str
    result_url: Optional[str] = None
    error: Optional[str] = None


class ProcessRequest(BaseModel):
    task_id: str
    user_id: str
    instruction: str
