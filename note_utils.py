"""
NOTE UTILITIES MODULE

Helper functions for managing file notes (metadata for AI sorting).
These functions work with the memory manager and file index.
"""

from pathlib import Path
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QMessageBox, QProgressDialog, QApplication
from PyQt6.QtCore import Qt

from filenameParser import parse_file_info
from contentReader import read_file_content
from contentAnalyzer import analyze_file


def refresh_notes_list(notes_list: QListWidget, memory) -> None:
    """Refresh the file notes list widget with current notes from memory.
    
    Args:
        notes_list: QListWidget to populate
        memory: MemoryManager instance
    """
    notes_list.clear()
    file_notes = memory.data.get("file_notes", {})
    for file_path, note in sorted(file_notes.items()):
        # Better formatting: file name on first line, note preview below
        file_name = Path(file_path).name if "/" in file_path else file_path
        # Truncate note for preview (first 60 chars)
        note_preview = note if len(note) <= 60 else note[:57] + "..."
        item_text = f"{file_name}\n  {note_preview}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, file_path)  # Store full path
        item.setData(Qt.ItemDataRole.ToolTipRole, f"File: {file_path}\nNote: {note}")  # Full info in tooltip
        notes_list.addItem(item)


def edit_note_dialog(parent, file_path: str, current_note: str, theme_colors: dict) -> tuple:
    """Create and show edit note dialog.
    
    Args:
        parent: Parent widget
        file_path: Path to the file
        current_note: Current note text
        theme_colors: Dict with theme colors (bg, panel, text, border_dark, border_light, button_bg)
        
    Returns:
        Tuple of (accepted: bool, new_note: str)
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("Edit File Note")
    dialog.setMinimumSize(500, 300)
    
    bg = theme_colors.get("bg", "#a8a8a8")
    panel = theme_colors.get("panel", "#ffffff")
    text = theme_colors.get("text", "#000000")
    border_dark = theme_colors.get("border_dark", "#808080")
    border_light = theme_colors.get("border_light", "#ffffff")
    
    dialog.setStyleSheet(f"""
        QDialog {{
            background-color: {bg};
        }}
        QLabel {{
            color: {text};
            font-size: 10px;
            font-family: 'Courier New', 'Monaco', monospace;
        }}
        QPlainTextEdit {{
            background-color: {panel};
            color: {text};
            border: 2px inset {border_dark};
            font-size: 10px;
            font-family: 'Courier New', 'Monaco', monospace;
            padding: 4px;
        }}
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #d4d0c8, stop:1 #c0c0c0);
            border: 1px outset {border_light};
            color: {text};
            font-size: 9px;
            font-family: 'Courier New', 'Monaco', monospace;
            padding: 4px 12px;
            min-width: 70px;
        }}
        QPushButton:pressed {{
            border: 1px inset {border_dark};
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #e0e0e0, stop:1 #d0d0d0);
        }}
    """)
    
    layout = QVBoxLayout()
    layout.setSpacing(8)
    layout.setContentsMargins(10, 10, 10, 10)
    
    # File path label
    file_label = QLabel(f"File: {file_path}")
    file_label.setWordWrap(True)
    layout.addWidget(file_label)
    
    # Note text area
    note_edit = QPlainTextEdit()
    note_edit.setPlainText(current_note)
    note_edit.setPlaceholderText("Enter note for AI...")
    layout.addWidget(note_edit)
    
    # Buttons
    button_layout = QHBoxLayout()
    button_layout.addStretch()
    
    cancel_btn = QPushButton("Cancel")
    cancel_btn.clicked.connect(dialog.reject)
    button_layout.addWidget(cancel_btn)
    
    save_btn = QPushButton("Save")
    save_btn.setDefault(True)
    save_btn.clicked.connect(dialog.accept)
    button_layout.addWidget(save_btn)
    
    layout.addLayout(button_layout)
    dialog.setLayout(layout)
    
    # Show dialog
    if dialog.exec() == QDialog.DialogCode.Accepted:
        new_note = note_edit.toPlainText().strip()
        return True, new_note
    else:
        return False, ""


def remove_file_note(file_path: str, memory) -> bool:
    """Remove a file note from memory.
    
    Args:
        file_path: Path to the file
        memory: MemoryManager instance
        
    Returns:
        True if note was removed, False if it didn't exist
    """
    if "file_notes" not in memory.data:
        return False
    
    if file_path in memory.data["file_notes"]:
        del memory.data["file_notes"][file_path]
        memory.save()
        return True
    
    return False


def generate_notes_for_files(perms, memory, parent_widget, theme_colors: dict) -> None:
    """Generate notes for files that don't have notes yet.
    
    Args:
        perms: PermissionsStore instance
        memory: MemoryManager instance
        parent_widget: Parent widget for dialogs
        theme_colors: Dict with theme colors
    """
    if not perms.allowed_root or not perms.allowed_root.exists():
        QMessageBox.warning(parent_widget, "No Root Directory", "Please set a root directory in Permissions first.")
        return
    
    # Get file index
    file_index = memory.data.get("file_index", {})
    all_files = file_index.get("all_files", [])
    
    if not all_files:
        QMessageBox.information(parent_widget, "No Files", "No files found. Please scan files first or wait for automatic scan.")
        return
    
    # Filter to root-level files only (files to be sorted)
    root_files = [f for f in all_files if "/" not in f.get("path", "") or f.get("path", "").count("/") == 0]
    
    if not root_files:
        QMessageBox.information(parent_widget, "No Root Files", "No files found in root directory to generate notes for.")
        return
    
    # Get existing notes
    existing_notes = memory.data.get("file_notes", {})
    if "file_notes" not in memory.data:
        memory.data["file_notes"] = {}
    
    # Only process files that don't have notes yet
    files_to_process = [f for f in root_files if str(f.get("path", "")) not in existing_notes]
    
    if not files_to_process:
        QMessageBox.information(parent_widget, "All Notes Generated", f"All {len(root_files)} file(s) already have notes. No new files to process.")
        return
    
    # Create progress dialog
    progress = QProgressDialog(f"Generating notes for {len(files_to_process)} file(s) without notes...", "Cancel", 0, len(files_to_process), parent_widget)
    progress.setWindowTitle("Generating Notes for New Files")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)  # Show immediately
    progress.setValue(0)
    
    # Get content reading config
    content_config = memory.data.get("content_reading_config", {})
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
    
    root_path = perms.allowed_root
    notes_generated = 0
    
    for idx, file_info in enumerate(files_to_process):
        if progress.wasCanceled():
            break
        
        file_path_str = str(file_info.get("path", ""))
        progress.setLabelText(f"Processing: {file_info.get('name', '')}")
        progress.setValue(idx)
        QApplication.processEvents()  # Update UI
        
        try:
            # Get full path
            full_path = Path(root_path) / file_path_str
            if not full_path.exists():
                continue
            
            # Ensure parsed data exists
            if "parsed" not in file_info:
                file_info = parse_file_info(file_info)
            
            # Read content if enabled and not already done
            if "content" not in file_info:
                content_data = None
                if content_config.get("enabled", False):
                    content_data = read_file_content(
                        full_path,
                        file_info.get("extension", ""),
                        content_config
                    )
                if content_data:
                    file_info = analyze_file(
                        file_info,
                        content_data,
                        ai_url,
                        ai_model
                    )
            
            # Generate note
            note_parts = []
            
            if file_info.get("parsed"):
                parsed = file_info["parsed"]
                if parsed.get("course"):
                    note_parts.append(f"Course: {parsed['course']}")
                if parsed.get("type"):
                    note_parts.append(f"Type: {parsed['type']}")
                if parsed.get("date"):
                    note_parts.append(f"Date: {parsed['date']}")
                if parsed.get("subject_hints"):
                    subjects = ", ".join(parsed["subject_hints"][:2])
                    note_parts.append(f"Subjects: {subjects}")
            
            if file_info.get("content", {}).get("summary"):
                summary = file_info["content"]["summary"]
                if len(summary) > 80:
                    summary = summary[:77] + "..."
                note_parts.append(summary)
            elif file_info.get("content", {}).get("keywords"):
                keywords = ", ".join(file_info["content"]["keywords"][:5])
                note_parts.append(f"Keywords: {keywords}")
            
            if note_parts:
                auto_note = " | ".join(note_parts)
                memory.data["file_notes"][file_path_str] = auto_note
                notes_generated += 1
        except Exception:
            continue
    
    # Save notes
    memory.save()
    progress.setValue(len(files_to_process))
    
    if notes_generated > 0:
        QMessageBox.information(parent_widget, "Notes Generated", f"Generated notes for {notes_generated} file(s).")

