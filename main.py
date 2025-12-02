from firebase_functions import https_fn
from firebase_admin import initialize_app
import telebot
import os
from dotenv import load_dotenv

load_dotenv()

initialize_app()

telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")

bot = telebot.TeleBot(telegram_bot_token)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я твой Homework Taskbot. Как я могу помочь?")

@https_fn.on_request(region="europe-west1")
def webhook(req: https_fn.Request) -> https_fn.Response:
    try:
        if req.method == "POST":
            update = telebot.types.Update.de_json(req.get_json())
            bot.process_new_updates([update])
            return https_fn.Response("OK", status=200)
        return https_fn.Response("Unsupported method", status=405)
    except Exception as e:
        print(e)
        return https_fn.Response("Error", status=500)
