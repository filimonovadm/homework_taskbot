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
            "created_at": utc_datetime.isoformat()
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
            "assigned_to": "Another"
        }
        
        formatted_message = main.format_task_message(mock_task)
        
        self.assertNotIn("Дата создания", formatted_message)
        self.assertIn(mock_task['text'], formatted_message)
        self.assertIn(task_manager.STATUS_DONE, formatted_message)
        self.assertIn(mock_task['assigned_to'], formatted_message)

@patch('main.task_manager')
@patch('main.telebot')
@patch('main.https_fn')
class TestWebhookLogic(unittest.TestCase):

    def setUp(self):
        # Reset the global bot instance for each test
        main._bot_instance = None
        # Correctly patch os.environ
        self.os_patcher = patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token"})
        self.os_patcher.start()

    def tearDown(self):
        self.os_patcher.stop()
        main._bot_instance = None

    def _create_mock_update(self, text, chat_id=123, message_id=100):
        """Helper to create a mock Update object."""
        mock_update = MagicMock()
        mock_update.message = MagicMock()
        mock_update.message.text = text
        mock_update.message.chat.id = chat_id
        mock_update.message.message_id = message_id
        mock_update.callback_query = None
        main.telebot.types.Update.de_json.return_value = mock_update
        return mock_update

    def test_show_tasks_deletes_old_messages(self, mock_https_fn, mock_telebot, mock_task_manager):
        """Verify that show_tasks cleans up previous messages."""
        # Arrange
        chat_id = 123
        user_message_id = 100
        old_bot_message_ids = [98, 99]

        mock_bot = mock_telebot.TeleBot.return_value
        self._create_mock_update("Задачи в работе", chat_id=chat_id, message_id=user_message_id)
        
        mock_task_manager.get_user_state.return_value = {
            "state": "idle",
            "data": {"last_task_list_message_ids": old_bot_message_ids}
        }
        mock_task_manager.get_tasks.return_value = [{"id": "task1", "text": "Test", "status": "в работе"}]
        mock_bot.send_message.side_effect = [
            MagicMock(message_id=201),
            MagicMock(message_id=202)
        ]

        # Act
        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.get_json.return_value = {}
        main.webhook(mock_request)

        # Assert
        mock_bot.delete_message.assert_any_call(chat_id, user_message_id)
        mock_bot.delete_message.assert_any_call(chat_id, old_bot_message_ids[0])
        mock_bot.delete_message.assert_any_call(chat_id, old_bot_message_ids[1])
        
        self.assertEqual(mock_bot.send_message.call_count, 2)
        
        mock_task_manager.set_user_state.assert_called_once()
        _, kwargs = mock_task_manager.set_user_state.call_args
        self.assertEqual(kwargs['data']['last_task_list_message_ids'], [201, 202])

if __name__ == '__main__':
    unittest.main()
