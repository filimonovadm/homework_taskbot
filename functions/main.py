from firebase_functions import https_fn
from firebase_admin import initialize_app
import telebot
import os
import json

# Internal modules
import task_manager
import views
import utils
import handlers
from models import STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_ARCHIVED
from views import BTN_CREATE, BTN_OPEN, BTN_IN_PROGRESS, BTN_DONE, BTN_ARCHIVED, BTN_STATISTICS, BTN_HELP

# --- Webhook ---

_bot_instance = None
_firebase_app_initialized = False

def get_bot():
    global _bot_instance
    if _bot_instance is None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")
        _bot_instance = telebot.TeleBot(token, threaded=False) # Important: threaded=False for functions
    return _bot_instance

def process_routing(bot, message):
    text = message.text
    if not text:
        return False

    routes = [
        (lambda t: t.startswith("/start"), handlers.handle_start_command),
        (lambda t: t.startswith("/help") or t == BTN_HELP, handlers.send_welcome_and_help),
        (lambda t: t.startswith("/new"), handlers.add_new_task),
        (lambda t: t == BTN_CREATE, handlers.handle_create_task_request),
        (lambda t: t == BTN_STATISTICS, handlers.show_statistics),
        (lambda t: t.startswith(BTN_OPEN), lambda b, m: handlers.show_tasks(b, m, STATUS_NEW)),
        (lambda t: t.startswith(BTN_IN_PROGRESS), lambda b, m: handlers.show_tasks(b, m, STATUS_IN_PROGRESS)),
        (lambda t: t.startswith(BTN_DONE), lambda b, m: handlers.show_tasks(b, m, STATUS_DONE)),
        (lambda t: t.startswith(BTN_ARCHIVED), lambda b, m: handlers.show_tasks(b, m, STATUS_ARCHIVED)),
    ]

    for check, handler in routes:
        if check(text):
            handler(bot, message)
            return True
            
    return False

@https_fn.on_request(region="europe-west1")
def webhook(req: https_fn.Request) -> https_fn.Response:
    global _firebase_app_initialized
    if not _firebase_app_initialized:
        initialize_app()
        _firebase_app_initialized = True

    try:
        bot = get_bot()
    except ValueError:
        return https_fn.Response("Bot not initialized", status=500)

    try:
        if req.method == "POST":
            json_data = req.get_json(force=True)
            update = telebot.types.Update.de_json(json_data)

            if update.message and update.message.text:
                user_id = update.message.chat.id
                
                try:
                    user_state = task_manager.get_user_state(user_id)
                except Exception:
                    user_state = None

                # 1. Check states first (Priority)
                if user_state:
                    state = user_state.get("state")
                    if state == "awaiting_task_description":
                        handlers.handle_task_description_input(bot, update.message)
                        return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})
                    if state == "awaiting_comment":
                        handlers.handle_comment_input(bot, update.message, user_state)
                        return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})

                # 2. Check Routing
                if process_routing(bot, update.message):
                    return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})

            elif update.callback_query:
                handlers.handle_callback_query(bot, update.callback_query)
                return https_fn.Response(json.dumps({'status': 'ok'}), status=200, headers={'Content-Type': 'application/json'})

            return https_fn.Response(json.dumps({'status': 'unhandled'}), status=200, headers={'Content-Type': 'application/json'})
        
        return https_fn.Response("Unsupported method", status=405)
    
    except Exception as e:
        return https_fn.Response("Error", status=500)
