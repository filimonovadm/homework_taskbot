import telebot
from telebot import types
from datetime import datetime
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP

# Internal modules
import task_manager
import views
import utils
from models import Task, STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_ARCHIVED
from views import BTN_CREATE, BTN_OPEN, BTN_IN_PROGRESS, BTN_DONE, BTN_ARCHIVED, BTN_STATISTICS, BTN_HELP

HELP_TEXT = (
    "Привет! Я — ваш персональный менеджер задач. Я помогу вам отслеживать домашние дела и ничего не забывать.\n\n"
    "🤖 *Работа в групповых чатах:*"
    "Чтобы я мог эффективно работать в группе, мне нужны права администратора. Это позволит мне удалять сообщения и управлять задачами.\n\n"
    "⬇️ *Основные команды (клавиатура внизу):*\n"
    f"  - `{BTN_CREATE}`: Интерактивное создание новой задачи.\n"
    f"  - `{BTN_OPEN}`: Показывает все новые задачи, ожидающие исполнителя.\n"
    f"  - `{BTN_IN_PROGRESS}`: Список задач, которые уже кто-то выполняет.\n"
    f"  - `{BTN_DONE}`: Показывает успешно завершенные задачи.\n"
    f"  - `{BTN_ARCHIVED}`: Список задач, которые были убраны в архив.\n"
    f"  - `{BTN_STATISTICS}`: Показывает общую статистику по задачам.\n"
    f"  - `{BTN_HELP}`: Отображает это справочное сообщение.\n\n"
    "🔄 *Жизненный цикл задачи:*"
    "  - `🆕 Новая`: Задача только создана.\n"
    "  - `👨‍💻 В работе`: Кто-то взялся за выполнение.\n"
    "  - `✅ Выполнена`: Задача успешно завершена.\n"
    "  - `🗄️ Архивирована`: Задача убрана в архив.\n\n"
    "⚙️ *Действия с задачами (кнопки под сообщением):*\n"
    "  - `▶️ В работу`: Взять новую задачу на себя.\n"
    "  - `🗓️ Срок`: Установить или изменить срок.\n"
    "  - `✅ Завершить`: Отметить задачу как выполненную.\n"
    "  - `⭐ Оценить`: Поставить оценку выполненной задаче (от 1 до 5).\n"
    "  - `🔄 Отменить`: Вернуть задачу из статуса `в работе` в `новые`.\n"
    "  - `💬 Добавить коммент`: Добавить комментарий к задаче в работе.\n"
    "  - `⏪ Вернуть в работу`: Вернуть задачу из `выполненных` обратно `в работу`.\n"
    "  - `🗄️ Архивировать`: Убрать выполненную задачу в архив.\n"
    "  - `❌ Удалить`: Полностью удалить задачу (только для новых).\n\n"
    "⌨️ *Текстовые команды:*\n"
    "  - `/new <текст>`: Быстрое создание задачи без лишних вопросов.\n"
    "  - `/start` или `/help`: Вызов этой справки.\n\n"
    "Нажмите одну из кнопок, чтобы начать!"
)

# --- Helper Wrapper ---
def get_main_keyboard_wrapper(chat_id: int):
    tasks = task_manager.get_all_tasks(chat_id)
    return views.get_main_keyboard(tasks)

# --- Bot Handlers ---

def handle_start_command(bot, message):
    """Handles the /start command."""
    chat_id = message.chat.id
    new_message_ids = []

    # Clean up the bot's previous messages.
    utils.cleanup_previous_bot_messages(bot, chat_id)

    # Send the welcome message
    try:
        sent_msg = bot.send_message(chat_id, HELP_TEXT, parse_mode='Markdown', reply_markup=get_main_keyboard_wrapper(chat_id))
        new_message_ids.append(sent_msg.message_id)
    except Exception as e:
        print(f"Error sending reply: {e}")
        try:
            err_msg = bot.send_message(chat_id, "Произошла ошибка при отображении справки.", reply_markup=get_main_keyboard_wrapper(chat_id))
            new_message_ids.append(err_msg.message_id)
        except Exception as inner_e:
            print(f"Critical error sending error message: {inner_e}")

    # Overwrite the state with the new message ID
    utils.save_new_bot_messages(chat_id, new_message_ids)

