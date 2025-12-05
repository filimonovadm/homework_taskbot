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

    def test_format_task_message_with_renamed_deadline(self):
        """Tests that the deadline field is renamed to 'Срок'."""
        mock_task = {
            "id": "102",
            "text": "Task with deadline",
            "status": task_manager.STATUS_NEW,
            "deadline_at": "2025-12-31T23:59:59"
        }
        formatted_message = main.format_task_message(mock_task)
        self.assertIn("Срок: ", formatted_message)
        self.assertNotIn("Дедлайн: ", formatted_message)

    @patch('main.task_manager.get_all_tasks')
    def test_get_main_keyboard_with_task_counts(self, mock_get_all_tasks):
        """Tests that the main keyboard buttons display correct task counts."""
        mock_get_all_tasks.return_value = [
            {"status": task_manager.STATUS_NEW},  # 1 new
            {"status": task_manager.STATUS_NEW},  # 2 new
            {"status": task_manager.STATUS_IN_PROGRESS}, # 1 in progress
            {"status": task_manager.STATUS_DONE}, # 1 done
            {"status": task_manager.STATUS_ARCHIVED}, # 1 archived
        ]

        chat_id = 123

        # Create a mock for ReplyKeyboardMarkup and its buttons
        mock_keyboard = MagicMock(spec=main.types.ReplyKeyboardMarkup)
        mock_button_create = MagicMock(spec=main.types.KeyboardButton, text=main.BTN_CREATE)
        mock_button_open = MagicMock(spec=main.types.KeyboardButton, text=f"{main.BTN_OPEN} (2)")
        mock_button_in_progress = MagicMock(spec=main.types.KeyboardButton, text=f"{main.BTN_IN_PROGRESS} (1)")
        mock_button_done = MagicMock(spec=main.types.KeyboardButton, text=main.BTN_DONE)
        mock_button_archived = MagicMock(spec=main.types.KeyboardButton, text=main.BTN_ARCHIVED)
        mock_button_statistics = MagicMock(spec=main.types.KeyboardButton, text=main.BTN_STATISTICS)
        mock_button_help = MagicMock(spec=main.types.KeyboardButton, text=main.BTN_HELP)

        mock_keyboard.keyboard = [
            [mock_button_create],
            [mock_button_open, mock_button_in_progress],
            [mock_button_done, mock_button_archived, mock_button_statistics, mock_button_help]
        ]
        
        # Patch the actual ReplyKeyboardMarkup and KeyboardButton creation
        with patch('main.types.ReplyKeyboardMarkup', return_value=mock_keyboard) as MockReplyKeyboardMarkup:
            with patch('main.types.KeyboardButton') as MockKeyboardButton:
                # Make MockKeyboardButton return the pre-defined mock buttons based on their text
                def side_effect_for_kb_button(text):
                    if text == main.BTN_CREATE: return mock_button_create
                    if text == f"{main.BTN_OPEN} (2)": return mock_button_open
                    if text == f"{main.BTN_IN_PROGRESS} (1)": return mock_button_in_progress
                    if text == main.BTN_DONE: return mock_button_done
                    if text == main.BTN_ARCHIVED: return mock_button_archived
                    if text == main.BTN_STATISTICS: return mock_button_statistics
                    if text == main.BTN_HELP: return mock_button_help
                    return MagicMock(spec=main.types.KeyboardButton, text=text) # Fallback

                MockKeyboardButton.side_effect = side_effect_for_kb_button

                keyboard = main.get_main_keyboard(chat_id)
                
                # Extract button texts from the returned (mocked) keyboard
                button_texts = [button.text for row in keyboard.keyboard for button in row]

                self.assertIn(f"{main.BTN_OPEN} (2)", button_texts)
                self.assertIn(f"{main.BTN_IN_PROGRESS} (1)", button_texts)
                self.assertIn(main.BTN_DONE, button_texts)
                self.assertIn(main.BTN_ARCHIVED, button_texts)
                self.assertIn(main.BTN_CREATE, button_texts)
                self.assertIn(main.BTN_STATISTICS, button_texts)
                self.assertIn(main.BTN_HELP, button_texts)
                mock_get_all_tasks.assert_called_once_with(chat_id)

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
        mock_update.message.from_user = MagicMock()
        mock_update.message.from_user.username = "testuser"
        mock_update.message.from_user.first_name = "Test"
        main.telebot.types.Update.de_json.return_value = mock_update
        return mock_update

    def _create_mock_callback_update(self, data, chat_id=123, message_id=101):
        mock_update = MagicMock()
        mock_update.message = None
        mock_update.callback_query = MagicMock()
        mock_update.callback_query.data = data
        mock_update.callback_query.message.chat.id = chat_id
        mock_update.callback_query.message.message_id = message_id
        mock_update.callback_query.from_user = MagicMock()
        mock_update.callback_query.from_user.username = "testuser"
        mock_update.callback_query.from_user.first_name = "Test"
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
        self._create_mock_update("👨‍💻 В работе", chat_id=chat_id, message_id=user_message_id)
        
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

    def test_delete_task_only_by_author(self, mock_https_fn, mock_telebot, mock_task_manager):
        mock_telebot.reset_mock()
        mock_task_manager.reset_mock()
        mock_bot = mock_telebot.TeleBot.return_value
        task_id = "task-to-delete"
        author_username = "taskauthor"
        non_author_username = "anotheruser"

        # Scenario 1: Author tries to delete the task
        mock_task_manager.get_task_by_id.return_value = {
            "id": task_id, "text": "Authored Task", "status": task_manager.STATUS_NEW, "created_by": f"@{author_username}"
        }
        mock_task_manager.delete_task.return_value = True

        mock_callback_update = self._create_mock_callback_update(f"delete_{task_id}")
        mock_callback_update.callback_query.from_user.username = author_username
        mock_callback_update.callback_query.from_user.first_name = "TaskAuthor"
        main.telebot.types.Update.de_json.return_value = mock_callback_update

        mock_request = MagicMock(method="POST")
        main.webhook(mock_request)

        mock_task_manager.delete_task.assert_called_once_with(task_id)
        mock_bot.edit_message_text.assert_called_once_with(chat_id=mock_callback_update.callback_query.message.chat.id,
                                                            message_id=mock_callback_update.callback_query.message.message_id,
                                                            text="Задача успешно удалена.", parse_mode='Markdown')
        mock_bot.answer_callback_query.assert_called_once_with(mock_callback_update.callback_query.id, "Задача удалена.")

        mock_task_manager.reset_mock()
        mock_bot.reset_mock()

        # Scenario 2: Non-author tries to delete the task
        mock_task_manager.get_task_by_id.return_value = {
            "id": task_id, "text": "Authored Task", "status": task_manager.STATUS_NEW, "created_by": f"@{author_username}"
        }

        mock_callback_update = self._create_mock_callback_update(f"delete_{task_id}")
        mock_callback_update.callback_query.from_user.username = non_author_username
        mock_callback_update.callback_query.from_user.first_name = "AnotherUser"
        main.telebot.types.Update.de_json.return_value = mock_callback_update

        main.webhook(mock_request)

        mock_task_manager.delete_task.assert_not_called() # Should not call delete_task
        mock_bot.answer_callback_query.assert_called_once_with(mock_callback_update.callback_query.id, "Удалить задачу может только ее автор.")
        mock_bot.edit_message_text.assert_not_called() # Should not edit message

        mock_task_manager.reset_mock()
        mock_bot.reset_mock()

        # Scenario 3: Task not found
        mock_task_manager.get_task_by_id.return_value = None

        mock_callback_update = self._create_mock_callback_update(f"delete_{task_id}")
        mock_callback_update.callback_query.from_user.username = author_username
        mock_callback_update.callback_query.from_user.first_name = "TaskAuthor"
        main.telebot.types.Update.de_json.return_value = mock_callback_update

        main.webhook(mock_request)
        mock_task_manager.delete_task.assert_not_called()
        mock_bot.answer_callback_query.assert_called_once_with(mock_callback_update.callback_query.id, "Задача не найдена.")
        mock_bot.edit_message_text.assert_not_called()


if __name__ == '__main__':
    unittest.main()
