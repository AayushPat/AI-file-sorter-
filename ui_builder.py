"""
UI BUILDER MODULE

Functions for building the main GUI components. This module contains all the
UI creation logic to keep the main FileAdvisorGUI class focused on logic.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QTextBrowser,
    QLineEdit, QPushButton, QSplitter, QStackedWidget, QListWidget
)

from ui_components import CustomTitleBar


def build_main_ui(gui_instance):
    """Build the main UI layout for FileAdvisorGUI.
    
    Args:
        gui_instance: The FileAdvisorGUI instance to attach UI elements to
    """
    central = QWidget()
    gui_instance.setCentralWidget(central)
    
    # CHAT WINDOW (LEFT) - with title bar
    chat_container = _build_chat_panel(gui_instance)
    
    # FILE TRACKER LOG (RIGHT) - with title bar
    log_container = _build_log_panel(gui_instance)
    
    # Splitter
    gui_instance.splitter = QSplitter(Qt.Orientation.Horizontal)
    gui_instance.splitter.addWidget(chat_container)
    gui_instance.splitter.addWidget(log_container)
    gui_instance.splitter.setSizes([700, 400])
    
    # INPUT
    _build_input_row(gui_instance)
    
    # COUNTERS (BOTTOM RIGHT)
    gui_instance.files_scanned_label = QLabel("Scanned: 0")
    gui_instance.files_moved_label = QLabel("Moved: 0")
    gui_instance.time_label = QLabel("Time: 0.0s")
    
    # Create stacked widget to combine operations list and detail view
    gui_instance.operations_stack = QStackedWidget()
    detail_page = _build_detail_page(gui_instance)
    gui_instance.operations_stack.addWidget(log_container)  # Page 0: operations list
    gui_instance.operations_stack.addWidget(detail_page)    # Page 1: detail view
    
    # PREFERENCES PANEL (above operations)
    prefs_panel = gui_instance._create_preferences_panel()
    
    # RIGHT PANEL → vertical stack of preferences + operations (with stack) + counters
    right_vertical_splitter = QSplitter(Qt.Orientation.Vertical)
    right_vertical_splitter.addWidget(prefs_panel)  # top: preferences
    right_vertical_splitter.addWidget(gui_instance.operations_stack)  # middle: operations list or detail view
    
    # Create counters widget container
    counters_widget = _build_counters_widget(gui_instance)
    right_vertical_splitter.addWidget(counters_widget)
    right_vertical_splitter.setSizes([250, 300, 50])  # preferences (bigger), operations stack (smaller), counters
    
    # TOP HALF → Conversation (left) | Right panel (right)
    top_horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)
    top_horizontal_splitter.addWidget(chat_container)
    top_horizontal_splitter.addWidget(right_vertical_splitter)
    top_horizontal_splitter.setSizes([700, 400])
    
    # MAIN LAYOUT (Vertical)
    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)
    
    # Add custom title bar at the top
    gui_instance.title_bar = CustomTitleBar(gui_instance)
    main_layout.addWidget(gui_instance.title_bar)
    
    # Add top splitter (chat | tracker+counter)
    main_layout.addWidget(top_horizontal_splitter)
    
    # Bottom Input Row
    input_row = QHBoxLayout()
    input_row.addWidget(gui_instance.input_box)
    input_row.addWidget(gui_instance.perms_btn)
    input_row.addWidget(gui_instance.send_btn)
    main_layout.addLayout(input_row)
    
    central.setLayout(main_layout)
    
    # Set main window background and border
    gui_instance.setStyleSheet(f"""
        QMainWindow {{
            background-color: {gui_instance.bg};
            border: 2px solid {gui_instance.border_dark};
        }}
        QLabel {{
            color: {gui_instance.text};
            font-family: 'Courier New', 'Monaco', monospace;
            font-size: 11px;
        }}
    """)


def _build_chat_panel(gui_instance) -> QWidget:
    """Build the chat/conversation panel."""
    chat_container = QWidget()
    chat_layout = QVBoxLayout()
    chat_layout.setContentsMargins(0, 0, 0, 0)
    chat_layout.setSpacing(0)
    
    # Chat title bar
    chat_title = QLabel("  CONVERSATION")
    chat_title.setFixedHeight(24)
    chat_title.setStyleSheet(f"""
        QLabel {{
            background-color: {gui_instance.button_bg};
            color: {gui_instance.text};
            font-family: 'Courier New', 'Monaco', monospace;
            font-size: 11px;
            font-weight: bold;
            padding-left: 8px;
            border-top: 2px inset {gui_instance.border_dark};
            border-left: 2px inset {gui_instance.border_dark};
            border-bottom: 1px solid {gui_instance.border_dark};
        }}
    """)
    chat_layout.addWidget(chat_title)
    
    gui_instance.chat_box = QTextEdit()
    gui_instance.chat_box.setReadOnly(True)
    gui_instance.chat_box.setStyleSheet(f"""
        QTextEdit {{
            background-color: {gui_instance.panel};
            color: {gui_instance.text};
            border-top: none;
            border-left: 2px solid {gui_instance.border_dark};
            border-bottom: 2px solid {gui_instance.border_light};
            border-right: 2px solid {gui_instance.border_light};
            border-radius: 0px;
            padding: 12px;
            font-family: 'Courier New', 'Monaco', monospace;
            font-size: 11px;
            font-weight: bold;
        }}
    """)
    chat_layout.addWidget(gui_instance.chat_box)
    chat_container.setLayout(chat_layout)
    return chat_container


def _build_log_panel(gui_instance) -> QWidget:
    """Build the file operations log panel."""
    log_container = QWidget()
    log_layout = QVBoxLayout()
    log_layout.setContentsMargins(0, 0, 0, 0)
    log_layout.setSpacing(0)
    
    # Log title bar
    log_title = QLabel("  FILE OPERATIONS")
    log_title.setFixedHeight(24)
    log_title.setStyleSheet(f"""
        QLabel {{
            background-color: {gui_instance.button_bg};
            color: {gui_instance.text};
            font-family: 'Courier New', 'Monaco', monospace;
            font-size: 11px;
            font-weight: bold;
            padding-left: 8px;
            border-top: 2px inset {gui_instance.border_dark};
            border-left: 2px inset {gui_instance.border_dark};
            border-bottom: 1px solid {gui_instance.border_dark};
        }}
    """)
    log_layout.addWidget(log_title)
    
    gui_instance.log_box = QTextBrowser()
    gui_instance.log_box.setOpenExternalLinks(False)
    gui_instance.log_box.setStyleSheet(f"""
        QTextBrowser {{
            background-color: {gui_instance.panel};
            color: {gui_instance.text};
            border-top: none;
            border-left: 2px solid {gui_instance.border_dark};
            border-bottom: 2px solid {gui_instance.border_light};
            border-right: 2px solid {gui_instance.border_light};
            border-radius: 0px;
            padding: 10px;
            font-family: 'Courier New', 'Monaco', monospace;
            font-size: 10px;
            font-weight: bold;
        }}
    """)
    gui_instance.log_box.anchorClicked.connect(gui_instance.on_operation_clicked)
    log_layout.addWidget(gui_instance.log_box)
    log_container.setLayout(log_layout)
    return log_container


def _build_input_row(gui_instance) -> None:
    """Build the input row with text field and buttons."""
    gui_instance.input_box = QLineEdit()
    gui_instance.input_box.setPlaceholderText("Type your message…")
    gui_instance.input_box.setStyleSheet(f"""
        QLineEdit {{
            background-color: white;
            color: #000000;
            border-radius: 0px;
            border-top: 2px inset {gui_instance.border_dark};
            border-left: 2px inset {gui_instance.border_dark};
            border-bottom: 2px inset {gui_instance.border_light};
            border-right: 2px inset {gui_instance.border_light};
            padding: 8px;
            font-family: 'Courier New', 'Monaco', monospace;
            font-size: 11px;
        }}
        QLineEdit:focus {{
            border-top: 2px inset {gui_instance.border_dark};
            border-left: 2px inset {gui_instance.border_dark};
            border-bottom: 2px inset {gui_instance.border_light};
            border-right: 2px inset {gui_instance.border_light};
        }}
    """)
    
    # Permissions button
    gui_instance.perms_btn = QPushButton("⚙")
    gui_instance.perms_btn.setFixedWidth(55)
    gui_instance.perms_btn.setStyleSheet(f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #d4d0c8, stop:1 #c0c0c0);
            color: {gui_instance.text};
            border-radius: 0px;
            font-size: 18px;
            border-top: 2px outset {gui_instance.border_light};
            border-left: 2px outset {gui_instance.border_light};
            border-bottom: 2px outset {gui_instance.border_dark};
            border-right: 2px outset {gui_instance.border_dark};
            font-weight: bold;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #e8e4dc, stop:1 #d4d0c8);
        }}
        QPushButton:pressed {{
            background: {gui_instance.button_bg};
            border-top: 2px inset {gui_instance.border_dark};
            border-left: 2px inset {gui_instance.border_dark};
            border-bottom: 2px inset {gui_instance.border_light};
            border-right: 2px inset {gui_instance.border_light};
        }}
    """)
    gui_instance.perms_btn.clicked.connect(gui_instance.open_permissions)
    
    # Send button
    gui_instance.send_btn = QPushButton("➤")
    gui_instance.send_btn.setFixedWidth(55)
    gui_instance.send_btn.setStyleSheet(f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #d4d0c8, stop:1 #c0c0c0);
            color: {gui_instance.text};
            border-radius: 0px;
            font-size: 20px;
            border-top: 2px outset {gui_instance.border_light};
            border-left: 2px outset {gui_instance.border_light};
            border-bottom: 2px outset {gui_instance.border_dark};
            border-right: 2px outset {gui_instance.border_dark};
            font-weight: bold;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #e8e4dc, stop:1 #d4d0c8);
        }}
        QPushButton:pressed {{
            background: {gui_instance.button_bg};
            border-top: 2px inset {gui_instance.border_dark};
            border-left: 2px inset {gui_instance.border_dark};
            border-bottom: 2px inset {gui_instance.border_light};
            border-right: 2px inset {gui_instance.border_light};
        }}
        QPushButton:disabled {{
            background-color: #a0a0a0;
            color: #808080;
        }}
    """)
    gui_instance.input_box.setFocus()
    gui_instance.input_box.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    gui_instance.send_btn.clicked.connect(gui_instance.handle_send)
    gui_instance.input_box.returnPressed.connect(gui_instance.handle_send)


def _build_detail_page(gui_instance) -> QWidget:
    """Build the operation detail view page."""
    detail_page = QWidget()
    detail_layout = QVBoxLayout()
    detail_layout.setContentsMargins(0, 0, 0, 0)
    detail_layout.setSpacing(0)
    
    # Back button header
    back_header = QWidget()
    back_header_layout = QHBoxLayout()
    back_header_layout.setContentsMargins(4, 4, 4, 4)
    back_btn = QPushButton("← Back")
    back_btn.setStyleSheet(f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #d4d0c8, stop:1 #c0c0c0);
            color: {gui_instance.text};
            border-radius: 0px;
            font-size: 11px;
            font-weight: bold;
            padding: 6px 12px;
            border-top: 2px outset {gui_instance.border_light};
            border-left: 2px outset {gui_instance.border_light};
            border-bottom: 2px outset {gui_instance.border_dark};
            border-right: 2px outset {gui_instance.border_dark};
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #e8e4dc, stop:1 #d4d0c8);
        }}
        QPushButton:pressed {{
            border-top: 2px inset {gui_instance.border_dark};
            border-left: 2px inset {gui_instance.border_dark};
            border-bottom: 2px inset {gui_instance.border_light};
            border-right: 2px inset {gui_instance.border_light};
        }}
    """)
    back_btn.clicked.connect(lambda: gui_instance.operations_stack.setCurrentIndex(0))
    back_header_layout.addWidget(back_btn)
    back_header_layout.addStretch()
    back_header.setLayout(back_header_layout)
    back_header.setStyleSheet(f"""
        background-color: {gui_instance.button_bg};
        border-bottom: 1px solid {gui_instance.border_dark};
    """)
    detail_layout.addWidget(back_header)
    
    # Detail content
    gui_instance.operation_detail_label = QTextBrowser()
    gui_instance.operation_detail_label.setReadOnly(True)
    gui_instance.operation_detail_label.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    gui_instance.operation_detail_label.setText("Click an operation above to see details")
    gui_instance.operation_detail_label.setStyleSheet(f"""
        QTextBrowser {{
            background-color: {gui_instance.panel};
            color: {gui_instance.text};
            border: none;
            padding: 15px;
            font-family: 'Courier New', 'Monaco', monospace;
            font-size: 11px;
        }}
    """)
    detail_layout.addWidget(gui_instance.operation_detail_label)
    detail_page.setLayout(detail_layout)
    return detail_page


