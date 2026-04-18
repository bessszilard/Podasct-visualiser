"""Live preview canvas widget"""
import numpy as np
from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import (QPainter, QColor, QFont, QFontMetrics,
                            QPen, QBrush, QImage, QPixmap)
from pathlib import Path


class PreviewCanvas(QWidget):
    """Renders a scaled-down live preview of the banner."""

    TARGET_W = 1920
    TARGET_H = 1080

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._bar_heights = np.zeros(config.soundwave.bar_count)
        self._anim_phase = 0.0   # for idle animation
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._tick_idle)
        self._idle_timer.start(50)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(640, 360)

    def set_bar_heights(self, bars: np.ndarray):
        self._bar_heights = bars
        self.update()

    def _tick_idle(self):
        """Animate soundwave when no audio is playing"""
        self._anim_phase += 0.12
        n = self.config.soundwave.bar_count
        t = self._anim_phase
        bars = np.abs(np.sin(np.linspace(0, np.pi * 2, n) + t)) * 0.6 + 0.05
        # Only a portion active (left side like in reference)
        active = int(n * 0.35)
        bars[active:] = 0.04
        self._bar_heights = bars
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Scale to fit widget keeping 16:9 aspect ratio
        w = self.width()
        h = self.height()
        scale = min(w / self.TARGET_W, h / self.TARGET_H)
        canvas_w = int(self.TARGET_W * scale)
        canvas_h = int(self.TARGET_H * scale)
        ox = (w - canvas_w) // 2
        oy = (h - canvas_h) // 2

        painter.translate(ox, oy)
        painter.scale(scale, scale)

        cfg = self.config
        # Background
        painter.fillRect(0, 0, self.TARGET_W, self.TARGET_H,
                         QColor(cfg.background_color))

        # Title
        self._paint_text(painter, cfg.title)

        # Subtitle
        self._paint_text(painter, cfg.subtitle)

        # Images
        for img_el in cfg.images:
            self._paint_image(painter, img_el)

        # Soundwave
        self._paint_soundwave(painter, cfg.soundwave, self._bar_heights)

        painter.end()

    def _paint_text(self, painter: QPainter, el):
        if not el.text.strip():
            return
        font = QFont(el.font_family, el.font_size)
        font.setBold(el.bold)
        font.setItalic(el.italic)
        painter.setFont(font)
        painter.setPen(QColor(el.color))

        x = int(el.x * self.TARGET_W)
        y = int(el.y * self.TARGET_H)
        max_w = int(el.width * self.TARGET_W)
        max_h = int(el.height * self.TARGET_H)

        fm = QFontMetrics(font)
        words = el.text.split()
        lines = []
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            if fm.horizontalAdvance(test) <= max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        cy = y
        for line in lines:
            painter.drawText(x, cy + fm.ascent(), line)
            cy += fm.height() + int(el.font_size * 0.1)

    def _paint_image(self, painter: QPainter, el):
        if not el.path or not Path(el.path).exists():
            return
        px = int(el.x * self.TARGET_W)
        py = int(el.y * self.TARGET_H)
        pw = int(el.width * self.TARGET_W)
        ph = int(el.height * self.TARGET_H)
        pixmap = QPixmap(el.path)
        if pixmap.isNull():
            return
        pixmap = pixmap.scaled(pw, ph, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.setOpacity(el.opacity)
        painter.drawPixmap(px, py, pixmap)
        painter.setOpacity(1.0)

    def _paint_soundwave(self, painter: QPainter, sw, bar_heights):
        x0 = int(sw.x * self.TARGET_W)
        y0 = int(sw.y * self.TARGET_H)
        sw_w = int(sw.width * self.TARGET_W)
        sw_h = int(sw.height * self.TARGET_H)
        cx_y = y0 + sw_h // 2
        color = QColor(sw.color)
        n = len(bar_heights)
        if n == 0:
            return

        from PySide6.QtGui import QPainterPath, QPolygonF

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))

        def bar_metrics():
            bw = max(2, sw_w // n - 2)
            gp = max(1, (sw_w - bw * n) // max(1, n - 1))
            return bw, gp

        def qpt(i, h, offset=0.45):
            bx = x0 + int(i / max(1, n - 1) * sw_w)
            by = cx_y - int(h * sw_h * offset)
            return QPointF(bx, by)

        def draw_line_path(pts, width=4):
            if len(pts) < 2:
                return
            pen = QPen(color, width)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            path = QPainterPath()
            path.moveTo(pts[0])
            for p in pts[1:]:
                path.lineTo(p)
            painter.drawPath(path)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))

        style = sw.style

        if style == "bars":
            bar_w, gap = bar_metrics()
            for i, h in enumerate(bar_heights):
                bh = max(2, int(h * sw_h * 0.9))
                bx = x0 + i * (bar_w + gap)
                painter.drawRect(bx, cx_y - bh // 2, bar_w, bh)
            # dashed continuation
            pen = QPen(color, 3, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(x0 + n * (bar_w + gap), cx_y, x0 + sw_w, cx_y)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))

        elif style == "mirror":
            bar_w, gap = bar_metrics()
            for i, h in enumerate(bar_heights):
                bh = max(2, int(h * sw_h * 0.45))
                bx = x0 + i * (bar_w + gap)
                painter.drawRect(bx, cx_y - bh, bar_w, bh)
                painter.drawRect(bx, cx_y, bar_w, bh)

        elif style == "line":
            draw_line_path([qpt(i, h) for i, h in enumerate(bar_heights)], 4)

        elif style == "smooth":
            raw = [qpt(i, h) for i, h in enumerate(bar_heights)]
            if len(raw) > 2:
                path = QPainterPath()
                path.moveTo(raw[0])
                for i in range(len(raw) - 1):
                    p1, p2 = raw[i], raw[i + 1]
                    cx = (p1.x() + p2.x()) / 2
                    path.cubicTo(QPointF(cx, p1.y()), QPointF(cx, p2.y()), p2)
                pen = QPen(color, 4)
                pen.setCapStyle(Qt.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(path)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(color))

        elif style == "filled":
            pts = [qpt(i, h) for i, h in enumerate(bar_heights)]
            poly = pts + [QPointF(x0 + sw_w, cx_y), QPointF(x0, cx_y)]
            painter.drawPolygon(QPolygonF(poly))

        elif style == "filled mirror":
            pts_top = [qpt(i, h, 0.45) for i, h in enumerate(bar_heights)]
            pts_bot = [qpt(i, h, -0.45) for i, h in enumerate(bar_heights)]
            poly = pts_top + list(reversed(pts_bot))
            painter.drawPolygon(QPolygonF(poly))

        elif style == "dots":
            r = max(3, sw_h // 20)
            for i, h in enumerate(bar_heights):
                p = qpt(i, h)
                painter.drawEllipse(p, r, r)
                p2 = QPointF(p.x(), cx_y + (cx_y - p.y()))
                painter.drawEllipse(p2, r, r)

        elif style == "blocks":
            bar_w, gap = bar_metrics()
            bottom = y0 + sw_h
            for i, h in enumerate(bar_heights):
                bh = max(2, int(h * sw_h * 0.95))
                bx = x0 + i * (bar_w + gap)
                painter.drawRect(bx, bottom - bh, bar_w, bh)

        elif style == "outline bars":
            bar_w, gap = bar_metrics()
            t = max(2, bar_w // 4)
            for i, h in enumerate(bar_heights):
                bh = max(4, int(h * sw_h * 0.9))
                bx = x0 + i * (bar_w + gap)
                top = cx_y - bh // 2
                bot = cx_y + bh // 2
                painter.drawRect(bx, top, bar_w, t)           # top cap
                painter.drawRect(bx, bot - t, bar_w, t)       # bottom cap
                painter.drawRect(bx, top, t, bh)              # left edge
                painter.drawRect(bx + bar_w - t, top, t, bh)  # right edge

        elif style == "heartbeat":
            pts = []
            for i, h in enumerate(bar_heights):
                bx = x0 + int(i / max(1, n - 1) * sw_w)
                if h > 0.3:
                    pts += [QPointF(bx - 4, cx_y),
                            QPointF(bx, cx_y - h * sw_h * 0.85),
                            QPointF(bx + 4, cx_y + h * sw_h * 0.25),
                            QPointF(bx + 8, cx_y)]
                else:
                    pts.append(QPointF(bx, cx_y))
            draw_line_path(pts, 3)

        elif style == "circle":
            import math
            cx = x0 + sw_w // 2
            cy = cx_y
            base_r = min(sw_w, sw_h) // 2 - 10
            lw = max(2, sw_w // (n * 2))
            pen = QPen(color, lw)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            for i, h in enumerate(bar_heights):
                angle = (i / n) * 2 * math.pi - math.pi / 2
                r_inner = base_r
                r_outer = base_r + int(h * sw_h * 0.4)
                x1 = cx + r_inner * math.cos(angle)
                y1 = cy + r_inner * math.sin(angle)
                x2 = cx + r_outer * math.cos(angle)
                y2 = cy + r_outer * math.sin(angle)
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