def send_welcome_and_help(bot, message):
    """Отправляет приветственное сообщение и справку по командам, очищая предыдущие сообщения."""
    chat_id = message.chat.id
    new_message_ids = []

    # 1. Clean up old messages
    utils.cleanup_previous_bot_messages(bot, chat_id)

    # Also delete the user's command message that triggered this
    utils.cleanup_user_message(bot, chat_id, message.message_id)

    # 2. Send the help message
    try:
        sent_msg = bot.send_message(chat_id, HELP_TEXT, parse_mode='Markdown', reply_markup=get_main_keyboard_wrapper(chat_id))
        new_message_ids.append(sent_msg.message_id)
    except Exception as e:
        print(f"Error sending reply: {e}")
        err_msg = bot.send_message(chat_id, "Произошла ошибка при отображении справки.", reply_markup=get_main_keyboard_wrapper(chat_id))
        new_message_ids.append(err_msg.message_id)

    # 3. Save the new message ID to state
    utils.save_new_bot_messages(chat_id, new_message_ids)

def handle_create_task_request(bot, message):
    """Initiates the interactive task creation process."""
    user_id = message.chat.id

    # Clean up previous messages first
    utils.cleanup_previous_bot_messages(bot, user_id)
    utils.cleanup_user_message(bot, user_id, message.message_id)

    # Now, proceed with the original logic
    try:
        sent_msg = bot.send_message(user_id, "Пожалуйста, введите описание задачи:", reply_markup=get_main_keyboard_wrapper(user_id))
        utils.save_new_bot_messages(user_id, [sent_msg.message_id], state="awaiting_task_description")
    except Exception as e:
        print(f"Error in handle_create_task_request: {e}")

def handle_task_description_input(bot, message):
    """Handles the text input when user is in 'awaiting_task_description' state."""
    user_id = message.chat.id

    # First, clean up the "Пожалуйста, введите..." prompt message.
    utils.cleanup_previous_bot_messages(bot, user_id)

    task_text = message.text
    new_message_ids = []

    try:
        # Also delete the user's message with the description
        bot.delete_message(chat_id=user_id, message_id=message.message_id)
    except Exception: pass

    if not task_text:
        msg = bot.send_message(user_id, "Описание задачи не может быть пустым. Пожалуйста, попробуйте еще раз.", reply_markup=get_main_keyboard_wrapper(user_id))
        new_message_ids.append(msg.message_id)
        utils.save_new_bot_messages(user_id, new_message_ids, state="awaiting_task_description")
    else:
        try:
            user_info = message.from_user
            created_by_user = f"@{user_info.username}" if user_info.username else user_info.first_name or "Unknown User"
            new_task = task_manager.add_task(user_id, task_text, created_by=created_by_user)
            reply_text = views.format_task_message(new_task)
            keyboard = views.get_task_keyboard(new_task)

            # Send "Success" message with the main keyboard, then the task with its inline keyboard
            msg1 = bot.send_message(user_id, "Задача успешно создана!", reply_markup=get_main_keyboard_wrapper(user_id))
            msg2 = bot.send_message(user_id, reply_text, parse_mode='Markdown', reply_markup=keyboard)
            new_message_ids.extend([msg1.message_id, msg2.message_id])
        except Exception as e:
            print(f"Ошибка при добавлении задачи через кнопку: {e}")
            err_msg = bot.send_message(user_id, "Произошла ошибка при создании задачи.", reply_markup=get_main_keyboard_wrapper(user_id))
            new_message_ids.append(err_msg.message_id)

        # Reset state to idle
        utils.save_new_bot_messages(user_id, new_message_ids, state="idle")

