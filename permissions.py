"""
PERMISSIONS MODULE

Handles the sandbox system that restricts AI file operations to a user-approved
root directory. Includes the PermissionsStore class and PermissionsDialog.
"""

import json
from pathlib import Path
from typing import Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QCheckBox, QLineEdit, QFileDialog, QMessageBox, QWidget, QComboBox
)

from config import CONFIG_DIR, CONFIG_PATH, DEFAULT_SORTME, ROOT, DEFAULT_AI_MODEL, POPULAR_MODELS


# PermissionsStore manages the sandbox system that restricts AI file operations
# to a single user-approved root directory. This is a safety feature separate
# from macOS privacy permissions - it ensures the AI can only access files
# within the directory the user explicitly allows.
class PermissionsStore:
    """
    App-level safety guardrail.
    The AI may only read/write/move within a single user-approved root folder.
    This is separate from macOS privacy permissions.
    """

    def __init__(self) -> None:
        self.allowed_root: Optional[Path] = None
        self.preview_mode: bool = False
        self.ai_model: str = DEFAULT_AI_MODEL
        self.load_or_init()

    def load_or_init(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        DEFAULT_SORTME.mkdir(parents=True, exist_ok=True)

        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text())
                # Support both old format (allowed_roots list) and new format (allowed_root single)
                if "allowed_root" in data:
                    root_str = data.get("allowed_root")
                    if root_str and isinstance(root_str, str):
                        self.allowed_root = Path(root_str).expanduser()
                elif "allowed_roots" in data:
                    # Migrate from old format: use first root or SortMe
                    roots = data.get("allowed_roots", [])
                    if roots and isinstance(roots, list) and len(roots) > 0:
                        self.allowed_root = Path(roots[0]).expanduser()
                    else:
                        self.allowed_root = DEFAULT_SORTME if DEFAULT_SORTME.exists() else None
                else:
                    self.allowed_root = None
                self.preview_mode = data.get("preview_mode", False)
                self.ai_model = data.get("ai_model", DEFAULT_AI_MODEL)
            except Exception:
                self.allowed_root = None
                self.preview_mode = False
                self.ai_model = DEFAULT_AI_MODEL
        else:
            self.preview_mode = False
            self.ai_model = DEFAULT_AI_MODEL
        if not self.allowed_root:
            # First run default: use SortMe if it exists
            self.allowed_root = DEFAULT_SORTME if DEFAULT_SORTME.exists() else None
            self.save()

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "allowed_root": str(self.allowed_root) if self.allowed_root else None,
            "preview_mode": getattr(self, "preview_mode", False),
            "ai_model": getattr(self, "ai_model", DEFAULT_AI_MODEL)
        }
        CONFIG_PATH.write_text(json.dumps(payload, indent=2))

    def _expand_macros(self, p: str) -> str:
        # Support your prompt's {ROOT} macro + standard ~
        return p.replace("{ROOT}", ROOT)

    def normalize(self, path_str: str) -> Optional[Path]:
        if not isinstance(path_str, str) or not path_str.strip():
            return None
        try:
            expanded = self._expand_macros(path_str.strip())
            p = Path(expanded).expanduser()
            # For existing paths, resolve them. For non-existent paths (like new folders),
            # resolve the parent and then append the name
            if p.exists():
                return p.resolve()
            else:
                # Path doesn't exist yet - resolve parent if it exists, then append name
                parent = p.parent
                if parent.exists():
                    resolved_parent = parent.resolve()
                    return resolved_parent / p.name
                else:
                    # Try to resolve what we can
                    try:
                        return p.resolve()
                    except:
                        # If resolve fails, return the path as-is (absolute if possible)
                        return p.absolute() if p.is_absolute() else p
        except Exception:
            return None

    def is_allowed(self, path: Path) -> bool:
        """Check if a path is within the allowed root directory."""
        if not self.allowed_root:
            return False
        try:
            root = self.allowed_root.expanduser().resolve()
            # For non-existent paths, check if parent is within allowed root
            path = path.expanduser()
            # then the path itself will be allowed
            if not path.exists():
                parent = path.parent
                if parent.exists():
                    parent = parent.resolve()
                    try:
                        parent.relative_to(root)
                        # Parent is within root, so path will be allowed
                        return True
                    except ValueError:
                        return False
                # If parent doesn't exist, try to resolve path parts
                try:
                    path = path.resolve()
                except:
                    # Can't resolve, try absolute
                    path = path.absolute()
            else:
                path = path.resolve()
            
            # Check if path is the same as root, or if path is within root
            if path == root:
                return True
            # Check if path is a subdirectory of root
            try:
                path.relative_to(root)
                return True
            except ValueError:
                return False
        except Exception:
            return False

    def require_allowed(self, path_str: str, *, purpose: str = "access") -> Tuple[bool, str]:
        p = self.normalize(path_str)
        if p is None:
            return False, f"Blocked: invalid path for {purpose}."
        if not self.is_allowed(p):
            return False, (
                "Blocked: that path is outside the folders you've granted access to. "
                "Open Permissions (⚙) and enable the folder first."
            )
        return True, str(p)


