from firebase_admin import firestore
import uuid
from datetime import datetime
from typing import List, Dict, Any

TASKS_COLLECTION = "tasks"
USER_STATES_COLLECTION = "user_states"
CHAT_COUNTERS_COLLECTION = "chat_counters"

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


@firestore.transactional
def _get_next_task_number_transaction(transaction, counter_ref):
    """Transaction to get and increment the task number."""
    snapshot = counter_ref.get(transaction=transaction)
    current_number = snapshot.get("count") if snapshot.exists else 0
    next_number = current_number + 1
    transaction.set(counter_ref, {"count": next_number})
    return next_number


def get_next_task_number(chat_id: int) -> int:
    """
    Gets the next available task number for a given chat, incrementing it atomically.
    """
    db = firestore.client()
    counter_ref = db.collection(CHAT_COUNTERS_COLLECTION).document(str(chat_id))
    transaction = db.transaction()
    return _get_next_task_number_transaction(transaction, counter_ref)


def add_task(chat_id: int, text: str, created_by: str, deadline_at: str | None = None) -> Dict[str, Any]:
    """Adds a new task to the Firestore collection for a specific chat."""
    db = firestore.client()
    task_id = str(uuid.uuid4())
    task_number = get_next_task_number(chat_id)
    new_task = {
        "id": task_id,
        "chat_id": chat_id,
        "task_number": task_number,
        "text": text,
        "status": STATUS_NEW,
        "created_by": created_by,
        "assigned_to": None,
        "created_at": datetime.now().isoformat(),
        "accumulated_time_seconds": 0,
        "rating": None,
    }
    if deadline_at:
        new_task["deadline_at"] = deadline_at
    db.collection(TASKS_COLLECTION).document(task_id).set(new_task)
    return new_task


def get_tasks(chat_id: int, status: str | None = None) -> List[Dict[str, Any]]:
    """Returns a list of tasks for a specific chat, optionally filtered by status."""
    db = firestore.client()
    tasks = []
    query = db.collection(TASKS_COLLECTION).where("chat_id", "==", chat_id)
    if status == "open":
        query = query.where("status", "in", [STATUS_NEW, STATUS_IN_PROGRESS])
    elif status:
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


def update_task_deadline(task_id: str, deadline_at: str) -> bool:
    """Updates the deadline of a task."""
    db = firestore.client()
    doc_ref = db.collection(TASKS_COLLECTION).document(task_id)
    if doc_ref.get().exists:
        doc_ref.update({"deadline_at": deadline_at})
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
        STATUS_ARCHIVED: [],
    }
    if new_status not in allowed_transitions.get(current_status, []):
        print(f"Invalid status transition from {current_status} to {new_status} for task {task_id}")
        return False
    update_data["status"] = new_status
    now = datetime.now()
    if current_status == STATUS_IN_PROGRESS and new_status != STATUS_IN_PROGRESS:
        in_progress_at_str = current_task.get("in_progress_at")
        if in_progress_at_str:
            try:
                in_progress_dt = datetime.fromisoformat(in_progress_at_str)
                session_seconds = (now - in_progress_dt).total_seconds()
                current_accumulated = current_task.get("accumulated_time_seconds", 0)
                update_data["accumulated_time_seconds"] = current_accumulated + session_seconds
                update_data["in_progress_at"] = firestore.DELETE_FIELD
            except (ValueError, TypeError) as e:
                print(f"Could not parse in_progress_at '{in_progress_at_str}': {e}")
    if new_status == STATUS_IN_PROGRESS:
        update_data["in_progress_at"] = now.isoformat()
        if user_info:
            update_data["assigned_to"] = f"{user_info.first_name} (@{user_info.username})"
        if "completed_at" in current_task:
            update_data["completed_at"] = firestore.DELETE_FIELD
    elif new_status == STATUS_DONE:
        update_data["completed_at"] = now.isoformat()
        if "rating" in current_task:
            update_data["rating"] = None
    elif new_status == STATUS_NEW:
        if "assigned_to" in current_task:
            update_data["assigned_to"] = firestore.DELETE_FIELD
        if "completed_at" in current_task:
            update_data["completed_at"] = firestore.DELETE_FIELD
    doc_ref.update(update_data)
    return True


def rate_task(task_id: str, rating: int) -> bool:
    """Sets the rating for a completed task."""
    db = firestore.client()
    doc_ref = db.collection(TASKS_COLLECTION).document(task_id)
    if not 1 <= rating <= 5:
        print(f"Invalid rating value: {rating}. Must be between 1 and 5.")
        return False
    task = doc_ref.get()
    if task.exists and task.to_dict().get("status") == STATUS_DONE:
        doc_ref.update({"rating": rating})
        return True
    print(f"Task {task_id} not found or not in 'done' status.")
    return False