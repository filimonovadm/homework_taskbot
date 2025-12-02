from firebase_functions import https_fn
from firebase_admin import initialize_app
import telebot
import os
import task_manager
from telebot import types

# Initialize Firebase Admin SDK
initialize_app()

# Initialize TeleBot
telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
if not telegram_bot_token:
    print("TELEGRAM_BOT_TOKEN is not set. Bot application will not be initialized.")
bot = telebot.TeleBot(telegram_bot_token)


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
    return text

def send_welcome_and_help(message):
    """Отправляет приветственное сообщение и справку по командам."""
    print("send_welcome_and_help function called")
    help_text = (
        "Привет! Я бот для учета домашних дел. Вот что я умею:\n\n"
        "*/new <описание задачи>* - создать новую задачу.\n"
        "*/tasks* - показать список активных задач.\n"
        "*/help* - показать это сообщение.\n"
    )
    try:
        bot.reply_to(message, help_text, parse_mode='Markdown')
        print("Successfully sent reply.")
    except Exception as e:
        print(f"Error sending reply: {e}")

def add_new_task(message):
    """Добавляет новую задачу и отправляет ее с клавиатурой."""
    try:
        task_text = message.text.split(maxsplit=1)[1]
    except IndexError:
        task_text = ""

    if not task_text:
        bot.reply_to(message, "Пожалуйста, укажите текст задачи после команды. Например: `/new Купить молоко`")
        return
    try:
        new_task = task_manager.add_task(task_text)
        reply_text = format_task_message(new_task)
        keyboard = get_task_keyboard(new_task['id'], new_task['status'])
        bot.send_message(message.chat.id, reply_text, parse_mode='Markdown', reply_markup=keyboard)
    except Exception as e:
        print(f"Ошибка при добавлении задачи: {e}")
        bot.reply_to(message, "Произошла ошибка при добавлении задачи.")

def show_active_tasks(message):
    """Показывает список активных задач с клавиатурами."""
    try:
        active_tasks = task_manager.get_active_tasks()
        if not active_tasks:
            bot.reply_to(message, "Активных задач нет. Отличная работа! ✨")
            return
            
        bot.send_message(message.chat.id, "🔥 *Активные задачи:*", parse_mode='Markdown')
        for task in active_tasks:
            task_text = format_task_message(task)
            keyboard = get_task_keyboard(task['id'], task['status'])
            bot.send_message(message.chat.id, task_text, parse_mode='Markdown', reply_markup=keyboard)
            
    except Exception as e:
        print(f"Ошибка при получении списка задач: {e}")
        bot.reply_to(message, "Произошла ошибка при получении списка задач.")

def handle_callback_query(call):
    """Обрабатывает нажатия на инлайн-кнопки."""
    try:
        action, task_id = call.data.split('_', 1)
        user_info = call.from_user
        
        new_status = None
        if action == "take":
            new_status = task_manager.STATUS_IN_PROGRESS
        elif action == "done":
            new_status = task_manager.STATUS_DONE

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

@https_fn.on_request(region="europe-west1")
def webhook(req: https_fn.Request) -> https_fn.Response:
    """Handles incoming Telegram updates."""
    if bot is None:
        print("Bot not initialized. Check TELEGRAM_BOT_TOKEN.")
        return https_fn.Response("Bot not initialized", status=500)
    
    try:
        if req.method == "POST":
            json_data = req.get_json(force=True)
            print(f"Received POST data: {json_data}")
            update = telebot.types.Update.de_json(json_data)
            
            if update.message and update.message.text:
                if update.message.text.startswith("/start") or update.message.text.startswith("/help"):
                    send_welcome_and_help(update.message)
                elif update.message.text.startswith("/new"):
                    add_new_task(update.message)
                elif update.message.text.startswith("/tasks"):
                    show_active_tasks(update.message)
            elif update.callback_query:
                handle_callback_query(update.callback_query)

            return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})
        return https_fn.Response("Unsupported method", status=405)
    except Exception as e:
        print(f"Error processing update: {e}")
        return https_fn.Response("Error", status=500)
