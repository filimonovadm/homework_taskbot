from telebot import types
from datetime import datetime, timedelta, timezone
from models import Task, STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_ARCHIVED, Comment
from typing import List

# Define a timezone for UTC+3 (Moscow time for example)
MOSCOW_TZ = timezone(timedelta(hours=3))

# --- Constants ---
BTN_CREATE = "❇️ Создать задачу"
BTN_OPEN = "🔥 Открытые"
BTN_IN_PROGRESS = "👨‍💻 В работе"
BTN_DONE = "✅ Готово"
BTN_ARCHIVED = "🗄️ Архив"
BTN_STATISTICS = "📊"
BTN_HELP = "❓"

def convert_utc_to_local(utc_dt: datetime) -> datetime:
    """Converts a UTC datetime object to Moscow timezone (UTC+3)."""
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(MOSCOW_TZ)

def get_task_keyboard(task: Task):
    """Создает инлайн-клавиатуру для задачи в зависимости от ее статуса."""
    keyboard = types.InlineKeyboardMarkup()
    if task.status == STATUS_NEW:
        button_take = types.InlineKeyboardButton("▶️ В работу", callback_data=f"take_{task.id}")
        button_deadline = types.InlineKeyboardButton("🗓️ Срок", callback_data=f"set_deadline_{task.id}")
        button_delete = types.InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{task.id}")
        keyboard.add(button_take, button_deadline, button_delete)
    elif task.status == STATUS_IN_PROGRESS:
        button_done = types.InlineKeyboardButton("✅ Завершить", callback_data=f"done_{task.id}")
        button_reopen_new = types.InlineKeyboardButton("🔄 Отменить", callback_data=f"reopen_new_{task.id}")
        button_add_comment = types.InlineKeyboardButton("💬 Добавить коммент", callback_data=f"add_comment_{task.id}")
        keyboard.add(button_done, button_reopen_new)
        keyboard.add(button_add_comment)
    elif task.status == STATUS_DONE:
        button_archive = types.InlineKeyboardButton("🗄️ Архивировать", callback_data=f"archive_{task.id}")
        button_reopen_in_progress = types.InlineKeyboardButton("⏪ Вернуть в работу", callback_data=f"reopen_in_progress_{task.id}")
        keyboard.add(button_archive, button_reopen_in_progress)

        # Allow rating only if the task has not been rated yet.
        if task.rating is None:
            button_rate = types.InlineKeyboardButton("⭐ Оценить", callback_data=f"rate_{task.id}")
            keyboard.add(button_rate)
    return keyboard

def format_accumulated_time(total_seconds: float) -> str:
    """Formats a total number of seconds into a human-readable string."""
    if total_seconds < 0:
        total_seconds = 0

    total_seconds = int(total_seconds)
    days = total_seconds // 86400
    seconds_remaining = total_seconds % 86400
    hours = seconds_remaining // 3600
    minutes = (seconds_remaining % 3600) // 60

    def pluralize(number, one, few, many):
        if number % 10 == 1 and number % 100 != 11:
            return one
        elif 2 <= number % 10 <= 4 and (number % 100 < 10 or number % 100 >= 20):
            return few
        else:
            return many

    parts = []
    if days > 0:
        parts.append(f"{days} {pluralize(days, 'день', 'дня', 'дней')}")
    if hours > 0:
        parts.append(f"{hours} {pluralize(hours, 'час', 'часа', 'часов')}")
    if minutes > 0 or not parts:
        parts.append(f"{minutes} {pluralize(minutes, 'минута', 'минуты', 'минут')}")

    if not parts:
        return "Затраченное время: 0 минут"

    return f"Затраченное время: {' '.join(parts)}"

