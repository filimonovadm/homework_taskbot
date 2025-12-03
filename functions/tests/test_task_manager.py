import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import sys
import os

# Add the 'functions' directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import task_manager
# Mock firebase_admin before it's used
sys.modules['firebase_admin'] = MagicMock()
from firebase_admin import firestore, initialize_app

class TestTaskManager(unittest.TestCase):

    @patch('task_manager.firestore.client')
    def test_add_task_adds_created_at_timestamp_and_chat_id(self, mock_firestore_client):
        # Mock the Firestore client and collection/document methods
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_document = MagicMock()

        mock_firestore_client.return_value = mock_db
        mock_db.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_document

        # Call the add_task function
        task_text = "Test task with timestamp"
        chat_id = 12345
        new_task = task_manager.add_task(chat_id, task_text)

        # Assertions
        self.assertIn('created_at', new_task)
        self.assertIsInstance(new_task['created_at'], str)
        self.assertEqual(new_task['chat_id'], chat_id)
        
        # Verify the format of the timestamp
        try:
            datetime.fromisoformat(new_task['created_at'])
        except ValueError:
            self.fail("created_at timestamp is not in ISO format")
            
        # Verify that set was called with the new task data
        mock_document.set.assert_called_once()
        called_args, _ = mock_document.set.call_args
        set_data = called_args[0]
        
        self.assertEqual(set_data['text'], task_text)
        self.assertEqual(set_data['chat_id'], chat_id)
        self.assertEqual(set_data['status'], task_manager.STATUS_NEW)
        self.assertIn('created_at', set_data)
        
        # Ensure the timestamp in set_data is also valid
        try:
            datetime.fromisoformat(set_data['created_at'])
        except ValueError:
            self.fail("created_at timestamp in set_data is not in ISO format")

class TestGetTasks(unittest.TestCase):
    
    def setUp(self):
        # Patch firestore.client and initialize_app for all tests in this class
        self.firestore_patcher = patch('task_manager.firestore.client')
        self.init_app_patcher = patch('firebase_admin.initialize_app')
        
        self.mock_firestore_client = self.firestore_patcher.start()
        self.mock_init_app = self.init_app_patcher.start()
        
        self.mock_db = MagicMock()
        self.mock_firestore_client.return_value = self.mock_db
        
        self.tasks = [
            # Chat 1 tasks
            {'id': '1', 'chat_id': 1, 'text': 'Task 1 for chat 1', 'status': task_manager.STATUS_NEW},
            {'id': '2', 'chat_id': 1, 'text': 'Task 2 for chat 1', 'status': task_manager.STATUS_IN_PROGRESS},
            # Chat 2 tasks
            {'id': '3', 'chat_id': 2, 'text': 'Task 1 for chat 2', 'status': task_manager.STATUS_NEW},
        ]
        
        self.mock_query = MagicMock()
        self.mock_db.collection.return_value = self.mock_query

    def tearDown(self):
        self.firestore_patcher.stop()
        self.init_app_patcher.stop()

    def _get_mock_docs(self, filtered_tasks):
        mock_docs = []
        for task in filtered_tasks:
            mock_doc = MagicMock()
            mock_doc.to_dict.return_value = task
            mock_docs.append(mock_doc)
        return mock_docs

    def test_get_tasks_filters_by_chat_id(self):
        # Arrange
        chat_id_to_test = 1
        expected_tasks = [t for t in self.tasks if t['chat_id'] == chat_id_to_test]
        
        mock_filtered_query = MagicMock()
        self.mock_query.where.return_value = mock_filtered_query
        mock_filtered_query.stream.return_value = self._get_mock_docs(expected_tasks)

        # Act
        result = task_manager.get_tasks(chat_id_to_test)

        # Assert
        self.mock_query.where.assert_called_with("chat_id", "==", chat_id_to_test)
        self.assertEqual(len(result), len(expected_tasks))
        self.assertEqual([t['id'] for t in result], [t['id'] for t in expected_tasks])

    def test_get_all_tasks_filters_by_chat_id(self):
        # Arrange
        chat_id_to_test = 2
        expected_tasks = [t for t in self.tasks if t['chat_id'] == chat_id_to_test]
        
        mock_filtered_query = MagicMock()
        self.mock_query.where.return_value = mock_filtered_query
        mock_filtered_query.stream.return_value = self._get_mock_docs(expected_tasks)

        # Act
        result = task_manager.get_all_tasks(chat_id_to_test)

        # Assert
        self.mock_query.where.assert_called_with("chat_id", "==", chat_id_to_test)
        self.assertEqual(len(result), len(expected_tasks))
        self.assertEqual(result[0]['text'], 'Task 1 for chat 2')

    def test_get_tasks_with_status_filter(self):
        # Arrange
        chat_id_to_test = 1
        status_to_test = task_manager.STATUS_NEW
        expected_tasks = [t for t in self.tasks if t['chat_id'] == chat_id_to_test and t['status'] == status_to_test]
        
        mock_chat_query = MagicMock()
        mock_status_query = MagicMock()
        self.mock_query.where.return_value = mock_chat_query
        mock_chat_query.where.return_value = mock_status_query
        mock_status_query.stream.return_value = self._get_mock_docs(expected_tasks)

        # Act
        result = task_manager.get_tasks(chat_id_to_test, status=status_to_test)

        # Assert
        self.mock_query.where.assert_called_with("chat_id", "==", chat_id_to_test)
        mock_chat_query.where.assert_called_with("status", "==", status_to_test)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], '1')


