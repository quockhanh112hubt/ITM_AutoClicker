"""
Custom widget components for the GUI
"""
from PyQt6.QtWidgets import (
    QTreeWidget, QToolButton, QPushButton, QAbstractItemView, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QPixmap
from pynput import mouse


class ScriptTreeWidget(QTreeWidget):
    """Tree widget with signal after internal drag-drop reorder.
    
    Emits signals when tree order changes or when action replacement is requested.
    Validates drag-drop operations to prevent invalid rearrangements.
    """
    order_changed = pyqtSignal()
    replace_action_requested = pyqtSignal(object, object)  # source_payload, target_payload

    def dropEvent(self, event):
        """Handle drop event with validation logic
        
        Args:
            event: Drop event containing drag-drop information
        """
        # If user drops one action directly on another action, treat it as replace request.
        try:
            target_item = self.itemAt(event.position().toPoint())
        except Exception:
            target_item = None
        source_item = self.currentItem()
        source_payload = source_item.data(0, Qt.ItemDataRole.UserRole) if source_item else None
        target_payload = target_item.data(0, Qt.ItemDataRole.UserRole) if target_item else None
        indicator = self.dropIndicatorPosition()
        selected_action_payloads = []
        for it in self.selectedItems():
            try:
                p = it.data(0, Qt.ItemDataRole.UserRole)
            except Exception:
                p = None
            if (
                isinstance(p, tuple)
                and len(p) >= 3
                and p[0] == "action"
            ):
                selected_action_payloads.append((p[0], int(p[1]), int(p[2])))
        # Keep stable order and remove duplicates.
        selected_action_payloads = sorted(set(selected_action_payloads), key=lambda x: (x[1], x[2]))

        # Prevent branch-over-branch "OnItem" drops because Qt may interpret it as nesting,
        # which can hide/remove one top-level branch after rebuild.
        if (
            source_payload
            and isinstance(source_payload, tuple)
            and source_payload[0] == "group"
            and indicator == QAbstractItemView.DropIndicatorPosition.OnItem
        ):
            event.ignore()
            return

        # Branch can only be moved between branches.
        # Block any branch->action drop (on action or action gaps).
        if (
            source_payload and target_payload
            and isinstance(source_payload, tuple) and isinstance(target_payload, tuple)
            and source_payload[0] == "group" and target_payload[0] == "action"
        ):
            event.ignore()
            return

        # For action -> branch drops:
        # allow only dropping ON the branch row; block Above/Below gap drops.
        if (
            source_payload and target_payload
            and isinstance(source_payload, tuple) and isinstance(target_payload, tuple)
            and source_payload[0] == "action" and target_payload[0] == "group"
            and indicator != QAbstractItemView.DropIndicatorPosition.OnItem
        ):
            event.ignore()
            return

        # For action drags, block ambiguous/non-item drops (often branch gaps/viewport).
        if (
            source_payload
            and isinstance(source_payload, tuple)
            and source_payload[0] == "action"
            and not target_payload
        ):
            event.ignore()
            return

        if (
            source_payload and target_payload
            and isinstance(source_payload, tuple) and isinstance(target_payload, tuple)
            and len(source_payload) >= 3 and len(target_payload) >= 3
            and source_payload[0] == "action" and target_payload[0] == "action"
            and indicator == QAbstractItemView.DropIndicatorPosition.OnItem
        ):
            source_candidates = list(selected_action_payloads)
            if not source_candidates and source_payload != target_payload:
                source_candidates = [(source_payload[0], int(source_payload[1]), int(source_payload[2]))]
            source_candidates = [p for p in source_candidates if p != target_payload]
            if not source_candidates:
                event.ignore()
                return
            reply = QMessageBox.question(
                self,
                "Set Parent Action",
                (
                    f"Make {len(source_candidates)} dragged action(s) "
                    "child of target action?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                if len(source_candidates) == 1:
                    self.replace_action_requested.emit(source_candidates[0], target_payload)
                else:
                    self.replace_action_requested.emit(source_candidates, target_payload)
                event.ignore()
                return
            event.ignore()
            return

        super().dropEvent(event)
        self.order_changed.emit()


class DragCreateToolButton(QToolButton):
    """Toolbar button that creates action by drag-and-drop (click does nothing).
    
    Supports custom cursor display during drag operations and emits signal
    when action is dropped with screen coordinates.
    """
    action_dropped = pyqtSignal(str, int, int)  # choice_name, screen_x, screen_y

    def __init__(self, choice_name: str, parent=None):
        """
        Initialize the drag-create tool button
        
        Args:
            choice_name: Name/identifier for the action type
            parent: Parent widget
        """
        super().__init__(parent)
        self.choice_name = str(choice_name)
        self._press_pos = None
        self._dragging = False
        self._drag_cursor: QCursor | None = None
        self._cursor_active = False

    def set_drag_cursor_pixmap(self, pixmap: QPixmap, hot_x: int | None = None, hot_y: int | None = None):
        """Set custom cursor shown while dragging this action tool.
        
        Args:
            pixmap: Cursor pixmap image
            hot_x: Hotspot X coordinate (None = auto 30% from left)
            hot_y: Hotspot Y coordinate (None = auto 20% from top)
        """
        if pixmap is not None and not pixmap.isNull():
            if hot_x is None or hot_y is None:
                # Default hotspot near pointer tip area for better drop precision.
                hot_x = max(0, int(pixmap.width() * 0.30))
                hot_y = max(0, int(pixmap.height() * 0.20))
            self._drag_cursor = QCursor(pixmap, int(hot_x), int(hot_y))
        else:
            self._drag_cursor = None

    def mousePressEvent(self, event):
        """Handle mouse press event
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move event - detect drag start
        
        Args:
            event: Mouse event
        """
        if self._press_pos is not None:
            if (event.position().toPoint() - self._press_pos).manhattanLength() >= QApplication.startDragDistance():
                self._dragging = True
                if self._drag_cursor is not None and not self._cursor_active:
                    QApplication.setOverrideCursor(self._drag_cursor)
                    self._cursor_active = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release event - emit signal if dragged
        
        Args:
            event: Mouse event
        """
        if self._cursor_active:
            QApplication.restoreOverrideCursor()
            self._cursor_active = False
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            pos = mouse.Controller().position
            self.action_dropped.emit(self.choice_name, int(pos[0]), int(pos[1]))
        self._press_pos = None
        self._dragging = False
        super().mouseReleaseEvent(event)


class DragSelectTargetButton(QPushButton):
    """Button that supports click-to-open picker and drag-drop quick target select."""

    target_dropped = pyqtSignal(int, int)  # screen_x, screen_y

    def __init__(self, parent=None):
        super().__init__(parent)
        self._press_pos = None
        self._dragging = False
        self._drag_cursor: QCursor | None = None
        self._cursor_active = False

    def set_drag_cursor_pixmap(self, pixmap: QPixmap, hot_x: int | None = None, hot_y: int | None = None):
        """Set custom cursor shown while dragging this target-select button."""
        if pixmap is not None and not pixmap.isNull():
            if hot_x is None or hot_y is None:
                hot_x = max(0, int(pixmap.width() * 0.30))
                hot_y = max(0, int(pixmap.height() * 0.20))
            self._drag_cursor = QCursor(pixmap, int(hot_x), int(hot_y))
        else:
            self._drag_cursor = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_pos is not None:
            if (event.position().toPoint() - self._press_pos).manhattanLength() >= QApplication.startDragDistance():
                self._dragging = True
                if self._drag_cursor is not None and not self._cursor_active:
                    QApplication.setOverrideCursor(self._drag_cursor)
                    self._cursor_active = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._cursor_active:
            QApplication.restoreOverrideCursor()
            self._cursor_active = False
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            pos = QCursor.pos()
            self.target_dropped.emit(int(pos.x()), int(pos.y()))
            event.accept()
            self._press_pos = None
            self._dragging = False
            return
        self._press_pos = None
        self._dragging = False
        super().mouseReleaseEvent(event)
