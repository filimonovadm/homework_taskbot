import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from functions import views
from functions.models import Task, STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_ARCHIVED

class TestViews(unittest.TestCase):

    def test_format_task_message_with_created_at(self):
        # Create a mock task with a created_at timestamp in UTC
        utc_datetime = datetime(2023, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        mock_task = Task(
            id="123",
            chat_id=1,
            task_number=1,
            text="Test Task",
            created_by="user",
            status=STATUS_NEW,
            created_at=utc_datetime.isoformat()
        )
        
        # Calculate the expected time in Moscow Time (UTC+3)
        moscow_tz = timezone(timedelta(hours=3))
        expected_local_datetime = utc_datetime.astimezone(moscow_tz)
        expected_date_str = expected_local_datetime.strftime('%d.%m.%Y %H:%M')
        expected_output_part = f"\n`Дата создания: {expected_date_str}`"

        formatted_message = views.format_task_message(mock_task)
        
        self.assertIn(expected_output_part, formatted_message)
        self.assertIn(mock_task.text, formatted_message)
        self.assertIn(STATUS_NEW, formatted_message)
        
    def test_format_task_message_without_created_at(self):
        # Create a mock task without a created_at timestamp
        mock_task = Task(
            id="123",
            chat_id=1,
            task_number=1,
            text="Test Task Old",
            status=STATUS_DONE,
            created_by="Someone",
            assigned_to="Another",
            created_at=None # Simulate old data/issue
        )
        
        formatted_message = views.format_task_message(mock_task)
        
        self.assertNotIn("Дата создания", formatted_message)
        self.assertIn(mock_task.text, formatted_message)
        self.assertIn(STATUS_DONE, formatted_message)
        self.assertIn(mock_task.assigned_to, formatted_message)

    def test_format_task_message_with_task_number(self):
        mock_task = Task(
            id="123", chat_id=1, text="Numbered Task", created_by="u", status=STATUS_NEW,
            task_number=42
        )
        formatted_message = views.format_task_message(mock_task)
        self.assertIn("*(Задача #42)*", formatted_message)

    def test_format_task_message_with_rating(self):
        mock_task = Task(
            id="789", chat_id=1, task_number=1, text="Rated Task", created_by="u", status=STATUS_DONE,
            rating=4
        )
        formatted_message = views.format_task_message(mock_task)
        self.assertIn("Оценка: ⭐⭐⭐⭐", formatted_message)

    def test_format_task_message_with_none_rating(self):
        mock_task = Task(
            id="101", chat_id=1, task_number=1, text="None Rated Task", created_by="u", status=STATUS_DONE,
            rating=None
        )
        formatted_message = views.format_task_message(mock_task)
        self.assertNotIn("Оценка:", formatted_message)

    def test_format_task_message_with_renamed_deadline(self):
        mock_task = Task(
            id="102", chat_id=1, task_number=1, text="Task with deadline", created_by="u", status=STATUS_NEW,
            deadline_at="2025-12-31T23:59:59"
        )
        formatted_message = views.format_task_message(mock_task)
        self.assertIn("Срок: ", formatted_message)
        self.assertNotIn("Дедлайн: ", formatted_message)

    def test_get_main_keyboard_with_task_counts(self):
        tasks = [
            Task(id="1", chat_id=1, task_number=1, text="T", created_by="u", status=STATUS_NEW),
            Task(id="2", chat_id=1, task_number=2, text="T", created_by="u", status=STATUS_NEW),
            Task(id="3", chat_id=1, task_number=3, text="T", created_by="u", status=STATUS_IN_PROGRESS),
            Task(id="4", chat_id=1, task_number=4, text="T", created_by="u", status=STATUS_DONE),
            Task(id="5", chat_id=1, task_number=5, text="T", created_by="u", status=STATUS_ARCHIVED),
        ]

        # Patch types to inspect calls
        with patch('functions.views.types.ReplyKeyboardMarkup') as MockReplyKeyboardMarkup:
            with patch('functions.views.types.KeyboardButton') as MockKeyboardButton:
                views.get_main_keyboard(tasks)
                
                # Check that KeyboardButton was instantiated with correct text
                # We expect calls for: Open (2), InProgress (1)
                
                # Retrieve all 'text' arguments passed to KeyboardButton constructor
                called_texts = [call.args[0] for call in MockKeyboardButton.call_args_list]
                
                self.assertIn(f"{views.BTN_OPEN} (2)", called_texts)
                self.assertIn(f"{views.BTN_IN_PROGRESS} (1)", called_texts)

if __name__ == '__main__':
    unittest.main()
