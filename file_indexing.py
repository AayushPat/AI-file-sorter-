"""
FILE INDEXING MODULE

Functions for scanning files and building the file index for AI context.
"""

import os
import time
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QProgressDialog, QApplication

from filenameParser import parse_file_info
from contentReader import read_file_content
from contentAnalyzer import analyze_file
from workers import IndexingWorker


def scan_all_files_for_ai(gui_instance):
    """Scan all files in root directory and store in memory for AI context.
    
    Args:
        gui_instance: The FileAdvisorGUI instance
    """
    # Clear old file index first
    if "file_index" not in gui_instance.memory.data:
        gui_instance.memory.data["file_index"] = {}
    gui_instance.memory.data["file_index"]["all_files"] = []
    gui_instance.memory.data["file_index"]["last_scan"] = None
    
    if not gui_instance.perms.allowed_root or not gui_instance.perms.allowed_root.exists():
        # No root directory - clear the index and save
        gui_instance.memory.save()
        return
    
    try:
        # Scan all files recursively
        all_files = []
        root_path = gui_instance.perms.allowed_root
        
        # Get content reading configuration
        content_config = gui_instance.memory.data.get("content_reading_config", {})
        if not content_config:
            content_config = {
                "enabled": False,
                "enabled_types": [],
                "max_file_size": 5 * 1024 * 1024
            }
        
        # Get AI model info for content analysis
        from config import get_ai_model
        ai_url = "http://localhost:11434/api/generate"
        ai_model = get_ai_model()
        
        for root, dirs, files in os.walk(root_path):
            # Skip hidden files/directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]
            
            for file in files:
                file_path = Path(root) / file
                try:
                    # Get relative path from root
                    relative_path = file_path.relative_to(root_path)
                    file_info = {
                        "path": str(relative_path),
                        "name": file,
                        "full_path": str(file_path),
                        "extension": file_path.suffix.lower()
                    }
                    
                    # Step 1: Parse filename (ALWAYS do this - it's fast and provides basic info)
                    try:
                        file_info = parse_file_info(file_info)
                    except Exception:
                        # If parsing fails, keep basic info - file is still indexed
                        pass
                    
                    # Step 2: Try to read content if enabled (but don't fail if it doesn't work)
                    content_data = None
                    if content_config.get("enabled", False):
                        try:
                            content_data = read_file_content(
                                file_path,
                                file_info["extension"],
                                content_config
                            )
                        except Exception:
                            # Content reading failed, but file is still indexed with filename info
                            content_data = None
                    
                    # Step 3: Analyze content if we have content data (skip if slow/optional)
                    if content_data:
                        try:
                            file_info = analyze_file(
                                file_info,
                                content_data,
                                ai_url,
                                ai_model
                            )
                        except Exception:
                            # Content analysis failed, but file is still indexed with filename info
                            pass
                    
                    # ALWAYS add file to index, even if content reading/analysis failed
                    all_files.append(file_info)
                except (ValueError, PermissionError):
                    # Skip files we can't access, but continue with others
                    continue
                except Exception as e:
                    # Log error but continue with other files - don't let one bad file stop indexing
                    if hasattr(gui_instance, 'log_box'):
                        gui_instance.log_box.append(f"<span style='color:#ff6600; font-weight:bold; font-size:11px;'>Error processing {file}: {str(e)}</span>")
                    continue
        
        # Store in memory (overwrites the empty array we set earlier)
        gui_instance.memory.data["file_index"]["all_files"] = all_files
        gui_instance.memory.data["file_index"]["last_scan"] = time.time()
        gui_instance.memory.data["file_index"]["root_path"] = str(root_path)  # Store which root this index is for
        
        # Save file notes if any were auto-generated
        gui_instance.memory.save()
    except Exception as e:
        # Silently fail - don't block startup
        # But ensure we save the cleared state
        gui_instance.memory.save()
        pass


