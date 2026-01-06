"""
ACTION PROCESSOR MODULE

Handles processing of AI-generated actions (list_files, move_file, create_folder, etc.).
This module contains the core logic for executing file operations and handling
action inference when the AI claims to do something but doesn't generate proper actions.
"""

import re
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import QDialog

from tools import list_files, move_file, file_type, create_folder, read_file, list_all_files
from dialogs import PreviewDialog


def process_single_action(
    gui_instance,
    ai: dict,
    is_multi_action: bool = False,
    action_num: int = 1,
    total_actions: int = 1
) -> None:
    """Process a single action. Can be called for single or multiple actions.
    
    Args:
        gui_instance: The FileAdvisorGUI instance (needed to access UI elements and state)
        ai: Action dict with 'action', 'args', and 'message' keys
        is_multi_action: Whether this is part of a multi-action sequence
        action_num: Action number in sequence (for display)
        total_actions: Total number of actions in sequence
    """
    # Show action number if multiple actions
    if is_multi_action and total_actions > 1:
        prefix = f"[Action {action_num}/{total_actions}] "
    else:
        prefix = ""
    
    # Check if AI said it will do something but action is "none" or "chat"
    action = ai.get("action")
    msg = ai.get("message", "").strip()
    msg_lower = msg.lower()
    user_msg = gui_instance.conversation_history[-1].get("content", "").lower() if gui_instance.conversation_history else ""
    
    print(f"[DEBUG] _process_single_action: action={action}, msg={msg[:50]}, user_msg={user_msg[:50]}")
    
    # Check if this is a question - if so, don't infer actions, let the AI ask
    is_question = msg.endswith("?") or any(word in msg_lower for word in ["would you", "should i", "do you", "which", "what", "how", "can you", "could you", "would you like"])
    
    # Phrases that indicate the AI said it will do something (not asking)
    create_phrases = ["create", "creating", "created", "make", "making", "set up", "i'll create", "let me create", "new category", "category"]
    sort_phrases = ["sorted", "sort", "sorting", "organized", "organize", "organizing", "moved", "move", "moving", "i sorted", "i've sorted", "i'll sort", "i moved", "i've moved", "i'll move"]
    repeat_phrases = ["again", "one more time", "do it again", "repeat", "let's do it", "alright, let's", "i'll scan", "i'll do"]
    
    # If AI says it sorted/moved files but action is none/chat, try to infer move actions
    if action in ["none", "chat"] and not is_question and any(phrase in msg_lower for phrase in sort_phrases):
        _infer_and_execute_move_actions(gui_instance, user_msg, msg_lower)
        return
    
    # If AI says it will create something but action is none/chat, infer create_folder
    if action in ["none", "chat"] and not is_question and any(phrase in msg_lower for phrase in create_phrases):
        if any(word in user_msg for word in ["create", "make", "folder", "file", "directory", "category"]):
            folder_name = _extract_folder_name(user_msg)
            if folder_name:
                ai = {
                    "action": "create_folder",
                    "args": {"path": folder_name},
                    "message": ai.get("message", "").strip() or f"Creating folder: {folder_name}"
                }
                action = ai.get("action")
                gui_instance.log_box.append(f"<span style='color:{gui_instance.highlight_blue}; font-weight:bold; font-size:11px;'>Inferred create_folder action for: {folder_name}</span>")
    
    # If AI said it will repeat but didn't - force it to repeat the last action
    elif action in ["none", "chat"] and not is_question and gui_instance.last_action and any(phrase in msg_lower for phrase in repeat_phrases):
        ai = {
            "action": gui_instance.last_action,
            "args": gui_instance.last_action_args.copy() if gui_instance.last_action_args else {},
            "message": ai.get("message", "").strip() or f"Repeating: {gui_instance.last_action}"
        }
        action = ai.get("action")
    
    # Handle "chat" or "none" actions - these are for conversational responses/questions
    if ai.get("action") in ["chat", "none"]:
        msg = ai.get("message", "").strip()
        if not msg:
            msg = "I'm here, but I didn't get a response. Try again?"
        is_question = msg.endswith("?") or any(word in msg.lower() for word in ["would you", "should i", "do you", "which", "what", "how", "can you", "could you"])
        if is_question:
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.highlight_blue}; font-weight:bold; font-size:12px;'>{gui_instance.ai_name}:</span> <span style='color:{gui_instance.text}; font-weight:bold; font-style:italic;'>{msg}</span>")
        else:
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.highlight_blue}; font-weight:bold; font-size:12px;'>{gui_instance.ai_name}:</span> <span style='color:{gui_instance.text}; font-weight:bold;'>{msg}</span>")
        return
    
    # Command mode - show the conversation message
    msg = ai.get("message", "").strip()
    if not msg:
        msg = "Processing your request..."
    gui_instance.chat_box.append(f"<span style='color:{gui_instance.highlight_blue}; font-weight:bold; font-size:12px;'>{gui_instance.ai_name}:</span> <span style='color:{gui_instance.text}; font-weight:bold;'>{msg}</span>")
    
    action = ai.get("action")
    args = ai.get("args", {})
    
    # Check if preview mode is enabled and this is a file operation
    if gui_instance.perms.preview_mode and action and action not in ["none", "chat"]:
        preview_dialog = PreviewDialog([{"action": action, "args": args}], gui_instance)
        if preview_dialog.exec() != QDialog.DialogCode.Accepted:
            gui_instance.chat_box.append(f"<span style='color:#ff6600; font-weight:bold; font-size:12px;'>CANCELLED:</span> <span style='color:#ff6600; font-weight:bold;'>Action cancelled by user</span>")
            return
    
    # Store last action for "again" / "repeat" commands (only for actual file operations)
    if action and action not in ["none", "chat"]:
        gui_instance.last_action = action
        gui_instance.last_action_args = args.copy() if args else {}
    
    result = None
    
    # Show action status if not "none" or "chat"
    if action and action not in ["none", "chat"]:
        action_names = {
            "list_files": "Listing files",
            "list_all_files": "Scanning all files",
            "read_file": "Reading file",
            "move_file": "Moving file",
            "create_folder": "Creating folder",
            "file_type": "Checking file type"
        }
        action_display = action_names.get(action, action)
        if is_multi_action:
            gui_instance.chat_box.append(f"<span style='color:#666; font-weight:bold; font-size:11px;'>{prefix}Performing: {action_display}...</span>")
        else:
            gui_instance.chat_box.append(f"<span style='color:#666; font-weight:bold; font-size:11px;'>Performing: {action_display}...</span>")
    
    # Execute the action
    if action == "list_all_files":
        result = _handle_list_all_files(gui_instance, args)
    elif action == "list_files":
        result = _handle_list_files(gui_instance, args)
    elif action == "read_file":
        result = _handle_read_file(gui_instance, args)
    elif action == "move_file":
        result = _handle_move_file(gui_instance, args)
    elif action == "create_folder":
        result = _handle_create_folder(gui_instance, args)
    
    # Conversational summary for user-facing chat
    if action == "list_files" and result:
        files = result.get("files", [])
        if len(files) == 0:
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.success_green}; font-weight:bold; font-size:12px;'>RESULT:</span> <span style='color:{gui_instance.success_green}; font-weight:bold;'>No files found.</span>")
        elif len(files) == 1:
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.success_green}; font-weight:bold; font-size:12px;'>RESULT:</span> <span style='color:{gui_instance.success_green}; font-weight:bold;'>One file found: {files[0]}</span>")
        else:
            summary = ", ".join(files[:min(len(files), 3)])
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.success_green}; font-weight:bold; font-size:12px;'>RESULT:</span> <span style='color:{gui_instance.success_green}; font-weight:bold;'>Files found: {summary}</span>")
    
    # UPDATE COUNTERS
    gui_instance.update_counters()
    
    # PRINT CLEAN RESULT TO CHAT (only if successful and not already shown)
    if result and action != "create_folder":
        clean_msg = result.get("message") or result.get("status") or str(result)
        if result.get("error"):
            error_msg = result.get("error", "Unknown error")
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.error_red}; font-weight:bold; font-size:12px;'>{gui_instance.ai_name}:</span> <span style='color:{gui_instance.error_red}; font-weight:bold;'>I can't do that. {error_msg}</span>")
            gui_instance.log_box.append(f"<span style='color:{gui_instance.error_red}; font-weight:bold; font-size:11px;'>Error: {error_msg}</span>")
        else:
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.success_green}; font-weight:bold; font-size:12px;'>COMPLETE:</span> <span style='color:{gui_instance.success_green}; font-weight:bold;'>{clean_msg}</span>")


