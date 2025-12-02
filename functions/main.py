from firebase_functions import https_fn
from firebase_admin import initialize_app
import telebot
import os
import task_manager
from telebot import types
from datetime import datetime, timedelta, timezone


# Initialize Firebase Admin SDK
initialize_app()

# Initialize TeleBot
# Define a timezone for UTC+3 (Moscow time for example)
MOSCOW_TZ = timezone(timedelta(hours=3))

def convert_utc_to_local(utc_dt: datetime) -> datetime:
    """Converts a UTC datetime object to Moscow timezone (UTC+3)."""
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(MOSCOW_TZ)

# --- Bot Handlers (copied from bot.py) ---

def get_task_keyboard(task_id: str, status: str):
    """Создает инлайн-клавиатуру для задачи в зависимости от ее статуса."""
    keyboard = types.InlineKeyboardMarkup()
    if status == task_manager.STATUS_NEW:
        button = types.InlineKeyboardButton("Взять в работу", callback_data=f"take_{task_id}")
        keyboard.add(button)
    elif status == task_manager.STATUS_IN_PROGRESS:
        button = types.InlineKeyboardButton("✅ Завершить", callback_data=f"done_{task_id}")
        keyboard.add(button)
    elif status == task_manager.STATUS_DONE:
        button = types.InlineKeyboardButton("🗄️ Архивировать", callback_data=f"archive_{task_id}")
        keyboard.add(button)
    return keyboard

def format_task_message(task: dict) -> str:
    """Форматирует текст сообщения для задачи."""
    status_emoji = {
        task_manager.STATUS_NEW: "🆕",
        task_manager.STATUS_IN_PROGRESS: "👨‍💻",
        task_manager.STATUS_DONE: "✅"
    }
    text = f"""{status_emoji.get(task['status'], '')} *{task['text']}*
`Статус: {task['status']}`"""
    if task.get('assigned_to'):
        text += f"\n`Исполнитель: {task['assigned_to']}`"
    if task.get('created_at'):
        try:
            created_datetime = datetime.fromisoformat(task['created_at'])
            local_created_datetime = convert_utc_to_local(created_datetime)
            text += f"\n`Дата создания: {local_created_datetime.strftime('%d.%m.%Y %H:%M')}`"
        except ValueError:
            text += f"\n`Дата создания: {task['created_at']}`"
    if task.get('completed_at'):
        try:
            completed_datetime = datetime.fromisoformat(task['completed_at'])
            local_completed_datetime = convert_utc_to_local(completed_datetime)
            text += f"\n`Дата завершения: {local_completed_datetime.strftime('%d.%m.%Y %H:%M')}`"
        except ValueError:
            text += f"\n`Дата завершения: {task['completed_at']}`"
    return text


def get_main_keyboard():
    """Создает основную клавиатуру с кнопками 'Создать задачу', 'Открытые задачи', 'Задачи в работе', 'Задачи выполненные', 'Архивные задачи' и 'Помощь'."""
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    button_create_task = types.KeyboardButton("Создать задачу")
    button_all_tasks = types.KeyboardButton("Открытые задачи")
    button_in_progress_tasks = types.KeyboardButton("Задачи в работе")
    button_done_tasks = types.KeyboardButton("Задачи выполненные")
    button_archived_tasks = types.KeyboardButton("Архивные задачи")
    button_help = types.KeyboardButton("Помощь")
    keyboard.add(button_create_task, button_all_tasks)
    keyboard.add(button_in_progress_tasks, button_done_tasks)
    keyboard.add(button_archived_tasks, button_help)
    return keyboard

def send_welcome_and_help(bot, message):
    """Отправляет приветственное сообщение и справку по командам."""
    print("send_welcome_and_help function called")
    help_text = (
        "Привет! Я бот для учета домашних дел. Вот что я умею:\n\n"
        "*Основные кнопки (под полем ввода сообщения):*\n"
        "  - *Создать задачу*: Позволяет быстро добавить новую задачу.\n"
        "  - *Открытые задачи*: Показывает список всех *новых* задач, ожидающих начала работы.\n"
        "  - *Задачи в работе*: Показывает задачи, которые сейчас выполняются.\n"
        "  - *Задачи выполненные*: Показывает задачи, которые были успешно завершены.\n"
        "  - *Архивные задачи*: Показывает задачи, которые были заархивированы после завершения.\n"
        "  - *Помощь*: Отображает это справочное сообщение.\n\n"
        "*Статусы задач:*\n"
        "  - `новая`: Задача только что создана, никто еще не начал ее выполнять.\n"
        "  - `в работе`: Задача активно выполняется.\n"
        "  - `выполнена`: Задача успешно завершена.\n"
        "  - `архивирована`: Задача завершена и перемещена в архив.\n\n"
        "*Взаимодействие с задачами (инлайн-кнопки под задачами):*\n"
        "  - *Взять в работу*: Появляется у *новых* задач. Назначит задачу вам и изменит статус на `в работе`.\n"
        "  - *Завершить*: Появляется у задач `в работе`. Отметит задачу как `выполненную`.\n"
        "  - *Архивировать*: Появляется у *выполненных* задач. Переместит задачу в архив.\n\n"
        "*Другие команды:*\n"
        "  - `/new <описание задачи>`: Быстрое создание новой задачи (без интерактивного режима).\n"
        "  - `/start` или `/help`: Вызывает это приветственное сообщение.\n\n"
        "Нажмите одну из кнопок, чтобы начать!"
    )
    try:
        bot.reply_to(message, help_text, parse_mode='Markdown', reply_markup=get_main_keyboard())
        print("Successfully sent reply.")
    except Exception as e:
        print(f"Error sending reply: {e}")