# PermissionsDialog is the settings window where users configure:
# - The root directory for file sorting
# - Preview mode (show actions before executing)
# - Content reading settings (which file types to analyze)
class PermissionsDialog(QDialog):
    def __init__(self, store: PermissionsStore, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Permissions")
        self.setMinimumWidth(520)

        layout = QVBoxLayout()

        # Single root directory selection
        layout.addWidget(QLabel("Choose the root directory for file sorting:"))
        layout.addWidget(QLabel("All files to be sorted must be inside this directory."))
        
        # Current directory display
        self.current_dir_label = QLabel("No directory selected")
        self.current_dir_label.setWordWrap(True)
        self.current_dir_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px inset #808080;
                padding: 8px;
                font-family: 'Courier New', 'Monaco', monospace;
            }
        """)
        layout.addWidget(self.current_dir_label)

        # Select directory button
        self.select_btn = QPushButton("Select Directory…")
        self.select_btn.clicked.connect(self.select_folder)
        layout.addWidget(self.select_btn)

        # Preview mode setting
        layout.addWidget(QLabel(""))  # Spacer
        self.cb_preview_mode = QCheckBox("Preview mode: Show actions before executing")
        self.cb_preview_mode.setToolTip("When enabled, you'll see a preview of all file operations before they're executed")
        layout.addWidget(self.cb_preview_mode)

        # Content Reading Settings
        layout.addWidget(QLabel(""))  # Spacer
        content_reading_label = QLabel("Content Reading Settings:")
        content_reading_label.setStyleSheet("font-weight: bold; font-family: 'Courier New', 'Monaco', monospace;")
        layout.addWidget(content_reading_label)
        
        # Master toggle
        self.content_reading_enabled = QCheckBox("Enable content reading")
        self.content_reading_enabled.setToolTip("Read file contents to improve sorting accuracy")
        layout.addWidget(self.content_reading_enabled)
        
        # File type checkboxes in a grid
        file_types_layout = QVBoxLayout()
        file_types_layout.setContentsMargins(20, 0, 0, 0)
        
        self.content_reading_text = QCheckBox("Text files (.txt, .md, .py, etc.)")
        file_types_layout.addWidget(self.content_reading_text)
        
        self.content_reading_pdf = QCheckBox("PDFs")
        file_types_layout.addWidget(self.content_reading_pdf)
        
        self.content_reading_office = QCheckBox("Office documents (.docx, .xlsx)")
        file_types_layout.addWidget(self.content_reading_office)
        
        self.content_reading_images = QCheckBox("Images (metadata only)")
        file_types_layout.addWidget(self.content_reading_images)
        
        self.content_reading_archives = QCheckBox("Archives (.zip, .tar)")
        file_types_layout.addWidget(self.content_reading_archives)
        
        file_types_widget = QWidget()
        file_types_widget.setLayout(file_types_layout)
        layout.addWidget(file_types_widget)
        
        # Max file size setting
        max_size_layout = QHBoxLayout()
        max_size_layout.setContentsMargins(20, 0, 0, 0)
        max_size_label = QLabel("Max file size (MB):")
        max_size_layout.addWidget(max_size_label)
        self.content_reading_max_size = QLineEdit()
        self.content_reading_max_size.setPlaceholderText("5")
        self.content_reading_max_size.setMaximumWidth(60)
        max_size_layout.addWidget(self.content_reading_max_size)
        max_size_layout.addStretch()
        max_size_widget = QWidget()
        max_size_widget.setLayout(max_size_layout)
        layout.addWidget(max_size_widget)

        # AI Model Selection
        layout.addWidget(QLabel(""))  # Spacer
        ai_model_label = QLabel("AI Model:")
        ai_model_label.setStyleSheet("font-weight: bold; font-family: 'Courier New', 'Monaco', monospace;")
        layout.addWidget(ai_model_label)
        
        model_layout = QHBoxLayout()
        model_layout.setContentsMargins(0, 0, 0, 0)
        self.ai_model_combo = QComboBox()
        self.ai_model_combo.setEditable(True)  # Allow custom model names
        self.ai_model_combo.addItems(POPULAR_MODELS)
        self.ai_model_combo.setToolTip("Select an AI model. You can also type a custom model name.")
        model_layout.addWidget(self.ai_model_combo)
        model_layout.addStretch()
        model_widget = QWidget()
        model_widget.setLayout(model_layout)
        layout.addWidget(model_widget)

        # Buttons
        buttons_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.close_btn = QPushButton("Close")
        buttons_row.addStretch()
        buttons_row.addWidget(self.save_btn)
        buttons_row.addWidget(self.close_btn)
        layout.addLayout(buttons_row)

        self.setLayout(layout)

        self.save_btn.clicked.connect(self.save)
        self.close_btn.clicked.connect(self.close)

        self._sync_from_store()

    def _sync_from_store(self) -> None:
        # Display current root directory
        if self.store.allowed_root and self.store.allowed_root.exists():
            self.current_dir_label.setText(str(self.store.allowed_root))
        else:
            self.current_dir_label.setText("No directory selected")
        
        # Sync preview mode
        self.cb_preview_mode.setChecked(getattr(self.store, "preview_mode", False))
        
        # Sync content reading config from parent window's memory
        parent_window = self.parent()
        if parent_window and hasattr(parent_window, 'memory'):
            config = parent_window.memory.data.get("content_reading_config", {})
            default_config = {
                "enabled": False,
                "enabled_types": ["text"],
                "max_file_size": 5 * 1024 * 1024
            }
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            
            self.content_reading_enabled.setChecked(config.get("enabled", False))
            enabled_types = config.get("enabled_types", [])
            self.content_reading_text.setChecked("text" in enabled_types)
            self.content_reading_pdf.setChecked("pdf" in enabled_types)
            self.content_reading_office.setChecked("office" in enabled_types)
            self.content_reading_images.setChecked("images" in enabled_types)
            self.content_reading_archives.setChecked("archives" in enabled_types)
            
            max_size_mb = config.get("max_file_size", 5 * 1024 * 1024) / (1024 * 1024)
            self.content_reading_max_size.setText(str(int(max_size_mb)))
        
        # Sync AI model
        current_model = getattr(self.store, "ai_model", DEFAULT_AI_MODEL)
        self.ai_model_combo.setCurrentText(current_model)

    def select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose root directory for file sorting")
        if not folder:
            return

        chosen = Path(folder).expanduser().resolve()
        if chosen.exists() and chosen.is_dir():
            self.store.allowed_root = chosen
            self.current_dir_label.setText(str(chosen))

    def save(self) -> None:
        # Save preview mode
        self.store.preview_mode = self.cb_preview_mode.isChecked()
        
        # Save AI model
        selected_model = self.ai_model_combo.currentText().strip()
        if selected_model:
            self.store.ai_model = selected_model
        
        self.store.save()
        
        # Save content reading config to parent window's memory
        parent_window = self.parent()
        if parent_window and hasattr(parent_window, 'memory'):
            config = {
                "enabled": self.content_reading_enabled.isChecked(),
                "enabled_types": [],
                "max_file_size": 5 * 1024 * 1024
            }
            
            if self.content_reading_text.isChecked():
                config["enabled_types"].append("text")
            if self.content_reading_pdf.isChecked():
                config["enabled_types"].append("pdf")
            if self.content_reading_office.isChecked():
                config["enabled_types"].append("office")
            if self.content_reading_images.isChecked():
                config["enabled_types"].append("images")
            if self.content_reading_archives.isChecked():
                config["enabled_types"].append("archives")
            
            try:
                max_size_mb = float(self.content_reading_max_size.text() or "5")
                config["max_file_size"] = int(max_size_mb * 1024 * 1024)
            except ValueError:
                config["max_file_size"] = 5 * 1024 * 1024
            
            parent_window.memory.data["content_reading_config"] = config
            parent_window.memory.save()
        
        # Update interpreter with new allowed path and AI model
        if parent_window and hasattr(parent_window, 'interpreter'):
            if self.store.allowed_root:
                parent_window.interpreter.allowed_paths = [str(self.store.allowed_root)]
            else:
                parent_window.interpreter.allowed_paths = []
            # Update AI model
            parent_window.interpreter.ai_model = self.store.ai_model
            # Refresh categories when directory changes
            if hasattr(parent_window, '_refresh_categories_on_directory_change'):
                parent_window._refresh_categories_on_directory_change()
        QMessageBox.information(self, "Saved", "Settings updated.")
        self._sync_from_store()

