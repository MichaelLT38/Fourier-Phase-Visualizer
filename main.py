import math
import sys
from enum import Enum
from typing import Optional, Tuple

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ShapeKind(str, Enum):
    SQUARE = "square"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"


# Supersample factor for FFT rasterization. Cost is ~ss² for paint+downsample;
# ss=8 is ~4× the pixels of ss=4 and still cheap for a single filled shape at 256².
FFT_SUPERSAMPLE = 8
FFT_RESOLUTION = 256
# Mild post-downsample blur further kills residual edge aliasing / drag shimmer.
FFT_BLUR_SIGMA = 0.65


def _gaussian_kernel1d(sigma: float) -> np.ndarray:
    if sigma <= 0.0:
        return np.array([1.0], dtype=np.float32)
    radius = max(1, int(math.ceil(3.0 * sigma)))
    x = np.arange(-radius, radius + 1, dtype=np.float32)
    k = np.exp(-(x * x) / (2.0 * sigma * sigma))
    k /= k.sum()
    return k.astype(np.float32)


def _gaussian_blur(arr: np.ndarray, sigma: float) -> np.ndarray:
    """Separable Gaussian blur (reflect edges). Fast enough for interactive 256² updates."""
    if sigma <= 0.0:
        return arr
    k = _gaussian_kernel1d(sigma)
    pad = len(k) // 2

    # Horizontal pass
    padded = np.pad(arr, ((0, 0), (pad, pad)), mode="reflect")
    tmp = np.zeros_like(arr, dtype=np.float32)
    for i, w in enumerate(k):
        tmp += w * padded[:, i : i + arr.shape[1]]

    # Vertical pass
    padded = np.pad(tmp, ((pad, pad), (0, 0)), mode="reflect")
    out = np.zeros_like(arr, dtype=np.float32)
    for i, w in enumerate(k):
        out += w * padded[i : i + arr.shape[0], :]
    return out