def _infer_and_execute_move_actions(gui_instance, user_msg: str, msg_lower: str) -> None:
    """Infer move_file actions when AI claims to sort but doesn't generate actions."""
    gui_instance.log_box.append(f"<span style='color:#ff6600; font-weight:bold; font-size:11px;'>AI claimed to sort files but returned action 'none' or 'chat'. Attempting to infer move actions...</span>")
    
    file_index = gui_instance.memory.data.get("file_index", {}).get("all_files", [])
    categories = gui_instance.memory.data.get("categories", {})
    root_files = [f for f in file_index if "/" not in f.get("path", "") or f.get("path", "").count("/") == 0]
    
    inferred_actions = []
    user_msg_lower = user_msg.lower()
    
    # Check if user mentioned specific file types (e.g., "csv files", ".csv files")
    if ".csv" in user_msg_lower or "csv" in user_msg_lower:
        csv_files = [f for f in root_files if f.get("extension", "").lower() == ".csv"]
        for cat_name in categories.keys():
            if cat_name.lower() in user_msg_lower:
                for file_info in csv_files:
                    source_path = file_info.get("full_path", "")
                    if not source_path and gui_instance.perms.allowed_root:
                        source_path = str(gui_instance.perms.allowed_root / file_info.get("name", ""))
                    
                    if gui_instance.perms.allowed_root:
                        destination_path = str(gui_instance.perms.allowed_root / cat_name / file_info.get("name", ""))
                    else:
                        destination_path = f"{cat_name}/{file_info.get('name', '')}"
                    
                    inferred_actions.append({
                        "action": "move_file",
                        "args": {
                            "source": source_path,
                            "destination": destination_path
                        },
                        "message": f"Moving {file_info.get('name', '')} to {cat_name}"
                    })
                break
    
    # If no specific type mentioned, try to match files to categories semantically
    if not inferred_actions and root_files and categories:
        for file_info in root_files[:10]:  # Limit to first 10
            file_name = file_info.get("name", "").lower()
            for cat_name, cat_path in categories.items():
                cat_lower = cat_name.lower()
                if cat_lower in file_name or any(keyword in file_name for keyword in ["math", "calc", "algebra", "equation"] if cat_lower == "math"):
                    source_path = file_info.get("full_path", "")
                    if not source_path and gui_instance.perms.allowed_root:
                        source_path = str(gui_instance.perms.allowed_root / file_info.get("name", ""))
                    
                    if gui_instance.perms.allowed_root:
                        destination_path = str(gui_instance.perms.allowed_root / cat_name / file_info.get("name", ""))
                    else:
                        destination_path = f"{cat_name}/{file_info.get('name', '')}"
                    
                    inferred_actions.append({
                        "action": "move_file",
                        "args": {
                            "source": source_path,
                            "destination": destination_path
                        },
                        "message": f"Moving {file_info.get('name', '')} to {cat_name}"
                    })
                    break
    
    if inferred_actions:
        gui_instance.log_box.append(f"<span style='color:{gui_instance.highlight_blue}; font-weight:bold; font-size:11px;'>Inferred {len(inferred_actions)} move_file action(s)</span>")
        for i, action_item in enumerate(inferred_actions):
            process_single_action(gui_instance, action_item, is_multi_action=True, action_num=i+1, total_actions=len(inferred_actions))
    else:
        helpful_msg = "I see you want me to sort files, but I need a bit more information. Could you try asking again, or tell me which specific files you'd like me to organize?"
        gui_instance.chat_box.append(f"<span style='color:{gui_instance.highlight_blue}; font-weight:bold; font-size:12px;'>{gui_instance.ai_name}:</span> <span style='color:{gui_instance.text}; font-weight:bold;'>{helpful_msg}</span>")


