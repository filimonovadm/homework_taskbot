from firebase_admin import firestore
import uuid
from datetime import datetime
from typing import List, Dict, Any

TASKS_COLLECTION = "tasks"

# Status constants
STATUS_NEW = "новая"
STATUS_IN_PROGRESS = "в работе"
STATUS_DONE = "выполнена"

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

def get_active_tasks() -> List[Dict[str, Any]]:
    """Returns a list of tasks that are not done."""
    db = firestore.client()
    tasks = []
    docs = db.collection(TASKS_COLLECTION).where("status", "!=", STATUS_DONE).stream()
    for doc in docs:
        tasks.append(doc.to_dict())
    return tasks

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
        doc_ref.update(update_data)
        return True
    return False