def handle_comment_input(bot, message, user_state):
    """Handles text input when adding a comment."""
    user_id = message.chat.id

    utils.cleanup_previous_bot_messages(bot, user_id)

    comment_text = message.text
    state_data = user_state.get("data", {})
    task_id = state_data.get("comment_task_id")
    original_message_id = state_data.get("comment_task_message_id")

    new_message_ids = []

    try:
        bot.delete_message(chat_id=user_id, message_id=message.message_id)
    except Exception: pass

    if not comment_text:
            msg = bot.send_message(user_id, "Комментарий не может быть пустым.", reply_markup=get_main_keyboard_wrapper(user_id))
            new_message_ids.append(msg.message_id)
            # Stay in awaiting_comment state
            utils.save_new_bot_messages(user_id, new_message_ids, state="awaiting_comment", additional_data=state_data)
    else:
        try:
            user_info = message.from_user
            author = f"@{user_info.username}" if user_info.username else user_info.first_name or "Unknown User"

            if task_manager.add_comment_to_task(task_id, comment_text, author):
                task = task_manager.get_task_by_id(task_id)
                if task:
                    new_text = views.format_task_message(task)
                    keyboard = views.get_task_keyboard(task)

                    # Try to update the original message if it exists
                    message_updated = False
                    if original_message_id:
                        try:
                            bot.edit_message_text(chat_id=user_id, message_id=original_message_id,
                                                    text=new_text, parse_mode='Markdown', reply_markup=keyboard)
                            message_updated = True
                        except Exception as e:
                            print(f"Failed to edit original message: {e}")

                    if not message_updated:
                            msg = bot.send_message(user_id, new_text, parse_mode='Markdown', reply_markup=keyboard)
                            new_message_ids.append(msg.message_id)

                    success_msg = bot.send_message(user_id, "Комментарий добавлен!", reply_markup=get_main_keyboard_wrapper(user_id))
                    new_message_ids.append(success_msg.message_id)
            else:
                err_msg = bot.send_message(user_id, "Ошибка при добавлении комментария. Задача не найдена.", reply_markup=get_main_keyboard_wrapper(user_id))
                new_message_ids.append(err_msg.message_id)

        except Exception as e:
            print(f"Error adding comment: {e}")
            err_msg = bot.send_message(user_id, "Произошла ошибка при добавлении комментария.", reply_markup=get_main_keyboard_wrapper(user_id))
            new_message_ids.append(err_msg.message_id)

        # Reset to idle and clear temp data (comment_task_id etc will be lost as we overwrite data)
        utils.save_new_bot_messages(user_id, new_message_ids, state="idle")

def add_new_task(bot, message):
    """Добавляет новую задачу и отправляет ее с клавиатурой, участвуя в очистке чата."""
    chat_id = message.chat.id
    new_message_ids = []

    # 1. Clean up old messages
    utils.cleanup_previous_bot_messages(bot, chat_id)
    utils.cleanup_user_message(bot, chat_id, message.message_id)

    try:
        task_text = message.text.split(maxsplit=1)[1]
    except IndexError:
        task_text = ""

    if not task_text:
        sent_msg = bot.send_message(chat_id, "Пожалуйста, укажите текст задачи после команды. Например: `/new Купить молоко`", reply_markup=get_main_keyboard_wrapper(chat_id))
        new_message_ids.append(sent_msg.message_id)
    else:
        try:
            user_info = message.from_user
            created_by_user = f"@{user_info.username}" if user_info.username else user_info.first_name or "Unknown User"
            new_task = task_manager.add_task(user_id, task_text, created_by=created_by_user)
            reply_text = views.format_task_message(new_task)
            keyboard = views.get_task_keyboard(new_task)

            # Send "Success" message with the main keyboard, then the task with its inline keyboard
            msg1 = bot.send_message(chat_id, "Задача успешно создана!", reply_markup=get_main_keyboard_wrapper(chat_id))
            msg2 = bot.send_message(chat_id, reply_text, parse_mode='Markdown', reply_markup=keyboard)
            new_message_ids.extend([msg1.message_id, msg2.message_id])

        except Exception as e:
            print(f"Ошибка при добавлении задачи: {e}")
            err_msg = bot.send_message(chat_id, "Произошла ошибка при добавлении задачи.", reply_markup=get_main_keyboard_wrapper(chat_id))
            new_message_ids.append(err_msg.message_id)

    # Finally, save the new message IDs to the user's state
    utils.save_new_bot_messages(chat_id, new_message_ids)

