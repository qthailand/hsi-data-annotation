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
    class_changed = pyqtSignal(int, str, QColor)

    _DEFAULTS = [
        (1, "Class 1", QColor(231, 76, 60)),
        (2, "Class 2", QColor(46, 204, 113)),
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

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["ID", "Class Name", "Color"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self._table.setColumnWidth(0, 60)
        self._table.setColumnWidth(2, 80)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setStyleSheet(
            "QTableWidget { background:#1e1e1e; color:#e0e0e0; gridline-color:#333; }"
            "QHeaderView::section { background:#2b2b2b; color:#ccc; padding:4px; }"
            "QTableWidget::item:selected { background:#3a3a5c; }"
        )
        self._table.itemSelectionChanged.connect(self._on_selection)
        self._table.itemChanged.connect(self._on_item_changed)
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

        self._suspend_item_change = False

        for class_id, name, color in self._DEFAULTS:
            self._insert_row(class_id, name, color)
        self._table.selectRow(0)

    def _insert_row(self, class_id, name, color):
        row = self._table.rowCount()
        self._table.insertRow(row)

        id_item = QTableWidgetItem(str(class_id))
        id_item.setFlags(id_item.flags() | Qt.ItemIsEditable)
        self._table.setItem(row, 0, id_item)

        name_item = QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
        self._table.setItem(row, 1, name_item)

        button = QPushButton()
        button.setFixedHeight(26)
        button.setStyleSheet(
            "background:{0}; border:1px solid #555; border-radius:3px;".format(color.name())
        )
        button.setProperty("_color", color)
        button.clicked.connect(lambda _, btn=button: self._pick_color_for_button(btn))
        self._table.setCellWidget(row, 2, button)

    def _row_of_button(self, button):
        for row in range(self._table.rowCount()):
            if self._table.cellWidget(row, 2) is button:
                return row
        return -1

    def _pick_color_for_button(self, button):
        row = self._row_of_button(button)
        if row >= 0:
            self._pick_color(row)

    def _pick_color(self, row):
        button = self._table.cellWidget(row, 2)
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
        _, _, color = self._DEFAULTS[row % len(self._DEFAULTS)]
        class_id = self._next_available_id()
        self._insert_row(class_id, "Class {0}".format(row + 1), color)
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

    def _on_item_changed(self, item):
        if self._suspend_item_change:
            return
        if item.column() == 0:
            self._normalize_id_item(item)
        if item.row() == self._table.currentRow() and item.column() in (0, 1):
            self._emit_active()

    def _next_available_id(self):
        used = set()
        for row in range(self._table.rowCount()):
            class_id = self._class_id_from_row(row)
            if class_id is not None:
                used.add(class_id)
        candidate = 1
        while candidate in used:
            candidate += 1
        return candidate

    def _normalize_id_item(self, item):
        text = (item.text() or "").strip()
        if text.isdigit() and int(text) >= 0:
            normalized = str(int(text))
        else:
            normalized = str(item.row() + 1)
        if normalized != item.text():
            self._suspend_item_change = True
            item.setText(normalized)
            self._suspend_item_change = False

    def _class_id_from_row(self, row):
        item = self._table.item(row, 0)
        if item is None:
            return None
        text = (item.text() or "").strip()
        if not text.isdigit():
            return None
        return int(text)

    def validate_class_ids(self):
        if self._table.rowCount() == 0:
            return False, "ยังไม่มี class ให้บันทึก"

        seen = set()
        for row in range(self._table.rowCount()):
            class_id = self._class_id_from_row(row)
            if class_id is None:
                return False, "ID ของ class แถว {0} ต้องเป็นจำนวนเต็ม".format(row + 1)
            if class_id <= 0:
                return False, "ID ของ class แถว {0} ต้องมากกว่า 0 (0 สงวนไว้เป็น background)".format(
                    row + 1
                )
            if class_id > 255:
                return False, "ID ของ class แถว {0} ต้องไม่เกิน 255".format(row + 1)
            if class_id in seen:
                return False, "ID ซ้ำกันที่ค่า {0}".format(class_id)
            seen.add(class_id)
        return True, ""

    def _emit_active(self):
        row = self._table.currentRow()
        if row < 0:
            return
        class_id = self._class_id_from_row(row)
        if class_id is None:
            class_id = row + 1
        name_item = self._table.item(row, 1)
        name = name_item.text() if name_item else "Class {0}".format(row + 1)
        button = self._table.cellWidget(row, 2)
        color = button.property("_color") if button else QColor(Qt.red)
        fg = "#000" if color.lightness() > 128 else "#fff"
        self._active_lbl.setText("Active: <b>{0}</b> (ID={1})".format(name, class_id))
        self._active_lbl.setStyleSheet(
            "font-size:12px; font-weight:bold; padding:4px; border-radius:3px;"
            "background:{0}; color:{1};".format(color.name(), fg)
        )
        self.class_changed.emit(class_id, name, color)

    def active_color(self):
        row = self._table.currentRow()
        if row < 0:
            return QColor(Qt.red)
        button = self._table.cellWidget(row, 2)
        return button.property("_color") if button else QColor(Qt.red)

    def active_name(self):
        row = self._table.currentRow()
        if row < 0:
            return "Unknown"
        item = self._table.item(row, 1)
        return item.text() if item else "Class {0}".format(row + 1)

    def active_class_id(self):
        row = self._table.currentRow()
        if row < 0:
            return 1
        class_id = self._class_id_from_row(row)
        return class_id if class_id is not None else row + 1

    def get_all(self):
        result = []
        for row in range(self._table.rowCount()):
            class_id = self._class_id_from_row(row)
            if class_id is None:
                class_id = row + 1
            item = self._table.item(row, 1)
            name = item.text() if item else "Class {0}".format(row + 1)
            button = self._table.cellWidget(row, 2)
            color = button.property("_color") if button else QColor(Qt.red)
            result.append((class_id, name, color))
        return result