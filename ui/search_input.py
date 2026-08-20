from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QLineEdit


class SearchInput(QLineEdit):
    query_changed = Signal(str)
    query_submitted = Signal(str)

    DEFAULT_TIPS = (
        "Search apps, files, commands...",
        "Use > to discover and install apps"
    )
    TIP_OPACITY = 0.62

    def __init__(self, parent=None, tips=None):
        super().__init__(parent)

        self.setObjectName("searchInput")
        self.setPlaceholderText("")
        self.setAttribute(Qt.WA_MacShowFocusRect, False)
        self.setFocusPolicy(Qt.StrongFocus)

        self._tips = tuple(tips or self.DEFAULT_TIPS)
        self._tip_index = 0
        self._tip_label = QLabel(self._tips[0], self)
        self._tip_label.setObjectName("searchTip")
        self._tip_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._tip_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._tip_label.setContentsMargins(4, 0, 0, 0)

        self._tip_opacity = QGraphicsOpacityEffect(self._tip_label)
        self._tip_label.setGraphicsEffect(self._tip_opacity)
        self._tip_opacity.setOpacity(self.TIP_OPACITY)

        self._tip_timer = QTimer(self)
        self._tip_timer.setInterval(2500)
        self._tip_timer.timeout.connect(self._rotate_tip)
        self._tip_timer.start()

        self.textChanged.connect(self._on_text_changed)
        self.returnPressed.connect(self._on_return_pressed)
        self._update_tip_visibility("")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._tip_label.setGeometry(0, 0, self.width(), self.height())

    def set_tips(self, tips):
        values = tuple(str(t).strip() for t in (tips or ()) if str(t).strip())
        if not values:
            values = self.DEFAULT_TIPS
        self._tips = values
        self._tip_index = 0
        self._tip_label.setText(self._tips[0])

    def _update_tip_visibility(self, text):
        empty = not str(text or "")
        self._tip_label.setVisible(empty)
        if empty:
            self._tip_opacity.setOpacity(self.TIP_OPACITY)
            self._tip_timer.start()
        else:
            self._tip_timer.stop()

    def _rotate_tip(self):
        if self.text():
            self._update_tip_visibility(self.text())
            return

        fade_out = QPropertyAnimation(self._tip_opacity, b"opacity", self)
        fade_out.setDuration(260)
        fade_out.setStartValue(self.TIP_OPACITY)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.InOutCubic)

        def swap_tip():
            if self.text():
                self._tip_opacity.setOpacity(0.0)
                self._tip_label.hide()
                return
            self._tip_index = (self._tip_index + 1) % len(self._tips)
            self._tip_label.setText(self._tips[self._tip_index])

            fade_in = QPropertyAnimation(self._tip_opacity, b"opacity", self)
            fade_in.setDuration(360)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(self.TIP_OPACITY)
            fade_in.setEasingCurve(QEasingCurve.InOutCubic)
            self._tip_animation = fade_in
            fade_in.start()

        fade_out.finished.connect(swap_tip)
        self._tip_animation = fade_out
        fade_out.start()

    def _on_text_changed(self, text: str):
        self._update_tip_visibility(text)
        self.query_changed.emit(text)

    def _on_return_pressed(self):
        self.query_submitted.emit(self.text())

    def get_query(self) -> str:
        return self.text().strip()