def show_tasks(bot, message, status: str | None = None):
    """Показывает список задач, опционально фильтруя по статусу. Удаляет предыдущий список задач."""
    chat_id = message.chat.id
    new_message_ids = []

    # 1. Get current state and delete old messages
    chat_state = task_manager.get_user_state(chat_id) or {}
    current_state_name = chat_state.get("state", "idle")

    utils.cleanup_previous_bot_messages(bot, chat_id)
    utils.cleanup_user_message(bot, chat_id, message.message_id)

    try:
        # 2. Get tasks to display
        if status == STATUS_NEW:
            tasks_to_show = task_manager.get_tasks(chat_id, status=STATUS_NEW)
            header_text = f"🔥 *Открытые ({len(tasks_to_show)}):*"
            no_tasks_text = "Новых задач нет. Отличная работа! ✨"
        elif status == STATUS_ARCHIVED:
            tasks_to_show = task_manager.get_tasks(chat_id, status=STATUS_ARCHIVED)
            header_text = f"🗄️ *Архив ({len(tasks_to_show)}):*"
            no_tasks_text = "Архивных задач нет. ✨"
        elif status == STATUS_IN_PROGRESS:
            tasks_to_show = task_manager.get_tasks(chat_id, status=status)
            header_text = f"👨‍💻 *В работе ({len(tasks_to_show)}):*"
            no_tasks_text = "Нет задач в работе. ✨"
        elif status == STATUS_DONE:
            tasks_to_show = task_manager.get_tasks(chat_id, status=status)
            header_text = f"✅ *Готово ({len(tasks_to_show)}):*"
            no_tasks_text = "Нет выполненных задач. ✨"
        elif status:
            tasks_to_show = task_manager.get_tasks(chat_id, status=status)
            header_text = f"Задачи со статусом '{status}':*"
            no_tasks_text = f"Нет задач со статусом '{status}'. Отличная работа! ✨"
        else:
            tasks_to_show = task_manager.get_all_tasks(chat_id)
            header_text = f"🔥 *Все задачи ({len(tasks_to_show)}):*"
            no_tasks_text = "Нет задач. Отличная работа! ✨"

        # 3. Send new messages and collect their IDs
        if not tasks_to_show:
            sent_msg = bot.send_message(chat_id, no_tasks_text, reply_markup=get_main_keyboard_wrapper(chat_id), parse_mode='Markdown')
            new_message_ids.append(sent_msg.message_id)
        else:
            header_msg = bot.send_message(chat_id, header_text, parse_mode='Markdown', reply_markup=get_main_keyboard_wrapper(chat_id))
            new_message_ids.append(header_msg.message_id)
            for task in tasks_to_show:
                task_text = views.format_task_message(task)
                keyboard = views.get_task_keyboard(task)
                task_msg = bot.send_message(chat_id, task_text, parse_mode='Markdown', reply_markup=keyboard)
                new_message_ids.append(task_msg.message_id)

    except Exception as e:
        print(f"Ошибка при получении списка задач: {e}")
        error_msg = bot.send_message(chat_id, "Произошла ошибка при получении списка задач.", reply_markup=get_main_keyboard_wrapper(chat_id))
        new_message_ids.append(error_msg.message_id)

    finally:
        # 4. Save the new message IDs to the user's state
        utils.save_new_bot_messages(chat_id, new_message_ids, state=current_state_name)

