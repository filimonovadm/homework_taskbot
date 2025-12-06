from firebase_admin import firestore
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from models import Task, STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_ARCHIVED
from repositories import TaskRepository

# Initialize Repository
repo = TaskRepository()

# Status constants (re-exported for compatibility)
STATUS_NEW = STATUS_NEW
STATUS_IN_PROGRESS = STATUS_IN_PROGRESS
STATUS_DONE = STATUS_DONE
STATUS_ARCHIVED = STATUS_ARCHIVED


def set_user_state(user_id: int, state: str, data: Dict[str, Any] = None):
    """Sets the conversation state for a user."""
    repo.set_user_state(user_id, state, data)


def get_user_state(user_id: int) -> Dict[str, Any] | None:
    """Gets the current conversation state for a user."""
    return repo.get_user_state(user_id)


def get_next_task_number(chat_id: int) -> int:
    """Gets the next available task number for a given chat."""
    return repo.get_next_task_number(chat_id)


def add_task(chat_id: int, text: str, created_by: str, deadline_at: str | None = None) -> Task:
    """Adds a new task to the Firestore collection for a specific chat."""
    task_id = str(uuid.uuid4())
    task_number = repo.get_next_task_number(chat_id)
    
    new_task = Task(
        id=task_id,
        chat_id=chat_id,
        task_number=task_number,
        text=text,
        created_by=created_by,
        deadline_at=deadline_at
    )
    
    repo.add_task(new_task)
    return new_task


def get_tasks(chat_id: int, status: str | None = None) -> List[Task]:
    """Returns a list of tasks for a specific chat, optionally filtered by status."""
    return repo.get_tasks_by_chat(chat_id, status)


def get_all_tasks(chat_id: int) -> List[Task]:
    """Returns all tasks for a specific chat, regardless of status."""
    return repo.get_tasks_by_chat(chat_id, None)


def get_task_by_id(task_id: str) -> Task | None:
    """Finds a task by its unique ID."""
    return repo.get_task(task_id)


def delete_task(task_id: str) -> bool:
    """Deletes a task by its unique ID."""
    return repo.delete_task(task_id)


def update_task_deadline(task_id: str, deadline_at: str) -> bool:
    """Updates the deadline of a task."""
    return repo.update_task(task_id, {"deadline_at": deadline_at})


def update_task_status(task_id: str, new_status: str, user_name: str, user_handle: str = "") -> bool:
    """
    Updates the status of a task and manages accumulated time.
    
    Args:
        task_id: The ID of the task.
        new_status: The new status to transition to.
        user_name: Display name of the user performing the action.
        user_handle: Optional handle (e.g. @username) for display.
    """
    current_task = repo.get_task(task_id)
    if not current_task:
        return False

    current_status = current_task.status
    update_data = {}
    
    allowed_transitions = {
        STATUS_NEW: [STATUS_IN_PROGRESS, STATUS_ARCHIVED],
        STATUS_IN_PROGRESS: [STATUS_NEW, STATUS_DONE, STATUS_ARCHIVED],
        STATUS_DONE: [STATUS_IN_PROGRESS, STATUS_ARCHIVED],
        STATUS_ARCHIVED: [],
    }

    if new_status not in allowed_transitions.get(current_status, []):
        print(f"Invalid status transition from {current_status} to {new_status} for task {task_id}")
        return False

    update_data["status"] = new_status
    now = datetime.now()

    # Time tracking logic
    if current_status == STATUS_IN_PROGRESS and new_status != STATUS_IN_PROGRESS:
        in_progress_at_str = current_task.in_progress_at
        if in_progress_at_str:
            try:
                in_progress_dt = datetime.fromisoformat(in_progress_at_str)
                session_seconds = (now - in_progress_dt).total_seconds()
                current_accumulated = current_task.accumulated_time_seconds or 0
                update_data["accumulated_time_seconds"] = current_accumulated + session_seconds
                update_data["in_progress_at"] = firestore.DELETE_FIELD
            except (ValueError, TypeError) as e:
                print(f"Could not parse in_progress_at '{in_progress_at_str}': {e}")

    # Status specific updates
    if new_status == STATUS_IN_PROGRESS:
        update_data["in_progress_at"] = now.isoformat()
        if current_status == STATUS_NEW and user_name:
            # Format: "Name (@handle)" or just "Name"
            assigned = f"{user_name} ({user_handle})" if user_handle else user_name
            update_data["assigned_to"] = assigned
        
        if current_task.completed_at:
             update_data["completed_at"] = firestore.DELETE_FIELD

    elif new_status == STATUS_DONE:
        update_data["completed_at"] = now.isoformat()
        if current_task.rating is not None:
            update_data["rating"] = None # Reset rating if moved back to done? Or just ensure it's clear.

    elif new_status == STATUS_NEW:
        if current_task.assigned_to:
            update_data["assigned_to"] = firestore.DELETE_FIELD
        if current_task.completed_at:
            update_data["completed_at"] = firestore.DELETE_FIELD

    return repo.update_task(task_id, update_data)


def rate_task(task_id: str, rating: int) -> bool:
    """Sets the rating for a completed task."""
    if not 1 <= rating <= 5:
        print(f"Invalid rating value: {rating}. Must be between 1 and 5.")
        return False
    
    task = repo.get_task(task_id)
    if task and task.status == STATUS_DONE:
        return repo.update_task(task_id, {"rating": rating})
    
    print(f"Task {task_id} not found or not in 'done' status.")
    return False


def add_comment_to_task(task_id: str, comment_text: str, author: str) -> bool:
    """Adds a comment to a task."""
    comment = {
        "text": comment_text,
        "author": author,
        "created_at": datetime.now().isoformat()
    }
    return repo.add_comment(task_id, comment)