def _extract_folder_name(user_msg: str) -> str:
    """Extract folder name from user message using regex patterns."""
    folder_name = ""
    # Try multiple patterns to extract folder name
    match = re.search(r'(?:create|make).*?(?:folder|file|directory|category).*?(?:called|named|name)?\s+(?:called|named)?\s*(\w+)', user_msg, re.IGNORECASE)
    if match:
        folder_name = match.group(1)
    elif "math" in user_msg.lower():
        folder_name = "math"
    else:
        match = re.search(r'(?:create|make)\s+(?:a|an)?\s*(?:folder|file|directory|category)?\s*(?:called|named)?\s*(\w+)', user_msg, re.IGNORECASE)
        if match:
            folder_name = match.group(1)
        else:
            match = re.search(r'(?:category|folder)\s+(?:called|named)?\s*(\w+)', user_msg, re.IGNORECASE)
            if match:
                folder_name = match.group(1)
    return folder_name


def _handle_list_all_files(gui_instance, args: dict) -> Optional[Dict[str, Any]]:
    """Handle list_all_files action."""
    path = args.get("path", "").strip()
    
    if not path:
        if not gui_instance.perms.allowed_root:
            return None
        
        total_count = 0
        scanned_paths = []
        root_path = gui_instance.perms.allowed_root
        try:
            if root_path.exists() and root_path.is_dir():
                test_result = list_all_files(root_path)
                if test_result and "error" not in test_result:
                    count = test_result.get("count", 0)
                    op_id = gui_instance.add_action_card("scan.png", "Deep Scan", str(root_path), "#c0d9ff", "list_all_files")
                    total_count += count
                    gui_instance.update_operation_stats(op_id, files_scanned=count)
                    scanned_paths.append(str(root_path))
        except (PermissionError, OSError):
            pass
        
        if scanned_paths:
            paths_display = ", ".join([Path(p).name for p in scanned_paths])
            result = {
                "count": total_count,
                "message": f"Scan complete. Found {total_count} files in {len(scanned_paths)} directory(ies): {paths_display}"
            }
            gui_instance.files_scanned += total_count
            return result
        else:
            return {"count": 0, "message": "No accessible directories found to scan."}
    else:
        op_id = gui_instance.add_action_card("scan.png", "Deep Scan", path, "#c0d9ff", "list_all_files")
        ok, norm = gui_instance.perms.require_allowed(path, purpose='scan')
        if not ok:
            error_msg = f"<span style='color:{gui_instance.error_red}; font-weight:bold; font-size:12px;'>PERMISSION DENIED:</span> <span style='color:{gui_instance.error_red}; font-weight:bold;'>{norm}</span>"
            gui_instance.chat_box.append(error_msg)
            return None
        result = list_all_files(norm)
        if result:
            count = result.get("count", 0)
            gui_instance.files_scanned += count
            gui_instance.update_operation_stats(op_id, files_scanned=count)
        return result


