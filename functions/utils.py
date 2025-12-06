from typing import List, Dict, Any, Optional
import task_manager

def delete_messages(bot, chat_id: int, message_ids: List[int]) -> None:
    """Deletes a list of messages from a chat."""
    if not message_ids:
        return
        
    for msg_id in message_ids:
        try:
            bot.delete_message(chat_id, msg_id)
        except Exception as e:
            # It's common to fail deleting old messages or messages that don't exist
            print(f"Could not delete message {msg_id}: {e}")

def cleanup_previous_bot_messages(bot, chat_id: int) -> None:
    """
    Retrieves the list of previous bot message IDs from the user state
    and deletes them.
    """
    chat_state = task_manager.get_user_state(chat_id) or {}
    old_message_ids = chat_state.get("data", {}).get("last_task_list_message_ids", [])
    delete_messages(bot, chat_id, old_message_ids)

def cleanup_user_message(bot, chat_id: int, message_id: int) -> None:
    """Attempts to delete a specific user message."""
    try:
        bot.delete_message(chat_id, message_id)
    except Exception as e:
        print(f"Could not delete user command message: {e}")

def save_new_bot_messages(chat_id: int, new_message_ids: List[int], state: str = "idle", additional_data: Dict[str, Any] = None) -> None:
    """
    Saves the IDs of newly sent bot messages to the user state so they can be
    cleaned up later. preserving other data in the state.
    """
    chat_state = task_manager.get_user_state(chat_id) or {}
    current_data = chat_state.get("data", {})
    
    # Update data with new message IDs
    current_data['last_task_list_message_ids'] = new_message_ids
    
    # Merge additional data if provided
    if additional_data:
        current_data.update(additional_data)
        
    task_manager.set_user_state(chat_id, state, data=current_data)
