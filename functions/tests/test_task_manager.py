import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add the 'functions' directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock firebase_admin before it's used
sys.modules['firebase_admin'] = MagicMock()
from firebase_admin import firestore

# Now import the module to be tested
import task_manager

class TestAddTask(unittest.TestCase):

    @patch('task_manager.get_next_task_number', return_value=42)
    @patch('task_manager.firestore.client')
    def test_add_task_initializes_correctly(self, mock_firestore_client, mock_get_next_number):
        # Mock the Firestore client and its methods
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_document = MagicMock()
        mock_firestore_client.return_value = mock_db
        mock_db.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_document

        # Call the function
        task_text = "Test accumulator task"
        chat_id = 12345
        created_by_user = "test_user"
        new_task = task_manager.add_task(chat_id, task_text, created_by_user)

        # Assertions on the returned dictionary
        self.assertEqual(new_task['task_number'], 42)
        self.assertIn('created_at', new_task)
        self.assertEqual(new_task['chat_id'], chat_id)
        self.assertEqual(new_task['text'], task_text)
        self.assertEqual(new_task['status'], task_manager.STATUS_NEW)
        self.assertEqual(new_task['accumulated_time_seconds'], 0)
        self.assertIsNone(new_task['rating'])  # Check for rating
        self.assertEqual(new_task['created_by'], created_by_user)
        mock_get_next_number.assert_called_once_with(chat_id)

        # Verify that set was called with the correct data
        mock_document.set.assert_called_once()
        called_args, _ = mock_document.set.call_args
        set_data = called_args[0]
        
        self.assertEqual(set_data['task_number'], 42)
        self.assertEqual(set_data['text'], task_text)
        self.assertEqual(set_data['chat_id'], chat_id)
        self.assertEqual(set_data['status'], task_manager.STATUS_NEW)
        self.assertIn('created_at', set_data)
        self.assertEqual(set_data['accumulated_time_seconds'], 0)
        self.assertIsNone(set_data['rating']) # Check for rating in set data
        self.assertEqual(set_data['created_by'], created_by_user)


class TestUpdateTaskStatusWithTimeAccumulation(unittest.TestCase):

    def setUp(self):
        # Patch firestore.client for all tests in this class
        self.patcher = patch('task_manager.firestore.client')
        self.mock_firestore_client = self.patcher.start()
        
        self.mock_db = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_document_ref = MagicMock()
        self.mock_document_snapshot = MagicMock()

        self.mock_firestore_client.return_value = self.mock_db
        self.mock_db.collection.return_value = self.mock_collection
        self.mock_collection.document.return_value = self.mock_document_ref
        
        self.mock_user_info = MagicMock()
        self.mock_user_info.first_name = "Test"
        self.mock_user_info.username = "testuser"

    def tearDown(self):
        self.patcher.stop()

    def _mock_task_get(self, status, accumulated_time_seconds=0, in_progress_at=None, completed_at=None, rating=None, exists=True):
        """Helper to mock the task document fetched from Firestore."""
        self.mock_document_snapshot.exists = exists
        task_data = {
            "id": "task123",
            "text": "Test Task",
            "status": status,
            "created_at": "2025-01-01T00:00:00",
            "accumulated_time_seconds": accumulated_time_seconds,
            "rating": rating
        }
        if completed_at:
            task_data["completed_at"] = completed_at
        if in_progress_at:
            task_data["in_progress_at"] = in_progress_at
        
        self.mock_document_snapshot.to_dict.return_value = task_data
        self.mock_document_ref.get.return_value = self.mock_document_snapshot

    @patch('task_manager.datetime')
    def test_time_accumulation_full_lifecycle(self, mock_datetime):
        # --- Make the mock act like the real datetime for this method ---
        mock_datetime.fromisoformat.side_effect = lambda iso_string: datetime.fromisoformat(iso_string)
        
        # --- SCENARIO: Full task lifecycle with accumulation ---

        # 1. Start: Task is NEW, accumulator is 0.
        self._mock_task_get(task_manager.STATUS_NEW, accumulated_time_seconds=0)

        # 2. ACTION: Move to IN_PROGRESS.
        # Mock 'now' to a fixed point in time for predictable calculations.
        mock_datetime.now.return_value = datetime.fromisoformat("2025-01-01T12:00:00")
        task_manager.update_task_status("task123", task_manager.STATUS_IN_PROGRESS, self.mock_user_info)

        # VERIFY: Status updated, 'in_progress_at' is set, accumulator is unchanged.
        update_args = self.mock_document_ref.update.call_args[0][0]
        self.assertEqual(update_args["status"], task_manager.STATUS_IN_PROGRESS)
        self.assertEqual(update_args["in_progress_at"], "2025-01-01T12:00:00")
        self.assertNotIn("accumulated_time_seconds", update_args, "Accumulator should not change when starting work.")
        self.mock_document_ref.update.reset_mock()

        # 3. State: Task is IN_PROGRESS for 1 hour.
        self._mock_task_get(task_manager.STATUS_IN_PROGRESS, 
                            accumulated_time_seconds=0, 
                            in_progress_at="2025-01-01T12:00:00")
        
        # 4. ACTION: Move to DONE.
        mock_datetime.now.return_value = datetime.fromisoformat("2025-01-01T13:00:00") # 1 hour (3600s) has passed.
        task_manager.update_task_status("task123", task_manager.STATUS_DONE, self.mock_user_info)
        
        # VERIFY: Status updated, 'completed_at' set, 'in_progress_at' deleted, accumulator has 3600s, rating is None
        update_args = self.mock_document_ref.update.call_args[0][0]
        self.assertEqual(update_args["status"], task_manager.STATUS_DONE)
        self.assertIn("completed_at", update_args)
        self.assertIs(update_args["in_progress_at"], task_manager.firestore.DELETE_FIELD)
        self.assertAlmostEqual(update_args["accumulated_time_seconds"], 3600)
        self.assertIsNone(update_args["rating"]) # Rating should be reset to None
        self.mock_document_ref.update.reset_mock()

        # 5. State: Task is DONE, with 3600s accumulated.
        self._mock_task_get(task_manager.STATUS_DONE, 
                            accumulated_time_seconds=3600,
                            completed_at="2025-01-01T13:00:00",
                            rating=5) # Let's assume it was rated

        # 6. ACTION: Re-open task, move back to IN_PROGRESS.
        mock_datetime.now.return_value = datetime.fromisoformat("2025-01-01T14:00:00")
        task_manager.update_task_status("task123", task_manager.STATUS_IN_PROGRESS, self.mock_user_info)

        # VERIFY: Status updated, new 'in_progress_at' set, 'completed_at' deleted, accumulator and rating unchanged.
        update_args = self.mock_document_ref.update.call_args[0][0]
        self.assertEqual(update_args["status"], task_manager.STATUS_IN_PROGRESS)
        self.assertEqual(update_args["in_progress_at"], "2025-01-01T14:00:00")
        self.assertIs(update_args["completed_at"], task_manager.firestore.DELETE_FIELD)
        self.assertNotIn("accumulated_time_seconds", update_args)
        self.assertNotIn("rating", update_args)
        self.mock_document_ref.update.reset_mock()

        # 7. State: Task is IN_PROGRESS again, with 3600s accumulated and a new start time.
        self._mock_task_get(task_manager.STATUS_IN_PROGRESS, 
                            accumulated_time_seconds=3600, 
                            in_progress_at="2025-01-01T14:00:00",
                            rating=5) # Rating persists

        # 8. ACTION: Move to DONE again after 30 more minutes.
        mock_datetime.now.return_value = datetime.fromisoformat("2025-01-01T14:30:00") # 30 mins (1800s) later.
        task_manager.update_task_status("task123", task_manager.STATUS_DONE, self.mock_user_info)

        # VERIFY: Status updated, 'in_progress_at' deleted, accumulator now holds total time, rating is reset.
        update_args = self.mock_document_ref.update.call_args[0][0]
        self.assertEqual(update_args["status"], task_manager.STATUS_DONE)
        self.assertIs(update_args["in_progress_at"], task_manager.firestore.DELETE_FIELD)
        self.assertAlmostEqual(update_args["accumulated_time_seconds"], 5400)
        self.assertIsNone(update_args["rating"]) # Rating is reset
        self.mock_document_ref.update.reset_mock()
        
    def test_invalid_status_transition(self):
        # Initial state: task is new
        self._mock_task_get(task_manager.STATUS_NEW)

        # Call update_task_status with an invalid transition (NEW to DONE)
        result = task_manager.update_task_status("task123", task_manager.STATUS_DONE, None)

        self.assertFalse(result)
        self.mock_document_ref.update.assert_not_called()