def start_indexing(gui_instance):
    """Start background indexing and note generation.
    
    Args:
        gui_instance: The FileAdvisorGUI instance
    """
    if gui_instance.indexing_worker and gui_instance.indexing_worker.isRunning():
        return  # Already running
    
    # Check if we already have a valid index
    file_index = gui_instance.memory.data.get("file_index", {})
    stored_root = file_index.get("root_path")
    current_root = str(gui_instance.perms.allowed_root) if gui_instance.perms.allowed_root else None
    last_scan = file_index.get("last_scan")
    all_files = file_index.get("all_files", [])
    
    # Count actual files on disk to detect new files
    actual_file_count = 0
    if gui_instance.perms.allowed_root and gui_instance.perms.allowed_root.exists():
        try:
            for root, dirs, files in os.walk(gui_instance.perms.allowed_root):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                files = [f for f in files if not f.startswith('.')]
                actual_file_count += len(files)
        except (PermissionError, OSError):
            actual_file_count = 0
    
    indexed_file_count = len(all_files)
    
    # Check if index is still valid (same root and recent - within last 24 hours)
    # Also check if file count matches (to detect new files)
    index_valid = (
        stored_root == current_root and
        last_scan is not None and
        (time.time() - last_scan) < 86400 and  # 24 hours
        len(all_files) > 0 and
        actual_file_count == indexed_file_count  # File count must match
    )
    
    if index_valid:
        # Index is valid, only generate missing notes
        root_files = [f for f in all_files if "/" not in f.get("path", "") or f.get("path", "").count("/") == 0]
        existing_notes = gui_instance.memory.data.get("file_notes", {})
        files_needing_notes = [f for f in root_files if str(f.get("path", "")) not in existing_notes]
        
        if not files_needing_notes:
            # Everything is up to date, no need to run
            if hasattr(gui_instance, 'notes_list'):
                gui_instance._refresh_notes_list()
            return
    
    # Need to index or generate notes - show progress dialog
    gui_instance.indexing_progress = QProgressDialog("Indexing files and generating notes...", "Cancel", 0, 100, gui_instance)
    gui_instance.indexing_progress.setWindowTitle("Initializing File Sorter")
    gui_instance.indexing_progress.setWindowModality(Qt.WindowModality.WindowModal)
    gui_instance.indexing_progress.setMinimumDuration(0)  # Show immediately
    gui_instance.indexing_progress.setValue(0)
    gui_instance.indexing_progress.canceled.connect(gui_instance._cancel_indexing)
    
    # Make the dialog larger
    gui_instance.indexing_progress.setMinimumSize(400, 120)
    gui_instance.indexing_progress.resize(400, 120)
    
    # Style the progress dialog to match Windows 95 theme
    gui_instance.indexing_progress.setStyleSheet(f"""
        QDialog {{
            background-color: {gui_instance.bg};
            border: 2px outset {gui_instance.border_light};
        }}
        QLabel {{
            background-color: {gui_instance.panel};
            color: {gui_instance.text};
            border: 1px inset {gui_instance.border_dark};
            padding: 4px;
            font-size: 10px;
            font-family: 'Courier New', 'Monaco', monospace;
        }}
        QProgressBar {{
            border: 2px inset {gui_instance.border_dark};
            background-color: {gui_instance.panel};
            text-align: center;
            font-size: 9px;
            font-family: 'Courier New', 'Monaco', monospace;
            color: {gui_instance.text};
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #0080ff, stop:1 #0066cc);
            border: 1px solid #004080;
        }}
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #d4d0c8, stop:1 #c0c0c0);
            border: 1px outset {gui_instance.border_light};
            color: {gui_instance.text};
            font-size: 9px;
            font-family: 'Courier New', 'Monaco', monospace;
            padding: 3px 8px;
            min-width: 60px;
        }}
        QPushButton:pressed {{
            border: 1px inset {gui_instance.border_dark};
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #c0c0c0, stop:1 #d4d0c8);
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #e0e0e0, stop:1 #d0d0d0);
        }}
    """)
    
    # Create and start worker
    gui_instance.indexing_worker = IndexingWorker(gui_instance.perms, gui_instance.memory, skip_indexing=index_valid)
    gui_instance.indexing_worker.progress.connect(gui_instance._on_indexing_progress)
    gui_instance.indexing_worker.finished.connect(gui_instance._on_indexing_finished)
    gui_instance.indexing_worker.start()


def auto_scan_for_missing_args(gui_instance, action_type="scan"):
    """Automatically scan files to help user when args are missing.
    
    Args:
        gui_instance: The FileAdvisorGUI instance
        action_type: Type of action ("read", "move", "scan", etc.)
    """
    if not gui_instance.perms.allowed_root:
        return
    
    from operation_utils import add_action_card, update_operation_stats
    from tools import list_files
    
    gui_instance.chat_box.append(f"<span style='color:#666; font-weight:bold; font-size:11px;'>Performing: Scanning files to help you choose...</span>")
    total_count = 0
    scanned_paths = []
    all_files = []
    
    root_path = gui_instance.perms.allowed_root
    try:
        if root_path.exists() and root_path.is_dir():
            op_id = add_action_card(gui_instance, "scan.png", "Scanning", str(root_path), "#c0d9ff", "list_files")
            result = list_files(root_path)
            if result and "error" not in result:
                files = result.get("files", [])
                all_files.extend(files)
                scanned_paths.append(str(root_path))
                update_operation_stats(gui_instance, op_id, files_scanned=len(files))
                total_count += len(files)
    except (PermissionError, OSError):
        pass
    
    if scanned_paths and all_files:
        paths_display = ", ".join([Path(p).name for p in scanned_paths])
        # Show first few files as examples
        file_examples = [Path(f).name for f in all_files[:5]]
        examples_text = ", ".join(file_examples)
        if len(all_files) > 5:
            examples_text += f", and {len(all_files) - 5} more"
        
        if action_type == "read":
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.success_green}; font-weight:bold; font-size:12px;'>COMPLETE:</span> <span style='color:{gui_instance.success_green}; font-weight:bold;'>Found {total_count} files in {paths_display}. Here are some examples: {examples_text}. Which file would you like me to read?</span>")
        elif action_type == "move":
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.success_green}; font-weight:bold; font-size:12px;'>COMPLETE:</span> <span style='color:{gui_instance.success_green}; font-weight:bold;'>Found {total_count} files in {paths_display}. Examples: {examples_text}. Which files would you like me to move, and where?</span>")
        else:
            gui_instance.chat_box.append(f"<span style='color:{gui_instance.success_green}; font-weight:bold; font-size:12px;'>COMPLETE:</span> <span style='color:{gui_instance.success_green}; font-weight:bold;'>Found {total_count} files in {paths_display}. Examples: {examples_text}.</span>")
        
        gui_instance.files_scanned += total_count
        gui_instance.update_counters()

