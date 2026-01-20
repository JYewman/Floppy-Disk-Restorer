"""
Session preset dialog for Floppy Workbench.

This dialog allows users to save and manage session presets.
Supports two modes:
- Save mode: Save the current session as a named preset
- Manage mode: View, load, and delete existing presets

Part of Phase 4: UI Implementation
"""

import logging
from typing import Optional, List

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QGroupBox,
    QMessageBox,
    QDialogButtonBox,
    QFrame,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont

from floppy_formatter.core.session import DiskSession
from floppy_formatter.core.session_manager import SessionManager

logger = logging.getLogger(__name__)


class SessionPresetDialog(QDialog):
    """
    Dialog for saving and managing session presets.

    Modes:
        - "save": Save a session as a new preset
        - "manage": View, load, and delete presets
    """

    def __init__(
        self,
        mode: str = "save",
        session: Optional[DiskSession] = None,
        parent=None
    ):
        """
        Initialize the preset dialog.

        Args:
            mode: Dialog mode ("save" or "manage")
            session: Session to save (required for save mode)
            parent: Parent widget
        """
        super().__init__(parent)

        self._mode = mode
        self._session = session
        self._session_manager = SessionManager.instance()
        self._preset_name: Optional[str] = None
        self._selected_preset: Optional[str] = None

        self._setup_ui()
        self._connect_signals()

        if mode == "manage":
            self._load_presets()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        if self._mode == "save":
            self.setWindowTitle("Save Session Preset")
            self.setMinimumSize(400, 250)
        else:
            self.setWindowTitle("Manage Session Presets")
            self.setMinimumSize(500, 400)

        self.setStyleSheet("""
            QDialog {
                background-color: #252526;
            }
            QLabel {
                color: #cccccc;
            }
            QLineEdit {
                background-color: #3a3d41;
                color: #cccccc;
                border: 1px solid #4a4d51;
                border-radius: 4px;
                padding: 8px;
            }
            QLineEdit:focus {
                border-color: #007acc;
            }
            QGroupBox {
                font-weight: bold;
                color: #cccccc;
                border: 1px solid #3a3d41;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QListWidget {
                background-color: #2d2d30;
                color: #cccccc;
                border: 1px solid #3a3d41;
                border-radius: 4px;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
            QListWidget::item:hover:!selected {
                background-color: #2a2d2e;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        if self._mode == "save":
            self._setup_save_ui(main_layout)
        else:
            self._setup_manage_ui(main_layout)

    def _setup_save_ui(self, layout: QVBoxLayout) -> None:
        """Set up the save preset UI."""
        # Session info
        if self._session:
            info_frame = QFrame()
            info_frame.setStyleSheet("""
                QFrame {
                    background-color: #2d2d30;
                    border: 1px solid #3a3d41;
                    border-radius: 4px;
                }
            """)
            info_layout = QVBoxLayout(info_frame)
            info_layout.setContentsMargins(12, 12, 12, 12)

            session_label = QLabel(f"Session: {self._session.name}")
            session_label.setStyleSheet("font-weight: bold; border: none; background: transparent;")
            info_layout.addWidget(session_label)

            details_label = QLabel(
                f"Format: {self._session.gw_format} | "
                f"Geometry: {self._session.cylinders}C/{self._session.heads}H/"
                f"{self._session.sectors_per_track}S"
            )
            details_label.setStyleSheet("color: #888888; border: none; background: transparent;")
            info_layout.addWidget(details_label)

            layout.addWidget(info_frame)

        # Preset name input
        name_group = QGroupBox("Preset Name")
        name_layout = QVBoxLayout(name_group)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Enter a name for this preset...")
        if self._session:
            self._name_input.setText(self._session.name)
        name_layout.addWidget(self._name_input)

        layout.addWidget(name_group)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setStyleSheet(self._get_button_style())
        button_layout.addWidget(self._cancel_btn)

        self._save_btn = QPushButton("Save Preset")
        self._save_btn.setStyleSheet(self._get_primary_button_style())
        self._save_btn.setDefault(True)
        button_layout.addWidget(self._save_btn)

        layout.addLayout(button_layout)

    def _setup_manage_ui(self, layout: QVBoxLayout) -> None:
        """Set up the manage presets UI."""
        # Preset list
        list_group = QGroupBox("Saved Presets")
        list_layout = QVBoxLayout(list_group)

        self._preset_list = QListWidget()
        list_layout.addWidget(self._preset_list)

        # List actions
        actions_layout = QHBoxLayout()

        self._load_btn = QPushButton("Load")
        self._load_btn.setStyleSheet(self._get_button_style())
        self._load_btn.setEnabled(False)
        actions_layout.addWidget(self._load_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setStyleSheet(self._get_danger_button_style())
        self._delete_btn.setEnabled(False)
        actions_layout.addWidget(self._delete_btn)

        actions_layout.addStretch()
        list_layout.addLayout(actions_layout)

        layout.addWidget(list_group)

        # Preview panel
        preview_group = QGroupBox("Preset Details")
        preview_layout = QVBoxLayout(preview_group)

        self._preview_label = QLabel("Select a preset to see details")
        self._preview_label.setStyleSheet("color: #888888;")
        self._preview_label.setWordWrap(True)
        preview_layout.addWidget(self._preview_label)

        layout.addWidget(preview_group)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._close_btn = QPushButton("Close")
        self._close_btn.setStyleSheet(self._get_button_style())
        button_layout.addWidget(self._close_btn)

        layout.addLayout(button_layout)

    def _get_button_style(self) -> str:
        """Get standard button style."""
        return """
            QPushButton {
                background-color: #3a3d41;
                color: #cccccc;
                border: 1px solid #4a4d51;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a4d51;
                border-color: #5a5d61;
            }
            QPushButton:pressed {
                background-color: #2a2d31;
            }
            QPushButton:disabled {
                background-color: #2a2d31;
                color: #666666;
                border-color: #3a3d41;
            }
        """

    def _get_primary_button_style(self) -> str:
        """Get primary button style."""
        return """
            QPushButton {
                background-color: #007acc;
                color: #ffffff;
                border: 1px solid #0088dd;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0088dd;
                border-color: #0099ee;
            }
            QPushButton:pressed {
                background-color: #006abb;
            }
            QPushButton:disabled {
                background-color: #3a3d41;
                color: #666666;
                border-color: #4a4d51;
            }
        """

    def _get_danger_button_style(self) -> str:
        """Get danger button style."""
        return """
            QPushButton {
                background-color: #8b3a3a;
                color: #ffffff;
                border: 1px solid #9b4a4a;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #9b4a4a;
                border-color: #ab5a5a;
            }
            QPushButton:pressed {
                background-color: #7b2a2a;
            }
            QPushButton:disabled {
                background-color: #4a3a3a;
                color: #888888;
                border-color: #5a4a4a;
            }
        """

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        if self._mode == "save":
            self._cancel_btn.clicked.connect(self.reject)
            self._save_btn.clicked.connect(self._on_save_clicked)
            self._name_input.textChanged.connect(self._on_name_changed)
        else:
            self._close_btn.clicked.connect(self.accept)
            self._preset_list.currentItemChanged.connect(self._on_preset_selected)
            self._preset_list.itemDoubleClicked.connect(self._on_load_clicked)
            self._load_btn.clicked.connect(self._on_load_clicked)
            self._delete_btn.clicked.connect(self._on_delete_clicked)

    def _load_presets(self) -> None:
        """Load presets into the list."""
        self._preset_list.clear()

        presets = self._session_manager.list_presets()
        for name in sorted(presets):
            info = self._session_manager.get_preset_info(name)
            if info:
                item = QListWidgetItem()
                item.setText(name)
                item.setData(Qt.ItemDataRole.UserRole, info)
                self._preset_list.addItem(item)

        if not presets:
            item = QListWidgetItem("No saved presets")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._preset_list.addItem(item)

    def _on_name_changed(self, text: str) -> None:
        """Handle name input change."""
        self._save_btn.setEnabled(bool(text.strip()))

    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Invalid Name",
                "Please enter a name for the preset."
            )
            return

        if not self._session:
            QMessageBox.warning(
                self, "No Session",
                "No session to save."
            )
            return

        # Check if preset already exists
        existing = self._session_manager.list_presets()
        if name in existing:
            reply = QMessageBox.question(
                self, "Preset Exists",
                f"A preset named '{name}' already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Save the preset
        try:
            self._session_manager.save_preset(name, self._session)
            self._preset_name = name
            logger.info(f"Preset saved: {name}")
            self.accept()
        except Exception as e:
            logger.error(f"Error saving preset: {e}")
            QMessageBox.critical(
                self, "Error",
                f"Failed to save preset: {e}"
            )

    def _on_preset_selected(self, current: Optional[QListWidgetItem],
                            previous: Optional[QListWidgetItem]) -> None:
        """Handle preset selection change."""
        if current is None or current.flags() == Qt.ItemFlag.NoItemFlags:
            self._load_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            self._preview_label.setText("Select a preset to see details")
            self._selected_preset = None
            return

        info = current.data(Qt.ItemDataRole.UserRole)
        if info:
            self._selected_preset = current.text()
            self._load_btn.setEnabled(True)
            self._delete_btn.setEnabled(True)

            preview_text = (
                f"<b>Name:</b> {info.get('name', 'Unknown')}<br>"
                f"<b>Format:</b> {info.get('gw_format', 'Unknown')}<br>"
                f"<b>Platform:</b> {info.get('platform', 'Unknown')}<br>"
                f"<b>Created:</b> {info.get('created_at', 'Unknown')}"
            )
            self._preview_label.setText(preview_text)

    def _on_load_clicked(self) -> None:
        """Handle load button click."""
        if not self._selected_preset:
            return

        session = self._session_manager.load_preset(self._selected_preset)
        if session:
            self._session_manager.set_active_session(session)
            logger.info(f"Preset loaded and activated: {self._selected_preset}")
            self.accept()
        else:
            QMessageBox.warning(
                self, "Load Error",
                f"Failed to load preset '{self._selected_preset}'."
            )

    def _on_delete_clicked(self) -> None:
        """Handle delete button click."""
        if not self._selected_preset:
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete preset '{self._selected_preset}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self._session_manager.delete_preset(self._selected_preset):
                logger.info(f"Preset deleted: {self._selected_preset}")
                self._load_presets()
            else:
                QMessageBox.warning(
                    self, "Delete Error",
                    f"Failed to delete preset '{self._selected_preset}'."
                )

    def get_preset_name(self) -> Optional[str]:
        """
        Get the name of the saved preset.

        Returns:
            The preset name if saved, else None
        """
        return self._preset_name

    def get_selected_preset(self) -> Optional[str]:
        """
        Get the name of the selected preset (manage mode).

        Returns:
            The selected preset name, or None
        """
        return self._selected_preset

    def keyPressEvent(self, event) -> None:
        """
        Handle keyboard navigation.

        Supported keys:
            - Escape: Close dialog (reject)
            - Enter/Return: Save preset (save mode) or load preset (manage mode)
        """
        key = event.key()

        if key == Qt.Key.Key_Escape:
            self.reject()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._mode == "save":
                if hasattr(self, '_save_btn') and self._save_btn.isEnabled():
                    self._on_save_clicked()
                    return
            else:  # manage mode
                if hasattr(self, '_load_btn') and self._load_btn.isEnabled():
                    self._on_load_clicked()
                    return

        super().keyPressEvent(event)
