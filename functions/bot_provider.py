"""Shared helpers for creating and reusing the Telegram bot instance.

The Firebase function creates a new Python process per invocation, but we
still want to avoid re-creating the bot client for every request inside the
process.  This module centralizes the lazy initialization logic and keeps the
main entrypoint focused on routing and error handling.
"""

from __future__ import annotations

import os
import telebot


class BotProvider:
    """A small wrapper that lazily constructs a TeleBot instance."""

    def __init__(self) -> None:
        self._bot_instance: telebot.TeleBot | None = None

    def get_bot(self) -> telebot.TeleBot:
        """Return a singleton TeleBot instance.

        Raises:
            ValueError: if the environment variable with the token is missing.
        """

        if self._bot_instance is None:
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            if not token:
                raise ValueError("TELEGRAM_BOT_TOKEN not set")

            # Important: threaded=False for functions
            self._bot_instance = telebot.TeleBot(token, threaded=False)

        return self._bot_instance


bot_provider = BotProvider()

