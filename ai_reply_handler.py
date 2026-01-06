"""
AI REPLY HANDLER MODULE

Functions for processing AI replies and handling validation errors.
"""

import re

from validation import validate_ai_payload


def process_ai_reply(gui_instance, ai):
    """Process an AI reply and execute actions.
    
    Args:
        gui_instance: The FileAdvisorGUI instance
        ai: The AI response dict
    """
    # Debug: log what we received
    print(f"[DEBUG] process_ai_reply received: {ai}")
    
    # Clean up worker after processing
    if gui_instance.current_worker:
        gui_instance.current_worker.deleteLater()
        gui_instance.current_worker = None
    
    # Add AI response to conversation history
    ai_message = ai.get("message", "").strip()
    if ai_message:
        gui_instance.conversation_history.append({"role": "assistant", "content": ai_message})
        # Keep only last 10 messages
        if len(gui_instance.conversation_history) > 10:
            gui_instance.conversation_history = gui_instance.conversation_history[-10:]
    
    # Re-enable input
    gui_instance.set_processing_state(False)
    
    # Replace "Thinking..." with actual response (simple text replacement)
    html = gui_instance.chat_box.toHtml()
    if "Thinking..." in html or "id='thinking'" in html:
        # Find and replace the thinking message (more flexible pattern matching)
        html = re.sub(r"<span[^>]*id=['\"]thinking['\"][^>]*>.*?</span>", '', html, flags=re.DOTALL)
        # Remove empty AI line if it exists
        html = html.replace(f'<span style="color:#888; font-style:italic;">{gui_instance.ai_name}:</span> <br>', '')
        html = html.replace(f'<span style="color:#0080ff; font-style:italic; font-weight:bold; font-size:11px; background:#e6f2ff; padding:2px 6px; border:1px solid #0080ff;">{gui_instance.ai_name}:</span> <br>', '')
        gui_instance.chat_box.setHtml(html)
    
    # Ensure we always have a dict
    if not isinstance(ai, dict):
        # Log warning to file operations log instead of chat
        gui_instance.log_box.append(f"<span style='color:#8b4513; font-weight:bold; font-size:11px;'>Warning: Invalid response format from AI worker</span>")
        return
    
    ok, ai_norm, err = validate_ai_payload(ai)
    print(f"[DEBUG] validate_ai_payload: ok={ok}, err={err}, normalized={ai_norm}")
    if not ok:
        # Show any conversational message we did get, but don't show technical errors in chat
        msg = str(ai.get("message", "") or "").strip()
        if msg:
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.highlight_blue}; font-weight:bold; font-size:12px;'>{gui_instance.ai_name}:</span> <span style='color:{gui_instance.text}; font-weight:bold;'>{msg}</span>")
        # Log error to file operations log instead of chat
        if err:
            _handle_validation_error(gui_instance, err, ai)
        return
    
    ai = ai_norm
    print(f"[DEBUG] After validation, processing: action={ai.get('action')}, args={ai.get('args')}, has_actions={('actions' in ai)}")
    
    # Handle multiple actions
    if "actions" in ai and isinstance(ai["actions"], list):
        # Process multiple actions sequentially
        actions_list = ai["actions"]
        for i, action_item in enumerate(actions_list):
            # Map "create_file" to "create_folder" for each action
            if action_item.get("action") == "create_file":
                action_item["action"] = "create_folder"
            # Process each action
            gui_instance._process_single_action(action_item, is_multi_action=True, action_num=i+1, total_actions=len(actions_list))
        return
    
    # Single action processing (existing logic)
    # Map "create_file" to "create_folder" (users often say "create file" but mean folder)
    if ai.get("action") == "create_file":
        ai["action"] = "create_folder"
    
    gui_instance._process_single_action(ai, is_multi_action=False)


def _handle_validation_error(gui_instance, err, ai):
    """Handle validation errors by showing helpful messages to the user.
    
    Args:
        gui_instance: The FileAdvisorGUI instance
        err: Error message from validation
        ai: The AI response dict
    """
    from file_indexing import auto_scan_for_missing_args
    
    # Generate helpful, conversational error messages based on missing args
    helpful_msg = None
    action_attempted = ai.get("action", "unknown")
    user_msg = gui_instance.conversation_history[-1].get("content", "").lower() if gui_instance.conversation_history else ""
    
    if "Missing required args" in err:
        # Extract which args are missing
        if "read_file" in err and "path" in err:
            helpful_msg = "I'd be happy to read a file for you! Which file would you like me to read? You can tell me the file name or path, or I can list the files in your folders first so you can choose one."
            # Auto-scan to help user see available files
            auto_scan_for_missing_args(gui_instance, "read")
        elif "move_file" in err:
            if "source" in err or "destination" in err:
                helpful_msg = "I need to know which files to move and where to move them. Would you like me to scan your files first so you can tell me which ones to organize?"
                auto_scan_for_missing_args(gui_instance, "move")
        elif "file_type" in err and "path" in err:
            helpful_msg = "Which file would you like me to check the type of? I can list your files first if you'd like."
            auto_scan_for_missing_args(gui_instance, "check")
        else:
            # Generic helpful message
            helpful_msg = f"I need a bit more information to {action_attempted.replace('_', ' ')}. Could you provide more details about what you'd like me to do?"
    
    if helpful_msg:
        gui_instance.chat_box.append(f"<span style='color:{gui_instance.highlight_blue}; font-weight:bold; font-size:12px;'>{gui_instance.ai_name}:</span> <span style='color:{gui_instance.text}; font-weight:bold;'>{helpful_msg}</span>")
    else:
        # Log technical error to operations log
        gui_instance.log_box.append(f"<span style='color:{gui_instance.error_red}; font-weight:bold; font-size:11px;'>Error: {err}</span>")

