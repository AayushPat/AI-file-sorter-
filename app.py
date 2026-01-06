"""
FILE SORTER AI - MAIN APPLICATION

Main GUI application for AI-powered file sorting and organization.
Uses Ollama for local AI processing and PyQt6 for the Windows 95-style interface.
"""

import sys
import time
from pathlib import Path

from Interpreter import Interpreter

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QMenu, QDialog, QFileDialog
)

# IMPORT VALIDATION FUNCTIONS
from validation import validate_ai_payload

# IMPORT CONFIGURATION CONSTANTS
from config import ROOT

# IMPORT MEMORY MANAGEMENT
from memoryManagement import MemoryManager

# IMPORT PERMISSIONS AND DIALOGS
from permissions import PermissionsStore, PermissionsDialog
from dialogs import PreviewDialog
from startup_dialog import StartupDialog
from workers import AIWorker, IndexingWorker
from ui_components import CustomTitleBar

# IMPORT UTILITY MODULES
from category_utils import add_category, auto_add_directory_categories, refresh_categories_list, remove_category
from note_utils import refresh_notes_list, edit_note_dialog, remove_file_note, generate_notes_for_files
from action_processor import process_single_action
from ui_builder import build_main_ui, build_preferences_panel
from operation_utils import add_action_card, show_operation_details, update_operation_stats
from file_indexing import scan_all_files_for_ai, start_indexing, auto_scan_for_missing_args
from ai_reply_handler import process_ai_reply




