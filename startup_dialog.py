"""
STARTUP DIALOG MODULE

Shows a dialog before the main window opens to configure essential settings
like root directory and AI model. This ensures the model is selected before
indexing and note generation begin.
"""

import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QComboBox, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt

from config import DEFAULT_AI_MODEL, POPULAR_MODELS, DEFAULT_SORTME
from permissions import PermissionsStore


def get_installed_ollama_models():
    """
    Get list of installed Ollama models by running 'ollama list'.
    Returns list of model names, or empty list if command fails.
    """
    try:
        result = subprocess.run(
            ['ollama', 'list'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            models = []
            # Skip header line (usually "NAME            ID              SIZE    MODIFIED")
            for line in lines[1:]:
                if line.strip():
                    # Extract model name (first column)
                    model_name = line.split()[0]
                    if model_name and model_name not in models:
                        models.append(model_name)
            return models if models else POPULAR_MODELS  # Fallback to popular models if empty
        else:
            return POPULAR_MODELS  # Fallback if command fails
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        # Ollama not installed or not running, use fallback
        return POPULAR_MODELS


class StartupDialog(QDialog):
    """Dialog shown before main window to configure root directory and AI model."""
    
    def __init__(self, store: PermissionsStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("File Sorter AI - Initial Setup")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        
        # Apply Windows 95 retro theme
        self.setStyleSheet("""
            QDialog {
                background-color: #c0c0c0;
                font-family: 'Courier New', 'Monaco', monospace;
            }
            QLabel {
                color: #000000;
                font-size: 11px;
            }
            QPushButton {
                background-color: #c0c0c0;
                border: 2px outset #c0c0c0;
                padding: 4px 12px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:pressed {
                border: 2px inset #c0c0c0;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px inset #808080;
                padding: 4px;
                min-width: 200px;
                color: #000000;
            }
            QComboBox:focus {
                border: 2px solid #0000ff;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #0080ff;
                selection-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Welcome to File Sorter AI")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0000ff;")
        layout.addWidget(title)
        
        layout.addWidget(QLabel("Please configure these settings before starting:"))
        layout.addWidget(QLabel(""))  # Spacer
        
        # Root directory selection
        dir_label = QLabel("Root Directory:")
        dir_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(dir_label)
        
        dir_desc = QLabel("All files to be sorted must be inside this directory.")
        dir_desc.setStyleSheet("font-size: 10px; color: #666666;")
        layout.addWidget(dir_desc)
        
        # Current directory display
        self.current_dir_label = QLabel("No directory selected")
        self.current_dir_label.setWordWrap(True)
        self.current_dir_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px inset #808080;
                padding: 8px;
                min-height: 30px;
            }
        """)
        layout.addWidget(self.current_dir_label)
        
        # Select directory button
        dir_btn_layout = QHBoxLayout()
        self.select_dir_btn = QPushButton("Select Directory…")
        self.select_dir_btn.clicked.connect(self.select_folder)
        # Make button more prominent and distinguishable
        self.select_dir_btn.setStyleSheet("""
            QPushButton {
                background-color: #0080ff;
                color: #ffffff;
                font-weight: bold;
                border: 2px outset #0080ff;
                padding: 6px 16px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #0090ff;
                border: 2px outset #0090ff;
            }
            QPushButton:pressed {
                background-color: #0070ee;
                border: 2px inset #0070ee;
            }
        """)
        dir_btn_layout.addWidget(self.select_dir_btn)
        dir_btn_layout.addStretch()
        layout.addLayout(dir_btn_layout)
        
        layout.addWidget(QLabel(""))  # Spacer
        
        # AI Model selection
        model_label = QLabel("AI Model:")
        model_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(model_label)
        
        model_desc = QLabel("Select the AI model to use for file sorting and analysis.")
        model_desc.setStyleSheet("font-size: 10px; color: #666666;")
        layout.addWidget(model_desc)
        
        model_layout = QHBoxLayout()
        self.ai_model_combo = QComboBox()
        self.ai_model_combo.setEditable(False)  # Dropdown only, no custom typing
        
        # Get installed models from Ollama, fallback to popular models
        installed_models = get_installed_ollama_models()
        self.ai_model_combo.addItems(installed_models)
        self.ai_model_combo.setToolTip("Select an AI model from your installed Ollama models.")
        
        # Ensure text color is black
        self.ai_model_combo.setStyleSheet("""
            QComboBox {
                color: #000000;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        model_layout.addWidget(self.ai_model_combo)
        model_layout.addStretch()
        layout.addLayout(model_layout)
        
        layout.addStretch()
        
        # Buttons
        buttons_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setDefault(True)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #0080ff;
                color: #ffffff;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #0090ff;
            }
        """)
        self.cancel_btn = QPushButton("Cancel")
        buttons_row.addStretch()
        buttons_row.addWidget(self.cancel_btn)
        buttons_row.addWidget(self.start_btn)
        layout.addLayout(buttons_row)
        
        self.setLayout(layout)
        
        self.start_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        # Sync current settings
        self._sync_from_store()
    
    def _sync_from_store(self):
        """Load current settings from store"""
        # Directory
        if self.store.allowed_root and self.store.allowed_root.exists():
            self.current_dir_label.setText(str(self.store.allowed_root))
        else:
            # Try to use default
            if DEFAULT_SORTME.exists():
                self.store.allowed_root = DEFAULT_SORTME
                self.current_dir_label.setText(str(DEFAULT_SORTME))
            else:
                self.current_dir_label.setText("No directory selected")
        
        # AI Model
        current_model = getattr(self.store, "ai_model", DEFAULT_AI_MODEL)
        self.ai_model_combo.setCurrentText(current_model)
    
    def select_folder(self):
        """Open folder selection dialog"""
        folder = QFileDialog.getExistingDirectory(self, "Choose root directory for file sorting")
        if not folder:
            return
        
        chosen = Path(folder).expanduser().resolve()
        if chosen.exists() and chosen.is_dir():
            self.store.allowed_root = chosen
            self.current_dir_label.setText(str(chosen))
    
    def accept(self):
        """Save settings and close dialog"""
        # Validate directory
        if not self.store.allowed_root or not self.store.allowed_root.exists():
            QMessageBox.warning(
                self, 
                "Directory Required", 
                "Please select a root directory before starting."
            )
            return
        
        # Save AI model
        selected_model = self.ai_model_combo.currentText().strip()
        if selected_model:
            self.store.ai_model = selected_model
        
        # Save settings
        self.store.save()
        
        super().accept()