def show_statistics(bot, message):
    """Собирает и показывает статистику по задачам."""
    chat_id = message.chat.id
    new_message_ids = []

    utils.cleanup_previous_bot_messages(bot, chat_id)
    utils.cleanup_user_message(bot, chat_id, message.message_id)

    try:
        tasks = task_manager.get_all_tasks(chat_id)

        total_tasks = len(tasks)
        status_counts = {
            STATUS_NEW: 0,
            STATUS_IN_PROGRESS: 0,
            STATUS_DONE: 0,
            STATUS_ARCHIVED: 0
        }
        total_time_seconds = 0.0
        total_rating = 0
        rated_tasks_count = 0

        for task in tasks:
            status = task.status
            if status in status_counts:
                status_counts[status] += 1

            total_time_seconds += task.accumulated_time_seconds

            if task.rating:
                total_rating += task.rating
                rated_tasks_count += 1

        avg_rating = (total_rating / rated_tasks_count) if rated_tasks_count > 0 else 0

        stats_text = (
            f"📊 *Статистика задач*\n\n"
            f"Всего задач: *{total_tasks}*\n"
            f"----------------------\n"
            f"🆕 Новые: {status_counts[STATUS_NEW]}\n"
            f"👨‍💻 В работе: {status_counts[STATUS_IN_PROGRESS]}\n"
            f"✅ Выполненные: {status_counts[STATUS_DONE]}\n"
            f"🗄️архивные: {status_counts[STATUS_ARCHIVED]}\n"
            f"----------------------\n"
            f"⏱️ {views.format_accumulated_time(total_time_seconds)}\n"
        )

        if rated_tasks_count > 0:
            stats_text += f"⭐ Средняя оценка: {avg_rating:.1f} ({rated_tasks_count} оценок)"

        sent_msg = bot.send_message(chat_id, stats_text, parse_mode='Markdown', reply_markup=get_main_keyboard_wrapper(chat_id))
        new_message_ids.append(sent_msg.message_id)

    except Exception as e:
        print(f"Ошибка при формировании статистики: {e}")
        err_msg = bot.send_message(chat_id, "Произошла ошибка при получении статистики.", reply_markup=get_main_keyboard_wrapper(chat_id))
        new_message_ids.append(err_msg.message_id)

    utils.save_new_bot_messages(chat_id, new_message_ids)


