"""
DIALOGS MODULE

Contains dialog windows used throughout the application, including PreviewDialog
for showing pending file operations before execution.
"""

from typing import List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextBrowser
)


# PreviewDialog shows a list of pending file operations before they execute.
# When preview mode is enabled, this dialog appears so users can review and
# approve or cancel actions before they happen.
class PreviewDialog(QDialog):
    """Dialog to show preview of pending file operations before execution"""
    def __init__(self, actions: List[dict], parent=None):
        super().__init__(parent)
        self.actions = actions
        self.approved = False
        self.setWindowTitle("Preview Actions")
        self.setMinimumWidth(700)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Preview of File Operations")
        title.setStyleSheet("""
            QLabel {
                font-family: 'Courier New', 'Monaco', monospace;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                background-color: #e6f2ff;
                border: 2px inset #808080;
            }
        """)
        layout.addWidget(title)
        
        # Instructions
        info = QLabel("Review the actions below. Click 'Approve & Run' to execute them, or 'Cancel' to abort.")
        info.setWordWrap(True)
        info.setStyleSheet("""
            QLabel {
                font-family: 'Courier New', 'Monaco', monospace;
                font-size: 11px;
                padding: 8px;
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
            }
        """)
        layout.addWidget(info)
        
        # Actions list
        self.actions_list = QTextBrowser()
        self.actions_list.setReadOnly(True)
        self.actions_list.setStyleSheet("""
            QTextBrowser {
                background-color: white;
                border: 2px inset #808080;
                font-family: 'Courier New', 'Monaco', monospace;
                font-size: 11px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.actions_list)
        
        # Populate actions
        self._populate_actions()
        
        # Buttons
        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #d4d0c8, stop:1 #c0c0c0);
                color: black;
                border-radius: 0px;
                font-size: 11px;
                font-weight: bold;
                padding: 8px 20px;
                border-top: 2px outset #ffffff;
                border-left: 2px outset #ffffff;
                border-bottom: 2px outset #808080;
                border-right: 2px outset #808080;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e8e4dc, stop:1 #d4d0c8);
            }
            QPushButton:pressed {
                border-top: 2px inset #808080;
                border-left: 2px inset #808080;
                border-bottom: 2px inset #ffffff;
                border-right: 2px inset #ffffff;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        buttons_row.addWidget(cancel_btn)
        
        approve_btn = QPushButton("Approve & Run")
        approve_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #90ee90, stop:1 #00cc00);
                color: black;
                border-radius: 0px;
                font-size: 11px;
                font-weight: bold;
                padding: 8px 20px;
                border-top: 2px outset #ffffff;
                border-left: 2px outset #ffffff;
                border-bottom: 2px outset #808080;
                border-right: 2px outset #808080;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #a0ffa0, stop:1 #00ee00);
            }
            QPushButton:pressed {
                border-top: 2px inset #808080;
                border-left: 2px inset #808080;
                border-bottom: 2px inset #ffffff;
                border-right: 2px inset #ffffff;
            }
        """)
        approve_btn.clicked.connect(self.accept)
        buttons_row.addWidget(approve_btn)
        
        layout.addLayout(buttons_row)
        self.setLayout(layout)
    
    def _populate_actions(self):
        """Format and display all pending actions in a readable way"""
        if not self.actions:
            self.actions_list.setHtml("<p style='color: #666;'>No actions to preview.</p>")
            return
        
        html_parts = []
        action_names = {
            "list_files": "📁 List Files",
            "list_all_files": "🔍 Scan All Files",
            "read_file": "📄 Read File",
            "move_file": "➡️ Move File",
            "create_folder": "📂 Create Folder",
            "file_type": "🔎 Check File Type"
        }
        
        for i, action in enumerate(self.actions, 1):
            action_type = action.get("action", "unknown")
            args = action.get("args", {})
            action_display = action_names.get(action_type, action_type)
            
            html_parts.append(f"<div style='margin-bottom: 15px; padding: 10px; background-color: #f8f8f8; border: 1px solid #c0c0c0;'>")
            html_parts.append(f"<strong style='color: #000080; font-size: 12px;'>{i}. {action_display}</strong><br>")
            
            if action_type == "move_file":
                src = args.get("source") or args.get("src", "")
                dst = args.get("destination") or args.get("dst", "")
                html_parts.append(f"<span style='color: #333;'>From:</span> <code style='background: #e0e0e0; padding: 2px 4px;'>{src}</code><br>")
                html_parts.append(f"<span style='color: #333;'>To:</span> <code style='background: #e0e0e0; padding: 2px 4px;'>{dst}</code>")
            elif action_type == "create_folder":
                path = args.get("path", "")
                html_parts.append(f"<span style='color: #333;'>Path:</span> <code style='background: #e0e0e0; padding: 2px 4px;'>{path}</code>")
            elif action_type in ["list_files", "list_all_files", "read_file", "file_type"]:
                path = args.get("path", "")
                if path:
                    html_parts.append(f"<span style='color: #333;'>Path:</span> <code style='background: #e0e0e0; padding: 2px 4px;'>{path}</code>")
                else:
                    html_parts.append(f"<span style='color: #666;'>Will scan all accessible directories</span>")
                if "limit" in args:
                    html_parts.append(f"<br><span style='color: #333;'>Limit:</span> {args['limit']} items")
            
            html_parts.append("</div>")
        
        self.actions_list.setHtml("".join(html_parts))

