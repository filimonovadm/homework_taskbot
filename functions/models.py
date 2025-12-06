from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

# Status constants
STATUS_NEW = "новая"
STATUS_IN_PROGRESS = "в работе"
STATUS_DONE = "выполнена"
STATUS_ARCHIVED = "архивирована"

@dataclass
class Comment:
    text: str
    author: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class Task:
    id: str
    chat_id: int
    text: str
    created_by: str
    task_number: Optional[int] = None
    status: str = STATUS_NEW
    assigned_to: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    accumulated_time_seconds: float = 0.0
    rating: Optional[int] = None
    deadline_at: Optional[str] = None
    in_progress_at: Optional[str] = None
    completed_at: Optional[str] = None
    comments: List[Comment] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        comments_data = data.get("comments", [])
        comments = [Comment(**c) for c in comments_data]
        
        # Filter out keys that are not fields in the dataclass
        valid_keys = cls.__annotations__.keys()
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        
        # Manually handle comments since we already processed them
        if "comments" in filtered_data:
            del filtered_data["comments"]
            
        return cls(comments=comments, **filtered_data)

    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "chat_id": self.chat_id,
            "task_number": self.task_number,
            "text": self.text,
            "created_by": self.created_by,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at,
            "accumulated_time_seconds": self.accumulated_time_seconds,
            "rating": self.rating,
            "deadline_at": self.deadline_at,
            "in_progress_at": self.in_progress_at,
            "completed_at": self.completed_at,
            "comments": [{"text": c.text, "author": c.author, "created_at": c.created_at} for c in self.comments]
        }
        # Remove None values to keep Firestore documents clean (optional, but good practice)
        return {k: v for k, v in data.items() if v is not None}
