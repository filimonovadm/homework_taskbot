from firebase_functions import https_fn
from firebase_admin import initialize_app
import telebot
import os
import task_manager
from telebot import types
from datetime import datetime, timedelta, timezone
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP

# Initialize TeleBot
# Define a timezone for UTC+3 (Moscow time for example)
MOSCOW_TZ = timezone(timedelta(hours=3))

# --- Constants ---
HELP_TEXT = (
    "Привет! Я — ваш персональный менеджер задач. Я помогу вам отслеживать домашние дела и ничего не забывать.\n\n"
    "🤖 *Работа в групповых чатах:*\n"
    "Чтобы я мог эффективно работать в группе, мне нужны права администратора. Это позволит мне удалять сообщения и управлять задачами.\n\n"
    "⬇️ *Основные команды (клавиатура внизу):*\n"
    "  - `➕ Создать задачу`: Интерактивное создание новой задачи.\n"
    "  - `🔥 Открытые задачи`: Показывает все новые задачи, ожидающие исполнителя.\n"
    "  - `👨‍💻 Задачи в работе`: Список задач, которые уже кто-то выполняет.\n"
    "  - `✅ Задачи выполненные`: Показывает успешно завершенные задачи.\n"
    "  - `🗄️ Архивные задачи`: Список задач, которые были убраны в архив.\n"
    "  - `❓ Помощь`: Отображает это справочное сообщение.\n\n"
    "🔄 *Жизненный цикл задачи:*\n"
    "  - `🆕 Новая`: Задача только создана.\n"
    "  - `👨‍💻 В работе`: Кто-то взялся за выполнение.\n"
    "  - `✅ Выполнена`: Задача успешно завершена.\n"
    "  - `🗄️ Архивирована`: Задача убрана в архив.\n\n"
    "⚙️ *Действия с задачами (кнопки под сообщением):*\n"
    "  - `▶️ В работу`: Взять новую задачу на себя.\n"
    "  - `🗓️ Срок`: Установить или изменить дедлайн.\n"
    "  - `✅ Завершить`: Отметить задачу как выполненную.\n"
    "  - `🔄 Отменить`: Вернуть задачу из статуса `в работе` в `новые`.\n"
    "  - `⏪ Вернуть в работу`: Вернуть задачу из `выполненных` обратно `в работу`.\n"
    "  - `🗄️ Архивировать`: Убрать выполненную задачу в архив.\n"
    "  - `❌ Удалить`: Полностью удалить задачу (только для новых).\n\n"
    "⌨️ *Текстовые команды:*\n"
    "  - `/new <текст>`: Быстрое создание задачи без лишних вопросов.\n"
    "  - `/start` или `/help`: Вызов этой справки.\n\n"
    "Нажмите одну из кнопок, чтобы начать!"
)

def convert_utc_to_local(utc_dt: datetime) -> datetime:
    """Converts a UTC datetime object to Moscow timezone (UTC+3)."""
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(MOSCOW_TZ)

# --- Bot Handlers (copied from bot.py) ---

def get_task_keyboard(task_id: str, status: str):
    """Создает инлайн-клавиатуру для задачи в зависимости от ее статуса."""
    keyboard = types.InlineKeyboardMarkup()
    if status == task_manager.STATUS_NEW:
        button_take = types.InlineKeyboardButton("▶️ В работу", callback_data=f"take_{task_id}")
        button_deadline = types.InlineKeyboardButton("🗓️ Срок", callback_data=f"set_deadline_{task_id}")
        button_delete = types.InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{task_id}")
        keyboard.add(button_take, button_deadline, button_delete)
    elif status == task_manager.STATUS_IN_PROGRESS:
        button_done = types.InlineKeyboardButton("✅ Завершить", callback_data=f"done_{task_id}")
        button_reopen_new = types.InlineKeyboardButton("🔄 Отменить", callback_data=f"reopen_new_{task_id}")
        keyboard.add(button_done, button_reopen_new)
    elif status == task_manager.STATUS_DONE:
        button_archive = types.InlineKeyboardButton("🗄️ Архивировать", callback_data=f"archive_{task_id}")
        button_reopen_in_progress = types.InlineKeyboardButton("⏪ Вернуть в работу", callback_data=f"reopen_in_progress_{task_id}")
        keyboard.add(button_archive, button_reopen_in_progress)
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