def _build_counters_widget(gui_instance) -> QWidget:
    """Build the counters widget at the bottom."""
    counters_widget = QWidget()
    counters_layout = QHBoxLayout()
    counters_layout.addStretch()
    counters_layout.addWidget(gui_instance.files_scanned_label)
    counters_layout.addWidget(gui_instance.files_moved_label)
    counters_layout.addWidget(gui_instance.time_label)
    counters_widget.setLayout(counters_layout)
    counters_widget.setStyleSheet(f"""
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #d4d0c8, stop:1 #c0c0c0);
        border-radius: 0px;
        padding: 8px;
        border-top: 2px inset {gui_instance.border_dark};
        border-left: 2px inset {gui_instance.border_dark};
        border-bottom: 2px inset {gui_instance.border_light};
        border-right: 2px inset {gui_instance.border_light};
        color: {gui_instance.text};
        font-family: 'Courier New', 'Monaco', monospace;
        font-weight: bold;
    """)
    return counters_widget


def build_preferences_panel(gui_instance) -> QWidget:
    """Build the preferences panel with categories and file notes.
    
    Args:
        gui_instance: The FileAdvisorGUI instance
        
    Returns:
        QWidget: The preferences panel widget
    """
    panel = QWidget()
    panel.setFixedHeight(250)
    layout = QVBoxLayout()
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)
    
    # Title bar
    title = QLabel("  PREFERENCES")
    title.setFixedHeight(18)
    title.setStyleSheet(f"""
        QLabel {{
            background-color: {gui_instance.button_bg};
            color: {gui_instance.text};
            font-family: 'Courier New', 'Monaco', monospace;
            font-size: 9px;
            font-weight: bold;
            padding-left: 6px;
            border-top: 2px inset {gui_instance.border_dark};
            border-left: 2px inset {gui_instance.border_dark};
            border-bottom: 1px solid {gui_instance.border_dark};
        }}
    """)
    layout.addWidget(title)
    
    # Content area with horizontal sections
    content = QWidget()
    content_layout = QHBoxLayout()
    content_layout.setContentsMargins(6, 4, 6, 4)
    content_layout.setSpacing(8)
    
    # Categories section
    categories_group = _build_categories_section(gui_instance)
    content_layout.addWidget(categories_group, 1)
    
    # File Notes section
    notes_group = _build_notes_section(gui_instance)
    content_layout.addWidget(notes_group, 1)
    
    content.setLayout(content_layout)
    layout.addWidget(content)
    panel.setLayout(layout)
    panel.setStyleSheet(f"""
        QWidget {{
            background-color: {gui_instance.panel};
            border: 2px inset {gui_instance.border_dark};
        }}
    """)
    
    # Load existing categories and notes
    gui_instance._refresh_categories_list()
    gui_instance._auto_add_directory_categories()
    gui_instance._refresh_notes_list()
    
    return panel