def _handle_list_files(gui_instance, args: dict) -> Optional[Dict[str, Any]]:
    """Handle list_files action."""
    path = args.get("path", "").strip()
    limit = args.get("limit")
    
    if not path:
        if not gui_instance.perms.allowed_root:
            return None
        
        all_files = []
        scanned_paths = []
        root_path = gui_instance.perms.allowed_root
        try:
            if root_path.exists() and root_path.is_dir():
                op_id = gui_instance.add_action_card("folder.png", "Scanning Folder", str(root_path), "#b8d4ff", "list_files")
                result = list_files(root_path, limit)
                if result and "error" not in result:
                    files = result.get("files", [])
                    all_files.extend(files)
                    scanned_paths.append(str(root_path))
                    gui_instance.update_operation_stats(op_id, files_scanned=len(files))
        except (PermissionError, OSError):
            pass
        
        if scanned_paths:
            paths_display = ", ".join([Path(p).name for p in scanned_paths])
            result = {
                "count": len(all_files),
                "files": all_files[:limit] if limit else all_files,
                "message": f"Found {len(all_files)} items in {len(scanned_paths)} accessible directory(ies): {paths_display}"
            }
            gui_instance.files_scanned += len(all_files)
            return result
        else:
            return {"count": 0, "files": [], "message": "No accessible directories found to scan."}
    else:
        op_id = gui_instance.add_action_card("folder.png", "Scanning Folder", path, "#b8d4ff", "list_files")
        ok, norm = gui_instance.perms.require_allowed(path, purpose='list')
        if not ok:
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.error_red}; font-weight:bold; font-size:12px;'>PERMISSION DENIED:</span> <span style='color:{gui_instance.error_red}; font-weight:bold;'>{norm}</span>")
            return None
        result = list_files(norm, limit)
        count = result.get("count", 0)
        gui_instance.files_scanned += count
        gui_instance.update_operation_stats(op_id, files_scanned=count)
        return result