def format_task_message(task: dict) -> str:
    """Форматирует текст сообщения для задачи."""
    status_emoji = {
        task_manager.STATUS_NEW: "🆕",
        task_manager.STATUS_IN_PROGRESS: "👨‍💻",
        task_manager.STATUS_DONE: "✅"
    }

    task_number_str = f"*(Задача #{task['task_number']})* " if task.get('task_number') else ""

    text = f"""{status_emoji.get(task['status'], '')} {task_number_str}*{task['text']}*
`Статус: {task['status']}`"""

    if task.get('assigned_to'):
        text += f"\n`Исполнитель: {task['assigned_to']}`"

    if task.get('created_by'):
        text += f"\n`Создана: {task['created_by']}`"

    if task.get('created_at'):
        try:
            created_datetime = datetime.fromisoformat(task['created_at'])
            local_created_datetime = convert_utc_to_local(created_datetime)
            text += f"\n`Дата создания: {local_created_datetime.strftime('%d.%m.%Y %H:%M')}`"
        except ValueError:
            text += f"\n`Дата создания: {task['created_at']}`"

    if task.get('deadline_at'):
        try:
            deadline_datetime = datetime.fromisoformat(task['deadline_at'])
            local_deadline_datetime = convert_utc_to_local(deadline_datetime)
            text += f"\n`Дедлайн: {local_deadline_datetime.strftime('%d.%m.%Y')}`"
        except ValueError:
            text += f"\n`Дедлайн: {task['deadline_at']}`"

    # --- Completion Date (only show if actually completed) ---
    if task.get('completed_at'):
        try:
            completed_datetime = datetime.fromisoformat(task['completed_at'])
            local_completed_datetime = convert_utc_to_local(completed_datetime)
            text += f"\n`Дата завершения: {local_completed_datetime.strftime('%d.%m.%Y %H:%M')}`"
        except ValueError:
            text += f"\n`Дата завершения: {task['completed_at']}`"

    # --- Time Spent Logic ---
    time_spent_str = ""
    accumulated_seconds = task.get("accumulated_time_seconds", 0)

    if task['status'] == task_manager.STATUS_DONE and accumulated_seconds > 0:
        # For done tasks, show the final accumulated time
        time_spent_str = format_accumulated_time(accumulated_seconds)

    if time_spent_str:
        text += f"\n`{time_spent_str}`"

    return text


def get_main_keyboard():
    """Создает основную клавиатуру с кнопками 'Создать задачу', 'Открытые задачи', 'Задачи в работе', 'Задачи выполненные', 'Архивные задачи' и 'Помощь'."""
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    button_create_task = types.KeyboardButton("➕ Создать задачу")
    button_all_tasks = types.KeyboardButton("🔥 Открытые задачи")
    button_in_progress_tasks = types.KeyboardButton("👨‍💻 Задачи в работе")
    button_done_tasks = types.KeyboardButton("✅ Задачи выполненные")
    button_archived_tasks = types.KeyboardButton("🗄️ Архивные задачи")
    button_help = types.KeyboardButton("❓ Помощь")
    keyboard.add(button_create_task, button_all_tasks)
    keyboard.add(button_in_progress_tasks, button_done_tasks)
    keyboard.add(button_archived_tasks, button_help)
    return keyboard

