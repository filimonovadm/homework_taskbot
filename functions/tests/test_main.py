import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import telebot 

# Mock firebase_admin before it's used
sys.modules['firebase_admin'] = MagicMock()

# Import from package (assuming PYTHONPATH includes 'functions')
import main
import handlers # Import handlers directly to inspect/patch
from models import Task, STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_ARCHIVED

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
        mock_update.message.from_user = MagicMock()
        mock_update.message.from_user.username = "testuser"
        mock_update.message.from_user.first_name = "Test"
        main.telebot.types.Update.de_json.return_value = mock_update
        return mock_update

    def _create_mock_callback_update(self, data, chat_id=123, message_id=101):
        mock_update = MagicMock()
        mock_update.message = None
        mock_update.callback_query = MagicMock()
        mock_update.callback_query.id = "cb_id"
        mock_update.callback_query.data = data
        mock_update.callback_query.message.chat.id = chat_id
        mock_update.callback_query.message.message_id = message_id
        mock_update.callback_query.from_user = MagicMock()
        mock_update.callback_query.from_user.username = "testuser"
        mock_update.callback_query.from_user.first_name = "Test"
        main.telebot.types.Update.de_json.return_value = mock_update
        return mock_update

    @patch('handlers.task_manager')
    @patch('main.telebot')
    @patch('main.https_fn')
    def test_rate_button_shows_rating_keyboard(self, mock_https_fn, mock_telebot, mock_task_manager):
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
        # Check keys count
        all_buttons = [btn for row in reply_markup.keyboard for btn in row]
        self.assertEqual(len(all_buttons), 5)

    @patch('handlers.task_manager')
    @patch('main.telebot')
    @patch('main.https_fn')
    def test_set_rating_callback_updates_task(self, mock_https_fn, mock_telebot, mock_task_manager):
        # Setup constants
        mock_task_manager.STATUS_NEW = STATUS_NEW
        mock_task_manager.STATUS_IN_PROGRESS = STATUS_IN_PROGRESS
        mock_task_manager.STATUS_DONE = STATUS_DONE
        mock_task_manager.STATUS_ARCHIVED = STATUS_ARCHIVED

        mock_bot = mock_telebot.TeleBot.return_value
        task_id = "task-xyz"
        rating = 4
        
        self._create_mock_callback_update(f"set_rating_{rating}_{task_id}")
        
        mock_task_manager.rate_task.return_value = True
        
        # Return a Task object
        updated_task = Task(id=task_id, chat_id=1, task_number=1, text="Completed Task", created_by="u", status=STATUS_DONE, rating=rating)
        mock_task_manager.get_task_by_id.return_value = updated_task
        
        mock_request = MagicMock(method="POST")
        main.webhook(mock_request)
        
        mock_task_manager.rate_task.assert_called_once_with(task_id, rating)
        mock_bot.edit_message_text.assert_called_once()
        
        args, kwargs = mock_bot.edit_message_text.call_args
        text_arg = args[0] if args else kwargs.get('text')
        self.assertIn("Оценка: ⭐⭐⭐⭐", text_arg)

    @patch('handlers.utils')
    @patch('handlers.task_manager')
    @patch('main.telebot')
    @patch('main.https_fn')
    def test_show_tasks_deletes_old_messages(self, mock_https_fn, mock_telebot, mock_task_manager, mock_utils):
        # This test now verifies that `main` correctly delegates to `utils` via handlers
        chat_id = 123
        user_message_id = 100

        mock_bot = mock_telebot.TeleBot.return_value
        self._create_mock_update("👨‍💻 В работе", chat_id=chat_id, message_id=user_message_id)
        
        mock_task_manager.get_user_state.return_value = {"state": "idle"}
        
        # Return list of Task objects
        task_obj = Task(id="task1", chat_id=chat_id, task_number=1, text="Test", created_by="u", status=STATUS_IN_PROGRESS)
        mock_task_manager.get_tasks.return_value = [task_obj]
        
        mock_bot.send_message.side_effect = [
            MagicMock(message_id=201),
            MagicMock(message_id=202)
        ]

        mock_request = MagicMock(method="POST")
        main.webhook(mock_request)

        # Assert delegation to utils
        mock_utils.cleanup_previous_bot_messages.assert_called_once_with(mock_bot, chat_id)
        mock_utils.cleanup_user_message.assert_called_once_with(mock_bot, chat_id, user_message_id)
        
        self.assertEqual(mock_bot.send_message.call_count, 2)
        
        # Assert saving new state
        mock_utils.save_new_bot_messages.assert_called_once_with(chat_id, [201, 202], state="idle")

    @patch('handlers.task_manager')
    @patch('main.telebot')
    @patch('main.https_fn')
    def test_delete_task_only_by_author(self, mock_https_fn, mock_telebot, mock_task_manager):
        mock_bot = mock_telebot.TeleBot.return_value
        task_id = "task-to-delete"
        author_username = "taskauthor"
        non_author_username = "anotheruser"

        # Scenario 1: Author tries to delete the task
        task_obj = Task(id=task_id, chat_id=1, task_number=1, text="Authored Task", status=STATUS_NEW, created_by=f"@{author_username}")
        mock_task_manager.get_task_by_id.return_value = task_obj
        mock_task_manager.delete_task.return_value = True

        mock_callback_update = self._create_mock_callback_update(f"delete_{task_id}")
        mock_callback_update.callback_query.from_user.username = author_username
        mock_callback_update.callback_query.from_user.first_name = "TaskAuthor"
        main.telebot.types.Update.de_json.return_value = mock_callback_update

        mock_request = MagicMock(method="POST")
        main.webhook(mock_request)

        mock_task_manager.delete_task.assert_called_once_with(task_id)
        mock_bot.answer_callback_query.assert_called_once_with("cb_id", "Задача удалена.")

        mock_task_manager.reset_mock()
        mock_bot.reset_mock()

        # Scenario 2: Non-author tries to delete
        mock_task_manager.get_task_by_id.return_value = task_obj

        mock_callback_update = self._create_mock_callback_update(f"delete_{task_id}")
        mock_callback_update.callback_query.from_user.username = non_author_username
        mock_callback_update.callback_query.from_user.first_name = "AnotherUser"
        main.telebot.types.Update.de_json.return_value = mock_callback_update

        main.webhook(mock_request)

        mock_task_manager.delete_task.assert_not_called()
        mock_bot.answer_callback_query.assert_called_once_with("cb_id", "Удалить задачу может только ее автор.")

if __name__ == '__main__':
    unittest.main()