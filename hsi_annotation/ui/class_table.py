from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ClassTable(QWidget):
    class_changed = pyqtSignal(str, QColor)

    _DEFAULTS = [
        ("Class 1", QColor(231, 76, 60)),
        ("Class 2", QColor(46, 204, 113)),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel("🏷️  Class Labels")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(
            "font-weight:bold; font-size:13px; padding:5px;"
            "background:#2b2b2b; color:#e0e0e0; border-radius:4px;"
        )
        layout.addWidget(header)

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

        buttons = QHBoxLayout()
        add_button = QPushButton("➕  Add")
        remove_button = QPushButton("🗑  Remove")
        add_button.clicked.connect(self._add_row)
        remove_button.clicked.connect(self._remove_row)
        buttons.addWidget(add_button)
        buttons.addWidget(remove_button)
        layout.addLayout(buttons)

        self._active_lbl = QLabel("—")
        self._active_lbl.setAlignment(Qt.AlignCenter)
        self._active_lbl.setStyleSheet(
            "font-size:12px; padding:4px; border-radius:3px; color:#aaa;"
        )
        layout.addWidget(self._active_lbl)

        for name, color in self._DEFAULTS:
            self._insert_row(name, color)
        self._table.selectRow(0)

    def _insert_row(self, name, color):
        row = self._table.rowCount()
        self._table.insertRow(row)
        item = QTableWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self._table.setItem(row, 0, item)
        button = QPushButton()
        button.setFixedHeight(26)
        button.setStyleSheet(
            "background:{0}; border:1px solid #555; border-radius:3px;".format(color.name())
        )
        button.setProperty("_color", color)
        button.clicked.connect(lambda _, row_index=row: self._pick_color(row_index))
        self._table.setCellWidget(row, 1, button)

    def _pick_color(self, row):
        button = self._table.cellWidget(row, 1)
        if button is None:
            return
        old_color = button.property("_color") or QColor(Qt.red)
        color = QColorDialog.getColor(old_color, self, "เลือกสีคลาส")
        if color.isValid():
            button.setStyleSheet(
                "background:{0}; border:1px solid #555; border-radius:3px;".format(color.name())
            )
            button.setProperty("_color", color)
            if row == self._table.currentRow():
                self._emit_active()

    def _add_row(self):
        row = self._table.rowCount()
        _, color = self._DEFAULTS[row % len(self._DEFAULTS)]
        self._insert_row("Class {0}".format(row + 1), color)
        self._table.selectRow(row)

    def _remove_row(self):
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
            row_count = self._table.rowCount()
            if row_count > 0:
                self._table.selectRow(min(row, row_count - 1))

    def _on_selection(self):
        self._emit_active()

    def _emit_active(self):
        row = self._table.currentRow()
        if row < 0:
            return
        item = self._table.item(row, 0)
        name = item.text() if item else "Class {0}".format(row + 1)
        button = self._table.cellWidget(row, 1)
        color = button.property("_color") if button else QColor(Qt.red)
        fg = "#000" if color.lightness() > 128 else "#fff"
        self._active_lbl.setText("Active: <b>{0}</b>".format(name))
        self._active_lbl.setStyleSheet(
            "font-size:12px; font-weight:bold; padding:4px; border-radius:3px;"
            "background:{0}; color:{1};".format(color.name(), fg)
        )
        self.class_changed.emit(name, color)

    def active_color(self):
        row = self._table.currentRow()
        if row < 0:
            return QColor(Qt.red)
        button = self._table.cellWidget(row, 1)
        return button.property("_color") if button else QColor(Qt.red)

    def active_name(self):
        row = self._table.currentRow()
        if row < 0:
            return "Unknown"
        item = self._table.item(row, 0)
        return item.text() if item else "Class {0}".format(row + 1)

    def get_all(self):
        result = []
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            name = item.text() if item else "Class {0}".format(row + 1)
            button = self._table.cellWidget(row, 1)
            color = button.property("_color") if button else QColor(Qt.red)
            result.append((name, color))
        return result