import math
import sys
from typing import Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class DragCanvas(QWidget):
    changed = Signal()

    def __init__(self, size: int = 320, square_size: int = 70) -> None:
        super().__init__()
        self.setMinimumSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.square_size = float(square_size)
        self.square_pos = QPointF((size - square_size) / 2.0, (size - square_size) / 2.0)
        self.rotation_angle = 0.0
        self.dragging = False
        self.scaling = False
        self.rotating = False
        self.scale_key_down = False
        self.rotate_key_down = False
        self.drag_offset = QPointF(0, 0)
        self.scale_center = QPointF(0, 0)
        self.scale_start_dist = 1.0
        self.scale_start_size = self.square_size
        self.rotate_center = QPointF(0, 0)
        self.rotate_start_angle = 0.0
        self.start_rotation = 0.0

    def square_rect(self) -> QRectF:
        return QRectF(self.square_pos.x(), self.square_pos.y(), self.square_size, self.square_size)

    def square_center(self) -> QPointF:
        return QPointF(self.square_pos.x() + self.square_size / 2.0, self.square_pos.y() + self.square_size / 2.0)

    def _contains_square_point(self, p: QPointF) -> bool:
        c = self.square_center()
        dx = p.x() - c.x()
        dy = p.y() - c.y()

        cos_a = math.cos(-self.rotation_angle)
        sin_a = math.sin(-self.rotation_angle)
        lx = dx * cos_a - dy * sin_a
        ly = dx * sin_a + dy * cos_a

        half = self.square_size / 2.0
        return -half <= lx <= half and -half <= ly <= half

    def _clamp_rotation_centered(self) -> None:
        c = self.square_center()
        half = self.square_size / 2.0
        cx = min(max(c.x(), half), self.width() - half)
        cy = min(max(c.y(), half), self.height() - half)
        self.square_pos = QPointF(cx - half, cy - half)

    def center_square(self) -> None:
        cx = (self.width() - self.square_size) / 2.0
        cy = (self.height() - self.square_size) / 2.0
        self.square_pos = self._clamped_position(QPointF(cx, cy), self.square_size)
        self.rotation_angle = 0.0
        self.changed.emit()
        self.update()

    def _clamped_position(self, pos: QPointF, size: float) -> QPointF:
        max_x = max(0.0, self.width() - size)
        max_y = max(0.0, self.height() - size)
        x = min(max(pos.x(), 0.0), max_x)
        y = min(max(pos.y(), 0.0), max_y)
        return QPointF(x, y)

    def _set_square_from_center(self, center: QPointF, size: float) -> None:
        max_size = max(10.0, min(float(self.width()), float(self.height())))
        half_limited = min(center.x(), center.y(), self.width() - center.x(), self.height() - center.y())
        center_max_size = max(10.0, 2.0 * max(0.0, half_limited))

        new_size = min(max(size, 10.0), min(max_size, center_max_size))
        new_pos = QPointF(center.x() - new_size / 2.0, center.y() - new_size / 2.0)

        self.square_size = new_size
        self.square_pos = self._clamped_position(new_pos, self.square_size)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._contains_square_point(event.position()):
            self.setFocus()
            if self.rotate_key_down:
                self.rotating = True
                self.rotate_center = self.square_center()
                self.rotate_start_angle = math.atan2(
                    event.position().y() - self.rotate_center.y(),
                    event.position().x() - self.rotate_center.x(),
                )
                self.start_rotation = self.rotation_angle
            elif self.scale_key_down:
                self.scaling = True
                self.scale_center = self.square_center()
                dx = event.position().x() - self.scale_center.x()
                dy = event.position().y() - self.scale_center.y()
                self.scale_start_dist = max(1.0, math.hypot(dx, dy))
                self.scale_start_size = self.square_size
            else:
                self.dragging = True
                self.drag_offset = event.position() - self.square_pos
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.rotating:
            ang = math.atan2(
                event.position().y() - self.rotate_center.y(),
                event.position().x() - self.rotate_center.x(),
            )
            self.rotation_angle = self.start_rotation + (ang - self.rotate_start_angle)
            self.changed.emit()
            self.update()
            event.accept()
            return

        if self.scaling:
            dx = event.position().x() - self.scale_center.x()
            dy = event.position().y() - self.scale_center.y()
            dist = max(1.0, math.hypot(dx, dy))
            new_size = self.scale_start_size * (dist / self.scale_start_dist)

            self._set_square_from_center(self.scale_center, new_size)
            self.changed.emit()
            self.update()
            event.accept()
            return

        if self.dragging:
            nx = event.position().x() - self.drag_offset.x()
            ny = event.position().y() - self.drag_offset.y()

            self.square_pos = self._clamped_position(QPointF(nx, ny), self.square_size)
            self.changed.emit()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.scaling = False
            self.rotating = False
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_S:
            self.scale_key_down = True
            event.accept()
            return
        if event.key() == Qt.Key.Key_R:
            self.rotate_key_down = True
            event.accept()
            return
        if event.key() == Qt.Key.Key_C:
            self.center_square()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_S:
            self.scale_key_down = False
            event.accept()
            return
        if event.key() == Qt.Key.Key_R:
            self.rotate_key_down = False
            event.accept()
            return
        super().keyReleaseEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        c = self.square_center()
        painter.save()
        painter.translate(c)
        painter.rotate(math.degrees(self.rotation_angle))
        half = self.square_size / 2.0
        painter.fillRect(QRectF(-half, -half, self.square_size, self.square_size), Qt.GlobalColor.black)
        painter.restore()
        super().paintEvent(event)

    def as_binary_image(self, resolution: int = 256) -> np.ndarray:
        img = QImage(resolution, resolution, QImage.Format.Format_Grayscale8)
        img.fill(0)

        sx = resolution / max(1.0, float(self.width()))
        sy = resolution / max(1.0, float(self.height()))

        center = self.square_center()
        cx = center.x() * sx
        cy = center.y() * sy
        w = self.square_size * sx
        h = self.square_size * sy

        painter = QPainter(img)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.white)
        painter.translate(cx, cy)
        painter.rotate(math.degrees(self.rotation_angle))
        painter.drawRect(QRectF(-w / 2.0, -h / 2.0, w, h))
        painter.end()

        ptr = img.constBits()
        arr = np.frombuffer(ptr, dtype=np.uint8, count=resolution * resolution).reshape((resolution, resolution))
        return arr.astype(np.float32) / 255.0


