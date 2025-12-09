"""Firebase HTTPS webhook entrypoint for the Telegram bot."""

from __future__ import annotations

import json
import logging

from firebase_admin import initialize_app
from firebase_functions import https_fn
import telebot

from bot_provider import bot_provider
from update_processor import processor


logger = logging.getLogger(__name__)

_firebase_app_initialized = False


def _init_firebase_app() -> None:
    global _firebase_app_initialized
    if not _firebase_app_initialized:
        initialize_app()
        _firebase_app_initialized = True


def _json_response(payload: dict, status: int = 200) -> https_fn.Response:
    return https_fn.Response(
        json.dumps(payload), status=status, headers={"Content-Type": "application/json"}
    )


def _get_bot() -> telebot.TeleBot | None:
    try:
        return bot_provider.get_bot()
    except ValueError:
        logger.exception("Bot token is not configured")
        return None


def _handle_message(bot: telebot.TeleBot, message: telebot.types.Message) -> https_fn.Response:
    if processor.handle_message(bot, message):
        return _json_response({"status": "ok"})
    return _json_response({"status": "unhandled"})


def _handle_callback(bot: telebot.TeleBot, callback_query: telebot.types.CallbackQuery) -> https_fn.Response:
    processor.handle_callback(bot, callback_query)
    return _json_response({"status": "ok"})


def _handle_update(bot: telebot.TeleBot, update: telebot.types.Update) -> https_fn.Response:
    if update.message and update.message.text:
        return _handle_message(bot, update.message)
    if update.callback_query:
        return _handle_callback(bot, update.callback_query)
    return _json_response({"status": "unhandled"})


@https_fn.on_request(region="europe-west1")
def webhook(req: https_fn.Request) -> https_fn.Response:
    _init_firebase_app()

    bot = _get_bot()
    if bot is None:
        return https_fn.Response("Bot not initialized", status=500)

    if req.method != "POST":
        return https_fn.Response("Unsupported method", status=405)

    try:
        json_data = req.get_json(force=True)
        update = telebot.types.Update.de_json(json_data)
    except Exception:
        logger.exception("Failed to parse incoming update")
        return https_fn.Response("Error", status=500)

    try:
        return _handle_update(bot, update)
    except Exception:
        logger.exception("Unexpected error processing update")
        return https_fn.Response("Error", status=500)

