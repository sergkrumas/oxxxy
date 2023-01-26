

from PyQt5.QtWidgets import (QHBoxLayout, QVBoxLayout, QWidget, QMessageBox, QDesktopWidget, QApplication, QRadioButton)
from PyQt5.QtCore import (QRectF, QPoint, pyqtSignal, QSizeF, Qt, QPointF, QSize, QRect)
from PyQt5.QtGui import (QWindow, QPixmap, QBrush, QRegion, QImage, QRadialGradient, QColor,
                    QGuiApplication, QPen, QPainterPath, QPolygon, QLinearGradient, QPainter)

from _utils import (dot, )
import sys
import math
__all__ = (
    'CustomSlider'
)

class CustomSlider(QWidget):
    colorGrads = QLinearGradient(0, 0, 1, 0)
    colorGrads.setCoordinateMode(colorGrads.ObjectBoundingMode)
    xRatio = 1. / 6
    # rainbow gradient
    colorGrads.setColorAt(0, Qt.red)
    colorGrads.setColorAt(xRatio, Qt.magenta)
    colorGrads.setColorAt(xRatio * 2, Qt.blue)
    colorGrads.setColorAt(xRatio * 3, Qt.cyan)
    colorGrads.setColorAt(xRatio * 4, Qt.green)
    colorGrads.setColorAt(xRatio * 5, Qt.yellow)
    colorGrads.setColorAt(1, Qt.red)
    value_changed = pyqtSignal()
    def __init__(self, _type, width, default_value, flat_look):
        super().__init__()
        if _type == "PALETTE":
            self.default_value = 0.01
            self.value = 0.01
            self.palette_index = default_value
        else:
            self.default_value = default_value
            self.value = self.default_value
        self.offset = 15
        self.changing = False
        self.control_width = 18
        self.type = _type
        self.setFixedWidth(width)
        self.palette_colors = (
            QColor(0, 0, 0),
            QColor(255, 255, 255),
            QColor(255, 0, 0),
            QColor(0, 255, 0),
        )
        self.palette_radius = 15
        if _type == "PALETTE":
            if self.palette_index > len(self.palette_colors) - 1:
                self.palette_index = 0
            self.setFixedWidth(len(self.palette_colors)*self.palette_radius*3)
        #pylint
        self._inner_rect = QRect()
        self.image = None
        self.raw_value = 1.0
        self.flat_look = flat_look
        if self.type == "PALETTE":
            self.flat_look = True 
        self.refresh_image()

    def resizeEvent(self, event):
        self.refresh_image()

    def refresh_image(self):
        if self.type == "COLOR":
            self._inner_rect = self.rect()
            pixmap = QPixmap(self.rect().size())
            qp = QPainter(pixmap)
            qp.fillRect(self._inner_rect, self.colorGrads)
            qp.end()
            self.image = pixmap.toImage()

    def get_AB_rect(self):
        A, B = self.get_AB_points()
        offset = 3
        return QRect(A.toPoint() + QPoint(0, -offset), B.toPoint() + QPoint(0, offset))

    def get_AB_points(self):
        h = self.rect().height()/2
        A = QPointF(self.offset, h)
        B = QPointF(self.rect().width()-self.offset, h)
        return A, B

    def draw_bar(self, painter, color):
        A, B = self.get_AB_points()
        A += QPoint(0, 4)
        B += QPoint(0, 4)
        A1 = A + QPoint(0, -3)
        B1 = B + QPoint(0, -8)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        points = QPolygon([A.toPoint(), A1.toPoint(), B1.toPoint(), B.toPoint()])
        painter.drawPolygon(points)
        if not self.flat_look:
            cr = QRect(
                B1.toPoint()-QPoint(4, 0),
                B.toPoint()+QPoint(8, 0)-QPoint(4, 1)
            )
            painter.drawEllipse(cr)

    def mask(self, painter, side):
        A, B = self.get_AB_points()
        center_point = A*(1-self.value) + B*self.value
        p = center_point.toPoint()
        if side == "a":
            r = QRect(QPoint(0,0), p)
            r.setBottom(self.rect().height())
        elif side == "b":
            p = QPoint(p.x(), 0)
            r = QRect(p, self.rect().bottomRight())
        painter.setClipRegion(QRegion(r))

    def get_color_list_points(self):
        A, B = self.get_AB_points()
        color_list = []
        for n, color in enumerate(self.palette_colors):
            i = n/(len(self.palette_colors)-1)    
            point = A*(1-i) + B*i
            color_list.append((n, color, point))
        return color_list

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        # painter.fillRect(self.rect(), QColor("#303940"))
        if self.isEnabled():
            if self.type == "SCALAR":
                painter.setClipping(True)
                self.mask(painter, "b")
                self.draw_bar(painter, QColor("#1d2328"))
                self.mask(painter, "a")
                # draw bar
                # A, B = self.get_AB_points()
                # painter.setBrush(QBrush(QColor(self.color)))
                # painter.setPen(QPen(QColor(Qt.black), 1))
                # painter.drawLine(A, B)
                self.draw_bar(painter, Qt.gray)
                # no more mask
                painter.setClipping(False)
            elif self.type == "COLOR":
                # gradient
                gradient_path = QPainterPath()
                rect = self.get_AB_rect()
                rect.adjust(-5, 0, 5, 0)
                gradient_path.addRoundedRect(QRectF(rect), 5, 5)
                painter.setClipping(True)
                painter.setClipRect(self.get_AB_rect())
                painter.fillPath(gradient_path, self.colorGrads)
                painter.setClipping(False)
                h = self.get_AB_rect().height()
                # white corner
                white_rect = self.get_AB_rect()
                white_rect = QRect(self.get_AB_rect().topLeft() - QPoint(h, 0), QSize(h, h))
                painter.setClipping(True)
                painter.setClipRect(white_rect)
                painter.fillPath(gradient_path, Qt.white)
                painter.setClipping(False)
                # black corner
                black_rect = self.get_AB_rect()
                black_rect = QRect(self.get_AB_rect().topRight(), QSize(h, h))
                painter.setClipping(True)
                painter.setClipRect(black_rect)
                painter.fillPath(gradient_path, Qt.black)
                painter.setClipping(False)
            elif self.type == "PALETTE":
                for n, color, point in self.get_color_list_points():
                    pen = QPen(color, self.palette_radius)
                    if n == self.palette_index:
                        pass
                    else:
                        pen.setCapStyle(Qt.RoundCap)
                    painter.setPen(pen)
                    painter.drawPoint(point)

            if not self.flat_look or self.type == "COLOR":
                # draw button
                path = QPainterPath()
                r = QRectF(self.build_hot_rect(float=True))
                path.addEllipse(r)
                painter.setPen(Qt.NoPen)
                offset = 5
                r2 = r.adjusted(offset, offset, -offset, -offset)
                path.addEllipse(r2)
                if not self.flat_look:
                    gradient = QRadialGradient(r.center()-QPoint(0, int(r.height()/3)), self.control_width)
                    gradient.setColorAt(0, QColor(220, 220, 220))
                    gradient.setColorAt(1, QColor(50, 50, 50))
                    painter.setBrush(gradient)
                else:
                    painter.setBrush(QColor(100, 100, 100))
                painter.drawPath(path)
                painter.setBrush(Qt.NoBrush)
                if not self.flat_look:
                    painter.setPen(QPen(QColor(0, 0, 0), 1))
                else:
                    painter.setPen(QPen(QColor(100, 100, 100), 1))
                painter.drawEllipse(r2)
                painter.setPen(QPen(QColor(100, 100, 150), 1))
                painter.drawEllipse(r.adjusted(1,1,-1,-1))
                if self.type == "SCALAR":
                    color = QColor(220, 220, 220)
                    painter.setBrush(color)
                    painter.drawEllipse(r2)
                elif self.type == "COLOR":
                    color = self.get_color()
                    painter.setBrush(color)
                    # r2.moveTop(r2.top()+10)
                    # r2.adjust(1, 1, -1, -1)
                    painter.drawEllipse(r2)
        painter.end()
        super().paintEvent(event)

    def get_color_index(self):
        return self.palette_index

    def get_color(self, value=None):
        if self.type == "PALETTE":
            try:
                return self.palette_colors[self.palette_index]
            except:
                return QColor(255, 0, 0)
        parameter = value if value else self.value
        pos_x = int((self.image.width()-1)*parameter)
        if parameter == 0.0:
            return QColor(255, 255, 255)
        elif parameter == 1.0:
            return QColor(0, 0, 0)
        return QColor(self.image.pixel(pos_x, 1))

    def build_hot_rect(self, float=False):
        A, B = self.get_AB_points()
        center_point = A*(1-self.value) + B*self.value
        if not float:
            _w = int(self.control_width/2)
            return QRect(
                center_point.toPoint() - QPoint(_w, _w),
                QSize(self.control_width, self.control_width)
            )
        else:
            return QRectF(
                center_point - QPointF(self.control_width/2, self.control_width/2),
                QSizeF(self.control_width, self.control_width)
            )

    def build_click_rect(self):
        A, B = self.get_AB_points()
        a = A.toPoint() - QPoint(int(self.control_width/2), int(self.control_width/2))
        b = B.toPoint() + QPoint(int(self.control_width/2), int(self.control_width/2))
        return QRect(a, b)

    def set_value(self, event):
        A, B = self.get_AB_points()
        P = event.pos()
        AB = B - A
        AP = P - A
        # SCALAR, COLOR
        self.raw_value = dot(AP, AB)/dot(AB, AB)
        self.value = min(max(self.raw_value, 0.0), 1.0)
        # PALETTE
        if self.type == 'PALETTE':
            for n, color, point in self.get_color_list_points():
                Pp = P - point
                l = math.sqrt(dot(Pp, Pp))
                if l < self.palette_radius*2:
                    self.palette_index = n

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.set_value(event)
            if self.build_hot_rect().contains(event.pos()):
                self.changing = True
        self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            if self.changing:
                self.set_value(event)
        self.update()
        self.value_changed.emit()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.changing = False
            # for simple click
            if self.build_click_rect().contains(event.pos()):
                self.set_value(event)
        self.update()
        self.value_changed.emit()
        super().mouseReleaseEvent(event)

def main():
    app = QApplication(sys.argv)
    w = QWidget()
    w.resize(500, 300)
    style = "background: gray;"
    w.setStyleSheet(style)

    l = QVBoxLayout()
    l.addWidget(
        CustomSlider('COLOR', 400, 1.0, False))
    l.addWidget(
        CustomSlider('SCALAR', 400, 1.0, False))
    l.addWidget(
        CustomSlider('COLOR', 400, 1.0, True))
    l.addWidget(
        CustomSlider('SCALAR', 400, 1.0, True))
    l.addWidget(
        CustomSlider('PALETTE', 400, 2, True))

    w.setLayout(l)


    w.show()
    app.exec()

if __name__ == '__main__':
    main()