class TestUpdateTaskStatusTransitions(unittest.TestCase):

    def setUp(self):
        # Patch firestore.client for all tests in this class
        self.patcher = patch('task_manager.firestore.client')
        self.mock_firestore_client = self.patcher.start()
        self.mock_db = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_document_ref = MagicMock() # Renamed to avoid confusion with doc.get() return
        self.mock_document_snapshot = MagicMock() # Mock for the result of doc_ref.get()

        self.mock_firestore_client.return_value = self.mock_db
        self.mock_db.collection.return_value = self.mock_collection
        self.mock_collection.document.return_value = self.mock_document_ref
        
        # Mock user info for assigned_to field
        self.mock_user_info = MagicMock()
        self.mock_user_info.first_name = "Test"
        self.mock_user_info.username = "testuser"

    def tearDown(self):
        self.patcher.stop()

    def _mock_task_get(self, status, assigned_to=None, completed_at=None, exists=True):
        self.mock_document_snapshot.exists = exists
        task_data = {
            "id": "task123",
            "text": "Test Task",
            "status": status,
            "created_by": None,
            "assigned_to": assigned_to,
            "created_at": datetime.now().isoformat(),
        }
        if completed_at:
            task_data["completed_at"] = completed_at
        self.mock_document_snapshot.to_dict.return_value = task_data
        self.mock_document_ref.get.return_value = self.mock_document_snapshot

    def test_update_status_in_progress_to_new(self):
        # Initial state: task is in progress
        self._mock_task_get(task_manager.STATUS_IN_PROGRESS, assigned_to="Some User (@someuser)")

        # Call update_task_status to move to NEW
        result = task_manager.update_task_status("task123", task_manager.STATUS_NEW, None)

        self.assertTrue(result)
        self.mock_document_ref.update.assert_called_once()
        update_args = self.mock_document_ref.update.call_args[0][0]
        self.assertEqual(update_args["status"], task_manager.STATUS_NEW)
        self.assertEqual(update_args["assigned_to"], task_manager.firestore.DELETE_FIELD)

    def test_update_status_done_to_in_progress(self):
        # Initial state: task is done
        self._mock_task_get(task_manager.STATUS_DONE, completed_at=datetime.now().isoformat())

        # Call update_task_status to move to IN_PROGRESS
        result = task_manager.update_task_status("task123", task_manager.STATUS_IN_PROGRESS, self.mock_user_info)

        self.assertTrue(result)
        self.mock_document_ref.update.assert_called_once()
        update_args = self.mock_document_ref.update.call_args[0][0]
        self.assertEqual(update_args["status"], task_manager.STATUS_IN_PROGRESS)
        self.assertEqual(update_args["assigned_to"], "Test (@testuser)")
        self.assertEqual(update_args["completed_at"], task_manager.firestore.DELETE_FIELD)

    def test_invalid_status_transition_new_to_done(self):
        # Initial state: task is new
        self._mock_task_get(task_manager.STATUS_NEW)

        # Call update_task_status with an invalid transition (NEW to DONE)
        result = task_manager.update_task_status("task123", task_manager.STATUS_DONE, None)

        self.assertFalse(result)
        self.mock_document_ref.update.assert_not_called()

    def test_valid_status_transition_new_to_in_progress(self):
        # Initial state: task is new
        self._mock_task_get(task_manager.STATUS_NEW)

        # Call update_task_status with a valid transition (NEW to IN_PROGRESS)
        result = task_manager.update_task_status("task123", task_manager.STATUS_IN_PROGRESS, self.mock_user_info)

        self.assertTrue(result)
        self.mock_document_ref.update.assert_called_once()
        update_args = self.mock_document_ref.update.call_args[0][0]
        self.assertEqual(update_args["status"], task_manager.STATUS_IN_PROGRESS)
        self.assertEqual(update_args["assigned_to"], "Test (@testuser)")

    def test_valid_status_transition_in_progress_to_done(self):
        # Initial state: task is in progress
        self._mock_task_get(task_manager.STATUS_IN_PROGRESS, assigned_to="Some User (@someuser)")

        # Call update_task_status with a valid transition (IN_PROGRESS to DONE)
        result = task_manager.update_task_status("task123", task_manager.STATUS_DONE, None)

        self.assertTrue(result)
        self.mock_document_ref.update.assert_called_once()
        update_args = self.mock_document_ref.update.call_args[0][0]
        self.assertEqual(update_args["status"], task_manager.STATUS_DONE)
        self.assertIn("completed_at", update_args)
        # assigned_to should remain as it was not explicitly cleared
        self.assertNotIn("assigned_to", update_args)

    def test_valid_status_transition_done_to_archived(self):
        # Initial state: task is done
        self._mock_task_get(task_manager.STATUS_DONE, completed_at=datetime.now().isoformat())

        # Call update_task_status with a valid transition (DONE to ARCHIVED)
        result = task_manager.update_task_status("task123", task_manager.STATUS_ARCHIVED, None)

        self.assertTrue(result)
        self.mock_document_ref.update.assert_called_once()
        update_args = self.mock_document_ref.update.call_args[0][0]
        self.assertEqual(update_args["status"], task_manager.STATUS_ARCHIVED)
        self.assertEqual(update_args["completed_at"], task_manager.firestore.DELETE_FIELD)


    def test_delete_task_success(self):
        # Mock that the task exists
        self._mock_task_get(task_manager.STATUS_NEW, exists=True)
        
        result = task_manager.delete_task("task123")
        
        self.assertTrue(result)
        self.mock_document_ref.delete.assert_called_once()

    def test_delete_task_not_found(self):
        # Mock that the task does not exist
        self._mock_task_get(task_manager.STATUS_NEW, exists=False)

        result = task_manager.delete_task("non_existent_task")

        self.assertFalse(result)
        self.mock_document_ref.delete.assert_not_called()


if __name__ == '__main__':
    unittest.main()