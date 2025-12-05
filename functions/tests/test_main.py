import unittest
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime, timezone, timedelta
import sys
import os

# Add the 'functions' directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main
import task_manager

class TestMain(unittest.TestCase):

    def test_format_task_message_with_created_at(self):
        # Create a mock task with a created_at timestamp in UTC
        utc_datetime = datetime(2023, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        mock_task = {
            "id": "123",
            "text": "Test Task",
            "status": task_manager.STATUS_NEW,
            "created_by": None,
            "assigned_to": None,
            "created_at": utc_datetime.isoformat(),
            "rating": None
        }
        
        # Calculate the expected time in Moscow Time (UTC+3)
        moscow_tz = timezone(timedelta(hours=3))
        expected_local_datetime = utc_datetime.astimezone(moscow_tz)
        expected_date_str = expected_local_datetime.strftime('%d.%m.%Y %H:%M')
        expected_output_part = f"\n`Дата создания: {expected_date_str}`"

        formatted_message = main.format_task_message(mock_task)
        
        self.assertIn(expected_output_part, formatted_message)
        self.assertIn(mock_task['text'], formatted_message)
        self.assertIn(task_manager.STATUS_NEW, formatted_message)
        
    def test_format_task_message_without_created_at(self):
        # Create a mock task without a created_at timestamp (for backward compatibility)
        mock_task = {
            "id": "123",
            "text": "Test Task Old",
            "status": task_manager.STATUS_DONE,
            "created_by": "Someone",
            "assigned_to": "Another",
            "rating": None
        }
        
        formatted_message = main.format_task_message(mock_task)
        
        self.assertNotIn("Дата создания", formatted_message)
        self.assertIn(mock_task['text'], formatted_message)
        self.assertIn(task_manager.STATUS_DONE, formatted_message)
        self.assertIn(mock_task['assigned_to'], formatted_message)

    def test_format_task_message_with_task_number(self):
        """Tests that the task number is formatted correctly if it exists."""
        mock_task = {
            "id": "123",
            "text": "Numbered Task",
            "status": task_manager.STATUS_NEW,
            "task_number": 42,
            "rating": None
        }
        formatted_message = main.format_task_message(mock_task)
        self.assertIn("*(Задача #42)*", formatted_message)

    def test_format_task_message_without_task_number(self):
        """Tests that the task number is not shown if it doesn't exist."""
        mock_task = {
            "id": "456",
            "text": "Unnumbered Task",
            "status": task_manager.STATUS_IN_PROGRESS,
            "rating": None
        }
        formatted_message = main.format_task_message(mock_task)
        self.assertNotIn("Задача #", formatted_message)

    def test_format_task_message_with_rating(self):
        """Tests that a task with a rating shows stars."""
        mock_task = {
            "id": "789",
            "text": "Rated Task",
            "status": task_manager.STATUS_DONE,
            "rating": 4
        }
        formatted_message = main.format_task_message(mock_task)
        self.assertIn("Оценка: ⭐⭐⭐⭐", formatted_message)

    def test_format_task_message_with_none_rating(self):
        """Tests that a task with a None rating shows no rating."""
        mock_task = {
            "id": "101",
            "text": "None Rated Task",
            "status": task_manager.STATUS_DONE,
            "rating": None
        }
        formatted_message = main.format_task_message(mock_task)
        self.assertNotIn("Оценка:", formatted_message)

@patch('main.task_manager')
@patch('main.telebot')
@patch('main.https_fn')
class TestWebhookLogic(unittest.TestCase):

    def setUp(self):
        main._bot_instance = None
        self.os_patcher = patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token"})
        self.os_patcher.start()
        try:
            main.initialize_app()
        except ValueError:
            pass
        main._firebase_app_initialized = True

    def tearDown(self):
        self.os_patcher.stop()
        main._bot_instance = None

    def _create_mock_update(self, text, chat_id=123, message_id=100):
        mock_update = MagicMock()
        mock_update.message = MagicMock()
        mock_update.message.text = text
        mock_update.message.chat.id = chat_id
        mock_update.message.message_id = message_id
        mock_update.callback_query = None
        main.telebot.types.Update.de_json.return_value = mock_update
        return mock_update

    def _create_mock_callback_update(self, data, chat_id=123, message_id=101):
        mock_update = MagicMock()
        mock_update.message = None
        mock_update.callback_query = MagicMock()
        mock_update.callback_query.data = data
        mock_update.callback_query.message.chat.id = chat_id
        mock_update.callback_query.message.message_id = message_id
        main.telebot.types.Update.de_json.return_value = mock_update
        return mock_update

    def test_rate_button_shows_rating_keyboard(self, mock_https_fn, mock_telebot, mock_task_manager):
        mock_telebot.reset_mock()
        mock_task_manager.reset_mock()
        mock_bot = mock_telebot.TeleBot.return_value
        task_id = "task-abc"
        self._create_mock_callback_update(f"rate_{task_id}")

        mock_request = MagicMock(method="POST")
        main.webhook(mock_request)

        mock_bot.edit_message_text.assert_called_once()
        args, kwargs = mock_bot.edit_message_text.call_args
        text_arg = args[0] if args else kwargs.get('text')
        self.assertEqual(text_arg, "Оцените выполненную задачу:")
        
        reply_markup = kwargs['reply_markup']
        self.assertIsInstance(reply_markup, main.types.InlineKeyboardMarkup)
        
        all_buttons = [btn for row in reply_markup.keyboard for btn in row]
        self.assertEqual(len(all_buttons), 5)
        self.assertEqual(all_buttons[0].text, "⭐")
        self.assertEqual(all_buttons[0].callback_data, f"set_rating_1_{task_id}")
        self.assertEqual(all_buttons[4].text, "⭐⭐⭐⭐⭐")
        self.assertEqual(all_buttons[4].callback_data, f"set_rating_5_{task_id}")

    def test_set_rating_callback_updates_task(self, mock_https_fn, mock_telebot, mock_task_manager):
        mock_telebot.reset_mock()
        mock_task_manager.reset_mock()
        # Configure constants on the mock to match real values
        mock_task_manager.STATUS_NEW = task_manager.STATUS_NEW
        mock_task_manager.STATUS_IN_PROGRESS = task_manager.STATUS_IN_PROGRESS
        mock_task_manager.STATUS_DONE = task_manager.STATUS_DONE
        mock_task_manager.STATUS_ARCHIVED = task_manager.STATUS_ARCHIVED

        mock_bot = mock_telebot.TeleBot.return_value
        task_id = "task-xyz"
        rating = 4
        
        self._create_mock_callback_update(f"set_rating_{rating}_{task_id}")
        
        mock_task_manager.rate_task.return_value = True
        updated_task = {"id": task_id, "text": "Completed Task", "status": task_manager.STATUS_DONE, "rating": rating}
        mock_task_manager.get_task_by_id.return_value = updated_task
        
        mock_request = MagicMock(method="POST")
        main.webhook(mock_request)
        
        mock_task_manager.rate_task.assert_called_once_with(task_id, rating)
        mock_bot.edit_message_text.assert_called_once()
        
        args, kwargs = mock_bot.edit_message_text.call_args
        text_arg = args[0] if args else kwargs.get('text')
        self.assertIn("Оценка: ⭐⭐⭐⭐", text_arg)
        
        reply_markup = kwargs['reply_markup']
        all_buttons = [btn for row in reply_markup.keyboard for btn in row]
        self.assertTrue(any(btn.callback_data == f"archive_{task_id}" for btn in all_buttons))

    def test_show_tasks_deletes_old_messages(self, mock_https_fn, mock_telebot, mock_task_manager):
        mock_telebot.reset_mock()
        mock_task_manager.reset_mock()
        chat_id = 123
        user_message_id = 100
        old_bot_message_ids = [98, 99]

        mock_bot = mock_telebot.TeleBot.return_value
        self._create_mock_update("👨‍💻 Задачи в работе", chat_id=chat_id, message_id=user_message_id)
        
        mock_task_manager.get_user_state.return_value = {
            "state": "idle",
            "data": {"last_task_list_message_ids": old_bot_message_ids}
        }
        mock_task_manager.get_tasks.return_value = [{"id": "task1", "text": "Test", "status": "в работе", "rating": None}]
        mock_bot.send_message.side_effect = [
            MagicMock(message_id=201),
            MagicMock(message_id=202)
        ]

        mock_request = MagicMock(method="POST")
        main.webhook(mock_request)

        mock_bot.delete_message.assert_any_call(chat_id, user_message_id)
        mock_bot.delete_message.assert_any_call(chat_id, old_bot_message_ids[0])
        mock_bot.delete_message.assert_any_call(chat_id, old_bot_message_ids[1])
        
        self.assertEqual(mock_bot.send_message.call_count, 2)
        
        mock_task_manager.set_user_state.assert_called_once()
        _, kwargs = mock_task_manager.set_user_state.call_args
        self.assertEqual(kwargs['data']['last_task_list_message_ids'], [201, 202])

if __name__ == '__main__':
    unittest.main()
