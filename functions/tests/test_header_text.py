import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the 'functions' directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main
import task_manager

@patch('main.task_manager')
@patch('main.telebot')
@patch('main.https_fn')
class TestHeaderText(unittest.TestCase):

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

    def test_open_tasks_header_count(self, mock_https_fn, mock_telebot, mock_task_manager):
        mock_telebot.reset_mock()
        mock_task_manager.reset_mock()
        mock_bot = mock_telebot.TeleBot.return_value
        
        # Mock 5 open tasks
        tasks = [{"id": str(i), "text": f"Task {i}", "status": task_manager.STATUS_NEW, "rating": None} for i in range(5)]
        mock_task_manager.get_tasks.return_value = tasks
        mock_task_manager.STATUS_NEW = task_manager.STATUS_NEW
        
        self._create_mock_update("🔥 Открытые задачи")
        
        mock_request = MagicMock(method="POST")
        main.webhook(mock_request)
        
        # Verify the header message
        # We expect a call to send_message with the header
        # The first call might be deleting messages, then sending the header.
        # We look for the call with the expected text.
        
        expected_header = "🔥 *Открытые задачи (5):*"
        found = False
        for call in mock_bot.send_message.call_args_list:
            args, kwargs = call
            text = args[1] if len(args) > 1 else kwargs.get('text')
            if text == expected_header:
                found = True
                break
        
        self.assertTrue(found, f"Header '{expected_header}' not found in send_message calls.")

    def test_in_progress_tasks_header_count(self, mock_https_fn, mock_telebot, mock_task_manager):
        mock_telebot.reset_mock()
        mock_task_manager.reset_mock()
        mock_bot = mock_telebot.TeleBot.return_value
        
        # Mock 2 in progress tasks
        tasks = [{"id": str(i), "text": f"Task {i}", "status": task_manager.STATUS_IN_PROGRESS, "rating": None} for i in range(2)]
        mock_task_manager.get_tasks.return_value = tasks
        mock_task_manager.STATUS_IN_PROGRESS = task_manager.STATUS_IN_PROGRESS
        
        self._create_mock_update("👨‍💻 Задачи в работе")
        
        mock_request = MagicMock(method="POST")
        main.webhook(mock_request)
        
        expected_header = "👨‍💻 *Задачи в работе (2):*"
        found = False
        for call in mock_bot.send_message.call_args_list:
            args, kwargs = call
            text = args[1] if len(args) > 1 else kwargs.get('text')
            if text == expected_header:
                found = True
                break
        
        self.assertTrue(found, f"Header '{expected_header}' not found in send_message calls.")
    
    def test_archived_tasks_header_count(self, mock_https_fn, mock_telebot, mock_task_manager):
        mock_telebot.reset_mock()
        mock_task_manager.reset_mock()
        mock_bot = mock_telebot.TeleBot.return_value
        
        # Mock 10 archived tasks
        tasks = [{"id": str(i), "text": f"Task {i}", "status": task_manager.STATUS_ARCHIVED, "rating": None} for i in range(10)]
        mock_task_manager.get_tasks.return_value = tasks
        mock_task_manager.STATUS_ARCHIVED = task_manager.STATUS_ARCHIVED
        
        self._create_mock_update("🗄️ Архивные задачи")
        
        mock_request = MagicMock(method="POST")
        main.webhook(mock_request)
        
        expected_header = "🗄️ *Архивные задачи (10):*"
        found = False
        for call in mock_bot.send_message.call_args_list:
            args, kwargs = call
            text = args[1] if len(args) > 1 else kwargs.get('text')
            if text == expected_header:
                found = True
                break
        
        self.assertTrue(found, f"Header '{expected_header}' not found in send_message calls.")

if __name__ == '__main__':
    unittest.main()
