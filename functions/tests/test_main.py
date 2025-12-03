import unittest
from unittest.mock import patch, MagicMock
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

if __name__ == '__main__':
    unittest.main()
