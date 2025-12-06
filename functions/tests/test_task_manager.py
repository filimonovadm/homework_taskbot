import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import sys
import os
import importlib

# Mock firebase_admin before it's used
mock_firestore = MagicMock()
mock_firestore.DELETE_FIELD = "DELETE_FIELD_SENTINEL" 

sys.modules['firebase_admin'] = MagicMock()
sys.modules['firebase_admin'].firestore = mock_firestore
from firebase_admin import firestore

# Import from the package (assuming PYTHONPATH is set correctly)
import task_manager
# Reload task_manager to ensure it uses the custom mock_firestore defined above
importlib.reload(task_manager)

from models import Task, STATUS_NEW, STATUS_IN_PROGRESS, STATUS_DONE

class TestAddTask(unittest.TestCase):

    @patch('task_manager.repo')
    def test_add_task_initializes_correctly(self, mock_repo):
        # Setup
        mock_repo.get_next_task_number.return_value = 42
        
        chat_id = 12345
        task_text = "Test accumulator task"
        created_by_user = "test_user"

        # Execution
        new_task = task_manager.add_task(chat_id, task_text, created_by_user)

        # Assertions
        self.assertIsInstance(new_task, Task)
        self.assertEqual(new_task.task_number, 42)
        self.assertEqual(new_task.chat_id, chat_id)
        self.assertEqual(new_task.text, task_text)
        self.assertEqual(new_task.status, STATUS_NEW)
        self.assertEqual(new_task.created_by, created_by_user)
        
        # Verify Repository calls
        mock_repo.get_next_task_number.assert_called_once_with(chat_id)
        mock_repo.add_task.assert_called_once()
        saved_task = mock_repo.add_task.call_args[0][0]
        self.assertIsInstance(saved_task, Task)
        self.assertEqual(saved_task.text, task_text)


class TestUpdateTaskStatusWithTimeAccumulation(unittest.TestCase):

    def setUp(self):
        self.patcher = patch('task_manager.repo')
        self.mock_repo = self.patcher.start()
        self.user_name = "Test User"
        self.user_handle = "@testuser"

    def tearDown(self):
        self.patcher.stop()

    def _mock_task_get(self, status, accumulated_time_seconds=0.0, in_progress_at=None, completed_at=None, rating=None):
        """Helper to mock the task object fetched from Repository."""
        task = Task(
            id="task123",
            chat_id=1,
            task_number=1,
            text="Test Task",
            created_by="user",
            status=status,
            accumulated_time_seconds=accumulated_time_seconds,
            in_progress_at=in_progress_at,
            completed_at=completed_at,
            rating=rating
        )
        self.mock_repo.get_task.return_value = task
        return task

    @patch('task_manager.datetime')
    def test_time_accumulation_full_lifecycle(self, mock_datetime):
        mock_datetime.fromisoformat.side_effect = lambda iso_string: datetime.fromisoformat(iso_string)
        
        # 1. Start: Task is NEW
        self._mock_task_get(STATUS_NEW, accumulated_time_seconds=0)

        # 2. ACTION: Move to IN_PROGRESS.
        mock_datetime.now.return_value = datetime.fromisoformat("2025-01-01T12:00:00")
        task_manager.update_task_status("task123", STATUS_IN_PROGRESS, self.user_name, self.user_handle)

        # VERIFY
        self.mock_repo.update_task.assert_called_once()
        update_args = self.mock_repo.update_task.call_args[0][1]
        self.assertEqual(update_args["status"], STATUS_IN_PROGRESS)
        self.assertEqual(update_args["in_progress_at"], "2025-01-01T12:00:00")
        self.assertNotIn("accumulated_time_seconds", update_args)
        
        self.mock_repo.update_task.reset_mock()

        # 3. State: Task is IN_PROGRESS for 1 hour.
        self._mock_task_get(STATUS_IN_PROGRESS, 
                            accumulated_time_seconds=0, 
                            in_progress_at="2025-01-01T12:00:00")
        
        # 4. ACTION: Move to DONE.
        mock_datetime.now.return_value = datetime.fromisoformat("2025-01-01T13:00:00") # 1 hour later
        task_manager.update_task_status("task123", STATUS_DONE, self.user_name, self.user_handle)
        
        # VERIFY
        update_args = self.mock_repo.update_task.call_args[0][1]
        self.assertEqual(update_args["status"], STATUS_DONE)
        self.assertIn("completed_at", update_args)
        self.assertEqual(update_args["in_progress_at"], firestore.DELETE_FIELD)
        self.assertAlmostEqual(update_args["accumulated_time_seconds"], 3600.0)
        
        self.mock_repo.update_task.reset_mock()

    def test_invalid_status_transition(self):
        self._mock_task_get(STATUS_NEW)
        result = task_manager.update_task_status("task123", STATUS_DONE, self.user_name)
        self.assertFalse(result)
        self.mock_repo.update_task.assert_not_called()


class TestRateTask(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('task_manager.repo')
        self.mock_repo = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def _mock_task_get(self, status):
        task = Task(id="task123", chat_id=1, task_number=1, text="T", created_by="u", status=status)
        self.mock_repo.get_task.return_value = task

    def test_rate_task_success(self):
        self._mock_task_get(STATUS_DONE)
        result = task_manager.rate_task("task123", 4)
        self.assertTrue(result)
        self.mock_repo.update_task.assert_called_once_with("task123", {"rating": 4})

    def test_rate_task_not_done(self):
        self._mock_task_get(STATUS_IN_PROGRESS)
        result = task_manager.rate_task("task123", 5)
        self.assertFalse(result)
        self.mock_repo.update_task.assert_not_called()

if __name__ == '__main__':
    unittest.main()