def handle_start_command(bot, message):
    """
    Handles the /start command.
    Sends a fresh welcome message and resets the message state. It cleans up the
    bot's previous messages but intentionally avoids deleting the user's own
    /start message to prevent timeouts in scenarios like a cleared chat.
    """
    chat_id = message.chat.id
    new_message_ids = []

    # Clean up the bot's previous messages.
    chat_state = task_manager.get_user_state(chat_id) or {}
    old_message_ids = chat_state.get("data", {}).get("last_task_list_message_ids", [])
    if old_message_ids:
        for msg_id in old_message_ids:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception as e:
                print(f"Could not delete message {msg_id}: {e}")

    # Send the welcome message
    try:
        sent_msg = bot.send_message(chat_id, HELP_TEXT, parse_mode='Markdown', reply_markup=get_main_keyboard())
        new_message_ids.append(sent_msg.message_id)
    except Exception as e:
        print(f"Error sending reply: {e}")
        err_msg = bot.send_message(chat_id, "Произошла ошибка при отображении справки.", reply_markup=get_main_keyboard())
        new_message_ids.append(err_msg.message_id)

    # Overwrite the state with the new message ID, effectively resetting it.
    current_data = chat_state.get("data", {})
    current_data['last_task_list_message_ids'] = new_message_ids
    task_manager.set_user_state(chat_id, "idle", data=current_data)

def send_welcome_and_help(bot, message):
    """Отправляет приветственное сообщение и справку по командам, очищая предыдущие сообщения."""
    chat_id = message.chat.id
    new_message_ids = []

    # 1. Clean up old messages
    chat_state = task_manager.get_user_state(chat_id) or {}
    old_message_ids = chat_state.get("data", {}).get("last_task_list_message_ids", [])
    if old_message_ids:
        for msg_id in old_message_ids:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception as e:
                print(f"Could not delete message {msg_id}: {e}")

    # Also delete the user's command message that triggered this
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Could not delete user command message: {e}")

    # 2. Send the help message
    try:
        sent_msg = bot.send_message(chat_id, HELP_TEXT, parse_mode='Markdown', reply_markup=get_main_keyboard())
        new_message_ids.append(sent_msg.message_id)
    except Exception as e:
        print(f"Error sending reply: {e}")
        err_msg = bot.send_message(chat_id, "Произошла ошибка при отображении справки.", reply_markup=get_main_keyboard())
        new_message_ids.append(err_msg.message_id)

    # 3. Save the new message ID to state
    current_data = chat_state.get("data", {})
    current_data['last_task_list_message_ids'] = new_message_ids
    task_manager.set_user_state(chat_id, "idle", data=current_data)

def add_new_task(bot, message):
    """Добавляет новую задачу и отправляет ее с клавиатурой, участвуя в очистке чата."""
    chat_id = message.chat.id
    new_message_ids = []

    # 1. Clean up old messages
    chat_state = task_manager.get_user_state(chat_id) or {}
    old_message_ids = chat_state.get("data", {}).get("last_task_list_message_ids", [])
    if old_message_ids:
        for msg_id in old_message_ids:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception as e:
                print(f"Could not delete message {msg_id}: {e}")

    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Could not delete user command message: {e}")

    try:
        task_text = message.text.split(maxsplit=1)[1]
    except IndexError:
        task_text = ""

    if not task_text:
        sent_msg = bot.send_message(chat_id, "Пожалуйста, укажите текст задачи после команды. Например: `/new Купить молоко`", reply_markup=get_main_keyboard())
        new_message_ids.append(sent_msg.message_id)
    else:
        try:
            user_info = message.from_user
            created_by_user = f"@{user_info.username}" if user_info.username else user_info.first_name or "Unknown User"
            new_task = task_manager.add_task(chat_id, task_text, created_by=created_by_user)
            reply_text = format_task_message(new_task)
            keyboard = get_task_keyboard(new_task['id'], new_task['status'])

            # Send "Success" message with the main keyboard, then the task with its inline keyboard
            msg1 = bot.send_message(chat_id, "Задача успешно создана!", reply_markup=get_main_keyboard())
            msg2 = bot.send_message(chat_id, reply_text, parse_mode='Markdown', reply_markup=keyboard)
            new_message_ids.extend([msg1.message_id, msg2.message_id])

        except Exception as e:
            print(f"Ошибка при добавлении задачи: {e}")
            err_msg = bot.send_message(chat_id, "Произошла ошибка при добавлении задачи.", reply_markup=get_main_keyboard())
            new_message_ids.append(err_msg.message_id)

    # Finally, save the new message IDs to the user's state
    final_data = chat_state.get("data", {})
    final_data['last_task_list_message_ids'] = new_message_ids
    task_manager.set_user_state(chat_id, "idle", data=final_data)

