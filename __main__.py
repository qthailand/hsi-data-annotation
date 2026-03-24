import sys
import time
import numpy as np
import pyqtgraph as pg
from collections import deque

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView,
    QToolBar, QAction, QColorDialog, QLabel,
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGraphicsPixmapItem, QFileDialog, QMessageBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView, QAbstractItemView,
)
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap, QCursor, QImage, QPolygonF
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QObject

pg.setConfigOptions(imageAxisOrder="row-major", antialias=True)
import spectral as spy


# ─────────────────────────────────────────────────────────
#  Signals
# ─────────────────────────────────────────────────────────
class CanvasSignals(QObject):
    updated        = pyqtSignal()
    spectrum_ready = pyqtSignal(int, int, object)   # col, row, ndarray
    loaded         = pyqtSignal(int, int, int)      # ncols, nrows, nbands


# ─────────────────────────────────────────────────────────
#  ClassTable  – หน้าต่างที่ 3: ตารางกำหนด class & สี
# ─────────────────────────────────────────────────────────
class ClassTable(QWidget):
    """ตาราง 2 คอลัมน์: ชื่อคลาส | สี  – emit class_changed เมื่อเปลี่ยน"""
    class_changed = pyqtSignal(str, QColor)

    _DEFAULTS = [
        ("Class 1", QColor(231,  76,  60)),
        ("Class 2", QColor( 46, 204, 113)),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        hdr = QLabel("🏷️  Class Labels")
        hdr.setAlignment(Qt.AlignCenter)
        hdr.setStyleSheet(
            "font-weight:bold; font-size:13px; padding:5px;"
            "background:#2b2b2b; color:#e0e0e0; border-radius:4px;"
        )
        layout.addWidget(hdr)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Class Name", "Color"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self._table.setColumnWidth(1, 80)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setStyleSheet(
            "QTableWidget { background:#1e1e1e; color:#e0e0e0; gridline-color:#333; }"
            "QHeaderView::section { background:#2b2b2b; color:#ccc; padding:4px; }"
            "QTableWidget::item:selected { background:#3a3a5c; }"
        )
        self._table.itemSelectionChanged.connect(self._on_selection)
        layout.addWidget(self._table, stretch=1)

        btns = QHBoxLayout()
        b_add = QPushButton("➕  Add")
        b_del = QPushButton("🗑  Remove")
        b_add.clicked.connect(self._add_row)
        b_del.clicked.connect(self._remove_row)
        btns.addWidget(b_add)
        btns.addWidget(b_del)
        layout.addLayout(btns)

        self._active_lbl = QLabel("—")
        self._active_lbl.setAlignment(Qt.AlignCenter)
        self._active_lbl.setStyleSheet(
            "font-size:12px; padding:4px; border-radius:3px; color:#aaa;"
        )
        layout.addWidget(self._active_lbl)

        for name, color in self._DEFAULTS:
            self._insert_row(name, color)
        self._table.selectRow(0)

    # ── internal ──────────────────────────
    def _insert_row(self, name: str, color: QColor):
        r = self._table.rowCount()
        self._table.insertRow(r)
        item = QTableWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self._table.setItem(r, 0, item)
        btn = QPushButton()
        btn.setFixedHeight(26)
        btn.setStyleSheet(
            f"background:{color.name()}; border:1px solid #555; border-radius:3px;"
        )
        btn.setProperty("_color", color)
        btn.clicked.connect(lambda _, row=r: self._pick_color(row))
        self._table.setCellWidget(r, 1, btn)

    def _pick_color(self, row: int):
        btn = self._table.cellWidget(row, 1)
        if btn is None:
            return
        old = btn.property("_color") or QColor(Qt.red)
        c = QColorDialog.getColor(old, self, "เลือกสีคลาส")
        if c.isValid():
            btn.setStyleSheet(
                f"background:{c.name()}; border:1px solid #555; border-radius:3px;"
            )
            btn.setProperty("_color", c)
            if row == self._table.currentRow():
                self._emit_active()

    def _add_row(self):
        r = self._table.rowCount()
        _, color = self._DEFAULTS[r % len(self._DEFAULTS)]
        self._insert_row(f"Class {r + 1}", color)
        self._table.selectRow(r)

    def _remove_row(self):
        r = self._table.currentRow()
        if r >= 0:
            self._table.removeRow(r)
            nr = self._table.rowCount()
            if nr > 0:
                self._table.selectRow(min(r, nr - 1))

    def _on_selection(self):
        self._emit_active()

    def _emit_active(self):
        r = self._table.currentRow()
        if r < 0:
            return
        name  = (self._table.item(r, 0).text()
                 if self._table.item(r, 0) else f"Class {r+1}")
        btn   = self._table.cellWidget(r, 1)
        color = btn.property("_color") if btn else QColor(Qt.red)
        fg = "#000" if color.lightness() > 128 else "#fff"
        self._active_lbl.setText(f"Active: <b>{name}</b>")
        self._active_lbl.setStyleSheet(
            f"font-size:12px; font-weight:bold; padding:4px; border-radius:3px;"
            f"background:{color.name()}; color:{fg};"
        )
        self.class_changed.emit(name, color)

    # ── public API ───────────────────────
    def active_color(self) -> QColor:
        r = self._table.currentRow()
        if r < 0:
            return QColor(Qt.red)
        btn = self._table.cellWidget(r, 1)
        return btn.property("_color") if btn else QColor(Qt.red)

    def active_name(self) -> str:
        r = self._table.currentRow()
        if r < 0:
            return "Unknown"
        item = self._table.item(r, 0)
        return item.text() if item else f"Class {r+1}"

    def get_all(self) -> list:
        result = []
        for r in range(self._table.rowCount()):
            name  = (self._table.item(r, 0).text()
                     if self._table.item(r, 0) else f"Class {r+1}")
            btn   = self._table.cellWidget(r, 1)
            color = btn.property("_color") if btn else QColor(Qt.red)
            result.append((name, color))
        return result