def _handle_read_file(gui_instance, args: dict) -> Optional[Dict[str, Any]]:
    """Handle read_file action."""
    path = args.get("path") or args.get("paths")
    
    if not path or not path.strip():
        gui_instance.chat_box.append(f"<span style='color:{gui_instance.highlight_blue}; font-weight:bold; font-size:12px;'>{gui_instance.ai_name}:</span> <span style='color:{gui_instance.text}; font-weight:bold;'>Which file would you like me to read? Let me show you what's available...</span>")
        gui_instance._auto_scan_for_missing_args("read")
        return None
    
    op_id = gui_instance.add_action_card("file.png", "Reading File", path, "#b8d4ff", "read_file")
    ok, norm = gui_instance.perms.require_allowed(path, purpose='read')
    if not ok:
        gui_instance.chat_box.append(f"<span style='color:{gui_instance.error_red}; font-weight:bold; font-size:12px;'>PERMISSION DENIED:</span> <span style='color:{gui_instance.error_red}; font-weight:bold;'>{norm}</span>")
        return None
    result = read_file(norm)
    gui_instance.files_scanned += 1
    gui_instance.update_operation_stats(op_id, files_scanned=1)
    return result


def _handle_move_file(gui_instance, args: dict) -> Optional[Dict[str, Any]]:
    """Handle move_file action."""
    src = args.get("source") or args.get("src")
    dst = args.get("destination") or args.get("dst")
    
    op_id = gui_instance.add_action_card("arrow.png", "Moving File", f"{src} → {dst}", "#c0d9ff", "move_file")
    ok_src, norm_src = gui_instance.perms.require_allowed(src, purpose='move source')
    ok_dst, norm_dst = gui_instance.perms.require_allowed(dst, purpose='move destination')
    if not ok_src or not ok_dst:
        msg = norm_src if not ok_src else norm_dst
        gui_instance.chat_box.append(f"<span style='color:{gui_instance.error_red}; font-weight:bold; font-size:12px;'>PERMISSION DENIED:</span> <span style='color:{gui_instance.error_red}; font-weight:bold;'>{msg}</span>")
        return None
    result = move_file(norm_src, norm_dst)
    gui_instance.files_moved += 1
    gui_instance.update_operation_stats(op_id, files_moved=1)
    return result


