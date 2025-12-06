from firebase_admin import firestore
from typing import List, Optional, Dict, Any
from models import Task, STATUS_NEW, STATUS_IN_PROGRESS

TASKS_COLLECTION = "tasks"
USER_STATES_COLLECTION = "user_states"
CHAT_COUNTERS_COLLECTION = "chat_counters"

class TaskRepository:
    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = firestore.client()
        return self._db

    def get_user_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Gets the current conversation state for a user."""
        doc = self.db.collection(USER_STATES_COLLECTION).document(str(user_id)).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def set_user_state(self, user_id: int, state: str, data: Dict[str, Any] = None):
        """Sets the conversation state for a user."""
        doc_ref = self.db.collection(USER_STATES_COLLECTION).document(str(user_id))
        doc_ref.set({"state": state, "data": data or {}})

    @staticmethod
    @firestore.transactional
    def _get_next_task_number_transaction(transaction, counter_ref):
        """Transaction to get and increment the task number."""
        snapshot = counter_ref.get(transaction=transaction)
        current_number = snapshot.get("count") if snapshot.exists else 0
        next_number = current_number + 1
        transaction.set(counter_ref, {"count": next_number})
        return next_number

    def get_next_task_number(self, chat_id: int) -> int:
        """Gets the next available task number for a given chat."""
        # For transactions, we need the client to create transaction, but here we pass it
        # Actually transaction is created from db.transaction()
        counter_ref = self.db.collection(CHAT_COUNTERS_COLLECTION).document(str(chat_id))
        transaction = self.db.transaction()
        return self._get_next_task_number_transaction(transaction, counter_ref)

    def add_task(self, task: Task) -> None:
        """Saves a new task to Firestore."""
        self.db.collection(TASKS_COLLECTION).document(task.id).set(task.to_dict())

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieves a task by ID."""
        doc = self.db.collection(TASKS_COLLECTION).document(task_id).get()
        if doc.exists:
            return Task.from_dict(doc.to_dict())
        return None

    def get_tasks_by_chat(self, chat_id: int, status: Optional[str] = None) -> List[Task]:
        """Retrieves tasks for a chat, optionally filtered by status."""
        query = self.db.collection(TASKS_COLLECTION).where("chat_id", "==", chat_id)
        
        if status == "open":
            query = query.where("status", "in", [STATUS_NEW, STATUS_IN_PROGRESS])
        elif status:
            query = query.where("status", "==", status)
            
        docs = query.stream()
        return [Task.from_dict(doc.to_dict()) for doc in docs]

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """Updates specific fields of a task."""
        doc_ref = self.db.collection(TASKS_COLLECTION).document(task_id)
        # Check existence first strictly speaking, or just try update
        # For consistency with old code, we might want to check existence
        if not doc_ref.get().exists:
            return False
        
        # Handle field deletions (mapped from None in logic if needed, but Firestore uses DELETE_FIELD)
        doc_ref.update(updates)
        return True

    def delete_task(self, task_id: str) -> bool:
        """Deletes a task."""
        doc_ref = self.db.collection(TASKS_COLLECTION).document(task_id)
        if doc_ref.get().exists:
            doc_ref.delete()
            return True
        return False
        
    def add_comment(self, task_id: str, comment: Dict[str, Any]) -> bool:
        """Atomically adds a comment to a task."""
        doc_ref = self.db.collection(TASKS_COLLECTION).document(task_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.update({"comments": firestore.firestore.ArrayUnion([comment])})
        return True
