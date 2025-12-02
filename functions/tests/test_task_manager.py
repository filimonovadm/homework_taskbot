import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import sys
import os

# Add the 'functions' directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import task_manager

class TestTaskManager(unittest.TestCase):

    @patch('task_manager.firestore.client')
    def test_add_task_adds_created_at_timestamp(self, mock_firestore_client):
        # Mock the Firestore client and collection/document methods
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_document = MagicMock()

        mock_firestore_client.return_value = mock_db
        mock_db.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_document

        # Call the add_task function
        task_text = "Test task with timestamp"
        new_task = task_manager.add_task(task_text)

        # Assertions
        self.assertIn('created_at', new_task)
        self.assertIsInstance(new_task['created_at'], str)
        
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
        self.assertEqual(set_data['status'], task_manager.STATUS_NEW)
        self.assertIn('created_at', set_data)
        
        # Ensure the timestamp in set_data is also valid
        try:
            datetime.fromisoformat(set_data['created_at'])
        except ValueError:
            self.fail("created_at timestamp in set_data is not in ISO format")

if __name__ == '__main__':
    unittest.main()
