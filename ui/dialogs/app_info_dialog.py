"""Application information dialog."""
import json
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QThread, QObject, Signal, Slot
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QProgressBar, QFrame
)

from core.theming.theme_manager import Theme


class ManifestFetchWorker(QObject):
    finished = Signal(dict)
    failed = Signal(str)
    
    def __init__(self, manifest_url: str, parent=None):
        super().__init__(parent)
        self.manifest_url = str(manifest_url or "").strip()
    
    @Slot()
    def run(self):
        if not self.manifest_url:
            self.finished.emit({})
            return
        
        try:
            request = urllib.request.Request(
                self.manifest_url,
                headers={
                    "User-Agent": "eDock-Spotlight/1.0",
                    "Accept": "application/json",
                },
            )
            
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            self.finished.emit(data if isinstance(data, dict) else {})
        except Exception as error:
            self.failed.emit(str(error))
            self.finished.emit({})


class AppInfoDialog(QDialog):
    """Dialog for displaying app information and installation."""
    
    def __init__(self, app_data: dict, parent=None):
        """
        Initialize the dialog.
        
        Args:
            app_data: Dictionary containing app information
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.app_data = dict(app_data or {})
        self.manifest_data = {}
        self.fetch_thread = None
        self.fetch_worker = None
        
        # Dialog setup
        self.setWindowTitle("App Information")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setMinimumHeight(440)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Build UI
        self._build_ui()
        self._apply_style()
        
        # Fetch manifest if URL available
        manifest_url = self._get_manifest_url()
        if manifest_url:
            self.set_loading(True)
            QTimer.singleShot(0, self._start_fetch)
    
    def _build_ui(self):
        """Build the dialog UI."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(0)
        
        # Container with rounded corners
        self.container = QFrame(self)
        self.container.setObjectName("appInfoContainer")
        root_layout.addWidget(self.container)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        
        # Header with icon and title
        hero_layout = QHBoxLayout()
        hero_layout.setSpacing(14)
        
        self.icon_label = QLabel(str(self.app_data.get("icon", "m:apps")))
        self.icon_label.setObjectName("appIcon")
        self.icon_label.setFixedSize(54, 54)
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        title_area = QVBoxLayout()
        title_area.setSpacing(4)
        
        self.title_label = QLabel(self._get_display_title())
        self.title_label.setObjectName("appTitle")
        title_font = self.title_label.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        
        self.description_label = QLabel(
            str(self.app_data.get("subtitle") or self.app_data.get("description") or "")
        )
        self.description_label.setObjectName("appDescription")
        self.description_label.setWordWrap(True)
        
        title_area.addWidget(self.title_label)
        title_area.addWidget(self.description_label)
        
        self.close_button = QPushButton("✕", self)
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(30, 30)
        self.close_button.clicked.connect(self.reject)
        
        hero_layout.addWidget(self.icon_label)
        hero_layout.addLayout(title_area, 1)
        hero_layout.addWidget(self.close_button)
        
        # Divider
        divider = QFrame(self)
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.HLine)
        divider.setFixedHeight(1)
        
        # Loading progress
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        
        # Info text
        self.info_text = QTextEdit(self)
        self.info_text.setObjectName("infoText")
        self.info_text.setReadOnly(True)
        self.info_text.setPlainText("Loading app information...")
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        buttons_layout.addStretch(1)
        
        self.close_info_button = QPushButton("Close", self)
        self.close_info_button.clicked.connect(self.reject)
        
        self.action_button = QPushButton("Install", self)
        self.action_button.setObjectName("actionButton")
        self.action_button.clicked.connect(self.accept)
        
        buttons_layout.addWidget(self.close_info_button)
        buttons_layout.addWidget(self.action_button)
        
        # Add all to layout
        layout.addLayout(hero_layout)
        layout.addWidget(divider)
        layout.addWidget(self.progress)
        layout.addWidget(self.info_text, 1)
        layout.addLayout(buttons_layout)
    
    def _apply_style(self):
        uic = Theme.to_ui_color
        colors = Theme.get_colors()
        
        bg = uic(colors.get(Theme.Colors.BACKGROUND))
        text = uic(colors.get(Theme.Colors.TEXT))
        secondary_text = uic(colors.get(Theme.Colors.TEXT))
        border = uic(colors.get(Theme.Colors.BORDER))
        hover = uic(colors.get(Theme.Colors.SURFACE_HOVER))
        pressed = uic(colors.get(Theme.Colors.SURFACE_PRESSED))
        
        stylesheet = f"""
            QFrame#appInfoContainer {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            
            QLabel#appIcon {{
                background: {hover};
                color: {text};
                border: 1px solid {border};
                border-radius: 16px;
                font-size: 22px;
                font-weight: bold;
            }}
            
            QLabel#appTitle {{
                color: {text};
                font-size: 14px;
                font-weight: bold;
            }}
            
            QLabel#appDescription {{
                color: {secondary_text};
                font-size: 11px;
            }}
            
            QFrame#divider {{
                background: {border};
                border: none;
            }}
            
            QTextEdit#infoText {{
                background: transparent;
                border: none;
                color: {text};
                font-size: 11px;
                selection-background-color: {pressed};
            }}
            
            QProgressBar {{
                background: {hover};
                border: none;
                border-radius: 6px;
                height: 8px;
            }}
            
            QProgressBar::chunk {{
                background: {pressed};
                border-radius: 6px;
            }}
            
            QPushButton {{
                background: transparent;
                border: 1px solid {border};
                border-radius: 10px;
                color: {text};
                padding: 7px 14px;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background: {hover};
            }}
            
            QPushButton:pressed {{
                background: {pressed};
                color: white;
            }}
            
            QPushButton#actionButton {{
                background: {pressed};
                border: none;
                color: white;
            }}
            
            QPushButton#actionButton:hover {{
                background: {pressed};
                opacity: 0.8;
            }}
            
            QPushButton#closeButton {{
                border: none;
                padding: 0px;
                background: transparent;
            }}
        """
        
        self.setStyleSheet(stylesheet)
    
    def _get_display_title(self) -> str:
        """Get the display title for the app."""
        return str(
            self.app_data.get("title") or
            self.app_data.get("name") or
            self.app_data.get("id") or
            "Application"
        ).strip()
    
    def _get_manifest_url(self) -> str:
        """Get the manifest URL from app data."""
        return str(
            self.app_data.get("manifest_url") or
            self.app_data.get("manifest") or
            self.app_data.get("app_manifest") or
            ""
        ).strip()
    
    def set_loading(self, loading: bool):
        """Show/hide loading indicator."""
        self.progress.setVisible(bool(loading))
    
    def _start_fetch(self):
        """Start fetching the manifest."""
        manifest_url = self._get_manifest_url()
        if not manifest_url:
            self.set_loading(False)
            return
        
        self.fetch_thread = QThread(self)
        self.fetch_worker = ManifestFetchWorker(manifest_url)
        self.fetch_worker.moveToThread(self.fetch_thread)
        
        self.fetch_thread.started.connect(self.fetch_worker.run)
        self.fetch_worker.finished.connect(self._on_manifest_loaded)
        self.fetch_worker.finished.connect(self.fetch_thread.quit)
        self.fetch_worker.failed.connect(self._on_manifest_failed)
        self.fetch_worker.finished.connect(self.fetch_worker.deleteLater)
        self.fetch_thread.finished.connect(self.fetch_thread.deleteLater)
        
        self.fetch_thread.start()
    
    def _on_manifest_failed(self, message: str):
        """Handle manifest fetch failure."""
        if message:
            print(f"Manifest fetch error: {message}")
    
    def _on_manifest_loaded(self, data: dict):
        """Handle manifest loaded."""
        self.manifest_data = data if isinstance(data, dict) else {}
        merged = self._get_merged_data()
        
        self.title_label.setText(self._get_display_title())
        self.description_label.setText(
            str(merged.get("description") or merged.get("subtitle") or "")
        )
        self.info_text.setPlainText(self._build_info_text(merged))
        self.set_loading(False)
    
    def _get_merged_data(self) -> dict:
        """Merge app data with fetched manifest data."""
        merged = {}
        merged.update(self.app_data)
        merged.update(self.manifest_data)
        return merged
    
    def _build_info_text(self, data: dict) -> str:
        """Build the info text display."""
        keys = [
            "id", "app_id", "title", "version", "author", "description",
            "category", "keywords", "homepage", "size", "minDockVersion", "sha256"
        ]
        
        lines = []
        for key in keys:
            value = data.get(key)
            if value is None or value == "":
                continue
            
            if isinstance(value, (list, tuple)):
                value = ", ".join(str(v) for v in value)
            elif isinstance(value, dict):
                value = json.dumps(value, indent=2, ensure_ascii=False)
            
            formatted_key = key.replace("_", " ").title()
            lines.append(f"{formatted_key}: {value}")
        
        if not lines:
            return json.dumps(data, indent=2, ensure_ascii=False)
        
        return "\n".join(lines)
