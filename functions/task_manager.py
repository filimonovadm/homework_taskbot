from firebase_admin import firestore
import uuid
from datetime import datetime
from typing import List, Dict, Any

TASKS_COLLECTION = "tasks"
USER_STATES_COLLECTION = "user_states"

# Status constants
STATUS_NEW = "новая"
STATUS_IN_PROGRESS = "в работе"
STATUS_DONE = "выполнена"
STATUS_ARCHIVED = "архивирована"

def set_user_state(user_id: int, state: str, data: Dict[str, Any] = None):
    """Sets the conversation state for a user."""
    db = firestore.client()
    doc_ref = db.collection(USER_STATES_COLLECTION).document(str(user_id))
    doc_ref.set({"state": state, "data": data or {}})

def get_user_state(user_id: int) -> Dict[str, Any] | None:
    """Gets the current conversation state for a user."""
    db = firestore.client()
    doc = db.collection(USER_STATES_COLLECTION).document(str(user_id)).get()
    if doc.exists:
        return doc.to_dict()
    return None

def add_task(chat_id: int, text: str) -> Dict[str, Any]:
    """Adds a new task to the Firestore collection for a specific chat."""
    db = firestore.client()
    task_id = str(uuid.uuid4())
    new_task = {
        "id": task_id,
        "chat_id": chat_id,
        "text": text,
        "status": STATUS_NEW,
        "created_by": None,
        "assigned_to": None,
        "created_at": datetime.now().isoformat(),
        "accumulated_time_seconds": 0,  # Initialize accumulator
    }
    db.collection(TASKS_COLLECTION).document(task_id).set(new_task)
    return new_task

def get_tasks(chat_id: int, status: str | None = None) -> List[Dict[str, Any]]:
    """Returns a list of tasks for a specific chat, optionally filtered by status."""
    db = firestore.client()
    tasks = []
    
    query = db.collection(TASKS_COLLECTION).where("chat_id", "==", chat_id)
    
    if status == "open": # For "Открытые задачи"
        query = query.where("status", "==", STATUS_NEW)
    elif status: # For specific statuses like "в работе", "выполнена", "архивирована"
        query = query.where("status", "==", status)
    
    docs = query.stream()
    for doc in docs:
        tasks.append(doc.to_dict())
    return tasks

def get_all_tasks(chat_id: int) -> List[Dict[str, Any]]:
    """Returns all tasks for a specific chat, regardless of status."""
    return get_tasks(chat_id=chat_id, status=None)

def get_task_by_id(task_id: str) -> Dict[str, Any] | None:
    """Finds a task by its unique ID."""
    db = firestore.client()
    doc = db.collection(TASKS_COLLECTION).document(task_id).get()
    if doc.exists:
        return doc.to_dict()
    return None

def delete_task(task_id: str) -> bool:
    """Deletes a task by its unique ID."""
    db = firestore.client()
    doc_ref = db.collection(TASKS_COLLECTION).document(task_id)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.delete()
        return True
    return False

def update_task_status(task_id: str, new_status: str, user_info: Any) -> bool:
    """Updates the status of a task and manages accumulated time."""
    db = firestore.client()
    doc_ref = db.collection(TASKS_COLLECTION).document(task_id)
    doc = doc_ref.get()

    if not doc.exists:
        return False

    current_task = doc.to_dict()
    current_status = current_task.get("status")
    update_data = {}

    allowed_transitions = {
        STATUS_NEW: [STATUS_IN_PROGRESS, STATUS_ARCHIVED],
        STATUS_IN_PROGRESS: [STATUS_NEW, STATUS_DONE, STATUS_ARCHIVED],
        STATUS_DONE: [STATUS_IN_PROGRESS, STATUS_ARCHIVED],
        STATUS_ARCHIVED: []
    }

    if new_status not in allowed_transitions.get(current_status, []):
        print(f"Invalid status transition from {current_status} to {new_status} for task {task_id}")
        return False

    update_data["status"] = new_status
    now = datetime.now()

    # --- Handle leaving a state ---
    if current_status == STATUS_IN_PROGRESS and new_status != STATUS_IN_PROGRESS:
        # Task is moving OUT of 'in progress'. Finalize the session time.
        in_progress_at_str = current_task.get("in_progress_at")
        if in_progress_at_str:
            try:
                in_progress_dt = datetime.fromisoformat(in_progress_at_str)
                session_seconds = (now - in_progress_dt).total_seconds()
                
                current_accumulated = current_task.get("accumulated_time_seconds", 0)
                update_data["accumulated_time_seconds"] = current_accumulated + session_seconds
                
                # Clean up the session start time
                update_data["in_progress_at"] = firestore.DELETE_FIELD
            except (ValueError, TypeError) as e:
                print(f"Could not parse in_progress_at '{in_progress_at_str}': {e}")
    
    # --- Handle entering a state ---
    if new_status == STATUS_IN_PROGRESS:
        update_data["in_progress_at"] = now.isoformat()
        if user_info:
            update_data["assigned_to"] = f"{user_info.first_name} (@{user_info.username})"
        # If reopening from done, clear completion time
        if "completed_at" in current_task:
            update_data["completed_at"] = firestore.DELETE_FIELD

    elif new_status == STATUS_DONE:
        update_data["completed_at"] = now.isoformat()

    elif new_status == STATUS_NEW:
        # Unassign user and clear completion time.
        # As per user request, accumulated time is NOT cleared.
        if "assigned_to" in current_task:
            update_data["assigned_to"] = firestore.DELETE_FIELD
        if "completed_at" in current_task:
            update_data["completed_at"] = firestore.DELETE_FIELD
    
    doc_ref.update(update_data)
    return True