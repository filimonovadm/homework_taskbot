"""Encapsulated update processing logic for the Telegram bot webhook.

Separating this logic from the Firebase function entrypoint makes the code
easier to test and reason about without requiring HTTP plumbing.  The
processor orchestrates routing by text commands as well as stateful flows
based on the persisted user state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

import telebot

import handlers
import task_manager
from models import STATUS_ARCHIVED, STATUS_DONE, STATUS_IN_PROGRESS, STATUS_NEW
from views import BTN_ARCHIVED, BTN_CREATE, BTN_DONE, BTN_HELP, BTN_IN_PROGRESS, BTN_OPEN, BTN_STATISTICS


logger = logging.getLogger(__name__)


Handler = Callable[[telebot.TeleBot, telebot.types.Message], None]
StateHandler = Callable[[telebot.TeleBot, telebot.types.Message], None]


@dataclass
class Route:
    condition: Callable[[str], bool]
    handler: Handler


class UpdateProcessor:
    """Coordinates routing for messages and callback queries."""

    def __init__(self) -> None:
        self._routes: tuple[Route, ...] = self._build_routes()
        self._state_handlers: dict[str, StateHandler] = {
            "awaiting_task_description": handlers.handle_task_description_input,
            "awaiting_comment": self._handle_comment_state,
        }

    def _build_routes(self) -> tuple[Route, ...]:
        """Create the static routing table for text commands and buttons."""
        return (
            Route(lambda t: t.startswith("/start"), handlers.handle_start_command),
            Route(lambda t: t.startswith("/help") or t == BTN_HELP, handlers.send_welcome_and_help),
            Route(lambda t: t.startswith("/new"), handlers.add_new_task),
            Route(lambda t: t == BTN_CREATE, handlers.handle_create_task_request),
            Route(lambda t: t == BTN_STATISTICS, handlers.show_statistics),
            Route(lambda t: t.startswith(BTN_OPEN), lambda b, m: handlers.show_tasks(b, m, STATUS_NEW)),
            Route(lambda t: t.startswith(BTN_IN_PROGRESS), lambda b, m: handlers.show_tasks(b, m, STATUS_IN_PROGRESS)),
            Route(lambda t: t.startswith(BTN_DONE), lambda b, m: handlers.show_tasks(b, m, STATUS_DONE)),
            Route(lambda t: t.startswith(BTN_ARCHIVED), lambda b, m: handlers.show_tasks(b, m, STATUS_ARCHIVED)),
        )

    def handle_message(self, bot: telebot.TeleBot, message: telebot.types.Message) -> bool:
        """Handle an incoming message.

        Returns True when the message was processed by either a state handler or
        a route handler.  False means the message was not recognized.
        """

        if not message.text:
            return False

        user_id = message.chat.id
        user_state = self._safe_get_user_state(user_id)

        if self._handle_state(bot, message, user_state):
            return True

        return self._handle_routes(bot, message.text, message)

    def handle_callback(self, bot: telebot.TeleBot, callback_query: telebot.types.CallbackQuery) -> None:
        handlers.handle_callback_query(bot, callback_query)

    def _handle_state(
        self,
        bot: telebot.TeleBot,
        message: telebot.types.Message,
        user_state: dict | None,
    ) -> bool:
        state = (user_state or {}).get("state")
        if not state:
            return False

        handler = self._state_handlers.get(state)
        if not handler:
            logger.warning("Unknown state '%s' for user %s", state, message.chat.id)
            return False

        handler(bot, message)
        return True

    def _handle_routes(self, bot: telebot.TeleBot, text: str, message: telebot.types.Message) -> bool:
        for route in self._routes:
            if route.condition(text):
                route.handler(bot, message)
                return True
        return False

    def _handle_comment_state(self, bot: telebot.TeleBot, message: telebot.types.Message) -> None:
        user_state = self._safe_get_user_state(message.chat.id) or {}
        handlers.handle_comment_input(bot, message, user_state)

    @staticmethod
    def _safe_get_user_state(user_id: int) -> dict | None:
        try:
            return task_manager.get_user_state(user_id)
        except Exception:  # pragma: no cover - defensive fallback
            logger.exception("Failed to read user state for %s", user_id)
            return None


processor = UpdateProcessor()

