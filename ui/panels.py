"""Side panel widgets for controlling banner elements"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox,
    QDoubleSpinBox, QCheckBox, QPushButton, QColorDialog, QFileDialog,
    QGroupBox, QComboBox, QSlider, QScrollArea, QFrame, QSizePolicy,
    QListWidget, QListWidgetItem, QToolButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon


def color_button(color_hex: str, callback) -> QPushButton:
    btn = QPushButton()
    btn.setFixedSize(36, 28)
    btn.setStyleSheet(f"background:{color_hex}; border:1px solid #666; border-radius:3px;")
    btn.clicked.connect(lambda: _pick_color(btn, callback))
    return btn


def _pick_color(btn: QPushButton, callback):
    cur = btn.palette().button().color()
    c = QColorDialog.getColor(cur, btn, "Pick colour")
    if c.isValid():
        btn.setStyleSheet(
            f"background:{c.name()}; border:1px solid #666; border-radius:3px;")
        callback(c.name())


def _row(label: str, widget: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setFixedWidth(110)
    row.addWidget(lbl)
    row.addWidget(widget)
    return row


# ──────────────────────────────────────────────────────────────
class BackgroundPanel(QGroupBox):
    changed = Signal()

    def __init__(self, config, parent=None):
        super().__init__("Background", parent)
        self.config = config
        lay = QVBoxLayout(self)

        self._btn = color_button(config.background_color,
                                 self._set_bg)
        row = QHBoxLayout()
        row.addWidget(QLabel("Colour"))
        row.addWidget(self._btn)
        row.addStretch()
        lay.addLayout(row)

    def _set_bg(self, hex_color: str):
        self.config.background_color = hex_color
        self.changed.emit()


# ──────────────────────────────────────────────────────────────
class TextPanel(QGroupBox):
    changed = Signal()

    def __init__(self, title: str, el, parent=None):
        super().__init__(title, parent)
        self.el = el
        lay = QVBoxLayout(self)

        self._text_edit = QLineEdit(el.text)
        self._text_edit.setPlaceholderText("Enter text…")
        self._text_edit.textChanged.connect(self._on_text)
        lay.addLayout(_row("Text", self._text_edit))

        self._font_combo = QComboBox()
        fonts = ["Arial", "Impact", "Georgia", "Verdana", "Times New Roman",
                 "Helvetica", "Roboto", "Open Sans", "Bebas Neue", "Oswald"]
        self._font_combo.addItems(fonts)
        idx = self._font_combo.findText(el.font_family)
        if idx >= 0:
            self._font_combo.setCurrentIndex(idx)
        self._font_combo.currentTextChanged.connect(self._on_font)
        lay.addLayout(_row("Font", self._font_combo))

        self._size_spin = QSpinBox()
        self._size_spin.setRange(10, 300)
        self._size_spin.setValue(el.font_size)
        self._size_spin.valueChanged.connect(self._on_size)
        lay.addLayout(_row("Size", self._size_spin))

        chk_row = QHBoxLayout()
        self._bold_chk = QCheckBox("Bold")
        self._bold_chk.setChecked(el.bold)
        self._bold_chk.toggled.connect(self._on_bold)
        self._italic_chk = QCheckBox("Italic")
        self._italic_chk.setChecked(el.italic)
        self._italic_chk.toggled.connect(self._on_italic)
        chk_row.addWidget(self._bold_chk)
        chk_row.addWidget(self._italic_chk)
        chk_row.addStretch()
        lay.addLayout(chk_row)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Colour"))
        self._color_btn = color_button(el.color, self._on_color)
        color_row.addWidget(self._color_btn)
        color_row.addStretch()
        lay.addLayout(color_row)

        # Position
        self._x_spin = _make_double_spin(el.x, self._on_x)
        self._y_spin = _make_double_spin(el.y, self._on_y)
        lay.addLayout(_row("X (0-1)", self._x_spin))
        lay.addLayout(_row("Y (0-1)", self._y_spin))

    def _on_text(self, v): self.el.text = v; self.changed.emit()
    def _on_font(self, v): self.el.font_family = v; self.changed.emit()
    def _on_size(self, v): self.el.font_size = v; self.changed.emit()
    def _on_bold(self, v): self.el.bold = v; self.changed.emit()
    def _on_italic(self, v): self.el.italic = v; self.changed.emit()
    def _on_color(self, v): self.el.color = v; self.changed.emit()
    def _on_x(self, v): self.el.x = v; self.changed.emit()
    def _on_y(self, v): self.el.y = v; self.changed.emit()


# ──────────────────────────────────────────────────────────────
class SoundwavePanel(QGroupBox):
    changed = Signal()

    def __init__(self, sw, parent=None):
        super().__init__("Soundwave", parent)
        self.sw = sw
        lay = QVBoxLayout(self)

        # Style
        self._style = QComboBox()
        self._style.addItems([
            "bars",          # podcast style: active bars + dashed line
            "mirror",        # symmetric bars above & below center
            "line",          # simple connected line
            "smooth",        # bezier curved line
            "filled",        # filled area under line
            "filled mirror", # filled symmetric shape
            "dots",          # dot per bar (mirrored)
            "blocks",        # bars anchored to bottom
            "outline bars",  # hollow bar outlines
            "heartbeat",     # ECG spike style
            "circle",        # radial / circular
        ])
        self._style.setCurrentText(sw.style)
        self._style.currentTextChanged.connect(self._on_style)
        lay.addLayout(_row("Style", self._style))

        # Color
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Colour"))
        self._color_btn = color_button(sw.color, self._on_color)
        color_row.addWidget(self._color_btn)
        color_row.addStretch()
        lay.addLayout(color_row)

        # Bar count
        self._bars_spin = QSpinBox()
        self._bars_spin.setRange(10, 120)
        self._bars_spin.setValue(sw.bar_count)
        self._bars_spin.valueChanged.connect(self._on_bars)
        lay.addLayout(_row("Bar count", self._bars_spin))

        # Position & size
        self._x = _make_double_spin(sw.x, self._on_x)
        self._y = _make_double_spin(sw.y, self._on_y)
        self._w = _make_double_spin(sw.width, self._on_w)
        self._h = _make_double_spin(sw.height, self._on_h)
        lay.addLayout(_row("X (0-1)", self._x))
        lay.addLayout(_row("Y (0-1)", self._y))
        lay.addLayout(_row("Width", self._w))
        lay.addLayout(_row("Height", self._h))

    def _on_style(self, v): self.sw.style = v; self.changed.emit()
    def _on_color(self, v): self.sw.color = v; self.changed.emit()
    def _on_bars(self, v): self.sw.bar_count = v; self.changed.emit()
    def _on_x(self, v): self.sw.x = v; self.changed.emit()
    def _on_y(self, v): self.sw.y = v; self.changed.emit()
    def _on_w(self, v): self.sw.width = v; self.changed.emit()
    def _on_h(self, v): self.sw.height = v; self.changed.emit()


# ──────────────────────────────────────────────────────────────
class ImagesPanel(QGroupBox):
    changed = Signal()

    def __init__(self, config, parent=None):
        super().__init__("Images", parent)
        self.config = config
        lay = QVBoxLayout(self)

        self._list = QListWidget()
        self._list.setMaximumHeight(120)
        self._list.currentRowChanged.connect(self._on_select)
        lay.addWidget(self._list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Image")
        add_btn.clicked.connect(self._add_image)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_image)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        lay.addLayout(btn_row)

        self._detail = QWidget()
        detail_lay = QVBoxLayout(self._detail)
        self._x = _make_double_spin(0.8, self._on_x)
        self._y = _make_double_spin(0.6, self._on_y)
        self._w = _make_double_spin(0.17, self._on_w)
        self._h = _make_double_spin(0.35, self._on_h)
        self._op = _make_double_spin(1.0, self._on_opacity)
        detail_lay.addLayout(_row("X (0-1)", self._x))
        detail_lay.addLayout(_row("Y (0-1)", self._y))
        detail_lay.addLayout(_row("Width", self._w))
        detail_lay.addLayout(_row("Height", self._h))
        detail_lay.addLayout(_row("Opacity", self._op))
        self._detail.setVisible(False)
        lay.addWidget(self._detail)

        self._selected = -1
        self._refresh_list()

    def _refresh_list(self):
        self._list.clear()
        for img in self.config.images:
            from pathlib import Path
            self._list.addItem(Path(img.path).name if img.path else "(no file)")

    def _on_select(self, row):
        self._selected = row
        if 0 <= row < len(self.config.images):
            el = self.config.images[row]
            self._x.setValue(el.x)
            self._y.setValue(el.y)
            self._w.setValue(el.width)
            self._h.setValue(el.height)
            self._op.setValue(el.opacity)
            self._detail.setVisible(True)
        else:
            self._detail.setVisible(False)

    def _add_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.svg *.webp)")
        if not path:
            return
        from core.models import ImageElement
        el = ImageElement(path=path)
        self.config.images.append(el)
        self._refresh_list()
        self._list.setCurrentRow(len(self.config.images) - 1)
        self.changed.emit()

    def _remove_image(self):
        r = self._list.currentRow()
        if 0 <= r < len(self.config.images):
            del self.config.images[r]
            self._refresh_list()
            self._detail.setVisible(False)
            self.changed.emit()

    def _current_el(self):
        r = self._selected
        if 0 <= r < len(self.config.images):
            return self.config.images[r]
        return None

    def _on_x(self, v):
        el = self._current_el()
        if el: el.x = v; self.changed.emit()
    def _on_y(self, v):
        el = self._current_el()
        if el: el.y = v; self.changed.emit()
    def _on_w(self, v):
        el = self._current_el()
        if el: el.width = v; self.changed.emit()
    def _on_h(self, v):
        el = self._current_el()
        if el: el.height = v; self.changed.emit()
    def _on_opacity(self, v):
        el = self._current_el()
        if el: el.opacity = v; self.changed.emit()


# ──────────────────────────────────────────────────────────────
class AudioPanel(QGroupBox):
    changed = Signal()

    def __init__(self, config, parent=None):
        super().__init__("Audio", parent)
        self.config = config
        lay = QVBoxLayout(self)

        self._path_label = QLabel(config.audio_path or "(no audio)")
        self._path_label.setWordWrap(True)
        lay.addWidget(self._path_label)

        btn = QPushButton("Browse Audio…")
        btn.clicked.connect(self._browse)
        lay.addWidget(btn)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio", "",
            "Audio (*.mp3 *.wav *.ogg *.flac *.aac *.m4a)")
        if path:
            self.config.audio_path = path
            self._path_label.setText(path)
            self.changed.emit()


# ──────────────────────────────────────────────────────────────
def _make_double_spin(value: float, callback) -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(0.0, 1.0)
    sp.setSingleStep(0.01)
    sp.setDecimals(3)
    sp.setValue(value)
    sp.valueChanged.connect(callback)
    return sp