def _build_categories_section(gui_instance) -> QWidget:
    """Build the categories section of the preferences panel."""
    categories_group = QWidget()
    categories_layout = QVBoxLayout()
    categories_layout.setContentsMargins(4, 2, 4, 2)
    categories_layout.setSpacing(2)
    
    cat_label = QLabel("Categories:")
    cat_label.setFixedHeight(14)
    cat_label.setStyleSheet(f"font-size: 8px; font-weight: bold; color: {gui_instance.text};")
    categories_layout.addWidget(cat_label)
    
    # Category input and add button
    cat_input_row = QHBoxLayout()
    cat_input_row.setSpacing(4)
    gui_instance.category_input = QLineEdit()
    gui_instance.category_input.setPlaceholderText("New category...")
    gui_instance.category_input.setStyleSheet(f"""
        QLineEdit {{
            background-color: white;
            color: #000000;
            border: 1px inset {gui_instance.border_dark};
            padding: 2px 4px;
            font-size: 9px;
        }}
    """)
    gui_instance.category_input.setMaximumHeight(20)
    add_cat_btn = QPushButton("+")
    add_cat_btn.setFixedSize(20, 20)
    add_cat_btn.setStyleSheet(f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #d4d0c8, stop:1 #c0c0c0);
            border: 1px outset {gui_instance.border_light};
            font-size: 12px;
            font-weight: bold;
        }}
        QPushButton:pressed {{
            border: 1px inset {gui_instance.border_dark};
        }}
    """)
    add_cat_btn.clicked.connect(gui_instance._add_category)
    gui_instance.category_input.returnPressed.connect(gui_instance._add_category)
    cat_input_row.addWidget(gui_instance.category_input)
    cat_input_row.addWidget(add_cat_btn)
    categories_layout.addLayout(cat_input_row)
    
    # Categories list
    gui_instance.categories_list = QListWidget()
    gui_instance.categories_list.setMaximumHeight(100)
    gui_instance.categories_list.setStyleSheet(f"""
        QListWidget {{
            background-color: white;
            border: 1px inset {gui_instance.border_dark};
            font-size: 9px;
            color: {gui_instance.text};
        }}
        QListWidget::item {{
            color: {gui_instance.text};
        }}
    """)
    gui_instance.categories_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    gui_instance.categories_list.customContextMenuRequested.connect(gui_instance._show_category_context_menu)
    categories_layout.addWidget(gui_instance.categories_list)
    categories_group.setLayout(categories_layout)
    return categories_group


def _build_notes_section(gui_instance) -> QWidget:
    """Build the file notes section of the preferences panel."""
    notes_group = QWidget()
    notes_layout = QVBoxLayout()
    notes_layout.setContentsMargins(4, 2, 4, 2)
    notes_layout.setSpacing(2)
    
    notes_label = QLabel("File Notes:")
    notes_label.setFixedHeight(14)
    notes_label.setStyleSheet(f"font-size: 8px; font-weight: bold; color: {gui_instance.text};")
    notes_layout.addWidget(notes_label)
    
    # Button row for refresh and generate notes
    button_row = QHBoxLayout()
    button_row.setSpacing(4)
    
    # Refresh index button
    refresh_index_btn = QPushButton("Refresh Index")
    refresh_index_btn.setFixedHeight(22)
    refresh_index_btn.setStyleSheet(f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #d4d0c8, stop:1 #c0c0c0);
            border: 1px outset {gui_instance.border_light};
            font-size: 8px;
            font-weight: bold;
            color: {gui_instance.text};
        }}
        QPushButton:pressed {{
            border: 1px inset {gui_instance.border_dark};
        }}
    """)
    refresh_index_btn.clicked.connect(gui_instance._force_refresh_index)
    button_row.addWidget(refresh_index_btn)
    
    # Generate notes button
    generate_notes_btn = QPushButton("Generate Notes")
    generate_notes_btn.setFixedHeight(22)
    generate_notes_btn.setStyleSheet(f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #d4d0c8, stop:1 #c0c0c0);
            border: 1px outset {gui_instance.border_light};
            font-size: 8px;
            font-weight: bold;
            color: {gui_instance.text};
        }}
        QPushButton:pressed {{
            border: 1px inset {gui_instance.border_dark};
        }}
    """)
    generate_notes_btn.clicked.connect(gui_instance._generate_notes_for_all_files)
    button_row.addWidget(generate_notes_btn)
    
    notes_layout.addLayout(button_row)
    
    # Notes list label
    notes_list_label = QLabel("File Notes (double-click to edit):")
    notes_list_label.setFixedHeight(12)
    notes_list_label.setStyleSheet(f"font-size: 7px; font-weight: bold; color: {gui_instance.text};")
    notes_layout.addWidget(notes_list_label)
    
    # Notes list
    gui_instance.notes_list = QListWidget()
    gui_instance.notes_list.setMinimumHeight(120)
    gui_instance.notes_list.setStyleSheet(f"""
        QListWidget {{
            background-color: white;
            border: 2px inset {gui_instance.border_dark};
            font-size: 9px;
            color: {gui_instance.text};
        }}
        QListWidget::item {{
            color: {gui_instance.text};
            padding: 4px 2px;
            border-bottom: 1px solid #e0e0e0;
        }}
        QListWidget::item:selected {{
            background-color: #0080ff;
            color: white;
        }}
        QListWidget::item:hover {{
            background-color: #e0e0e0;
        }}
    """)
    gui_instance.notes_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    gui_instance.notes_list.customContextMenuRequested.connect(gui_instance._show_note_context_menu)
    gui_instance.notes_list.itemDoubleClicked.connect(gui_instance._edit_note)
    notes_layout.addWidget(gui_instance.notes_list)
    notes_group.setLayout(notes_layout)
    return notes_group