class TestRateTask(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('task_manager.firestore.client')
        self.mock_firestore_client = self.patcher.start()
        
        self.mock_db = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_document_ref = MagicMock()
        self.mock_document_snapshot = MagicMock()

        self.mock_firestore_client.return_value = self.mock_db
        self.mock_db.collection.return_value = self.mock_collection
        self.mock_collection.document.return_value = self.mock_document_ref
        
    def tearDown(self):
        self.patcher.stop()

    def _mock_task_get(self, status, exists=True):
        """Helper to mock the task document fetched from Firestore."""
        self.mock_document_snapshot.exists = exists
        task_data = {"id": "task123", "status": status}
        self.mock_document_snapshot.to_dict.return_value = task_data
        self.mock_document_ref.get.return_value = self.mock_document_snapshot

    def test_rate_task_success(self):
        self._mock_task_get(task_manager.STATUS_DONE)
        result = task_manager.rate_task("task123", 4)
        self.assertTrue(result)
        self.mock_document_ref.update.assert_called_once_with({"rating": 4})

    def test_rate_task_not_done(self):
        self._mock_task_get(task_manager.STATUS_IN_PROGRESS)
        result = task_manager.rate_task("task123", 5)
        self.assertFalse(result)
        self.mock_document_ref.update.assert_not_called()

    def test_rate_task_invalid_rating_too_high(self):
        self._mock_task_get(task_manager.STATUS_DONE)
        result = task_manager.rate_task("task123", 6)
        self.assertFalse(result)
        self.mock_document_ref.update.assert_not_called()

    def test_rate_task_invalid_rating_too_low(self):
        self._mock_task_get(task_manager.STATUS_DONE)
        result = task_manager.rate_task("task123", 0)
        self.assertFalse(result)
        self.mock_document_ref.update.assert_not_called()

    def test_rate_task_not_found(self):
        self._mock_task_get(task_manager.STATUS_DONE, exists=False)
        result = task_manager.rate_task("task123", 3)
        self.assertFalse(result)
        self.mock_document_ref.update.assert_not_called()


if __name__ == '__main__':
    unittest.main()