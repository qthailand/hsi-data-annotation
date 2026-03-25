import time
from collections import deque

import numpy as np
from PyQt5.QtCore import QObject, QPointF, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PyQt5.QtWidgets import QGraphicsPixmapItem

from .data import DEFAULT_HIGH_CUT, DEFAULT_LOW_CUT, build_rgb_preview, load_datacube_preview


class CanvasSignals(QObject):
    updated = pyqtSignal()
    spectrum_ready = pyqtSignal(int, int, object)
    loaded = pyqtSignal(int, int, int)


class BgItem(QGraphicsPixmapItem):
    def __init__(self):
        super().__init__()
        self.setZValue(0)
        self.setAcceptHoverEvents(False)

    def mousePressEvent(self, event):
        event.ignore()

    def mouseMoveEvent(self, event):
        event.ignore()

    def mouseReleaseEvent(self, event):
        event.ignore()


class CanvasItem(QGraphicsPixmapItem):
    def __init__(self):
        super().__init__()
        self.signals = CanvasSignals()
        self._datacube = None
        self._is_loaded = False
        self._drawing = False
        self._last_pos = QPointF()
        self._connect_start = None
        self._connect_last = None
        self._connect_points = []
        self._last_spectrum_emit = 0.0
        self._spectrum_interval_s = 0.06
        self._pen_color = QColor(231, 76, 60, 220)
        self._pen_width = 4
        self._tool = "pen"
        self._preview_low_cut = DEFAULT_LOW_CUT
        self._preview_high_cut = DEFAULT_HIGH_CUT
        self._preview_info = None
        self._init_mask(800, 600)
        self.setZValue(1)
        self.setOpacity(0.75)
        self.setShapeMode(QGraphicsPixmapItem.BoundingRectShape)

    @property
    def datacube(self):
        return self._datacube

    @property
    def is_loaded(self):
        return self._is_loaded

    @property
    def is_drawing(self):
        return self._drawing

    @property
    def preview_info(self):
        return self._preview_info

    @property
    def preview_low_cut(self):
        return self._preview_low_cut

    @property
    def preview_high_cut(self):
        return self._preview_high_cut

    def _init_mask(self, width, height):
        self._mask = QImage(width, height, QImage.Format_ARGB32)
        self._mask.fill(0)
        self.setPixmap(QPixmap.fromImage(self._mask))

    def set_tool(self, tool_name):
        self._tool = tool_name
        if tool_name != "connect":
            self._connect_start = None
            self._connect_last = None
            self._connect_points = []

    def set_pen_color(self, color):
        self._pen_color = color

    def set_pen_width(self, width):
        self._pen_width = width

    def set_preview_cuts(self, low_cut, high_cut):
        self._preview_low_cut = float(low_cut)
        self._preview_high_cut = float(high_cut)

    def get_mask(self):
        return self._mask

    def clear_mask(self):
        self._mask.fill(0)
        self.setPixmap(QPixmap.fromImage(self._mask))
        self.signals.updated.emit()

    def load_datacube(self, path):
        self._datacube, rgb_img, self._preview_info = load_datacube_preview(
            path,
            low_cut=self._preview_low_cut,
            high_cut=self._preview_high_cut,
        )
        self._init_mask(rgb_img.width(), rgb_img.height())
        self._is_loaded = True
        self.signals.loaded.emit(rgb_img.width(), rgb_img.height(), self._datacube.nbands)
        return rgb_img

    def render_preview(self, low_cut=None, high_cut=None):
        if self._datacube is None:
            return None
        if low_cut is not None:
            self._preview_low_cut = float(low_cut)
        if high_cut is not None:
            self._preview_high_cut = float(high_cut)
        rgb, self._preview_info = build_rgb_preview(
            self._datacube,
            low_cut=self._preview_low_cut,
            high_cut=self._preview_high_cut,
        )
        rgb8 = np.ascontiguousarray((rgb * 255).clip(0, 255).astype(np.uint8))
        height, width, _ = rgb8.shape
        return QImage(
            rgb8.data, width, height, width * 3, QImage.Format_RGB888
        ).convertToFormat(QImage.Format_ARGB32).copy()

    def _emit_spectrum(self, pos, force=False):
        if self._datacube is None:
            return
        now = time.perf_counter()
        if not force and (now - self._last_spectrum_emit) < self._spectrum_interval_s:
            return
        x, y = int(pos.x()), int(pos.y())
        if 0 <= x < self._datacube.ncols and 0 <= y < self._datacube.nrows:
            spec = np.array(self._datacube[y, x, :], dtype=np.float32).flatten()
            self._last_spectrum_emit = now
            self.signals.spectrum_ready.emit(x, y, spec)

    def mousePressEvent(self, event):
        if not self._is_loaded:
            return
        if event.button() == Qt.LeftButton:
            if self._tool == "fill":
                self.flood_fill(event.pos())
            elif self._tool == "connect":
                self._connect_click(event.pos())
                self._emit_spectrum(event.pos(), force=True)
            else:
                self._drawing = True
                self._last_pos = event.pos()
                self._draw_dot(event.pos())
                self._emit_spectrum(event.pos(), force=True)
        elif event.button() == Qt.RightButton and self._tool == "connect":
            self._close_connect_path()

    def mouseMoveEvent(self, event):
        if not self._is_loaded or self._tool in ("fill", "connect"):
            return
        if self._drawing and (event.buttons() & Qt.LeftButton):
            self._draw_line(self._last_pos, event.pos())
            self._last_pos = event.pos()
            self._emit_spectrum(event.pos())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._tool in ("pen", "eraser"):
            self._drawing = False
            self.signals.updated.emit()

    def _make_pen(self):
        if self._tool == "eraser":
            return QPen(
                Qt.transparent,
                self._pen_width * 3,
                Qt.SolidLine,
                Qt.RoundCap,
                Qt.RoundJoin,
            )
        color = QColor(self._pen_color)
        color.setAlpha(220)
        return QPen(
            color,
            self._pen_width,
            Qt.SolidLine,
            Qt.RoundCap,
            Qt.RoundJoin,
        )

    def _paint_on_mask(self, painter_fn):
        painter = QPainter(self._mask)
        if self._tool == "eraser":
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self._make_pen())
        painter_fn(painter)
        painter.end()
        self.setPixmap(QPixmap.fromImage(self._mask))

    def _draw_dot(self, pos):
        self._paint_on_mask(lambda painter: painter.drawPoint(pos))

    def _draw_line(self, p1, p2):
        self._paint_on_mask(lambda painter: painter.drawLine(p1, p2))

    def _connect_click(self, pos):
        if self._connect_last is None:
            self._connect_start = QPointF(pos)
            self._draw_dot(pos)
        else:
            self._draw_line(self._connect_last, pos)
        self._connect_last = QPointF(pos)
        self._connect_points.append(QPointF(pos))
        self.signals.updated.emit()

    def _fill_connect_polygon(self):
        if len(self._connect_points) < 3:
            return

        points = QPolygonF(self._connect_points)

        def fill_polygon(painter):
            color = QColor(self._pen_color)
            color.setAlpha(220)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawPolygon(points)

        self._paint_on_mask(fill_polygon)

    def _close_connect_path(self):
        if self._connect_last is None or self._connect_start is None:
            return
        if self._connect_last != self._connect_start:
            self._draw_line(self._connect_last, self._connect_start)
        self._fill_connect_polygon()
        self._connect_start = None
        self._connect_last = None
        self._connect_points = []
        self.signals.updated.emit()

    def flood_fill(self, pos):
        x0, y0 = int(pos.x()), int(pos.y())
        image = self._mask.convertToFormat(QImage.Format_RGBA8888)
        width, height = image.width(), image.height()
        if not (0 <= x0 < width and 0 <= y0 < height):
            return
        ptr = image.bits()
        ptr.setsize(height * width * 4)
        arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4)).copy()
        target_color = tuple(arr[y0, x0])
        color = self._pen_color
        fill_color = np.array([color.red(), color.green(), color.blue(), 220], dtype=np.uint8)
        if target_color == tuple(fill_color):
            return
        queue = deque([(y0, x0)])
        while queue:
            y, x = queue.popleft()
            if tuple(arr[y, x]) != target_color:
                continue
            arr[y, x] = fill_color
            if x > 0:
                queue.append((y, x - 1))
            if x < width - 1:
                queue.append((y, x + 1))
            if y > 0:
                queue.append((y - 1, x))
            if y < height - 1:
                queue.append((y + 1, x))
        self._mask = QImage(arr.data, width, height, width * 4, QImage.Format_RGBA8888).copy().convertToFormat(QImage.Format_ARGB32)
        self.setPixmap(QPixmap.fromImage(self._mask))
        self.signals.updated.emit()