def format_task_message(task: Task) -> str:
    """Форматирует текст сообщения для задачи."""
    status_emoji = {
        STATUS_NEW: "🆕",
        STATUS_IN_PROGRESS: "👨‍💻",
        STATUS_DONE: "✅",
        STATUS_ARCHIVED: "🗄️" # Added archived emoji just in case
    }

    task_number_str = f"*(Задача #{task.task_number})* " if task.task_number else ""

    text = f"{status_emoji.get(task.status, '')} {task_number_str}*{task.text}*\n`Статус: {task.status}`"

    if task.assigned_to:
        text += f"\n`Исполнитель: {task.assigned_to}`"

    if task.created_by:
        text += f"\n`Создана: {task.created_by}`"

    if task.created_at:
        try:
            created_datetime = datetime.fromisoformat(task.created_at)
            local_created_datetime = convert_utc_to_local(created_datetime)
            text += f"\n`Дата создания: {local_created_datetime.strftime('%d.%m.%Y %H:%M')}`"
        except ValueError:
            text += f"\n`Дата создания: {task.created_at}`"

    if task.deadline_at:
        try:
            deadline_datetime = datetime.fromisoformat(task.deadline_at)
            local_deadline_datetime = convert_utc_to_local(deadline_datetime)
            text += f"\n`Срок: {local_deadline_datetime.strftime('%d.%m.%Y')}`"
        except ValueError:
            text += f"\n`Срок: {task.deadline_at}`"

    # --- Completion Date (only show if actually completed) ---
    if task.completed_at:
        try:
            completed_datetime = datetime.fromisoformat(task.completed_at)
            local_completed_datetime = convert_utc_to_local(completed_datetime)
            text += f"\n`Дата завершения: {local_completed_datetime.strftime('%d.%m.%Y %H:%M')}`"
        except ValueError:
            text += f"\n`Дата завершения: {task.completed_at}`"

    # --- Time Spent Logic ---
    time_spent_str = ""
    accumulated_seconds = task.accumulated_time_seconds

    if task.status == STATUS_DONE and accumulated_seconds > 0:
        # For done tasks, show the final accumulated time
        time_spent_str = format_accumulated_time(accumulated_seconds)

    if time_spent_str:
        text += f"\n`{time_spent_str}`"

    # --- Rating ---
    if task.rating is not None:
        stars = "⭐" * task.rating
        text += f"\n`Оценка: {stars}`"

    # --- Comments ---
    if task.comments:
        text += "\n\n*Комментарии:*"
        for comment in task.comments:
            try:
                # Assuming comment is a Comment object or dict depending on migration status
                # but we are moving to Objects.
                # However, repo might return dicts if not careful.
                # Models.py handles conversion.
                comment_dt = datetime.fromisoformat(comment.created_at)
                local_comment_dt = convert_utc_to_local(comment_dt)
                date_str = local_comment_dt.strftime('%d.%m %H:%M')
            except ValueError:
                date_str = "??"
            text += f"\n— {comment.text} \n  `({comment.author}, {date_str})`"

    return text

def get_main_keyboard(tasks: List[Task]):
    """Создает основную клавиатуру с количеством задач на кнопках."""
    try:
        count_open = sum(1 for t in tasks if t.status == STATUS_NEW)
        count_in_progress = sum(1 for t in tasks if t.status == STATUS_IN_PROGRESS)
        count_done = sum(1 for t in tasks if t.status == STATUS_DONE)
        count_archived = sum(1 for t in tasks if t.status == STATUS_ARCHIVED)
    except Exception as e:
        print(f"Error fetching tasks for keyboard counts: {e}")
        count_open = count_in_progress = count_done = count_archived = 0

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    button_create_task = types.KeyboardButton(BTN_CREATE)
    button_all_tasks = types.KeyboardButton(f"{BTN_OPEN} ({count_open})")
    button_in_progress_tasks = types.KeyboardButton(f"{BTN_IN_PROGRESS} ({count_in_progress})")
    button_done_tasks = types.KeyboardButton(BTN_DONE)
    button_archived_tasks = types.KeyboardButton(BTN_ARCHIVED)
    button_statistics = types.KeyboardButton(BTN_STATISTICS)
    button_help = types.KeyboardButton(BTN_HELP)

    keyboard.row(button_create_task)
    keyboard.row(button_all_tasks, button_in_progress_tasks)
    keyboard.row(button_done_tasks, button_archived_tasks, button_statistics, button_help)
    return keyboard
