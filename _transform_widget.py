# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
#  Author: Sergei Krumas (github.com/sergkrumas)
#
# ##### END GPL LICENSE BLOCK #####

from PyQt5.QtWidgets import (QHBoxLayout, QVBoxLayout, QWidget, QMessageBox, QDesktopWidget, QApplication, QRadioButton)
from PyQt5.QtCore import (QRectF, QPoint, pyqtSignal, QSizeF, Qt, QPointF, QSize, QRect)
from PyQt5.QtGui import (QWindow, QPixmap, QBrush, QRegion, QImage, QRadialGradient, QColor,
                    QGuiApplication, QPen, QPainterPath, QPolygon, QLinearGradient, QPainter)

from _utils import (dot, elements45DegreeConstraint)

import sys
import math

__all__ = (
    # 'TransformWidgetPoint',
    'TransformWidget'
)

class TransformWidgetPoint():

    def __init__(self, point, name, _type):
        self.SIZE = 10
        self.set_pos(point)
        self.old_pos = point
        self.start_pos = point
        self.name = name
        self.type = _type

    def set_pos(self, point):
        self.point = point
        self.hit_region = QRect(0, 0, self.SIZE*2, self.SIZE*2)
        self.hit_region.moveCenter(self.point)
        self.display_region = QRect(0, 0, self.SIZE, self.SIZE)
        self.display_region.moveCenter(self.point)

    def display_rect(self):
        return self.display_region

    def hit_rect(self):
        return self.hit_region