def show_tasks(bot, message, status: str | None = None):
    """Показывает список задач, опционально фильтруя по статусу. Удаляет предыдущий список задач."""
    chat_id = message.chat.id
    new_message_ids = []

    # 1. Get current state and delete old messages
    chat_state = task_manager.get_user_state(chat_id) or {}
    old_message_ids = chat_state.get("data", {}).get("last_task_list_message_ids", [])

    if old_message_ids:
        for msg_id in old_message_ids:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception as e:
                print(f"Could not delete message {msg_id}: {e}")

    # Also delete the user's command message
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Could not delete user command message: {e}")

    try:
        # 2. Get tasks to display
        if status == "open":
            tasks_to_show = task_manager.get_tasks(chat_id, status="open")
            header_text = "🔥 *Открытые задачи:*"
            no_tasks_text = "Новых задач нет. Отличная работа! ✨"
        elif status == task_manager.STATUS_ARCHIVED:
            tasks_to_show = task_manager.get_tasks(chat_id, status=task_manager.STATUS_ARCHIVED)
            header_text = "🗄️ *Архивные задачи:*"
            no_tasks_text = "Архивных задач нет. ✨"
        elif status == task_manager.STATUS_IN_PROGRESS:
            tasks_to_show = task_manager.get_tasks(chat_id, status=status)
            header_text = "👨‍💻 *Задачи в работе:*"
            no_tasks_text = "Нет задач в работе. ✨"
        elif status == task_manager.STATUS_DONE:
            tasks_to_show = task_manager.get_tasks(chat_id, status=status)
            header_text = "✅ *Задачи выполненные:*"
            no_tasks_text = "Нет выполненных задач. ✨"
        elif status:
            tasks_to_show = task_manager.get_tasks(chat_id, status=status)
            header_text = f"Задачи со статусом '{status}':*"
            no_tasks_text = f"Нет задач со статусом '{status}'. Отличная работа! ✨"
        else:
            tasks_to_show = task_manager.get_all_tasks(chat_id)
            header_text = "🔥 *Все задачи:*"
            no_tasks_text = "Нет задач. Отличная работа! ✨"

        # 3. Send new messages and collect their IDs
        if not tasks_to_show:
            sent_msg = bot.send_message(chat_id, no_tasks_text, reply_markup=get_main_keyboard(), parse_mode='Markdown')
            new_message_ids.append(sent_msg.message_id)
        else:
            header_msg = bot.send_message(chat_id, header_text, parse_mode='Markdown', reply_markup=get_main_keyboard())
            new_message_ids.append(header_msg.message_id)
            for task in tasks_to_show:
                task_text = format_task_message(task)
                keyboard = get_task_keyboard(task['id'], task['status'])
                task_msg = bot.send_message(chat_id, task_text, parse_mode='Markdown', reply_markup=keyboard)
                new_message_ids.append(task_msg.message_id)

    except Exception as e:
        print(f"Ошибка при получении списка задач: {e}")
        error_msg = bot.send_message(chat_id, "Произошла ошибка при получении списка задач.", reply_markup=get_main_keyboard())
        new_message_ids.append(error_msg.message_id)

    finally:
        # 4. Save the new message IDs to the user's state
        current_data = chat_state.get("data", {})
        current_data['last_task_list_message_ids'] = new_message_ids
        task_manager.set_user_state(chat_id, chat_state.get("state", "idle"), data=current_data)

