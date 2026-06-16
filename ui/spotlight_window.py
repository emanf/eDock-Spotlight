import json
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QThread, QEvent, QItemSelectionModel, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListView, QApplication,
    QAbstractItemView, QSizePolicy, QDialog
)

from ..models import SearchResult
from ..core.constants import (
    QUERY_MODE_APPS, KIND_LOCAL, SEARCH_DEBOUNCE_MS,
    WINDOW_BASE_WIDTH, WINDOW_BASE_HEIGHT, INPUT_HEIGHT, RESULT_ROW_HEIGHT,
    FOCUS_HIDE_CLICK_BLOCK_SECONDS
)

from core.theming.theme_manager import Theme

from ..core.query_parser import QueryParser
from .search_input import SearchInput
from .results_list import ResultsListModel, ResultItemDelegate
from .dialogs import AppInfoDialog


class SpotlightWindow(QWidget):
    def __init__(self, app_ref, controller=None):
        super().__init__(None)
        
        self.app_ref = app_ref
        self.controller = controller
        
        # State
        self.current_results = []
        self.global_filter_installed = False
        self.last_focus_hide_time = 0.0
        self.search_in_progress = False
        
        # UI dimensions
        self.base_width = WINDOW_BASE_WIDTH
        self.base_height = WINDOW_BASE_HEIGHT
        self.input_height = INPUT_HEIGHT
        self.result_row_height = RESULT_ROW_HEIGHT
        
        # Timers
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self.search_timer.timeout.connect(self._on_search_timeout)
        
        self.close_focus_timer = QTimer(self)
        self.close_focus_timer.setSingleShot(True)
        self.close_focus_timer.setInterval(80)
        self.close_focus_timer.timeout.connect(self._close_if_unfocused)
        
        # Window setup
        self.setObjectName("spotlightWindow")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(self.base_width, self.base_height)
        
        # Build UI
        self._build_ui()
        self._apply_style()
        
        # Install global event filter
        app = QApplication.instance()
        if app is not None and not self.global_filter_installed:
            app.installEventFilter(self)
            self.global_filter_installed = True
    
    def _build_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setObjectName("mainLayout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Main container
        self.container = QWidget(self)
        self.container.setObjectName("spotlightContainer")
        self.container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.container.setAttribute(Qt.WA_StyledBackground, True)
        self.container.setAutoFillBackground(True)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(16, 12, 16, 12)
        container_layout.setSpacing(8)
        
        # Top spacer - centers input vertically in the middle of top half
        container_layout.addStretch(1)
        
        # Search input
        self.input = SearchInput(self.container)
        self.input.setFixedHeight(self.input_height)
        self.input.query_changed.connect(self._on_query_changed)
        self.input.query_submitted.connect(self._on_query_submitted)
        self.input.installEventFilter(self)
        container_layout.addWidget(self.input)
        
        # Bottom spacer
        container_layout.addStretch(1)
        
        # Results list
        self.list_view = QListView(self.container)
        self.list_view.setObjectName("searchListView")
        self.list_view.setFrameShape(QListView.NoFrame)
        self.list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setSpacing(4)
        self.list_view.setMouseTracking(True)
        self.list_view.installEventFilter(self)
        self.list_view.clicked.connect(self._on_result_selected)
        
        # Result model and delegate
        self.list_model = ResultsListModel(self)
        self.list_view.setModel(self.list_model)
        
        self.result_delegate = ResultItemDelegate(self.list_view)
        self.result_delegate.row_height = self.result_row_height
        self.list_model.row_height = self.result_row_height
        self.list_view.setItemDelegate(self.result_delegate)
        
        self.list_view.viewport().installEventFilter(self)
        self.list_view.hide()
        self.list_view.setFixedHeight(0)
        
        container_layout.addWidget(self.list_view)
        
        self.layout.addWidget(self.container)
    
    def _apply_style(self):
        uic = Theme.to_ui_color
        colors = Theme.get_colors()
        
        bg = uic(colors.get(Theme.Colors.BACKGROUND))
        border = uic(colors.get(Theme.Colors.BORDER))
        text = uic(colors.get(Theme.Colors.TEXT))
        hover_bg = uic(colors.get(Theme.Colors.SURFACE_HOVER))
        selected_bg = uic(colors.get(Theme.Colors.SURFACE_PRESSED))
        scrollbar_color = uic(colors.get(Theme.Colors.BORDER))
        
        stylesheet = f"""
            QWidget#spotlightContainer {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            
            QLineEdit#searchInput {{
                background: transparent;
                border: none;
                color: {text};
                font-size: 19px;
                padding: 0px 4px;
            }}
            
            QListView#searchListView {{
                background: transparent;
                border: none;
                color: {text};
                outline: none;
                padding: 0px;
                font-size: 14px;
            }}
            
            QListView#searchListView::item {{
                background: transparent;
                border: none;
                border-radius: 10px;
                padding: 10px 12px;
                margin: 0px;
            }}
            
            QListView#searchListView::item:selected {{
                background: {selected_bg};
                color: white;
            }}
            
            QListView#searchListView::item:hover {{
                background: {hover_bg};
            }}
            
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 4px 0px 4px 0px;
                border: none;
            }}
            
            QScrollBar::handle:vertical {{
                background: {scrollbar_color};
                border-radius: 4px;
                min-height: 28px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background: {hover_bg};
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                background: transparent;
            }}
        """
        
        self.setStyleSheet(stylesheet)
    
    def _on_query_changed(self, text: str):
        """Handle query text changes."""
        # Restart debounce timer
        self.search_timer.stop()
        self.search_timer.start()
    
    def _on_search_timeout(self):
        """Execute search after debounce."""
        if self.controller:
            query = self.input.get_query()
            mode, cleaned_query = QueryParser.parse(query)
            self.controller.search(cleaned_query, mode)
    
    def _on_query_submitted(self, query: str):
        """Handle Enter key press."""
        # Select first result if available
        if self.list_model.rowCount() > 0:
            index = self.list_model.index(0)
            self.list_view.setCurrentIndex(index)
            self._on_result_selected(index)
    
    def _on_result_selected(self, index):
        """Handle result selection."""
        if not index.isValid():
            return
        
        result_dict = index.data(ResultsListModel.ItemRole)
        if result_dict:
            if self.controller:
                self.controller.handle_result_action(result_dict)
                # Clear and hide after action
                self.clear()
    
    def update_results(self, results: list):
        """
        Update the displayed results.
        
        Args:
            results: List of SearchResult objects or dicts
        """
        self.current_results = results
        
        # Convert to dict format for display
        result_dicts = []
        for result in results:
            if isinstance(result, SearchResult):
                result_dicts.append(result.to_dict())
            else:
                result_dicts.append(result)
        
        self.list_model.set_results(result_dicts)
        
        # Update window height based on number of results
        self._update_window_size()
    
    def _update_window_size(self):
        """Update window size based on results count."""
        result_count = len(self.current_results)
        new_height = self.base_height
        
        if result_count > 0:
            list_height = min(result_count * self.result_row_height, 6 * self.result_row_height)
            new_height = self.base_height + list_height + 8  # 8 for spacing
        
        self.setFixedHeight(new_height)
        if result_count > 0:
            self.list_view.show()
            self.list_view.setFixedHeight(self.list_model.rowCount() * self.result_row_height + 8)
        else:
            self.list_view.hide()
            self.list_view.setFixedHeight(0)
    
    def toggle(self):
        """Toggle window visibility."""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.input.setFocus()
            self.input.selectAll()
    
    def clear(self):
        """Clear the search input and results."""
        self.input.clear()
        self.list_model.set_results([])
        self._update_window_size()
    
    def eventFilter(self, obj, event):
        """Handle global events."""
        if event.type() == QEvent.KeyPress:
            key = event.key()
            
            # Handle Escape key
            if key == Qt.Key_Escape:
                if self.isVisible():
                    self.hide()
                    return True
            
            # Handle arrow keys for navigation
            if obj is self.input or obj is self.list_view:
                if key == Qt.Key_Down:
                    if self.list_view.isVisible():
                        current = self.list_view.currentIndex()
                        if not current.isValid():
                            self.list_view.setCurrentIndex(self.list_model.index(0))
                        else:
                            next_row = current.row() + 1
                            if next_row < self.list_model.rowCount():
                                self.list_view.setCurrentIndex(self.list_model.index(next_row))
                        return True
                
                elif key == Qt.Key_Up:
                    if self.list_view.isVisible():
                        current = self.list_view.currentIndex()
                        if current.isValid():
                            prev_row = current.row() - 1
                            if prev_row >= 0:
                                self.list_view.setCurrentIndex(self.list_model.index(prev_row))
                            else:
                                self.input.setFocus()
                        return True
                
                elif key == Qt.Key_Return and self.list_view.currentIndex().isValid():
                    self._on_result_selected(self.list_view.currentIndex())
                    return True
        
        elif event.type() == QEvent.FocusOut:
            self.close_focus_timer.start()
        
        return super().eventFilter(obj, event)
    
    def _close_if_unfocused(self):
        """Close window if it loses focus."""
        if not self.hasFocus() and not self.underMouse():
            self.hide()
    
    def apply_theme_change(self):
        """Reapply theme styling."""
        helper = ThemeHelper()
        helper.clear_cache()
        self._apply_style()
