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

def add_task(text: str) -> Dict[str, Any]:
    """Adds a new task to the Firestore collection."""
    db = firestore.client()
    task_id = str(uuid.uuid4())
    new_task = {
        "id": task_id,
        "text": text,
        "status": STATUS_NEW,
        "created_by": None,
        "assigned_to": None,
        "created_at": datetime.now().isoformat()  # Add timestamp
    }
    db.collection(TASKS_COLLECTION).document(task_id).set(new_task)
    return new_task

def get_tasks(status: str | None = None) -> List[Dict[str, Any]]:
    """Returns a list of tasks, optionally filtered by status or for open tasks."""
    db = firestore.client()
    tasks = []
    
    query = db.collection(TASKS_COLLECTION)
    if status == "open": # For "Открытые задачи"
        query = query.where("status", "==", STATUS_NEW)
    elif status: # For specific statuses like "в работе", "выполнена", "архивирована"
        query = query.where("status", "==", status)
    
    docs = query.stream()
    for doc in docs:
        tasks.append(doc.to_dict())
    return tasks

def get_all_tasks() -> List[Dict[str, Any]]:
    """Returns all tasks, regardless of status."""
    return get_tasks(status=None)

def get_task_by_id(task_id: str) -> Dict[str, Any] | None:
    """Finds a task by its unique ID."""
    db = firestore.client()
    doc = db.collection(TASKS_COLLECTION).document(task_id).get()
    if doc.exists:
        return doc.to_dict()
    return None

def update_task_status(task_id: str, new_status: str, user_info: Any) -> bool:
    """Updates the status of a task and who it's assigned to."""
    db = firestore.client()
    doc_ref = db.collection(TASKS_COLLECTION).document(task_id)
    doc = doc_ref.get()
    if doc.exists:
        update_data = {"status": new_status}
        if new_status == STATUS_IN_PROGRESS and user_info:
            update_data["assigned_to"] = f"{user_info.first_name} (@{user_info.username})"
        
        if new_status == STATUS_DONE:
            update_data["completed_at"] = datetime.now().isoformat()
        elif doc.to_dict().get("status") == STATUS_DONE and new_status != STATUS_DONE:
            # If status is changing from DONE to something else, remove completed_at
            update_data["completed_at"] = firestore.DELETE_FIELD
            
        doc_ref.update(update_data)
        return True
    return False