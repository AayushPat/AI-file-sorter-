"""
ACTION VALIDATION MODULE

Validates AI responses to ensure they contain valid actions and arguments
before executing file operations. Prevents invalid commands from being executed.
"""

from typing import Tuple

# ALLOWED ACTIONS THAT THE AI CAN REQUEST
ALLOWED_ACTIONS = {
    "chat",
    "none",
    "list_files",
    "list_all_files",
    "move_file",
    "create_folder",
    "read_file",
    "file_type",
}

# REQUIRED ARGUMENTS FOR EACH ACTION TYPE
_REQUIRED_ARGS = {
    "list_files": ("path",),
    "list_all_files": ("path",),
    "move_file": ("source", "destination"),
    "create_folder": ("path",),
    "read_file": ("path",),
    "file_type": ("path",),
}


def validate_ai_payload(ai: object) -> Tuple[bool, dict, str]:
    """
    Validate and normalize a model/Interpreter response before executing tools.
    
    Handles both single actions and arrays of actions.
    
    Args:
        ai: The AI response object (dict, list, or invalid type)
    
    Returns:
        Tuple of (is_valid, normalized_ai_dict, error_message)
        - is_valid: True if validation passed
        - normalized_ai: Dict with 'action', 'args', 'message' (single) or 'actions' list (multiple)
        - error_message: Empty string if valid, error description if invalid
    """
    # HANDLE ARRAY OF ACTIONS
    if isinstance(ai, list):
        validated_actions = []
        for i, action_item in enumerate(ai):
            if not isinstance(action_item, dict):
                return False, {"action": "chat", "args": {}, "message": ""}, f"Action {i+1} in array is not a JSON object."
            ok, normalized, err = validate_single_action(action_item)
            if not ok:
                return False, {"action": "chat", "args": {}, "message": ""}, f"Action {i+1}: {err}"
            validated_actions.append(normalized)
        return True, {"actions": validated_actions, "message": f"Executing {len(validated_actions)} action(s)"}, ""
    
    # HANDLE INVALID TYPE
    if not isinstance(ai, dict):
        return False, {"action": "chat", "args": {}, "message": ""}, "AI output is not a JSON object."
    
    # HANDLE MULTI-ACTION FORMAT (dict with "actions" key)
    if "actions" in ai and isinstance(ai["actions"], list):
        validated_actions = []
        for i, action_item in enumerate(ai["actions"]):
            if not isinstance(action_item, dict):
                return False, {"action": "chat", "args": {}, "message": ""}, f"Action {i+1} in array is not a JSON object."
            ok, normalized, err = validate_single_action(action_item)
            if not ok:
                return False, {"action": "chat", "args": {}, "message": ""}, f"Action {i+1}: {err}"
            validated_actions.append(normalized)
        return True, {"actions": validated_actions, "message": ai.get("message", f"Executing {len(validated_actions)} action(s)")}, ""
    
    # HANDLE SINGLE ACTION
    return validate_single_action(ai)


def validate_single_action(ai: dict) -> Tuple[bool, dict, str]:
    """
    Validate a single action dictionary.
    
    Checks that:
    - Action field exists and is a valid action type
    - Required arguments are present
    - Arguments are the correct type
    
    Args:
        ai: Dictionary with 'action' and optionally 'args' keys
    
    Returns:
        Tuple of (is_valid, normalized_dict, error_message)
    """
    # CHECK ACTION FIELD EXISTS
    action = ai.get("action")
    if not isinstance(action, str) or not action.strip():
        return False, {"action": "chat", "args": {}, "message": ""}, "Missing or invalid 'action' field."

    action = action.strip()

    # CHECK ACTION IS ALLOWED
    if action not in ALLOWED_ACTIONS:
        return False, {"action": "chat", "args": {}, "message": ai.get("message", "")}, f"Unknown action '{action}'."

    # NORMALIZE ARGS AND MESSAGE
    args = ai.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return False, {"action": "chat", "args": {}, "message": ai.get("message", "")}, "Invalid 'args' (must be an object)."

    message = ai.get("message", "")
    if message is None:
        message = ""
    if not isinstance(message, str):
        message = str(message)

    # TREAT 'NONE' AS CHAT-ONLY TO AVOID ODD UI STATES
    if action == "none":
        return True, {"action": "chat", "args": {}, "message": message or "No file action required."}, ""

    # VALIDATE REQUIRED ARGUMENTS FOR TOOL ACTIONS
    required = _REQUIRED_ARGS.get(action, tuple())
    missing = [k for k in required if not isinstance(args.get(k), str) or not args.get(k).strip()]
    
    # SPECIAL HANDLING: ALLOW MISSING PATH FOR ACTIONS THAT CAN SCAN ALL ACCESSIBLE DIRECTORIES
    # Don't fail validation - let the action handler add default paths or ask user
    if action in ["create_folder", "list_files", "list_all_files", "read_file", "file_type"] and "path" in missing:
        # Add empty string - action handler will add default path(s) or ask user to choose
        args["path"] = ""  # Empty string will be handled by action handler
        missing.remove("path")
    
    if missing:
        return False, {"action": "chat", "args": {}, "message": message}, f"Missing required args for '{action}': {', '.join(missing)}."

    # NORMALIZE COMMON OPTIONAL ARGS
    if action == "list_files":
        # Optional 'limit' (int)
        if "limit" in args and args["limit"] is not None:
            try:
                args["limit"] = int(args["limit"])
            except Exception:
                return False, {"action": "chat", "args": {}, "message": message}, "Invalid 'limit' (must be an integer)."

    # RETURN NORMALIZED ACTION DICT
    return True, {"action": action, "args": args, "message": message}, ""