class DragCanvas(QWidget):
    changed = Signal()

    def __init__(self, size: int = 320, shape_size: int = 70) -> None:
        super().__init__()
        self.setMinimumSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.shape_kind = ShapeKind.SQUARE
        self.shape_w = float(shape_size)
        self.shape_h = float(shape_size)
        self.shape_pos = QPointF((size - shape_size) / 2.0, (size - shape_size) / 2.0)
        self.rotation_angle = 0.0

        self.dragging = False
        self.scaling = False
        self.rotating = False
        self.scale_key_down = False
        self.rotate_key_down = False
        self.scale_x_only = False
        self.scale_y_only = False

        self.drag_offset = QPointF(0, 0)
        self.scale_center = QPointF(0, 0)
        self.scale_start_local = QPointF(1.0, 1.0)
        self.scale_start_w = self.shape_w
        self.scale_start_h = self.shape_h
        self.scale_start_dist = 1.0
        self.rotate_center = QPointF(0, 0)
        self.rotate_start_angle = 0.0
        self.start_rotation = 0.0

    def shape_center(self) -> QPointF:
        return QPointF(self.shape_pos.x() + self.shape_w / 2.0, self.shape_pos.y() + self.shape_h / 2.0)

    def _to_local(self, p: QPointF, center: Optional[QPointF] = None) -> Tuple[float, float]:
        c = self.shape_center() if center is None else center
        dx = p.x() - c.x()
        dy = p.y() - c.y()
        cos_a = math.cos(-self.rotation_angle)
        sin_a = math.sin(-self.rotation_angle)
        lx = dx * cos_a - dy * sin_a
        ly = dx * sin_a + dy * cos_a
        return lx, ly

    def _aabb_half_extents(self) -> Tuple[float, float]:
        """Axis-aligned half-size of the rotated shape bounding box."""
        hw = self.shape_w / 2.0
        hh = self.shape_h / 2.0
        if self.shape_kind == ShapeKind.CIRCLE:
            # Circle/ellipse AABB is just the axis radii (rotation does not enlarge a circle;
            # for a non-square ellipse we still treat extents as hw/hh after rotation).
            cos_a = abs(math.cos(self.rotation_angle))
            sin_a = abs(math.sin(self.rotation_angle))
            return hw * cos_a + hh * sin_a, hw * sin_a + hh * cos_a

        cos_a = abs(math.cos(self.rotation_angle))
        sin_a = abs(math.sin(self.rotation_angle))
        return hw * cos_a + hh * sin_a, hw * sin_a + hh * cos_a

    def _contains_shape_point(self, p: QPointF) -> bool:
        lx, ly = self._to_local(p)
        hw = self.shape_w / 2.0
        hh = self.shape_h / 2.0
        if self.shape_kind == ShapeKind.CIRCLE:
            if hw <= 0.0 or hh <= 0.0:
                return False
            return (lx / hw) ** 2 + (ly / hh) ** 2 <= 1.0
        return -hw <= lx <= hw and -hh <= ly <= hh

    def _clamp_center(self, center: QPointF) -> QPointF:
        ax, ay = self._aabb_half_extents()
        cx = min(max(center.x(), ax), self.width() - ax)
        cy = min(max(center.y(), ay), self.height() - ay)
        return QPointF(cx, cy)

    def _apply_center_size(self, center: QPointF, width: float, height: float) -> None:
        min_size = 10.0
        max_w = max(min_size, float(self.width()))
        max_h = max(min_size, float(self.height()))
        width = min(max(width, min_size), max_w)
        height = min(max(height, min_size), max_h)

        # Keep the shape fully inside the canvas using its rotated AABB.
        self.shape_w = width
        self.shape_h = height
        c = self._clamp_center(center)
        # Further shrink if center clamp still can't fit (near edges while large).
        ax, ay = self._aabb_half_extents()
        if ax * 2.0 > self.width() or ay * 2.0 > self.height():
            scale = min(self.width() / max(1e-6, ax * 2.0), self.height() / max(1e-6, ay * 2.0), 1.0)
            self.shape_w = max(min_size, self.shape_w * scale)
            self.shape_h = max(min_size, self.shape_h * scale)
            if self.shape_kind in (ShapeKind.SQUARE, ShapeKind.CIRCLE):
                side = min(self.shape_w, self.shape_h)
                self.shape_w = side
                self.shape_h = side
            c = self._clamp_center(center)

        self.shape_pos = QPointF(c.x() - self.shape_w / 2.0, c.y() - self.shape_h / 2.0)

    def set_shape_kind(self, kind: ShapeKind) -> None:
        if kind == self.shape_kind:
            return
        center = self.shape_center()
        self.shape_kind = kind
        if kind in (ShapeKind.SQUARE, ShapeKind.CIRCLE):
            side = 0.5 * (self.shape_w + self.shape_h)
            self._apply_center_size(center, side, side)
        else:
            self._apply_center_size(center, self.shape_w, self.shape_h)
        self.changed.emit()
        self.update()

    def center_shape(self) -> None:
        c = QPointF(self.width() / 2.0, self.height() / 2.0)
        self.rotation_angle = 0.0
        self._apply_center_size(c, self.shape_w, self.shape_h)
        self.changed.emit()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._contains_shape_point(event.position()):
            self.setFocus()
            if self.rotate_key_down and self.shape_kind != ShapeKind.CIRCLE:
                self.rotating = True
                self.rotate_center = self.shape_center()
                self.rotate_start_angle = math.atan2(
                    event.position().y() - self.rotate_center.y(),
                    event.position().x() - self.rotate_center.x(),
                )
                self.start_rotation = self.rotation_angle
            elif self.scale_key_down:
                self.scaling = True
                self.scale_center = self.shape_center()
                lx, ly = self._to_local(event.position(), self.scale_center)
                self.scale_start_local = QPointF(max(1.0, abs(lx)), max(1.0, abs(ly)))
                self.scale_start_dist = max(1.0, math.hypot(lx, ly))
                self.scale_start_w = self.shape_w
                self.scale_start_h = self.shape_h
            else:
                self.dragging = True
                self.drag_offset = event.position() - self.shape_pos
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
            # Re-clamp after rotation changes the AABB.
            self._apply_center_size(self.rotate_center, self.shape_w, self.shape_h)
            self.changed.emit()
            self.update()
            event.accept()
            return

        if self.scaling:
            lx, ly = self._to_local(event.position(), self.scale_center)
            uniform = self.shape_kind in (ShapeKind.SQUARE, ShapeKind.CIRCLE)

            if uniform:
                dist = max(1.0, math.hypot(lx, ly))
                factor = dist / self.scale_start_dist
                new_w = self.scale_start_w * factor
                new_h = self.scale_start_h * factor
            else:
                # Rectangle: independent axes from local mouse position.
                # Hold X or Y to lock to one axis.
                fx = abs(lx) / self.scale_start_local.x()
                fy = abs(ly) / self.scale_start_local.y()
                if self.scale_x_only and not self.scale_y_only:
                    new_w = self.scale_start_w * fx
                    new_h = self.scale_start_h
                elif self.scale_y_only and not self.scale_x_only:
                    new_w = self.scale_start_w
                    new_h = self.scale_start_h * fy
                else:
                    new_w = self.scale_start_w * fx
                    new_h = self.scale_start_h * fy

            self._apply_center_size(self.scale_center, new_w, new_h)
            self.changed.emit()
            self.update()
            event.accept()
            return

        if self.dragging:
            proposed_pos = QPointF(
                event.position().x() - self.drag_offset.x(),
                event.position().y() - self.drag_offset.y(),
            )
            center = QPointF(
                proposed_pos.x() + self.shape_w / 2.0,
                proposed_pos.y() + self.shape_h / 2.0,
            )
            self._apply_center_size(center, self.shape_w, self.shape_h)
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
        key = event.key()
        if key == Qt.Key.Key_S:
            self.scale_key_down = True
            event.accept()
            return
        if key == Qt.Key.Key_R:
            self.rotate_key_down = True
            event.accept()
            return
        if key == Qt.Key.Key_X:
            self.scale_x_only = True
            event.accept()
            return
        if key == Qt.Key.Key_Y:
            self.scale_y_only = True
            event.accept()
            return
        if key == Qt.Key.Key_C:
            self.center_shape()
            event.accept()
            return
        if key == Qt.Key.Key_1:
            self.set_shape_kind(ShapeKind.SQUARE)
            event.accept()
            return
        if key == Qt.Key.Key_2:
            self.set_shape_kind(ShapeKind.RECTANGLE)
            event.accept()
            return
        if key == Qt.Key.Key_3:
            self.set_shape_kind(ShapeKind.CIRCLE)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_S:
            self.scale_key_down = False
            event.accept()
            return
        if key == Qt.Key.Key_R:
            self.rotate_key_down = False
            event.accept()
            return
        if key == Qt.Key.Key_X:
            self.scale_x_only = False
            event.accept()
            return
        if key == Qt.Key.Key_Y:
            self.scale_y_only = False
            event.accept()
            return
        super().keyReleaseEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        c = self.shape_center()
        painter.save()
        painter.translate(c)
        painter.rotate(math.degrees(self.rotation_angle))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.black)
        rect = QRectF(-self.shape_w / 2.0, -self.shape_h / 2.0, self.shape_w, self.shape_h)
        if self.shape_kind == ShapeKind.CIRCLE:
            painter.drawEllipse(rect)
        else:
            painter.drawRect(rect)
        painter.restore()
        super().paintEvent(event)

    def as_binary_image(
        self,
        resolution: int = FFT_RESOLUTION,
        supersample: int = FFT_SUPERSAMPLE,
        blur_sigma: float = FFT_BLUR_SIGMA,
    ) -> np.ndarray:
        """Rasterize the shape with area sampling so the FFT is not dominated by edge aliasing.

        A hard binary shape has infinite spatial bandwidth. Sampling it onto a pixel
        grid without filtering folds high frequencies into the spectrum, and those
        aliases shimmer as the shape moves by subpixel amounts. Rendering at a
        higher resolution with antialiasing, box-filtering down, then a mild
        Gaussian blur approximates band-limiting before the DFT.
        """
        ss = max(1, int(supersample))
        hi_res = resolution * ss

        img = QImage(hi_res, hi_res, QImage.Format.Format_Grayscale8)
        img.fill(0)

        sx = hi_res / max(1.0, float(self.width()))
        sy = hi_res / max(1.0, float(self.height()))

        center = self.shape_center()
        cx = center.x() * sx
        cy = center.y() * sy
        w = self.shape_w * sx
        h = self.shape_h * sy

        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.white)
        painter.translate(cx, cy)
        painter.rotate(math.degrees(self.rotation_angle))
        rect = QRectF(-w / 2.0, -h / 2.0, w, h)
        if self.shape_kind == ShapeKind.CIRCLE:
            painter.drawEllipse(rect)
        else:
            painter.drawRect(rect)
        painter.end()

        ptr = img.constBits()
        arr = np.frombuffer(ptr, dtype=np.uint8, count=hi_res * hi_res).reshape((hi_res, hi_res))
        arr_f = arr.astype(np.float32) / 255.0

        if ss > 1:
            arr_f = arr_f.reshape(resolution, ss, resolution, ss).mean(axis=(1, 3))

        if blur_sigma > 0.0:
            arr_f = _gaussian_blur(arr_f, blur_sigma)

        return np.clip(arr_f, 0.0, 1.0)


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
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Fourier Phase Visualizer")

        root = QWidget()
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        # Shape toolbar
        tools = QHBoxLayout()
        tools.setSpacing(8)
        tools_label = QLabel("Shape:")
        tools.addWidget(tools_label)

        self.shape_group = QButtonGroup(self)
        self.btn_square = QPushButton("Square")
        self.btn_rect = QPushButton("Rectangle")
        self.btn_circle = QPushButton("Circle")
        for btn in (self.btn_square, self.btn_rect, self.btn_circle):
            btn.setCheckable(True)
            self.shape_group.addButton(btn)
            tools.addWidget(btn)
        self.btn_square.setChecked(True)

        self.btn_square.clicked.connect(lambda: self._on_shape(ShapeKind.SQUARE))
        self.btn_rect.clicked.connect(lambda: self._on_shape(ShapeKind.RECTANGLE))
        self.btn_circle.clicked.connect(lambda: self._on_shape(ShapeKind.CIRCLE))

        tools.addSpacing(16)
        help_lbl = QLabel(
            "Drag move · S+drag scale · R+drag rotate · X/Y+S axis-lock (rect) · C center · 1/2/3 shape"
        )
        help_lbl.setStyleSheet("color: #444;")
        tools.addWidget(help_lbl, 1)
        outer.addLayout(tools)

        panels = QHBoxLayout()
        panels.setSpacing(10)

        self.canvas = DragCanvas()
        self.spectrum_panel = ArrayPanel("Frequency Spectrum |F(u, v)|")
        self.phase_panel = ArrayPanel("Phase Space angle(F(u, v))")

        panels.addWidget(self.canvas, 1)
        panels.addWidget(self.spectrum_panel, 1)
        panels.addWidget(self.phase_panel, 1)
        outer.addLayout(panels, 1)

        self.canvas.changed.connect(self.update_fft_views)
        self.canvas.setFocus()
        self.update_fft_views()

    def _on_shape(self, kind: ShapeKind) -> None:
        self.canvas.set_shape_kind(kind)
        self.canvas.setFocus()

    def update_fft_views(self) -> None:
        img = self.canvas.as_binary_image()
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
    window.resize(1320, 500)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
