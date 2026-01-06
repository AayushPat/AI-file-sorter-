"""
UI COMPONENTS MODULE

Reusable UI components for the application, including CustomTitleBar for the
Windows 95-style title bar with drag-to-move functionality.
"""

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QLinearGradient, QColor
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel


# CustomTitleBar creates a Windows 95-style title bar with drag-to-move.
# We use a frameless window and this custom bar replaces the native macOS
# title bar to get the retro look we want.
class CustomTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.drag_position = QPoint()
        self.setFixedHeight(30)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        
        # Window title - transparent background so gradient shows through
        self.title_label = QLabel("File Sorter AI")
        self.title_label.setStyleSheet("""
            QLabel {
                background: transparent;
                color: white;
                font-family: 'Courier New', 'Monaco', monospace;
                font-size: 11px;
                font-weight: bold;
                padding-left: 8px;
            }
        """)
        layout.addWidget(self.title_label)
        layout.addStretch()
        
        # Window buttons (Windows 95 style)
        # Minimize button
        self.min_btn = QPushButton("_")
        self.min_btn.setFixedSize(20, 20)
        self.min_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0c0c0;
                color: black;
                border: 1px outset #ffffff;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #d4d0c8;
            }
            QPushButton:pressed {
                border: 1px inset #808080;
            }
        """)
        self.min_btn.clicked.connect(parent.showMinimized)
        layout.addWidget(self.min_btn)
        
        # Maximize/Restore button
        self.max_btn = QPushButton("□")
        self.max_btn.setFixedSize(20, 20)
        self.max_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0c0c0;
                color: black;
                border: 1px outset #ffffff;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #d4d0c8;
            }
            QPushButton:pressed {
                border: 1px inset #808080;
            }
        """)
        self.max_btn.clicked.connect(self.toggle_maximize)
        layout.addWidget(self.max_btn)
        
        # Close button
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0c0c0;
                color: black;
                border: 1px outset #ffffff;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #ff0000;
                color: white;
            }
            QPushButton:pressed {
                border: 1px inset #808080;
            }
        """)
        self.close_btn.clicked.connect(parent.close)
        layout.addWidget(self.close_btn)
        
        self.setLayout(layout)
        
        # Title bar styling - gradient blue covering entire bar
        # Use paintEvent to ensure gradient is drawn
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
    
    def paintEvent(self, event):
        """Paint the gradient background"""
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor("#0080ff"))
        gradient.setColorAt(0.5, QColor("#0073e6"))
        gradient.setColorAt(1, QColor("#0066cc"))
        painter.fillRect(self.rect(), gradient)
        super().paintEvent(event)
    
    def toggle_maximize(self):
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
            self.max_btn.setText("□")
        else:
            self.parent_window.showMaximized()
            self.max_btn.setText("❐")
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            if self.drag_position:
                self.parent_window.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