def handle_callback_query(bot, call):
    """Обрабатывает нажатия на инлайн-кнопки."""
    try:
        # --- Rating Callbacks ---
        if call.data.startswith("rate_"):
            task_id = call.data.split('_')[1]
            rating_keyboard = types.InlineKeyboardMarkup()
            buttons = []
            for i in range(1, 6):
                buttons.append(types.InlineKeyboardButton("⭐" * i, callback_data=f"set_rating_{i}_{task_id}"))
            rating_keyboard.add(*buttons)
            bot.edit_message_text("Оцените выполненную задачу:", chat_id=call.message.chat.id,
                                  message_id=call.message.message_id, reply_markup=rating_keyboard)
            bot.answer_callback_query(call.id)
            return

        if call.data.startswith("set_rating_"):
            parts = call.data.split('_')
            rating = int(parts[2])
            task_id = parts[3]

            success = task_manager.rate_task(task_id, rating)
            if success:
                task = task_manager.get_task_by_id(task_id)
                if task:
                    new_text = views.format_task_message(task)
                    # Revert to the standard "done" keyboard
                    new_keyboard = views.get_task_keyboard(task)
                    bot.edit_message_text(new_text, chat_id=call.message.chat.id,
                                          message_id=call.message.message_id, reply_markup=new_keyboard,
                                          parse_mode='Markdown')
                    bot.answer_callback_query(call.id, f"Вы поставили оценку: {rating} ⭐")
                else:
                    bot.answer_callback_query(call.id, "Не удалось найти задачу после оценки.")
            else:
                bot.answer_callback_query(call.id, "Не удалось оценить задачу.")
            return

        # --- Calendar Callbacks ---
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

                new_text = views.format_task_message(task)
                new_keyboard = views.get_task_keyboard(task)

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

        # --- Other Task Action Callbacks ---
        if call.data.startswith("add_comment_"):
             task_id = call.data.split('_')[2]
             chat_id = call.message.chat.id

             utils.cleanup_previous_bot_messages(bot, chat_id)

             sent_msg = bot.send_message(chat_id, "Введите комментарий к задаче:", reply_markup=get_main_keyboard_wrapper(chat_id))

             # Prepare state data
             chat_state = task_manager.get_user_state(chat_id) or {}
             current_data = chat_state.get("data", {})
             additional_data = {
                 'comment_task_id': task_id,
                 'comment_task_message_id': call.message.message_id
             }

             utils.save_new_bot_messages(chat_id, [sent_msg.message_id], state="awaiting_comment", additional_data=additional_data)

             bot.answer_callback_query(call.id)
             return

        if call.data.startswith("set_deadline_"):
            task_id = call.data.split('_')[2]
            calendar, step = DetailedTelegramCalendar(locale='ru').build()
            bot.send_message(call.message.chat.id, f"Выберите {LSTEP[step]}", reply_markup=calendar)

            # Save state manually as we need specific fields
            user_state = task_manager.get_user_state(call.from_user.id)
            state_data = (user_state or {}).get("data", {}) or {}
            state_data['deadline_task_id'] = task_id
            state_data['deadline_task_message_id'] = call.message.message_id

            task_manager.set_user_state(call.from_user.id, "calendar_set_deadline", data=state_data)
            bot.answer_callback_query(call.id)
            return

        parts = call.data.split('_')
        task_id = parts[-1]
        action_prefix = "_".join(parts[:-1])

        user_info = call.from_user

        new_status = None
        if action_prefix == "take":
            new_status = STATUS_IN_PROGRESS
        elif action_prefix == "done":
            new_status = STATUS_DONE
        elif action_prefix == "archive":
            task_to_archive = task_manager.get_task_by_id(task_id)
            if task_to_archive:
                created_by_user = f"@{user_info.username}" if user_info.username else user_info.first_name or "Unknown User"
                if task_to_archive.created_by == created_by_user:
                    new_status = STATUS_ARCHIVED
                else:
                    bot.answer_callback_query(call.id, "Только автор задачи может ее архивировать.")
                    return
            else:
                bot.answer_callback_query(call.id, "Не удалось найти задачу.")
                return
        elif action_prefix == "delete":
            task_to_delete = task_manager.get_task_by_id(task_id)
            if not task_to_delete:
                bot.answer_callback_query(call.id, "Задача не найдена.")
                return

            current_user = f"@{user_info.username}" if user_info.username else user_info.first_name or "Unknown User"

            if task_to_delete.created_by != current_user:
                bot.answer_callback_query(call.id, "Удалить задачу может только ее автор.")
                return

            success = task_manager.delete_task(task_id)
            if success:
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Задача успешно удалена.", parse_mode='Markdown')
                bot.answer_callback_query(call.id, "Задача удалена.")
            else:
                bot.answer_callback_query(call.id, "Не удалось удалить задачу.")
            return
        elif action_prefix == "reopen_new":
            new_status = STATUS_NEW
        elif action_prefix == "reopen_in_progress":
            new_status = STATUS_IN_PROGRESS

        if not new_status:
            return

        # Prepare user info for the service layer
        user_name = user_info.first_name or "Unknown User"
        user_handle = f"@{user_info.username}" if user_info.username else ""

        success = task_manager.update_task_status(task_id, new_status, user_name, user_handle)

        if success:
            task = task_manager.get_task_by_id(task_id)
            if task:
                new_text = views.format_task_message(task)
                new_keyboard = views.get_task_keyboard(task)
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
