import json
import os
import uuid
from typing import List, Dict, Any

TASKS_FILE = "tasks.json"

# Определяем возможные статусы задач
STATUS_NEW = "новая"
STATUS_IN_PROGRESS = "в работе"
STATUS_DONE = "выполнена"


def _load_tasks() -> List[Dict[str, Any]]:
    """Загружает задачи из JSON-файла. Если файл не существует, возвращает пустой список."""
    if not os.path.exists(TASKS_FILE):
        return []
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            tasks = json.load(f)
            return tasks
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save_tasks(tasks: List[Dict[str, Any]]):
    """Сохраняет список задач в JSON-файл."""
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)


def add_task(text: str) -> Dict[str, Any]:
    """
    Добавляет новую задачу в список.
    """
    tasks = _load_tasks()
    new_task = {
        "id": str(uuid.uuid4()),
        "text": text,
        "status": STATUS_NEW,
        "created_by": None, # Можно будет добавить, кто создал
        "assigned_to": None, # Можно будет добавить, кто взял в работу
    }
    tasks.append(new_task)
    _save_tasks(tasks)
    return new_task

def get_active_tasks() -> List[Dict[str, Any]]:
    """Возвращает список задач, которые не выполнены."""
    tasks = _load_tasks()
    return [task for task in tasks if task.get("status") != STATUS_DONE]

def get_task_by_id(task_id: str) -> Dict[str, Any] | None:
    """Находит задачу по ее уникальному идентификатору."""
    tasks = _load_tasks()
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return None

def update_task_status(task_id: str, new_status: str, user_info: Any) -> bool:
    """
    Обновляет статус задачи и информацию о том, кто ее взял в работу.
    """
    tasks = _load_tasks()
    task_found = False
    for task in tasks:
        if task.get("id") == task_id:
            task["status"] = new_status
            # Сохраняем информацию о пользователе, который изменил статус
            if new_status == STATUS_IN_PROGRESS:
                task["assigned_to"] = f"{user_info.first_name} (@{user_info.username})"
            task_found = True
            break
    
    if task_found:
        _save_tasks(tasks)
        
    return task_found
