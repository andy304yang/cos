import uuid
import threading
import os
from typing import Dict, Optional
from datetime import datetime
from app.models import TaskStatus


class Task:
    def __init__(self, task_id: str, user_id: str, filename: str, local_path: str, cos_key: str):
        self.task_id = task_id
        self.user_id = user_id
        self.filename = filename
        self.local_path = local_path
        self.cos_key = cos_key
        self.status = TaskStatus.PENDING
        self.instruction = ""
        self.result_cos_key = ""
        self.result_url = ""
        self.error = ""
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "filename": self.filename,
            "status": self.status.value,
            "instruction": self.instruction,
            "result_url": self.result_url,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class TaskManager:
    """简单的内存任务管理器（生产环境建议用 Redis）"""
    _lock = threading.Lock()
    _tasks: Dict[str, Task] = {}
    _user_tasks: Dict[str, list] = {}  # user_id -> [task_id, ...]

    @classmethod
    def create_task(cls, user_id: str, filename: str, local_path: str, cos_key: str) -> Task:
        task_id = str(uuid.uuid4())[:8]
        task = Task(task_id, user_id, filename, local_path, cos_key)
        with cls._lock:
            cls._tasks[task_id] = task
            if user_id not in cls._user_tasks:
                cls._user_tasks[user_id] = []
            cls._user_tasks[user_id].append(task_id)
        return task

    @classmethod
    def get_task(cls, task_id: str) -> Optional[Task]:
        return cls._tasks.get(task_id)

    @classmethod
    def get_user_tasks(cls, user_id: str) -> list:
        with cls._lock:
            task_ids = cls._user_tasks.get(user_id, [])
            return [cls._tasks[tid] for tid in task_ids if tid in cls._tasks]

    @classmethod
    def update_task(cls, task_id: str, **kwargs):
        with cls._lock:
            task = cls._tasks.get(task_id)
            if task:
                for k, v in kwargs.items():
                    setattr(task, k, v)
                task.updated_at = datetime.now()

    @classmethod
    def delete_task_files(cls, task_id: str):
        """清理任务相关的本地文件"""
        task = cls._tasks.get(task_id)
        if not task:
            return
        for path in [task.local_path]:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