def handle_callback_query(bot, call):
    """Обрабатывает нажатия на инлайн-кнопки."""
    try:
        # Calendar callback handling
        if call.data.startswith('cbcal_'):
            result, key, step = DetailedTelegramCalendar(locale='ru').process(call.data)
            user_state = task_manager.get_user_state(call.from_user.id)
            state_data = (user_state or {}).get("data", {}) or {}

            if not result and key:
                if user_state and user_state.get("state") == "calendar_set_deadline":
                    bot.edit_message_text(f"Выберите {LSTEP[step]}", call.message.chat.id, call.message.message_id, reply_markup=key)
            elif result and user_state and user_state.get("state") == "calendar_set_deadline":
                task_id = state_data.get("deadline_task_id")
                original_message_id = state_data.get("deadline_task_message_id")
                last_message_ids = list(state_data.get("last_task_list_message_ids", []))

                if not task_id:
                    bot.edit_message_text("Произошла ошибка: не удалось найти задачу.", call.message.chat.id, call.message.message_id)
                    return

                deadline_str = result.isoformat()
                task_manager.update_task_deadline(task_id, deadline_str)
                task = task_manager.get_task_by_id(task_id)
                if not task:
                    bot.edit_message_text("Задача не найдена.", call.message.chat.id, call.message.message_id)
                    return

                new_text = format_task_message(task)
                new_keyboard = get_task_keyboard(task_id, task['status'])

                message_updated = False
                if original_message_id:
                    try:
                        bot.edit_message_text(chat_id=call.message.chat.id,
                                              message_id=original_message_id,
                                              text=new_text,
                                              parse_mode='Markdown',
                                              reply_markup=new_keyboard)
                        message_updated = True
                    except Exception as e:
                        print(f"Не удалось обновить исходное сообщение задачи: {e}")

                if not message_updated:
                    sent_msg = bot.send_message(call.message.chat.id, new_text, parse_mode='Markdown', reply_markup=new_keyboard)
                    if original_message_id and original_message_id in last_message_ids:
                        last_message_ids = [sent_msg.message_id if mid == original_message_id else mid for mid in last_message_ids]
                    else:
                        last_message_ids.append(sent_msg.message_id)
                try:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                except Exception as e:
                    print(f"Не удалось удалить сообщение календаря: {e}")

                cleaned_state_data = dict(state_data)
                cleaned_state_data.pop("deadline_task_id", None)
                cleaned_state_data.pop("deadline_task_message_id", None)
                cleaned_state_data['last_task_list_message_ids'] = last_message_ids
                task_manager.set_user_state(call.from_user.id, "idle", data=cleaned_state_data)
            return

        parts = call.data.split('_') # Split into all parts

        action_prefix = "_".join(parts[:-1])
        task_id = parts[-1]

        if action_prefix == "set_deadline":
            calendar, step = DetailedTelegramCalendar(locale='ru', current_date=datetime.now().date()).build()
            sent_calendar_msg = bot.send_message(call.message.chat.id, f"Выберите {LSTEP[step]}", reply_markup=calendar)
            
            existing_state = task_manager.get_user_state(call.from_user.id) or {}
            current_data = dict(existing_state.get("data") or {})
            
            message_ids_to_clean = current_data.get('last_task_list_message_ids', [])
            message_ids_to_clean.append(sent_calendar_msg.message_id)
            
            current_data.update({
                "deadline_task_id": task_id,
                "deadline_task_message_id": call.message.message_id,
                "last_task_list_message_ids": message_ids_to_clean
            })
            
            task_manager.set_user_state(call.from_user.id, "calendar_set_deadline", current_data)
            return

        # Reconstruct the action string based on the number of parts
        if len(parts) == 2: # e.g., "take_UUID", "done_UUID", "delete_UUID", "archive_UUID"
            action_full = parts[0]
        elif len(parts) == 3 and parts[0] == "reopen": # e.g., "reopen_new_UUID"
            action_full = f"{parts[0]}_{parts[1]}" # Reconstruct "reopen_new"
        elif len(parts) == 4 and parts[0] == "reopen" and parts[1] == "in" and parts[2] == "progress": # e.g., "reopen_in_progress_UUID"
            action_full = f"{parts[0]}_{parts[1]}_{parts[2]}" # Reconstruct "reopen_in_progress"
        else:
            action_full = "unknown" # Fallback for unexpected formats

        user_info = call.from_user

        new_status = None
        if action_full == "take":
            new_status = task_manager.STATUS_IN_PROGRESS
        elif action_full == "done":
            new_status = task_manager.STATUS_DONE
        elif action_full == "archive":
            task_to_archive = task_manager.get_task_by_id(task_id)
            if task_to_archive:
                created_by_user = f"@{user_info.username}" if user_info.username else user_info.first_name or "Unknown User"
                if task_to_archive.get("created_by") == created_by_user:
                    new_status = task_manager.STATUS_ARCHIVED
                else:
                    bot.answer_callback_query(call.id, "Только автор задачи может ее архивировать.")
                    return
            else:
                bot.answer_callback_query(call.id, "Не удалось найти задачу.")
                return
        elif action_full == "delete":
            success = task_manager.delete_task(task_id)
            if success:
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Задача успешно удалена.", parse_mode='Markdown')
                bot.answer_callback_query(call.id, "Задача удалена.")
            else:
                bot.answer_callback_query(call.id, "Не удалось удалить задачу.")
            return # Exit after deleting
        elif action_full == "reopen_new":
            new_status = task_manager.STATUS_NEW
        elif action_full == "reopen_in_progress":
            new_status = task_manager.STATUS_IN_PROGRESS

        if not new_status:
            # This case will be hit for "set_deadline" and other unhandled callbacks.
            # We already handled "set_deadline" and calendar callbacks, so we can ignore this.
            return

        success = task_manager.update_task_status(task_id, new_status, user_info)

        if success:
            task = task_manager.get_task_by_id(task_id)
            if task:
                new_text = format_task_message(task)
                new_keyboard = get_task_keyboard(task_id, new_status)
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=new_text, parse_mode='Markdown', reply_markup=new_keyboard)
                bot.answer_callback_query(call.id, f"Статус задачи обновлен на '{new_status}'")
            else:
                bot.answer_callback_query(call.id, "Задача не найдена после обновления.")
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Задача была удалена или не найдена.")
        else:
            bot.answer_callback_query(call.id, "Не удалось обновить задачу.")

    except Exception as e:
        print(f"Ошибка в обработчике колбэка: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка.")