def _handle_create_folder(gui_instance, args: dict) -> Optional[Dict[str, Any]]:
    """Handle create_folder action."""
    path = args.get("path", "").strip()
    
    # If path is empty or just a folder name (no slashes), create it in the allowed root directory
    if not path or ("/" not in path and "\\" not in path):
        if not gui_instance.perms.allowed_root or not gui_instance.perms.allowed_root.exists():
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.error_red}; font-weight:bold; font-size:12px;'>{gui_instance.ai_name}:</span> <span style='color:{gui_instance.error_red}; font-weight:bold;'>I can't create folders. No accessible directory is configured. Please open Permissions and select a root directory.</span>")
            return None
        
        base_path = gui_instance.perms.allowed_root
        if path:
            full_path = base_path / path
            path = str(full_path)
        else:
            path = str(base_path)
    
    if not path:
        return None
    
    op_id = gui_instance.add_action_card("folder.png", "Creating Folder", path, "#c0d9ff", "create_folder")
    
    # Normalize the path before checking permissions
    try:
        path_obj = Path(path).expanduser()
        # Resolve to absolute path for consistent checking
        if path_obj.exists():
            path = str(path_obj.resolve())
        else:
            # Resolve parent to get absolute path
            parent = path_obj.parent.resolve() if path_obj.parent.exists() else path_obj.parent
            path = str(path_obj.resolve() if path_obj.exists() else path_obj)
    except Exception:
        # If resolution fails, use path as-is
        pass
    
    ok, norm = gui_instance.perms.require_allowed(path, purpose='create folder')
    if not ok:
        gui_instance.chat_box.append(f"<span style='color:{gui_instance.error_red}; font-weight:bold; font-size:12px;'>PERMISSION DENIED:</span> <span style='color:{gui_instance.error_red}; font-weight:bold;'>{norm}</span>")
        return None
    
    # Resolve to absolute path for consistent checking
    try:
        norm_path = Path(norm).expanduser().resolve()
        norm = str(norm_path)
    except Exception:
        pass  # Use norm as-is if resolution fails
    
    # Create the folder
    try:
        result = create_folder(norm)
        if result and "error" not in result:
            if result.get("already_exists"):
                gui_instance.chat_box.append(f"<span style='color:{gui_instance.highlight_blue}; font-weight:bold; font-size:12px;'>{gui_instance.ai_name}:</span> <span style='color:{gui_instance.text}; font-weight:bold;'>That folder already exists at: {result.get('path', norm)}</span>")
            else:
                created_path = result.get("path", norm)
                created_path_obj = Path(created_path)
                
                # Automatically add to categories if it's within the allowed root
                if gui_instance.perms.allowed_root and created_path_obj.exists():
                    try:
                        relative_path = created_path_obj.relative_to(gui_instance.perms.allowed_root)
                        if len(relative_path.parts) == 1:
                            category_name = relative_path.parts[0]
                            if category_name not in gui_instance.memory.data.get("categories", {}):
                                gui_instance.memory.data.setdefault("categories", {})[category_name] = str(created_path_obj)
                                gui_instance.memory.save()
                                gui_instance._refresh_categories_list()
                                gui_instance.log_box.append(f"<span style='color:{gui_instance.highlight_blue}; font-weight:bold; font-size:11px;'>Added '{category_name}' to categories</span>")
                    except (ValueError, AttributeError):
                        pass
                
                gui_instance.chat_box.append(f"<span style='color:{gui_instance.success_green}; font-weight:bold; font-size:12px;'>COMPLETE:</span> <span style='color:{gui_instance.success_green}; font-weight:bold;'>Created folder at: {created_path}</span>")
                result = None  # Clear to prevent duplicate message
        else:
            error_msg = result.get("error", "Unknown error") if result else "Failed to create folder"
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.error_red}; font-weight:bold; font-size:12px;'>{gui_instance.ai_name}:</span> <span style='color:{gui_instance.error_red}; font-weight:bold;'>I can't create that folder. {error_msg}</span>")
            gui_instance.log_box.append(f"<span style='color:{gui_instance.error_red}; font-weight:bold; font-size:11px;'>Error: {error_msg}</span>")
            return None
    except Exception as e:
        gui_instance.chat_box.append(f"<span style='color:{gui_instance.error_red}; font-weight:bold; font-size:12px;'>{gui_instance.ai_name}:</span> <span style='color:{gui_instance.error_red}; font-weight:bold;'>I can't create that folder. {str(e)}</span>")
        gui_instance.log_box.append(f"<span style='color:{gui_instance.error_red}; font-weight:bold; font-size:11px;'>Error creating folder: {str(e)}</span>")
        return None
    
    return result