def add_new_task(bot, message):
    """Добавляет новую задачу и отправляет ее с клавиатурой."""
    try:
        task_text = message.text.split(maxsplit=1)[1]
    except IndexError:
        task_text = ""

    if not task_text:
        bot.reply_to(message, "Пожалуйста, укажите текст задачи после команды. Например: `/new Купить молоко`", reply_markup=get_main_keyboard())
        return
    try:
        new_task = task_manager.add_task(task_text)
        reply_text = format_task_message(new_task)
        keyboard = get_task_keyboard(new_task['id'], new_task['status'])
        bot.send_message(message.chat.id, reply_text, parse_mode='Markdown', reply_markup=keyboard)
    except Exception as e:
        print(f"Ошибка при добавлении задачи: {e}")
        bot.reply_to(message, "Произошла ошибка при добавлении задачи.", reply_markup=get_main_keyboard())

def show_tasks(bot, message, status: str | None = None):
    """Показывает список задач, опционально фильтруя по статусу."""
    try:
        if status == "open":
            tasks_to_show = task_manager.get_tasks(status="open")
            header_text = "🔥 *Новые задачи: *"
            no_tasks_text = "Новых задач нет. Отличная работа! ✨"
        elif status == task_manager.STATUS_ARCHIVED:
            tasks_to_show = task_manager.get_tasks(status=task_manager.STATUS_ARCHIVED)
            header_text = "🗄️ *Архивные задачи: *"
            no_tasks_text = "Архивных задач нет. ✨"
        elif status:
            tasks_to_show = task_manager.get_tasks(status=status)
            header_text = f"🔥 *Задачи со статусом '{status}':*"
            no_tasks_text = f"Нет задач со статусом '{status}'. Отличная работа! ✨"
        else:
            tasks_to_show = task_manager.get_all_tasks() # This will use get_tasks(None) from task_manager
            header_text = "🔥 *Все задачи: *"
            no_tasks_text = "Нет задач. Отличная работа! ✨"
            
        if not tasks_to_show:
            bot.reply_to(message, no_tasks_text, reply_markup=get_main_keyboard(), parse_mode='Markdown')
            return
            
        bot.send_message(message.chat.id, header_text, parse_mode='Markdown', reply_markup=get_main_keyboard())
        for task in tasks_to_show:
            task_text = format_task_message(task)
            keyboard = get_task_keyboard(task['id'], task['status'])
            bot.send_message(message.chat.id, task_text, parse_mode='Markdown', reply_markup=keyboard)
            
    except Exception as e:
        print(f"Ошибка при получении списка задач: {e}")
        bot.reply_to(message, "Произошла ошибка при получении списка задач.", reply_markup=get_main_keyboard())

def handle_callback_query(bot, call):
    """Обрабатывает нажатия на инлайн-кнопки."""
    try:
        action, task_id = call.data.split('_', 1)
        user_info = call.from_user
        
        new_status = None
        if action == "take":
            new_status = task_manager.STATUS_IN_PROGRESS
        elif action == "done":
            new_status = task_manager.STATUS_DONE
        elif action == "archive":
            new_status = task_manager.STATUS_ARCHIVED

        if not new_status:
            bot.answer_callback_query(call.id, "Неизвестное действие.")
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

@https_fn.on_request(region="europe-west1")
def webhook(req: https_fn.Request) -> https_fn.Response:
    """Handles incoming Telegram updates."""
    global _bot_instance
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
                    task_text = update.message.text
                    if not task_text:
                        bot.send_message(user_id, "Описание задачи не может быть пустым. Пожалуйста, попробуйте еще раз.", reply_markup=get_main_keyboard())
                        task_manager.set_user_state(user_id, "idle") # Clear state
                        return

                    try:
                        new_task = task_manager.add_task(task_text)
                        reply_text = format_task_message(new_task)
                        keyboard = get_task_keyboard(new_task['id'], new_task['status'])
                        bot.send_message(user_id, "Задача успешно создана!", reply_markup=get_main_keyboard())
                        bot.send_message(user_id, reply_text, parse_mode='Markdown', reply_markup=keyboard)
                    except Exception as e:
                        print(f"Ошибка при добавлении задачи через кнопку: {e}")
                        bot.send_message(user_id, "Произошла ошибка при создании задачи.", reply_markup=get_main_keyboard())
                    finally:
                        task_manager.set_user_state(user_id, "idle") # Clear state
                    return # Important: stop processing after handling the state

                if update.message.text.startswith("/start") or update.message.text.startswith("/help"):
                    send_welcome_and_help(bot, update.message)
                elif update.message.text == "Создать задачу":
                    bot.send_message(user_id, "Пожалуйста, введите описание задачи:", reply_markup=get_main_keyboard())
                    task_manager.set_user_state(user_id, "awaiting_task_description")
                elif update.message.text == "Открытые задачи":
                    show_tasks(bot, update.message, status="open")
                elif update.message.text == "Задачи в работе":
                    show_tasks(bot, update.message, status=task_manager.STATUS_IN_PROGRESS)
                elif update.message.text == "Задачи выполненные":
                    show_tasks(bot, update.message, status=task_manager.STATUS_DONE)
                elif update.message.text == "Архивные задачи":
                    show_tasks(bot, update.message, status=task_manager.STATUS_ARCHIVED)
                elif update.message.text == "Помощь":
                    send_welcome_and_help(bot, update.message)
                elif update.message.text.startswith("/new"):
                    add_new_task(bot, update.message)
            elif update.callback_query:
                handle_callback_query(bot, update.callback_query)

            return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})
        return https_fn.Response("Unsupported method", status=405)
    except Exception as e:
        print(f"Error processing update: {e}")
        return https_fn.Response("Error", status=500)