# --- Webhook ---

import json

_bot_instance = None # Use a global variable to store the bot instance

_firebase_app_initialized = False

@https_fn.on_request(region="europe-west1")
def webhook(req: https_fn.Request) -> https_fn.Response:
    """Handles incoming Telegram updates."""
    global _bot_instance, _firebase_app_initialized
    if not _firebase_app_initialized:
        initialize_app()
        _firebase_app_initialized = True
    if _bot_instance is None:
        telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not telegram_bot_token:
            print("TELEGRAM_BOT_TOKEN is not set. Bot application will not be initialized.")
            return https_fn.Response("Bot not initialized", status=500)
        _bot_instance = telebot.TeleBot(telegram_bot_token)

    bot = _bot_instance # Use the instantiated bot

    try:
        if req.method == "POST":
            json_data = req.get_json(force=True)
            print(f"Received POST data: {json_data}")
            update = telebot.types.Update.de_json(json_data)

            if update.message and update.message.text:
                user_id = update.message.chat.id
                user_state = task_manager.get_user_state(user_id)

                if user_state and user_state.get("state") == "awaiting_task_description":
                    # This is the handler for when the user provides the task description.

                    # First, clean up the "Пожалуйста, введите..." prompt message.
                    chat_state = user_state or {}
                    old_message_ids = chat_state.get("data", {}).get("last_task_list_message_ids", [])
                    if old_message_ids:
                        for msg_id in old_message_ids:
                            try:
                                bot.delete_message(user_id, msg_id)
                            except Exception as e:
                                print(f"Could not delete message {msg_id}: {e}")

                    task_text = update.message.text
                    new_message_ids = []

                    try:
                        # Also delete the user's message with the description
                        bot.delete_message(chat_id=user_id, message_id=update.message.message_id)
                    except Exception: pass

                    if not task_text:
                        msg = bot.send_message(user_id, "Описание задачи не может быть пустым. Пожалуйста, попробуйте еще раз.", reply_markup=get_main_keyboard())
                        new_message_ids.append(msg.message_id)
                    else:
                        try:
                            user_info = update.message.from_user
                            created_by_user = f"@{user_info.username}" if user_info.username else user_info.first_name or "Unknown User"
                            new_task = task_manager.add_task(user_id, task_text, created_by=created_by_user)
                            reply_text = format_task_message(new_task)
                            keyboard = get_task_keyboard(new_task['id'], new_task['status'])

                            # Send "Success" message with the main keyboard, then the task with its inline keyboard
                            msg1 = bot.send_message(user_id, "Задача успешно создана!", reply_markup=get_main_keyboard())
                            msg2 = bot.send_message(user_id, reply_text, parse_mode='Markdown', reply_markup=keyboard)
                            new_message_ids.extend([msg1.message_id, msg2.message_id])
                        except Exception as e:
                            print(f"Ошибка при добавлении задачи через кнопку: {e}")
                            err_msg = bot.send_message(user_id, "Произошла ошибка при создании задачи.", reply_markup=get_main_keyboard())
                            new_message_ids.append(err_msg.message_id)

                    # Save the IDs of the messages just sent, so the next command can clean them up.
                    final_state = task_manager.get_user_state(user_id) or {}
                    final_data = final_state.get("data", {})
                    final_data['last_task_list_message_ids'] = new_message_ids
                    task_manager.set_user_state(user_id, "idle", data=final_data)

                    return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})

                if update.message.text.startswith("/start"):
                    handle_start_command(bot, update.message)
                    return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})
                elif update.message.text.startswith("/help") or update.message.text == "❓ Помощь":
                    send_welcome_and_help(bot, update.message)
                    return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})
                elif update.message.text == "➕ Создать задачу":
                    # Clean up previous messages first
                    chat_state = task_manager.get_user_state(user_id) or {}
                    old_message_ids = chat_state.get("data", {}).get("last_task_list_message_ids", [])

                    if old_message_ids:
                        for msg_id in old_message_ids:
                            try:
                                bot.delete_message(user_id, msg_id)
                            except Exception as e:
                                print(f"Could not delete message {msg_id}: {e}")

                    try:
                        bot.delete_message(user_id, update.message.message_id)
                    except Exception as e:
                        print(f"Could not delete user command message: {e}")

                    # Now, proceed with the original logic
                    sent_msg = bot.send_message(user_id, "Пожалуйста, введите описание задачи:", reply_markup=get_main_keyboard())

                    # Store the ID of this prompt message so it can be cleaned up by the next action.
                    current_data = chat_state.get("data", {})
                    current_data['last_task_list_message_ids'] = [sent_msg.message_id]
                    task_manager.set_user_state(user_id, "awaiting_task_description", data=current_data)
                    return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})
                elif update.message.text == "🔥 Открытые задачи":
                    show_tasks(bot, update.message, status="open")
                    return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})
                elif update.message.text == "👨‍💻 Задачи в работе":
                    show_tasks(bot, update.message, status=task_manager.STATUS_IN_PROGRESS)
                    return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})
                elif update.message.text == "✅ Задачи выполненные":
                    show_tasks(bot, update.message, status=task_manager.STATUS_DONE)
                    return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})
                elif update.message.text == "🗄️ Архивные задачи":
                    show_tasks(bot, update.message, status=task_manager.STATUS_ARCHIVED)
                    return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})
                elif update.message.text.startswith("/new"):
                    add_new_task(bot, update.message)
                    return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})
            elif update.callback_query:
                handle_callback_query(bot, update.callback_query)
                return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})

            return https_fn.Response(json.dumps({'status': 'unhandled'}), status=200, headers={'Content-Type': 'application/json'})
        return https_fn.Response("Unsupported method", status=405)
    except Exception as e:
        print(f"Error processing update: {e}")
        return https_fn.Response("Error", status=500)

