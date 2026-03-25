import numpy as np
from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QImage, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QFileDialog,
    QGraphicsScene,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSpinBox,
    QSplitter,
    QToolBar,
)

from ..canvas import BgItem, CanvasItem
from ..data import DEFAULT_HIGH_CUT, DEFAULT_LOW_CUT, build_class_id_mask, compute_class_spectra
from .class_table import ClassTable
from .contrast_dialog import ContrastDialog
from .paint_view import PaintView
from .pg_panel import PgPanel


class PaintWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HSI Ground Truth Painter")
        self.resize(1800, 900)
        self._preview_low_cut = DEFAULT_LOW_CUT
        self._preview_high_cut = DEFAULT_HIGH_CUT

        self._scene = QGraphicsScene(self)
        self._bg = BgItem()
        self._canvas = CanvasItem()
        self._scene.addItem(self._bg)
        self._scene.addItem(self._canvas)
        self._scene.setSceneRect(QRectF(0, 0, 800, 600))

        self._view = PaintView(self._scene, self)
        self._pg_panel = PgPanel(self)
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

        self._canvas.signals.updated.connect(self._refresh_pg)
        self._canvas.signals.spectrum_ready.connect(self._pg_panel.update_spectrum)
        self._canvas.signals.loaded.connect(self._on_loaded)
        self._class_table.class_changed.connect(self._on_class_changed)

    def _on_loaded(self, ncols, nrows, nbands):
        preview = self._format_preview_info()
        self.statusBar().showMessage(
            "✅  Datacube โหลดสำเร็จ  │  {0}×{1} px  │  {2} bands"
            "  │  {3}  │  Ctrl+Wheel=Zoom  │  F=ถังสี  │  L=ต่อจุด  │  Ctrl+S=บันทึก GT".format(
                ncols, nrows, nbands, preview
            ),
            0,
        )
        for action in self._tool_actions.values():
            action.setEnabled(True)
        self._contrast_action.setEnabled(True)

    def _on_class_changed(self, name, color):
        active_color = QColor(color)
        active_color.setAlpha(220)
        self._canvas.set_pen_color(active_color)
        self._color_preview.setStyleSheet(
            "background:{0}; border:2px solid #888; border-radius:4px;".format(
                color.name()
            )
        )
        self._set_tool("pen")
        self._compute_class_spectra()

    def _refresh_pg(self):
        self._pg_panel.update_from_mask(self._canvas.get_mask())
        self._compute_class_spectra()

    def _compute_class_spectra(self):
        if self._canvas.datacube is None or self._canvas.is_drawing:
            return
        class_data = compute_class_spectra(
            self._canvas.datacube,
            self._canvas.get_mask(),
            self._class_table.get_all(),
        )
        self._pg_panel.update_class_spectra(class_data)

    def _build_toolbar(self):
        toolbar = QToolBar("Tools", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        act_pen = QAction("✏️ ปากกา", self)
        act_pen.setCheckable(True)
        act_pen.setChecked(True)
        act_pen.triggered.connect(lambda: self._set_tool("pen"))
        toolbar.addAction(act_pen)

        act_eraser = QAction("🧹 ยางลบ", self)
        act_eraser.setCheckable(True)
        act_eraser.triggered.connect(lambda: self._set_tool("eraser"))
        toolbar.addAction(act_eraser)

        act_fill = QAction("🪣 ถังสี", self)
        act_fill.setCheckable(True)
        act_fill.setShortcut("F")
        act_fill.triggered.connect(lambda: self._set_tool("fill"))
        toolbar.addAction(act_fill)

        act_connect = QAction("🔗 ต่อจุด", self)
        act_connect.setCheckable(True)
        act_connect.setShortcut("L")
        act_connect.triggered.connect(lambda: self._set_tool("connect"))
        toolbar.addAction(act_connect)

        self._tool_actions = {
            "pen": act_pen,
            "eraser": act_eraser,
            "fill": act_fill,
            "connect": act_connect,
        }
        toolbar.addSeparator()

        toolbar.addWidget(QLabel("  🎨 สีปัจจุบัน:  "))
        self._color_preview = QLabel()
        self._color_preview.setFixedSize(28, 28)
        self._color_preview.setStyleSheet(
            "background:#e74c3c; border:2px solid #888; border-radius:4px;"
        )
        toolbar.addWidget(self._color_preview)
        toolbar.addSeparator()

        toolbar.addWidget(QLabel("  🖌️ ขนาด:  "))
        self._size_spin = QSpinBox()
        self._size_spin.setRange(1, 100)
        self._size_spin.setValue(4)
        self._size_spin.setFixedWidth(60)
        self._size_spin.valueChanged.connect(self._canvas.set_pen_width)
        toolbar.addWidget(self._size_spin)

        toolbar.addWidget(QLabel("  👁 Opacity:  "))
        opacity_spin = QSpinBox()
        opacity_spin.setRange(10, 100)
        opacity_spin.setValue(75)
        opacity_spin.setSuffix(" %")
        opacity_spin.setFixedWidth(70)
        opacity_spin.valueChanged.connect(lambda value: self._canvas.setOpacity(value / 100))
        toolbar.addWidget(opacity_spin)
        toolbar.addSeparator()

        toolbar.addWidget(QLabel("  🔍 Zoom:  "))
        zoom_in = QAction("＋", self)
        zoom_in.setShortcut("Ctrl+=")
        zoom_in.triggered.connect(self._view.zoom_in)
        toolbar.addAction(zoom_in)

        zoom_out = QAction("－", self)
        zoom_out.setShortcut("Ctrl+-")
        zoom_out.triggered.connect(self._view.zoom_out)
        toolbar.addAction(zoom_out)

        zoom_reset = QAction("1:1", self)
        zoom_reset.setShortcut("Ctrl+0")
        zoom_reset.triggered.connect(self._view.zoom_reset)
        toolbar.addAction(zoom_reset)

        fit_action = QAction("⊡ Fit", self)
        fit_action.setShortcut("Ctrl+F")
        fit_action.triggered.connect(self._fit)
        toolbar.addAction(fit_action)
        toolbar.addSeparator()

        self._contrast_action = QAction("🎚 RGB Contrast", self)
        self._contrast_action.triggered.connect(self._open_contrast_dialog)
        self._contrast_action.setEnabled(False)
        toolbar.addAction(self._contrast_action)
        toolbar.addSeparator()

        open_action = QAction("📂 เปิด .hdr", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open)
        toolbar.addAction(open_action)

        clear_action = QAction("🗋 ล้าง GT", self)
        clear_action.setShortcut("Ctrl+N")
        clear_action.triggered.connect(self._clear)
        toolbar.addAction(clear_action)

        save_action = QAction("💾 บันทึก GT", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save)
        toolbar.addAction(save_action)

    def _build_statusbar(self):
        self._zoom_label = QLabel("Zoom: 100%")
        self.statusBar().addPermanentWidget(self._zoom_label)
        for action in self._tool_actions.values():
            action.setEnabled(False)
        self.statusBar().showMessage(
            "⚠️  โปรดโหลด Hyperspectral Datacube (.hdr) ก่อน  │  Ctrl+O = เปิดไฟล์"
        )
        self._on_class_changed(
            self._class_table.active_name(), self._class_table.active_color()
        )

    def update_zoom_label(self, zoom):
        self._zoom_label.setText("Zoom: {0:.0f}%".format(zoom * 100))

    def _set_tool(self, tool_name):
        self._canvas.set_tool(tool_name)
        for name, action in self._tool_actions.items():
            action.setChecked(name == tool_name)

    def _fit(self):
        self._view.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._view._zoom = self._view.transform().m11()
        self.update_zoom_label(self._view._zoom)

    def _open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "เปิด Hyperspectral Datacube", "", "ENVI Header (*.hdr)"
        )
        if not path:
            return
        self.statusBar().showMessage("⏳  กำลังโหลด datacube…")
        QApplication.processEvents()
        self._canvas.set_preview_cuts(self._preview_low_cut, self._preview_high_cut)
        rgb_img = self._canvas.load_datacube(path)
        self._bg.setPixmap(QPixmap.fromImage(rgb_img))
        self._scene.setSceneRect(QRectF(rgb_img.rect()))

    def _open_contrast_dialog(self):
        if not self._canvas.is_loaded:
            return
        original_low_cut = self._preview_low_cut
        original_high_cut = self._preview_high_cut
        dialog = ContrastDialog(original_low_cut, original_high_cut, self)
        dialog.preview_changed.connect(self._apply_preview_cuts)
        if dialog.exec_() != QDialog.Accepted:
            self._apply_preview_cuts(original_low_cut, original_high_cut)
            self._preview_low_cut = original_low_cut
            self._preview_high_cut = original_high_cut
            return
        self._preview_low_cut, self._preview_high_cut = dialog.values()
        self.statusBar().showMessage(
            "🎚 ปรับ RGB contrast แล้ว  │  {0}".format(self._format_preview_info()),
            5000,
        )

    def _apply_preview_cuts(self, low_cut, high_cut):
        rgb_img = self._canvas.render_preview(low_cut, high_cut)
        if rgb_img is None:
            return
        self._bg.setPixmap(QPixmap.fromImage(rgb_img))

    def _clear(self):
        if not self._canvas.is_loaded:
            return
        answer = QMessageBox.question(
            self, "ล้าง GT", "ล้าง Ground Truth layer?", QMessageBox.Yes | QMessageBox.No
        )
        if answer == QMessageBox.Yes:
            self._canvas.clear_mask()

    def _save(self):
        if not self._canvas.is_loaded:
            QMessageBox.warning(self, "ยังไม่มีข้อมูล", "โหลด datacube ก่อนบันทึก")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "บันทึก Ground Truth Mask (Class ID)",
            "gt_mask.png",
            "PNG (*.png);;TIFF (*.tif *.tiff)",
        )
        if not path:
            return

        id_arr = build_class_id_mask(self._canvas.get_mask(), self._class_table.get_all())
        height, width = id_arr.shape
        out_img = QImage(id_arr.data, width, height, width, QImage.Format_Grayscale8).copy()
        ok = out_img.save(path)
        n_classes = len(np.unique(id_arr)) - 1
        self.statusBar().showMessage(
            "{0}: {1}  │  {2} class(es)  │  pixel values = class ID (0=bg)".format(
                "✅ บันทึกสำเร็จ" if ok else "❌ บันทึกไม่สำเร็จ",
                path,
                n_classes,
            ),
            6000,
        )

    def _format_preview_info(self):
        preview_info = self._canvas.preview_info or {}
        low_cut = preview_info.get("low_cut", self._preview_low_cut)
        high_cut = preview_info.get("high_cut", self._preview_high_cut)
        actual = preview_info.get("actual_wavelengths")
        if actual:
            wavelength_text = "RGB≈{0:.0f}/{1:.0f}/{2:.0f} nm".format(*actual)
        else:
            bands = preview_info.get("band_indices")
            wavelength_text = (
                "RGB bands={0}/{1}/{2}".format(*bands)
                if bands
                else "RGB fallback bands"
            )
        return "{0}  │  cut {1:.1f}-{2:.1f}%".format(wavelength_text, low_cut, high_cut)