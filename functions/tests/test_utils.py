import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the 'functions' directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock firebase_admin before it's used
sys.modules['firebase_admin'] = MagicMock()

from functions import utils

class TestUtils(unittest.TestCase):

    def test_delete_messages(self):
        mock_bot = MagicMock()
        chat_id = 123
        message_ids = [1, 2, 3]

        utils.delete_messages(mock_bot, chat_id, message_ids)

        mock_bot.delete_message.assert_any_call(chat_id, 1)
        mock_bot.delete_message.assert_any_call(chat_id, 2)
        mock_bot.delete_message.assert_any_call(chat_id, 3)
        self.assertEqual(mock_bot.delete_message.call_count, 3)

    def test_delete_messages_empty(self):
        mock_bot = MagicMock()
        utils.delete_messages(mock_bot, 123, [])
        mock_bot.delete_message.assert_not_called()

    def test_delete_messages_exception(self):
        mock_bot = MagicMock()
        mock_bot.delete_message.side_effect = Exception("Delete failed")
        # Should not raise exception
        utils.delete_messages(mock_bot, 123, [1])
        mock_bot.delete_message.assert_called_once()

    @patch('functions.utils.task_manager')
    def test_cleanup_previous_bot_messages(self, mock_task_manager):
        mock_bot = MagicMock()
        chat_id = 123
        old_ids = [10, 11]
        
        mock_task_manager.get_user_state.return_value = {
            "data": {"last_task_list_message_ids": old_ids}
        }

        utils.cleanup_previous_bot_messages(mock_bot, chat_id)

        mock_bot.delete_message.assert_any_call(chat_id, 10)
        mock_bot.delete_message.assert_any_call(chat_id, 11)

    @patch('functions.utils.task_manager')
    def test_save_new_bot_messages(self, mock_task_manager):
        chat_id = 123
        new_ids = [20, 21]
        
        # Mock initial state
        mock_task_manager.get_user_state.return_value = {
            "data": {"some_other_data": "foo"}
        }

        utils.save_new_bot_messages(chat_id, new_ids, state="new_state")

        mock_task_manager.set_user_state.assert_called_once()
        args, kwargs = mock_task_manager.set_user_state.call_args
        
        self.assertEqual(args[0], chat_id)
        self.assertEqual(args[1], "new_state")
        self.assertEqual(kwargs['data']['last_task_list_message_ids'], new_ids)
        self.assertEqual(kwargs['data']['some_other_data'], "foo")

if __name__ == '__main__':
    unittest.main()