class FileAdvisorGUI(QMainWindow):
    def __init__(self, perms=None):
        super().__init__()

        # Remove native title bar and create custom one
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # Use provided perms or create new one
        self.perms = perms or PermissionsStore()
        # Pass allowed path and AI model to interpreter so AI knows what it can access
        allowed_paths = [str(self.perms.allowed_root)] if self.perms.allowed_root else []
        self.interpreter = Interpreter(ROOT, allowed_paths=allowed_paths, ai_model=self.perms.ai_model)
        self.memory = MemoryManager()  # For categories, file notes, preferences
        self.setMinimumSize(1100, 650)
        
        # Indexing worker (will be started after window is shown)
        self.indexing_worker = None
        self.indexing_progress = None
        
        # Conversation history for context (last 10 messages)
        self.conversation_history = []
        # Track last action performed (for "again" / "repeat" commands)
        self.last_action = None
        self.last_action_args = None

        # Counters
        self.files_scanned = 0
        self.files_moved = 0
        self.start_time = time.time()

        # Track individual operations for detailed stats
        self.operations = []  # List of operation dicts with id, action, path, stats, etc.
        self.operation_counter = 0
        self.selected_operation_id = None

        # Windows 95 retro theme colors - more vibrant!
        self.bg = "#a8a8a8"  # Darker Windows grey
        self.panel = "#ffffff"  # White panels
        self.accent = "#0000ff"  # Bright Windows blue
        self.text = "#000000"  # Black text
        self.border_light = "#ffffff"  # Light border (top/left)
        self.border_dark = "#808080"  # Dark border (bottom/right)
        self.title_bar = "#0080ff"  # Windows blue title bar
        self.button_bg = "#c0c0c0"  # Grey button background
        self.highlight_blue = "#0080ff"  # Bright blue for highlights
        self.success_green = "#00ff00"  # Bright green
        self.error_red = "#ff0000"  # Bright red
        
        # AI name - customize this!
        self.ai_name = "Allen Iverson"
        
        # Track if we're processing
        self.is_processing = False
        self.current_worker = None
        
        # Build the UI
        build_main_ui(self)

    # ACTION CARDS
    def add_action_card(self, icon, title, subtitle, bg, action_type=None):
        """Add an action card to the operations log."""
        return add_action_card(self, icon, title, subtitle, bg, action_type)
    
    def on_operation_clicked(self, url):
        """Handle click on operation card"""
        url_str = url.toString()
        if url_str.startswith("op_"):
            try:
                op_id = int(url_str.replace("op_", ""))
                self.show_operation_details(op_id)
            except ValueError:
                pass
    
    def show_operation_details(self, operation_id):
        """Show detailed stats for a specific operation"""
        show_operation_details(self, operation_id)
    
    def update_operation_stats(self, operation_id, files_scanned=0, files_moved=0):
        """Update stats for a specific operation"""
        update_operation_stats(self, operation_id, files_scanned, files_moved)
    
    def _create_preferences_panel(self):
        """Create the preferences panel with categories, file notes, and sorting options"""
        return build_preferences_panel(self)
    
    def _add_category(self):
        """Add a new category"""
        category = self.category_input.text().strip()
        if add_category(category, self.memory):
            self._refresh_categories_list()
            self.category_input.clear()
    
    def _auto_add_directory_categories(self):
        """Automatically scan subdirectories of the root directory and add them as categories"""
        auto_add_directory_categories(self.perms, self.memory)
        self._refresh_categories_list()
    
    def _scan_all_files_for_ai(self):
        """Scan all files in root directory and store in memory for AI context"""
        scan_all_files_for_ai(self)
    
    def _refresh_categories_on_directory_change(self):
        """Refresh categories when root directory changes"""
        # Check if root changed - if so, old file index will be cleared by _scan_all_files_for_ai
        old_root = self.memory.data.get("file_index", {}).get("root_path")
        new_root = str(self.perms.allowed_root) if self.perms.allowed_root else None
        
        # Update categories based on new root directory
        self._auto_add_directory_categories()
        # Scan all files for AI context (this will clear old files if root changed)
        self._scan_all_files_for_ai()
    
    def _refresh_categories_list(self):
        """Refresh the categories list widget"""
        refresh_categories_list(self.categories_list, self.memory)
    
    def _show_category_context_menu(self, position):
        """Show context menu for removing categories"""
        item = self.categories_list.itemAt(position)
        if item:
            menu = QMenu(self)
            remove_action = menu.addAction("Remove Category")
            action = menu.exec(self.categories_list.mapToGlobal(position))
            if action == remove_action:
                category = item.text()
                self._remove_category(category)
    
    def _remove_category(self, category):
        """Remove a category (AI will interpret as removing folder/reorganizing)"""
        if remove_category(category, self.memory):
            self._refresh_categories_list()
            # Note: AI will see this in memory and may ask about reorganization
    
    def _browse_for_file_note(self):
        """Browse for files/folders in the root directory"""
        if not self.perms.allowed_root or not self.perms.allowed_root.exists():
            QMessageBox.warning(self, "No Root", "Please set a root directory in Permissions first.")
            return
        
        # Ask user if they want to select a file or folder
        reply = QMessageBox.question(
            self, 
            "Select Type", 
            "Do you want to select a file or a folder?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        # Yes = File, No = Folder
        is_file = (reply == QMessageBox.StandardButton.Yes)
        
        # Show a dialog to browse files/folders
        dialog = QFileDialog(self, "Select File or Folder for Note")
        dialog.setDirectory(str(self.perms.allowed_root))
        if is_file:
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        else:
            dialog.setFileMode(QFileDialog.FileMode.Directory)
        
        if dialog.exec():
            selected = dialog.selectedFiles()
            if selected:
                selected_path = Path(selected[0])
                # Make path relative to root if possible
                try:
                    relative_path = selected_path.relative_to(self.perms.allowed_root)
                    self.note_file_input.setText(str(relative_path))
                except ValueError:
                    # If not relative, use full path
                    self.note_file_input.setText(str(selected_path))
    
    def _add_file_note(self):
        """Add a note for a specific file"""
        file_path_str = self.note_file_input.text().strip()
        note = self.note_text_input.text().strip()
        if file_path_str and note:
            if "file_notes" not in self.memory.data:
                self.memory.data["file_notes"] = {}
            
            # Resolve the path relative to root or use absolute
            if self.perms.allowed_root:
                try:
                    # Try to resolve as relative to root
                    full_path = (self.perms.allowed_root / file_path_str).resolve()
                    # Store relative path if within root, otherwise absolute
                    if self.perms.is_allowed(full_path):
                        relative = full_path.relative_to(self.perms.allowed_root)
                        file_path_str = str(relative)
                    else:
                        file_path_str = str(full_path)
                except Exception:
                    # Use as-is if resolution fails
                    pass
            
            self.memory.data["file_notes"][file_path_str] = note
            self.memory.save()
            self.note_file_input.clear()
            self.note_text_input.clear()
            self._refresh_notes_list()
            # Show confirmation
            QMessageBox.information(self, "Note Saved", f"Note saved for: {file_path_str}")
    
    def _refresh_notes_list(self):
        """Refresh the file notes list widget"""
        refresh_notes_list(self.notes_list, self.memory)
    
    def _show_note_context_menu(self, position):
        """Show context menu for editing/removing notes"""
        item = self.notes_list.itemAt(position)
        if item:
            menu = QMenu(self)
            edit_action = menu.addAction("Edit Note")
            remove_action = menu.addAction("Remove Note")
            action = menu.exec(self.notes_list.mapToGlobal(position))
            if action == edit_action:
                self._edit_note(item)
            elif action == remove_action:
                file_path = item.data(Qt.ItemDataRole.UserRole)
                self._remove_file_note(file_path)
    
    def _edit_note(self, item):
        """Edit an existing note with a proper dialog"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return
        
        file_notes = self.memory.data.get("file_notes", {})
        current_note = file_notes.get(file_path, "")
        
        theme_colors = {
            "bg": self.bg,
            "panel": self.panel,
            "text": self.text,
            "border_dark": self.border_dark,
            "border_light": self.border_light,
            "button_bg": self.button_bg
        }
        
        accepted, new_note = edit_note_dialog(self, file_path, current_note, theme_colors)
        if accepted:
            if new_note:
                self.memory.data["file_notes"][file_path] = new_note
                self.memory.save()
                self._refresh_notes_list()
            elif file_path in self.memory.data["file_notes"]:
                # If note is empty, remove it
                del self.memory.data["file_notes"][file_path]
                self.memory.save()
                self._refresh_notes_list()
    
    def _remove_file_note(self, file_path):
        """Remove a file note"""
        if remove_file_note(file_path, self.memory):
            self._refresh_notes_list()
            QMessageBox.information(self, "Note Removed", f"Note removed for: {file_path}")
    
    def _generate_notes_for_all_files(self):
        """Generate notes for files that don't have notes yet"""
        theme_colors = {
            "bg": self.bg,
            "panel": self.panel,
            "text": self.text,
            "border_dark": self.border_dark,
            "border_light": self.border_light,
            "button_bg": self.button_bg
        }
        generate_notes_for_files(self.perms, self.memory, self, theme_colors)
        self._refresh_notes_list()
    
    def _auto_scan_for_missing_args(self, action_type="scan"):
        """Automatically scan files to help user when args are missing"""
        auto_scan_for_missing_args(self, action_type)

    # COUNTER UPDATE
    def update_counters(self):
        elapsed = round(time.time() - self.start_time, 1)
        self.files_scanned_label.setText(f"Scanned: {self.files_scanned}")
        self.files_moved_label.setText(f"Moved: {self.files_moved}")
        self.time_label.setText(f"Time: {elapsed}s")


    def showEvent(self, event):
        """Start indexing when window is shown"""
        super().showEvent(event)
        if self.perms.allowed_root and self.perms.allowed_root.exists():
            self._start_indexing()
    
    def _start_indexing(self):
        """Start background indexing and note generation"""
        start_indexing(self)
    
    def _force_refresh_index(self):
        """Force a full re-index of all files, ignoring cache"""
        # Clear the file index to force a full re-scan
        if "file_index" in self.memory.data:
            self.memory.data["file_index"]["last_scan"] = None
            self.memory.data["file_index"]["all_files"] = []
            self.memory.save()
        
        # Start indexing (will detect that index is invalid and do full scan)
        self._start_indexing()
    
    def _on_indexing_progress(self, current, total, filename):
        """Update progress dialog"""
        if self.indexing_progress:
            # current is already a percentage (0-100)
            self.indexing_progress.setValue(current)
            self.indexing_progress.setLabelText(f"{filename}")
            QApplication.processEvents()
    
    def _cancel_indexing(self):
        """Cancel indexing when user clicks cancel"""
        if self.indexing_worker and self.indexing_worker.isRunning():
            self.indexing_worker.cancel()
    
    def _on_indexing_finished(self):
        """Handle indexing completion"""
        if self.indexing_progress:
            self.indexing_progress.setValue(100)
            self.indexing_progress.close()
            self.indexing_progress = None
        
        # Refresh UI elements that depend on file index
        if hasattr(self, 'notes_list'):
            self._refresh_notes_list()
        
        # Worker will be cleaned up automatically
        self.indexing_worker = None
    
    def closeEvent(self, event):
        """Clean up threads when window closes"""
        # Cancel indexing if running
        if self.indexing_worker and self.indexing_worker.isRunning():
            self.indexing_worker.cancel()
            self.indexing_worker.wait(3000)  # Wait up to 3 seconds
        
        if hasattr(self, 'current_worker') and self.current_worker:
            if self.current_worker.isRunning():
                # Disconnect signals first to prevent callbacks during cleanup
                try:
                    self.current_worker.finished.disconnect()
                except:
                    pass
                # Request interruption first (safer)
                if hasattr(self.current_worker, 'cancel'):
                    self.current_worker.cancel()
                self.current_worker.requestInterruption()
                # Wait for thread to finish gracefully
                if not self.current_worker.wait(1000):  # Wait up to 1 second
                    # If still running, force terminate
                    self.current_worker.terminate()
                    self.current_worker.wait(500)  # Wait a bit more
            # Clean up the worker
            self.current_worker = None
        event.accept()

    def open_permissions(self):
        dialog = PermissionsDialog(self.perms, self)
        dialog.exec()

    # SEND BUTTON
    def handle_send(self):
        # If processing, cancel the current request (send button becomes cancel button)
        if self.is_processing:
            self.cancel_request()
            return
        
        user_text = self.input_box.text().strip()
        if not user_text:
            return
        
        # Prevent submission if somehow processing started between check and here
        if self.is_processing:
            return

        # 1️ Show user message immediately (NO FREEZE)
        self.chat_box.append(f"<span style='color:{self.highlight_blue}; font-weight:bold; font-size:12px;'>You:</span> <span style='color:{self.text}; font-weight:bold;'>{user_text}</span>")
        self.input_box.clear()

        # 2️ Show thinking indicator
        self.set_processing_state(True)
        # Append thinking message - we'll replace it when response comes
        self.chat_box.append(f"<span style='color:{self.highlight_blue}; font-weight:bold; font-size:12px;'>{self.ai_name}:</span> <span style='color:#0080ff; font-style:italic; font-weight:bold; font-size:11px; background:#e6f2ff; padding:2px 6px; border:1px solid #0080ff;' id='thinking'>Thinking...</span>")

        # 3️ Add to conversation history (before processing)
        self.conversation_history.append({"role": "user", "content": user_text})
        # Keep only last 10 messages (5 exchanges)
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
        
        # 4️ Start background AI processing
        self.current_worker = AIWorker(self.interpreter, user_text, self.conversation_history)
        self.current_worker.setParent(self)  # Make it a child so it gets cleaned up
        self.current_worker.finished.connect(self.process_ai_reply)
        self.current_worker.start()
    
    def set_processing_state(self, processing):
        """Enable/disable UI elements during processing"""
        self.is_processing = processing
        # Keep input box enabled so user can type, but prevent submission
        # The input box stays enabled - we just prevent submission via handle_send
        self.send_btn.setEnabled(True)  # Always enabled, but changes function
        
        if processing:
            self.send_btn.setText("✕")
            self.send_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ff8080, stop:1 #ff0000);
                    color: white;
                    border-radius: 0px;
                    font-size: 16px;
                    font-weight: bold;
                    border-top: 2px outset {self.border_light};
                    border-left: 2px outset {self.border_light};
                    border-bottom: 2px outset {self.border_dark};
                    border-right: 2px outset {self.border_dark};
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ffa0a0, stop:1 #ff4040);
                }}
                QPushButton:pressed {{
                    background: #ff0000;
                    border-top: 2px inset {self.border_dark};
                    border-left: 2px inset {self.border_dark};
                    border-bottom: 2px inset {self.border_light};
                    border-right: 2px inset {self.border_light};
                }}
            """)
            self.send_btn.setToolTip("Cancel request")
        else:
            self.send_btn.setText("➤")
            self.send_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #d4d0c8, stop:1 #c0c0c0);
                    color: {self.text};
                    border-radius: 0px;
                    font-size: 20px;
                    border-top: 2px outset {self.border_light};
                    border-left: 2px outset {self.border_light};
                    border-bottom: 2px outset {self.border_dark};
                    border-right: 2px outset {self.border_dark};
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #e8e4dc, stop:1 #d4d0c8);
                }}
                QPushButton:pressed {{
                    background: {self.button_bg};
                    border-top: 2px inset {self.border_dark};
                    border-left: 2px inset {self.border_dark};
                    border-bottom: 2px inset {self.border_light};
                    border-right: 2px inset {self.border_light};
                }}
            """)
            self.send_btn.setToolTip("Send message")
            self.current_worker = None
    
    def cancel_request(self):
        """Cancel the current AI request"""
        if self.current_worker and self.current_worker.isRunning():
            # Request cancellation gracefully
            if hasattr(self.current_worker, 'cancel'):
                self.current_worker.cancel()
            self.current_worker.requestInterruption()
            if not self.current_worker.wait(500):  # Wait up to 0.5 seconds
                self.current_worker.terminate()
                self.current_worker.wait(500)
        
        self.set_processing_state(False)
        # Replace "Thinking..." with cancelled message
        html = self.chat_box.toHtml()
        html = html.replace("Thinking...", "Request cancelled")
        self.chat_box.setHtml(html)
        self.chat_box.append(f"<span style='color:#ff6600; font-weight:bold; font-size:12px;'>CANCELLED:</span> <span style='color:#ff6600; font-weight:bold;'>Request cancelled by user</span>")
    def process_ai_reply(self, ai):
        """Process an AI reply and execute actions"""
        process_ai_reply(self, ai)
    
    def _process_single_action(self, ai: dict, is_multi_action: bool = False, action_num: int = 1, total_actions: int = 1):
        """Process a single action. Can be called for single or multiple actions."""
        process_single_action(self, ai, is_multi_action, action_num, total_actions)


# Application entry point - create the window and start the event loop
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Courier New", 10))

    # Create permissions store
    perms = PermissionsStore()
    
    # Show startup dialog to configure root directory and AI model
    startup = StartupDialog(perms)
    if startup.exec() != QDialog.DialogCode.Accepted:
        # User cancelled, exit
        sys.exit(0)
    
    # Now create and show main window with configured settings
    # Pass the configured perms to the window
    window = FileAdvisorGUI(perms=perms)
    window.show()
    sys.exit(app.exec())
