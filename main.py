from firebase_functions import https_fn, options
from firebase_admin import initialize_app
import telebot
import os

options.set_global(
    region=options.SupportedRegion.EUROPE_WEST1,
)

initialize_app()

bot = telebot.TeleBot(options.config().telegram.bot_token)

@https_fn.on_request()
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
