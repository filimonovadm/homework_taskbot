import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Mock firebase_admin before it's used
sys.modules['firebase_admin'] = MagicMock()

import main
from bot_provider import bot_provider
from models import Task, STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_ARCHIVED

@patch('handlers.task_manager')
@patch('bot_provider.telebot')
@patch('update_processor.telebot')
@patch('main.telebot')
@patch('main.https_fn')
class TestHeaderText(unittest.TestCase):

    def setUp(self):
        bot_provider._bot_instance = None
        self.os_patcher = patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token"})
        self.os_patcher.start()
        try:
            main.initialize_app()
        except ValueError:
            pass
        main._firebase_app_initialized = True

    def tearDown(self):
        self.os_patcher.stop()
        bot_provider._bot_instance = None

    def _create_mock_update(self, text, chat_id=123, message_id=100):
        mock_update = MagicMock()
        mock_update.message = MagicMock()
        mock_update.message.text = text
        mock_update.message.chat.id = chat_id
        mock_update.message.message_id = message_id
        mock_update.callback_query = None
        main.telebot.types.Update.de_json.return_value = mock_update
        return mock_update

    def test_open_tasks_header_count(self, mock_https_fn, mock_telebot_main, mock_telebot_processor, mock_telebot_provider, mock_task_manager):
        mock_telebot_main.reset_mock()
        mock_task_manager.reset_mock()
        mock_bot = mock_telebot_main.TeleBot.return_value
        bot_provider._bot_instance = mock_bot
        
        # Mock 5 open tasks
        tasks = [Task(id=str(i), chat_id=123, text=f"Task {i}", created_by="u", status=STATUS_NEW) for i in range(5)]
        mock_task_manager.get_tasks.return_value = tasks
        
        self._create_mock_update("🔥 Открытые")
        
        mock_request = MagicMock(method="POST")
        main.webhook(mock_request)
        
        expected_header = "🔥 *Открытые (5):*"
        found = False
        for call in mock_bot.send_message.call_args_list:
            args, kwargs = call
            text = args[1] if len(args) > 1 else kwargs.get('text')
            if text == expected_header:
                found = True
                break
        
        self.assertTrue(found, f"Header '{expected_header}' not found in send_message calls.")

    def test_in_progress_tasks_header_count(self, mock_https_fn, mock_telebot_main, mock_telebot_processor, mock_telebot_provider, mock_task_manager):
        mock_telebot_main.reset_mock()
        mock_task_manager.reset_mock()
        mock_bot = mock_telebot_main.TeleBot.return_value
        bot_provider._bot_instance = mock_bot
        
        # Mock 2 in progress tasks
        tasks = [Task(id=str(i), chat_id=123, text=f"Task {i}", created_by="u", status=STATUS_IN_PROGRESS) for i in range(2)]
        mock_task_manager.get_tasks.return_value = tasks
        
        self._create_mock_update("👨‍💻 В работе")
        
        mock_request = MagicMock(method="POST")
        main.webhook(mock_request)
        
        expected_header = "👨‍💻 *В работе (2):*"
        found = False
        for call in mock_bot.send_message.call_args_list:
            args, kwargs = call
            text = args[1] if len(args) > 1 else kwargs.get('text')
            if text == expected_header:
                found = True
                break
        
        self.assertTrue(found, f"Header '{expected_header}' not found in send_message calls.")
    
    def test_archived_tasks_header_count(self, mock_https_fn, mock_telebot_main, mock_telebot_processor, mock_telebot_provider, mock_task_manager):
        mock_telebot_main.reset_mock()
        mock_task_manager.reset_mock()
        mock_bot = mock_telebot_main.TeleBot.return_value
        bot_provider._bot_instance = mock_bot
        
        # Mock 10 archived tasks
        tasks = [Task(id=str(i), chat_id=123, text=f"Task {i}", created_by="u", status=STATUS_ARCHIVED) for i in range(10)]
        mock_task_manager.get_tasks.return_value = tasks
        
        self._create_mock_update("🗄️ Архив")
        
        mock_request = MagicMock(method="POST")
        main.webhook(mock_request)
        
        expected_header = "🗄️ *Архив (10):*"
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