# ─────────────────────────────────────────────────────────
#  BgItem  – เลเยอร์ RGB reference (ไม่รับ mouse events)
# ─────────────────────────────────────────────────────────
class BgItem(QGraphicsPixmapItem):
    def __init__(self):
        super().__init__()
        self.setZValue(0)
        self.setAcceptHoverEvents(False)

    def mousePressEvent(self, e):   e.ignore()
    def mouseMoveEvent(self, e):    e.ignore()
    def mouseReleaseEvent(self, e): e.ignore()


# ─────────────────────────────────────────────────────────
#  CanvasItem  – เลเยอร์วาด Ground Truth (แยกจาก BG)
# ─────────────────────────────────────────────────────────
class CanvasItem(QGraphicsPixmapItem):
    def __init__(self):
        super().__init__()
        self.signals    = CanvasSignals()
        self._datacube  = None
        self._is_loaded = False
        self._drawing   = False
        self._last_pos  = QPointF()
        self._connect_start = None
        self._connect_last = None
        self._connect_points = []
        self._last_spectrum_emit = 0.0
        self._spectrum_interval_s = 0.06
        self._pen_color = QColor(231, 76, 60, 220)
        self._pen_width = 4
        self._tool      = "pen"   # "pen" | "eraser" | "fill" | "connect"
        self._init_mask(800, 600)
        self.setZValue(1)
        self.setOpacity(0.75)
        # ให้รับ mouse events ทั้งกรอบ แม้บริเวณที่ยังโปร่งใสอยู่
        self.setShapeMode(QGraphicsPixmapItem.BoundingRectShape)

    def _init_mask(self, w: int, h: int):
        self._mask = QImage(w, h, QImage.Format_ARGB32)
        self._mask.fill(Qt.transparent)
        self.setPixmap(QPixmap.fromImage(self._mask))

    # ── properties ───────────────────────
    def set_tool(self, t: str):
        self._tool = t
        if t != "connect":
            self._connect_start = None
            self._connect_last = None
            self._connect_points = []
    def set_pen_color(self, c: QColor): self._pen_color = c
    def set_pen_width(self, w: int):    self._pen_width = w
    def get_mask(self) -> QImage:       return self._mask

    def clear_mask(self):
        self._mask.fill(Qt.transparent)
        self.setPixmap(QPixmap.fromImage(self._mask))
        self.signals.updated.emit()

    def load_datacube(self, path: str) -> QImage:
        im   = spy.open_image(path)
        self._datacube = im          # lazy file handle – ไม่โหลดทั้งไฟล์
        rgb  = spy.get_rgb(im, bands=[29, 19, 9])
        rgb8 = np.ascontiguousarray((rgb * 255).clip(0, 255).astype(np.uint8))
        h, w, _ = rgb8.shape
        qimg = QImage(rgb8.data, w, h, w * 3, QImage.Format_RGB888)
        self._init_mask(w, h)
        self._is_loaded = True
        self.signals.loaded.emit(w, h, im.nbands)
        return qimg.convertToFormat(QImage.Format_ARGB32).copy()

    # ── spectrum helper ───────────────────
    def _emit_spectrum(self, pos: QPointF, force: bool = False):
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

    # ── mouse events ──────────────────────
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
                self._drawing  = True
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

    # ── drawing ───────────────────────────
    def _make_pen(self) -> QPen:
        if self._tool == "eraser":
            return QPen(Qt.transparent, self._pen_width * 3,
                        Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        c = QColor(self._pen_color); c.setAlpha(220)
        return QPen(c, self._pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    def _paint_on_mask(self, fn):
        p = QPainter(self._mask)
        if self._tool == "eraser":
            p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(self._make_pen())
        fn(p)
        p.end()
        self.setPixmap(QPixmap.fromImage(self._mask))

    def _draw_dot(self, pos):
        self._paint_on_mask(lambda p: p.drawPoint(pos))

    def _draw_line(self, p1, p2):
        self._paint_on_mask(lambda p: p.drawLine(p1, p2))

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

        def _fill(p: QPainter):
            c = QColor(self._pen_color)
            c.setAlpha(220)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawPolygon(points)

        self._paint_on_mask(_fill)

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

    def flood_fill(self, pos: QPointF):
        x0, y0 = int(pos.x()), int(pos.y())
        img = self._mask.convertToFormat(QImage.Format_RGBA8888)
        w, h = img.width(), img.height()
        if not (0 <= x0 < w and 0 <= y0 < h):
            return
        ptr = img.bits(); ptr.setsize(h * w * 4)
        arr = np.frombuffer(ptr, np.uint8).reshape((h, w, 4)).copy()
        tc  = tuple(arr[y0, x0])
        c   = self._pen_color
        fill = np.array([c.red(), c.green(), c.blue(), 220], dtype=np.uint8)
        if tc == tuple(fill):
            return
        q = deque([(y0, x0)])
        while q:
            y, x = q.popleft()
            if tuple(arr[y, x]) != tc:
                continue
            arr[y, x] = fill
            if x > 0:    q.append((y,     x - 1))
            if x < w-1:  q.append((y,     x + 1))
            if y > 0:    q.append((y - 1, x    ))
            if y < h-1:  q.append((y + 1, x    ))
        self._mask = QImage(arr.data, w, h, w*4,
                            QImage.Format_RGBA8888).copy().convertToFormat(
                            QImage.Format_ARGB32)
        self.setPixmap(QPixmap.fromImage(self._mask))
        self.signals.updated.emit()


# ─────────────────────────────────────────────────────────
#  PgPanel  – หน้าต่างที่ 2: PyQtGraph (Mask + Spectrum)
# ─────────────────────────────────────────────────────────
class PgPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._first = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        hdr = QLabel("📊  PyQtGraph – GT Mask & Spectrum")
        hdr.setAlignment(Qt.AlignCenter)
        hdr.setStyleSheet(
            "font-weight:bold; font-size:13px; padding:5px;"
            "background:#2b2b2b; color:#e0e0e0; border-radius:4px;"
        )
        layout.addWidget(hdr)

        self._img_view = pg.ImageView()
        self._img_view.ui.roiBtn.hide()
        self._img_view.ui.menuBtn.hide()
        self._img_view.ui.roiPlot.hide()
        layout.addWidget(self._img_view, stretch=3)

        spec_lbl = QLabel("📈  Spectrum at Cursor")
        spec_lbl.setAlignment(Qt.AlignCenter)
        spec_lbl.setStyleSheet(
            "font-weight:bold; color:#ccc; background:#2b2b2b;"
            "padding:3px; border-radius:3px;"
        )
        layout.addWidget(spec_lbl)

        self._spec_plot = pg.PlotWidget()
        self._spec_plot.setBackground("#1e1e1e")
        self._spec_plot.setLabel("left",   "Reflectance")
        self._spec_plot.setLabel("bottom", "Band index")
        self._spec_plot.showGrid(x=True, y=True, alpha=0.25)
        self._spec_plot.addLegend(offset=(10, 10))
        # เส้น at-cursor – สีขาว
        self._spec_curve = self._spec_plot.plot(
            [], [], pen=pg.mkPen((255, 255, 255), width=1.5), name="At cursor")
        # เส้น average by class – เก็บใน dict {name: PlotDataItem}
        self._class_curves: dict = {}
        layout.addWidget(self._spec_plot, stretch=2)

        self._spec_lbl = QLabel("คลิกบน canvas เพื่อดู spectrum")
        self._spec_lbl.setAlignment(Qt.AlignCenter)
        self._spec_lbl.setStyleSheet("font-size:10px; color:#888; padding:2px;")
        layout.addWidget(self._spec_lbl)

    def update_from_mask(self, mask: QImage):
        arr = self._to_np(mask)
        self._img_view.setImage(
            arr[:, :, :3],
            autoRange=self._first, autoLevels=self._first,
            autoHistogramRange=self._first,
        )
        self._first = False

    def update_spectrum(self, x: int, y: int, arr: np.ndarray):
        self._spec_curve.setData(np.arange(len(arr), dtype=float), arr.astype(float))
        self._spec_lbl.setText(
            f"cursor: col={x}  row={y}  bands={len(arr)}  mean={arr.mean():.4f}"
        )

    def update_class_spectra(self, class_data: list):
        """class_data: [(name, QColor, avg_ndarray_or_None), ...]"""
        # ลบเส้นเก่าออก
        for curve in self._class_curves.values():
            self._spec_plot.removeItem(curve)
        self._class_curves.clear()

        for name, color, avg in class_data:
            if avg is None:
                continue
            r, g, b = color.red(), color.green(), color.blue()
            curve = self._spec_plot.plot(
                np.arange(len(avg), dtype=float),
                avg.astype(float),
                pen=pg.mkPen((r, g, b), width=2.2),
                name=name,
            )
            self._class_curves[name] = curve

        # Update title summary
        parts = [f"<span style='color:#{c.red():02x}{c.green():02x}{c.blue():02x}'>"
                 f"{n}: n/a" if avg is None
                 else f"<span style='color:#{c.red():02x}{c.green():02x}{c.blue():02x}'>{n}</span>"
                 for n, c, avg in class_data if avg is not None]
        self._spec_plot.setTitle("  ".join(parts) if parts else "")

    @staticmethod
    def _to_np(img: QImage) -> np.ndarray:
        img = img.convertToFormat(QImage.Format_RGBA8888)
        w, h = img.width(), img.height()
        ptr = img.bits(); ptr.setsize(h * w * 4)
        return np.frombuffer(ptr, np.uint8).reshape((h, w, 4)).copy()


# ─────────────────────────────────────────────────────────
#  PaintView  – หน้าต่างที่ 1: วาด (Ctrl+Wheel Zoom)
# ─────────────────────────────────────────────────────────
class PaintView(QGraphicsView):
    ZI, ZO = 1.15, 1/1.15
    ZMIN, ZMAX = 0.05, 50.0

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self._zoom = 1.0
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setBackgroundBrush(QColor("#404040"))

    def zoom_in(self):    self._apply(self.ZI)
    def zoom_out(self):   self._apply(self.ZO)

    def zoom_reset(self):
        self.resetTransform(); self._zoom = 1.0; self._notify()

    def _apply(self, f):
        nz = self._zoom * f
        if self.ZMIN <= nz <= self.ZMAX:
            self._zoom = nz; self.scale(f, f); self._notify()

    def _notify(self):
        mw = self.window()
        if hasattr(mw, "update_zoom_label"):
            mw.update_zoom_label(self._zoom)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.zoom_in() if e.angleDelta().y() > 0 else self.zoom_out()
        else:
            super().wheelEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            fake = e.__class__(e.type(), e.pos(), Qt.LeftButton,
                               Qt.LeftButton, e.modifiers())
            super().mousePressEvent(fake)
        else:
            super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.NoDrag)
        else:
            super().mouseReleaseEvent(e)


# ─────────────────────────────────────────────────────────
#  Main Window  – 3-panel layout
#  ┌──────────────┬──────────────┬──────────────┐
#  │  PaintView   │   PgPanel    │  ClassTable  │
#  │  (วาด GT)   │  (pyqtgraph) │  (class/สี)  │
#  └──────────────┴──────────────┴──────────────┘
# ─────────────────────────────────────────────────────────
class PaintWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HSI Ground Truth Painter")
        self.resize(1800, 900)

        # Scene: BG layer + GT mask layer
        self._scene  = QGraphicsScene(self)
        self._bg     = BgItem()
        self._canvas = CanvasItem()
        self._scene.addItem(self._bg)
        self._scene.addItem(self._canvas)
        self._scene.setSceneRect(QRectF(0, 0, 800, 600))

        # 3 panels
        self._view        = PaintView(self._scene, self)
        self._pg_panel    = PgPanel(self)
        self._class_table = ClassTable(self)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._view)
        splitter.addWidget(self._pg_panel)
        splitter.addWidget(self._class_table)
        splitter.setSizes([860, 560, 300])
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(5)
        self.setCentralWidget(splitter)

        self._build_toolbar()
        self._build_statusbar()

        # Signals
        self._canvas.signals.updated.connect(self._refresh_pg)
        self._canvas.signals.spectrum_ready.connect(self._pg_panel.update_spectrum)
        self._canvas.signals.loaded.connect(self._on_loaded)
        self._class_table.class_changed.connect(self._on_class_changed)

    # ── Callbacks ─────────────────────────
    def _on_loaded(self, ncols: int, nrows: int, nbands: int):
        self.statusBar().showMessage(
            f"✅  Datacube โหลดสำเร็จ  │  {ncols}×{nrows} px  │  {nbands} bands"
            f"  │  Ctrl+Wheel=Zoom  │  F=ถังสี  │  L=ต่อจุด  │  Ctrl+S=บันทึก GT", 0)
        for a in self._tool_actions.values():
            a.setEnabled(True)

    def _on_class_changed(self, name: str, color: QColor):
        c = QColor(color); c.setAlpha(220)
        self._canvas.set_pen_color(c)
        self._color_preview.setStyleSheet(
            f"background:{color.name()}; border:2px solid #888; border-radius:4px;"
        )
        # สลับกลับเป็น pen ทุกครั้งที่เปลี่ยน class เพื่อป้องกันการ fill โดยไม่ตั้งใจ
        self._set_tool("pen")
        self._compute_class_spectra()

    def _refresh_pg(self):
        self._pg_panel.update_from_mask(self._canvas.get_mask())
        self._compute_class_spectra()

    def _compute_class_spectra(self):
        """คำนวณ average spectrum ต่อ class จาก mask + datacube แล้วส่งไปแสดง"""
        datacube = self._canvas._datacube
        if datacube is None or self._canvas._drawing:
            return
        mask = self._canvas.get_mask().convertToFormat(QImage.Format_RGBA8888)
        w, h = mask.width(), mask.height()
        ptr = mask.bits(); ptr.setsize(h * w * 4)
        mask_arr = np.frombuffer(ptr, np.uint8).reshape((h, w, 4)).copy()

        classes = self._class_table.get_all()
        class_data = []
        MAX_SAMPLES = 300   # จำกัดเพื่อไม่ให้ใช้ RAM มาก
        for name, color in classes:
            r, g, b = color.red(), color.green(), color.blue()
            # tolerance ±3 เพราะ QPainter มี rounding จาก alpha compositing
            match = (
                (np.abs(mask_arr[:, :, 0].astype(int) - r) <= 3) &
                (np.abs(mask_arr[:, :, 1].astype(int) - g) <= 3) &
                (np.abs(mask_arr[:, :, 2].astype(int) - b) <= 3) &
                (mask_arr[:, :, 3] > 0)
            )
            ys, xs = np.where(match)
            if len(ys) == 0:
                class_data.append((name, color, None))
                continue
            # สุ่มจำกัด samples
            if len(ys) > MAX_SAMPLES:
                idx = np.random.choice(len(ys), MAX_SAMPLES, replace=False)
                ys, xs = ys[idx], xs[idx]
            # clamp ให้อยู่ในขอบ datacube
            valid = (xs < datacube.ncols) & (ys < datacube.nrows)
            ys, xs = ys[valid], xs[valid]
            if len(ys) == 0:
                class_data.append((name, color, None))
                continue
            # lazy per-pixel read ผ่าน spectral – ไม่โหลด cube ทั้งหมด
            try:
                spectra = np.array(
                    [np.array(datacube[int(y), int(x), :],
                              dtype=np.float32).flatten()
                     for y, x in zip(ys, xs)]
                )   # (N, B)
                avg = spectra.mean(axis=0)  # (B,)
                class_data.append((name, color, avg))
            except Exception:
                class_data.append((name, color, None))

        self._pg_panel.update_class_spectra(class_data)

    # ── Toolbar ───────────────────────────
    def _build_toolbar(self):
        tb = QToolBar("Tools", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        act_pen = QAction("✏️ ปากกา", self)
        act_pen.setCheckable(True); act_pen.setChecked(True)
        act_pen.triggered.connect(lambda: self._set_tool("pen"))
        tb.addAction(act_pen)

        act_eraser = QAction("🧹 ยางลบ", self)
        act_eraser.setCheckable(True)
        act_eraser.triggered.connect(lambda: self._set_tool("eraser"))
        tb.addAction(act_eraser)

        act_fill = QAction("🪣 ถังสี", self)
        act_fill.setCheckable(True); act_fill.setShortcut("F")
        act_fill.triggered.connect(lambda: self._set_tool("fill"))
        tb.addAction(act_fill)

        act_connect = QAction("🔗 ต่อจุด", self)
        act_connect.setCheckable(True); act_connect.setShortcut("L")
        act_connect.triggered.connect(lambda: self._set_tool("connect"))
        tb.addAction(act_connect)

        self._tool_actions = {
            "pen": act_pen,
            "eraser": act_eraser,
            "fill": act_fill,
            "connect": act_connect,
        }
        tb.addSeparator()

        tb.addWidget(QLabel("  🎨 สีปัจจุบัน:  "))
        self._color_preview = QLabel()
        self._color_preview.setFixedSize(28, 28)
        self._color_preview.setStyleSheet(
            "background:#e74c3c; border:2px solid #888; border-radius:4px;")
        tb.addWidget(self._color_preview)
        tb.addSeparator()

        tb.addWidget(QLabel("  🖌️ ขนาด:  "))
        self._size_spin = QSpinBox()
        self._size_spin.setRange(1, 100); self._size_spin.setValue(4)
        self._size_spin.setFixedWidth(60)
        self._size_spin.valueChanged.connect(self._canvas.set_pen_width)
        tb.addWidget(self._size_spin)

        tb.addWidget(QLabel("  👁 Opacity:  "))
        op_spin = QSpinBox()
        op_spin.setRange(10, 100); op_spin.setValue(75); op_spin.setSuffix(" %")
        op_spin.setFixedWidth(70)
        op_spin.valueChanged.connect(lambda v: self._canvas.setOpacity(v / 100))
        tb.addWidget(op_spin)
        tb.addSeparator()

        tb.addWidget(QLabel("  🔍 Zoom:  "))
        a_zi = QAction("＋", self); a_zi.setShortcut("Ctrl+=")
        a_zi.triggered.connect(self._view.zoom_in); tb.addAction(a_zi)
        a_zo = QAction("－", self); a_zo.setShortcut("Ctrl+-")
        a_zo.triggered.connect(self._view.zoom_out); tb.addAction(a_zo)
        a_z1 = QAction("1:1", self); a_z1.setShortcut("Ctrl+0")
        a_z1.triggered.connect(self._view.zoom_reset); tb.addAction(a_z1)
        a_fit = QAction("⊡ Fit", self); a_fit.setShortcut("Ctrl+F")
        a_fit.triggered.connect(self._fit); tb.addAction(a_fit)
        tb.addSeparator()

        a_open = QAction("📂 เปิด .hdr", self); a_open.setShortcut("Ctrl+O")
        a_open.triggered.connect(self._open); tb.addAction(a_open)
        a_clr = QAction("🗋 ล้าง GT", self); a_clr.setShortcut("Ctrl+N")
        a_clr.triggered.connect(self._clear); tb.addAction(a_clr)
        a_save = QAction("💾 บันทึก GT", self); a_save.setShortcut("Ctrl+S")
        a_save.triggered.connect(self._save); tb.addAction(a_save)

    # ── Statusbar ─────────────────────────
    def _build_statusbar(self):
        self._zoom_label = QLabel("Zoom: 100%")
        self.statusBar().addPermanentWidget(self._zoom_label)
        for a in self._tool_actions.values():
            a.setEnabled(False)
        self.statusBar().showMessage(
            "⚠️  โปรดโหลด Hyperspectral Datacube (.hdr) ก่อน  │  Ctrl+O = เปิดไฟล์")
        self._on_class_changed(
            self._class_table.active_name(), self._class_table.active_color())

    def update_zoom_label(self, z: float):
        self._zoom_label.setText(f"Zoom: {z * 100:.0f}%")

    # ── Action slots ──────────────────────
    def _set_tool(self, t: str):
        self._canvas.set_tool(t)
        for n, a in self._tool_actions.items():
            a.setChecked(n == t)

    def _fit(self):
        self._view.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._view._zoom = self._view.transform().m11()
        self.update_zoom_label(self._view._zoom)

    def _open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "เปิด Hyperspectral Datacube", "", "ENVI Header (*.hdr)")
        if not path:
            return
        self.statusBar().showMessage("⏳  กำลังโหลด datacube…")
        QApplication.processEvents()
        rgb_img = self._canvas.load_datacube(path)
        self._bg.setPixmap(QPixmap.fromImage(rgb_img))
        self._scene.setSceneRect(QRectF(rgb_img.rect()))

    def _clear(self):
        if not self._canvas._is_loaded:
            return
        if QMessageBox.question(self, "ล้าง GT", "ล้าง Ground Truth layer?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._canvas.clear_mask()

    def _save(self):
        if not self._canvas._is_loaded:
            QMessageBox.warning(self, "ยังไม่มีข้อมูล", "โหลด datacube ก่อนบันทึก")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "บันทึก Ground Truth Mask (Class ID)", "gt_mask.png",
            "PNG (*.png);;TIFF (*.tif *.tiff)")
        if not path:
            return

        # แปลง ARGB mask → greyscale class-ID array
        # background (alpha=0)  = 0
        # class 1 = 1, class 2 = 2, …
        mask = self._canvas.get_mask().convertToFormat(QImage.Format_RGBA8888)
        w, h = mask.width(), mask.height()
        ptr = mask.bits(); ptr.setsize(h * w * 4)
        mask_arr = np.frombuffer(ptr, np.uint8).reshape((h, w, 4)).copy()

        id_arr = np.zeros((h, w), dtype=np.uint8)   # 0 = background
        for class_id, (name, color) in enumerate(self._class_table.get_all(), start=1):
            r, g, b = color.red(), color.green(), color.blue()
            match = (
                (np.abs(mask_arr[:, :, 0].astype(int) - r) <= 3) &
                (np.abs(mask_arr[:, :, 1].astype(int) - g) <= 3) &
                (np.abs(mask_arr[:, :, 2].astype(int) - b) <= 3) &
                (mask_arr[:, :, 3] > 0)
            )
            id_arr[match] = class_id

        # บันทึกเป็น greyscale 8-bit ผ่าน QImage
        id_contig = np.ascontiguousarray(id_arr)
        out_img = QImage(id_contig.data, w, h, w, QImage.Format_Grayscale8).copy()
        ok = out_img.save(path)
        n_classes = len(np.unique(id_arr)) - 1  # ไม่นับ 0
        self.statusBar().showMessage(
            f"{'✅ บันทึกสำเร็จ' if ok else '❌ บันทึกไม่สำเร็จ'}: {path}"
            f"  │  {n_classes} class(es)  │  pixel values = class ID (0=bg)", 6000)


# ─────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = PaintWindow()
    win.show()
    sys.exit(app.exec_())