class TransformWidget():
    # A---------C
    # |         |
    # |         |
    # |    x    |
    # |         |
    # |         |
    # D---------B
    def get_bounding_rect_from_corners(self):
        MAX = sys.maxsize
        left = MAX
        right = -MAX
        top = MAX
        bottom = -MAX
        for p in self.corners:
            p = p.point
            left = min(p.x(), left)
            right = max(p.x(), right)
            top = min(p.y(), top)
            bottom = max(p.y(), bottom)
        return QRect(QPoint(left, top), QPoint(right, bottom))

    def restore_points_positions(self, r=None):
        if r:
            bounding_rect = r
        else:
            bounding_rect = self.get_bounding_rect_from_corners()
        self.pA.set_pos(bounding_rect.topLeft())
        self.pB.set_pos(bounding_rect.bottomRight())
        self.pC.set_pos(bounding_rect.topRight())
        self.pD.set_pos(bounding_rect.bottomLeft())

        self.pCenter.set_pos(bounding_rect.center())

        self.peAC.set_pos(self.pA.point*.5+self.pC.point*.5)
        self.peCB.set_pos(self.pC.point*.5+self.pB.point*.5)
        self.peBD.set_pos(self.pB.point*.5+self.pD.point*.5)
        self.peDA.set_pos(self.pD.point*.5+self.pA.point*.5)

    def __init__(self, input_data, center_point_only=False):
        self.line_mode = False
        self.center_point_only = center_point_only
        if isinstance(input_data, QRect):
            self.line_mode = False
            bounding_rect = input_data
            self.pA = TransformWidgetPoint(bounding_rect.topLeft(), "A", "corner")
            self.pB = TransformWidgetPoint(bounding_rect.bottomRight(), "B", "corner")
            self.pC = TransformWidgetPoint(bounding_rect.topRight(), "C", "corner")
            self.pD = TransformWidgetPoint(bounding_rect.bottomLeft(), "D", "corner")
            self.pCenter = TransformWidgetPoint(bounding_rect.center(), "x", "center")
            self.peAC = TransformWidgetPoint(self.pA.point*.5+self.pC.point*.5, "ac", "edge")
            self.peCB = TransformWidgetPoint(self.pC.point*.5+self.pB.point*.5, "cb", "edge")
            self.peBD = TransformWidgetPoint(self.pB.point*.5+self.pD.point*.5, "bd", "edge")
            self.peDA = TransformWidgetPoint(self.pD.point*.5+self.pA.point*.5, "da", "edge")
        elif isinstance(input_data, tuple):
            self.line_mode = True
            a, b = input_data[0], input_data[1]
            if isinstance(a, QPointF):
                a = a.toPoint()
            if isinstance(b, QPointF):
                b = b.toPoint()
            self.pA = TransformWidgetPoint(a, "A", "corner")
            self.pB = TransformWidgetPoint(b, "B", "corner")
            self.pCenter = TransformWidgetPoint(a*0.5 + b*0.5, "x", "center")
        else:
            raise Exception("Unsupported data")
        if self.line_mode:
            self.corners = [
                self.pA,
                self.pB,
            ]
            self.edge_points = []
        else:
            self.corners = [
                self.pA,
                self.pB,
                self.pC,
                self.pD
            ]
            self.edge_points = [
                self.peAC,
                self.peCB,
                self.peBD,
                self.peDA
            ]
        self.points = []
        self.points.extend(self.corners)
        self.points.extend(self.edge_points)
        self.points.append(self.pCenter)

        self.br_aspect_ratio = self.get_bounding_rect_from_corners()
        if self.br_aspect_ratio.width() != 0:
            self.aspect_ratio = self.br_aspect_ratio.width()/self.br_aspect_ratio.height()
        else:
            self.aspect_ratio = 1.0

        self.current_point = None
        # scale_mode выключен по той причине, что из-за действий пользователя
        # хотя бы по одной из осей прямоугольник может схлопнутся, а то даже и сразу по двум
        # и тогда все точки виджета потеряют своё относительное положение, чего желательно избежать
        self.scale_mode = False
        # при выставлении в True меняет отрисовку на более информативную
        self.debug_mode = False

    def get_pivot_point(self):
        if not self.line_mode:
            # corners
            pair1 = [self.pA, self.pB]
            pair2 = [self.pC, self.pD]
            # edge points
            pair3 = [self.peAC, self.peBD]
            pair4 = [self.peCB, self.peDA]
        else:
            pair1 = [self.pA, self.pB]
            pair2 = []
            pair3 = []
            pair4 = []
        # checking
        for pair in [pair1, pair2, pair3, pair4]:
            if self.current_point in pair:
                pair.remove(self.current_point)
                return pair[0]
        return None

    def control_point_under_mouse(self, event_pos, delta_info=False):
        self.current_point = None
        for c in self.points:
            c.old_pos = c.start_pos = c.point
        # проверка точек
        if not self.center_point_only:
            for c in self.corners:
                if c.hit_rect().contains(event_pos):
                    self.current_point = c
                    break
            if not self.current_point:
                for c in self.edge_points:
                    if c.hit_rect().contains(event_pos):
                        self.current_point = c
                        break
        if not self.current_point:
            c = self.pCenter
            if c.hit_rect().contains(event_pos):
                self.current_point = c

        if self.scale_mode:
            rect = self.get_bounding_rect_from_corners()
            if rect.width() < 10 or rect.height() < 10:
                r = QRect(QPoint(0, 0), QSize(100, 100))
                r.moveCenter(rect.topLeft())
                self.restore_points_positions(r=r)
                self.current_point = self.pCenter
        if delta_info:
            return self.current_point, self.pCenter
        else:
            return self.current_point

    def retransform(self, event):
        points = self.points[:]
        # для центральной точки
        if self.current_point == self.pCenter:
            c = self.current_point
            delta = c.old_pos - event.pos()
            new_pos = c.point + event.pos() - c.old_pos
            c.set_pos(new_pos)
            c.old_pos = event.pos()
            points.remove(self.pCenter)
            for c in points:
                c.set_pos(c.point - delta)
                c.old_pos = c.point
        # для всех точек кроме центральной
        if self.current_point != self.pCenter:
            event_pos = event.pos()
            shift_mod = bool(QApplication.queryKeyboardModifiers() & Qt.ShiftModifier)
            ctrl_mod = bool(QApplication.queryKeyboardModifiers() & Qt.ControlModifier)
            if shift_mod and ctrl_mod:
                # 45 градусов. для контента типа пикч и прочего даёт квадратные размеры
                pp = self.get_pivot_point().point
                event_pos = elements45DegreeConstraint(pp, event_pos).toPoint()
            if shift_mod and not ctrl_mod:
                # для пропорционального редактирования
                pp = self.get_pivot_point().point
                delta = pp - event.pos()
                sign = math.copysign(1.0, delta.x())
                if delta.y() < 0:
                    if delta.x() < 0:
                        sign = 1.0
                    else:
                        sign = -1.0
                delta.setX(int(delta.y()*sign*self.aspect_ratio))
                event_pos = pp - delta
            new_pos = self.current_point.point + event_pos - self.current_point.old_pos
            if self.current_point.type == "edge":
                if self.current_point in [self.peAC, self.peBD]:
                    new_pos.setX(self.current_point.point.x())
                elif self.current_point in [self.peCB, self.peDA]:
                    new_pos.setY(self.current_point.point.y())
            self.current_point.set_pos(new_pos)
            self.current_point.old_pos = event_pos
            # изменение положения неактивных точек
            if self.scale_mode:
                # поддержка режима с изъёбствами
                pivot = self.get_pivot_point()
                points.remove(self.current_point)
                if pivot:
                    points.remove(pivot)
                try:
                    start_x = self.current_point.start_pos.x()
                    factor_x = (new_pos.x()-pivot.point.x())/(start_x-pivot.point.x())
                except ZeroDivisionError:
                    factor_x = 1
                try:
                    start_y = self.current_point.start_pos.y()
                    factor_y = (new_pos.y()-pivot.point.y())/(start_y-pivot.point.y())
                except ZeroDivisionError:
                    factor_y = 1
                for c in points:
                    c.set_pos(c.start_pos-pivot.point)
                    c.set_pos(QPoint(c.point.x()*factor_x, c.point.y()*factor_y))
                    c.set_pos(c.point+pivot.point)
                    c.old_pos = c.point
            else:
                # обычный режим без изъёбств
                if not self.center_point_only:
                    if not self.line_mode and self.current_point in [self.pA, self.pB]:
                        self.pC.set_pos(QPoint(self.pB.point.x(), self.pA.point.y()))
                        self.pD.set_pos(QPoint(self.pA.point.x(), self.pB.point.y()))
                    if not self.line_mode and self.current_point in [self.pC, self.pD]:
                        self.pB.set_pos(QPoint(self.pC.point.x(), self.pD.point.y()))
                        self.pA.set_pos(QPoint(self.pD.point.x(), self.pC.point.y()))
            # восстанавливаем позиции точек
            if len(self.corners) > 2:
                if self.current_point != self.pA:
                    pos = QPoint(self.peDA.point.x(), self.peAC.point.y())
                    self.pA.set_pos(pos)
                if self.current_point != self.pB:
                    pos = QPoint(self.peCB.point.x(), self.peBD.point.y())
                    self.pB.set_pos(pos)
                if self.current_point != self.pC:
                    pos = QPoint(self.peCB.point.x(), self.peAC.point.y())
                    self.pC.set_pos(pos)
                if self.current_point != self.pD:
                    pos = QPoint(self.peDA.point.x(), self.peBD.point.y())
                    self.pD.set_pos(pos)
                if self.current_point != self.peAC:
                    self.peAC.set_pos(self.pA.point*.5+self.pC.point*.5) # hor
                if self.current_point != self.peCB:
                    self.peCB.set_pos(self.pC.point*.5+self.pB.point*.5) # ver
                if self.current_point != self.peBD:
                    self.peBD.set_pos(self.pB.point*.5+self.pD.point*.5) # hor
                if self.current_point != self.peDA:
                    self.peDA.set_pos(self.pD.point*.5+self.pA.point*.5) # ver
            center_pos = self.get_bounding_rect_from_corners().center()
            self.pCenter.set_pos(center_pos)

    def retransform_end(self, event):
        self.current_point = None

    def draw_widget(self, painter):
        if self.debug_mode:
            # отрисовка рамки
            pen = QPen(Qt.gray, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.get_bounding_rect_from_corners())
        # отрисовка точек и буковок
        painter.setBrush(QBrush(Qt.white))
        painter.setPen(QPen(Qt.red, 1))
        font = painter.font()
        font.setPixelSize(20)
        painter.setFont(font)
        pivot = self.get_pivot_point()
        points = self.points[:]
        default_pen = QPen(QColor(220, 220, 220), 1)
        default_pen_red = QPen(QColor(220, 0, 0), 3)
        default_brush = QBrush(Qt.black)
        default_brush_red = QBrush(QColor(220, 0, 0))
        for c in points:
            if self.debug_mode:
                if c == pivot:
                    painter.setPen(Qt.green)
                elif c == self.current_point:
                    painter.setPen(Qt.red)
                elif c.type == "edge":
                    painter.setPen(Qt.blue)
                else:
                    painter.setPen(Qt.black)
                painter.drawRect(c.hit_region)
                if c == self.pCenter:
                    r = c.hit_rect().adjusted(-20, -20, 20, 20)
                else:
                    r = c.hit_rect().adjusted(-10, -10, 10, 10)
                painter.drawText(r, Qt.AlignCenter, c.name)
            else:
                if self.center_point_only and c != self.pCenter:
                    continue
                if c == self.current_point:
                    painter.setBrush(default_brush_red)
                else:
                    painter.setBrush(default_brush)
                painter.setPen(default_pen)
                if c == self.pCenter:
                    dr = c.display_rect()
                    dr = dr.adjusted(2, 2, -2, -2)
                    a, b = dr.topLeft(), dr.bottomRight()
                    e, f = dr.topRight(), dr.bottomLeft()
                    painter.setPen(QPen(Qt.white, 5))
                    painter.drawLine(a, b)
                    painter.drawLine(e, f)
                    if c == self.current_point:
                        painter.setPen(default_pen_red)
                    else:
                        painter.setPen(QPen(Qt.black, 3))
                    painter.drawLine(a, b)
                    painter.drawLine(e, f)
                else:
                    painter.drawEllipse(c.display_rect())
        painter.setBrush(Qt.NoBrush)

class TransformWidgetAdvanced():
    # TODO: полноценный виджет для:
        # - перемещения
        # - масштабирования по всем осям или отдельно по каждой из двух осей
        # - вращения вокруг пивота
    pass

def main():
    pass

if __name__ == '__main__':
    main()