class ArrayPanel(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.title = QLabel(title)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(320, 320)
        self.image_label.setStyleSheet("background: #ffffff; border: 1px solid #222;")

        layout.addWidget(self.title)
        layout.addWidget(self.image_label, 1)

        self._pixmap: Optional[QPixmap] = None

    def set_array(self, arr_01: np.ndarray) -> None:
        arr = np.asarray(arr_01, dtype=np.float32)
        arr = np.clip(arr, 0.0, 1.0)
        img8 = (arr * 255.0).astype(np.uint8)

        h, w = img8.shape
        qimg = QImage(img8.data, w, h, img8.strides[0], QImage.Format.Format_Grayscale8).copy()
        self._pixmap = QPixmap.fromImage(qimg)
        self._refresh_scaled_pixmap()

    def resizeEvent(self, event) -> None:
        self._refresh_scaled_pixmap()
        super().resizeEvent(event)

    def _refresh_scaled_pixmap(self) -> None:
        if self._pixmap is None:
            return
        scaled = self._pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.image_label.setPixmap(scaled)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Drag Square + Fourier Magnitude/Phase")

        root = QWidget()
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.canvas = DragCanvas()
        self.spectrum_panel = ArrayPanel("Frequency Spectrum |F(u, v)|")
        self.phase_panel = ArrayPanel("Phase Space angle(F(u, v))")

        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.spectrum_panel, 1)
        layout.addWidget(self.phase_panel, 1)

        self.canvas.changed.connect(self.update_fft_views)
        self.canvas.setFocus()
        self.update_fft_views()

    def update_fft_views(self) -> None:
        img = self.canvas.as_binary_image(256)
        f = np.fft.fft2(img)
        f_shift = np.fft.fftshift(f)

        magnitude = np.log1p(np.abs(f_shift))
        mag_max = float(np.max(magnitude))
        if mag_max > 0.0:
            magnitude /= mag_max

        phase = np.angle(f_shift)
        phase = (phase + math.pi) / (2.0 * math.pi)

        self.spectrum_panel.set_array(magnitude)
        self.phase_panel.set_array(phase)


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1320, 450)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
