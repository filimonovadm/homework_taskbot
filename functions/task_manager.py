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
        "created_at": datetime.now().isoformat()  # Add timestamp
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
    """Updates the status of a task and who it's assigned to."""
    db = firestore.client()
    doc_ref = db.collection(TASKS_COLLECTION).document(task_id)
    doc = doc_ref.get()
    if doc.exists:
        current_task = doc.to_dict()
        current_status = current_task.get("status")
        update_data = {}

        # Define allowed transitions
        allowed_transitions = {
            STATUS_NEW: [STATUS_IN_PROGRESS, STATUS_ARCHIVED],
            STATUS_IN_PROGRESS: [STATUS_NEW, STATUS_DONE, STATUS_ARCHIVED],
            STATUS_DONE: [STATUS_IN_PROGRESS, STATUS_ARCHIVED],
            STATUS_ARCHIVED: [] # Archived tasks cannot change status
        }

        if new_status not in allowed_transitions.get(current_status, []):
            print(f"Invalid status transition from {current_status} to {new_status} for task {task_id}")
            return False

        update_data["status"] = new_status

        if new_status == STATUS_IN_PROGRESS and user_info:
            update_data["assigned_to"] = f"{user_info.first_name} (@{user_info.username})"
        elif new_status == STATUS_NEW:
            # If moving back to NEW, clear assigned_to
            update_data["assigned_to"] = firestore.DELETE_FIELD
        
        if new_status == STATUS_DONE:
            update_data["completed_at"] = datetime.now().isoformat()
        elif current_status == STATUS_DONE and new_status != STATUS_DONE:
            # If status is changing from DONE to something else (e.g., IN_PROGRESS), remove completed_at
            update_data["completed_at"] = firestore.DELETE_FIELD
            
        doc_ref.update(update_data)
        return True
    return False