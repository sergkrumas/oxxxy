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

from collections import namedtuple
from enum import Enum
import datetime
import sys
import os
import subprocess
import time
import ctypes
import itertools
import traceback
import locale
import argparse
import importlib.util
import math

import pyperclip
from pynput import keyboard

from PyQt5.QtWidgets import (QSystemTrayIcon, QWidget, QMessageBox, QMenu, QGraphicsPixmapItem,
    QGraphicsScene, QFileDialog, QHBoxLayout, QCheckBox, QVBoxLayout, QTextEdit, QGridLayout,
    QPushButton, QGraphicsBlurEffect, QLabel, QApplication, QScrollArea, QDesktopWidget)
from PyQt5.QtCore import (QUrl, QMimeData, pyqtSignal, QPoint, QPointF, pyqtSlot, QRect, QEvent,
    QTimer, Qt, QSize, QRectF, QThread)
from PyQt5.QtGui import (QPainterPath, QColor, QKeyEvent, QMouseEvent, QBrush, QPixmap,
    QPaintEvent, QPainter, QWindow, QPolygon, QImage, QTransform, QPen, QLinearGradient,
    QIcon, QFont, QCursor, QPolygonF)


from _utils import (convex_hull, check_scancode_for, SettingsJson,
     generate_metainfo, build_valid_rect, dot, get_nearest_point_on_rect, get_creation_date,
     find_browser_exe_file, open_link_in_browser, open_in_google_chrome, save_meta_info,
     make_screenshot_pyqt, webRGBA, generate_gradient, draw_shadow, draw_cyberpunk,
     elements45DegreeConstraint)

from _sliders import (CustomSlider,)
from _transform_widget import (TransformWidget,)
from on_windows_startup import is_app_in_startup, add_to_startup, remove_from_startup

class Globals():
    DEBUG = True
    DEBUG_ELEMENTS = False
    CRUSH_SIMULATOR = False

    DEBUG_VIZ = False
    DEBUG_ANALYSE_CORNERS_SPACES = False

    AFTERCRUSH = False
    RUN_ONCE = False
    FULL_STOP = False

    ENABLE_FLAT_EDITOR_UI = False

    SCREENSHOT_FOLDER_PATH = ""

    VERSION_INFO = "v0.91"
    AUTHOR_INFO = "by Sergei Krumas"

    background_threads = []

def get_screenshot_filepath(params):
    return os.path.join(Globals.SCREENSHOT_FOLDER_PATH, f"{params}.png")

RegionInfo = namedtuple('RegionInfo', 'setter coords getter')

class QPoint(QPoint): #overriding default QPoint
    def __bool__(self):
        # ?????? ?????????????? ?????????? ??????????????, ?????? ???????????????????? ???????????????????? ??????????,
        # ?????????? ?????? ???????????????????? QPoint(0, 0) ?????? bool ???????????? ???????????????????????? True.
        # ???????????????? ?????????? ?????????????????? ???????????????????????? ?? ???????????? if
        return True

class LayerOpacity(Enum):
    FullTransparent = 1
    HalfTransparent = 2
    Opaque = 3

class RequestType(Enum):
    Fragment = 0
    Fullscreen = 1
    QuickFullscreen = 2
    Editor = 3

class CheckBoxCustom(QCheckBox):

    def __init__(self, *args):
        super().__init__(*args)
        self.stateChanged.connect(self.state_changed)

    def paintEvent(self, event):
        if self.isEnabled():
            super(type(self), self).paintEvent(event)

    def state_changed(self, int_value):
        self.update()
        if self.parent():
            self.parent().update()
            self.parent().on_parameters_changed()

class CustomPushButton(QPushButton):
    right_clicked = pyqtSignal()
    def __init__(self, *args, tool_id=False, checkable=False, checked=True):
        super().__init__(*args)

        self.setCheckable(checkable)
        self.setChecked(checked)

        if tool_id == "done":
            self.BUTTON_SIZE = 65
        else:
            self.BUTTON_SIZE = 50

        self.setFixedWidth(self.BUTTON_SIZE)
        self.setFixedHeight(self.BUTTON_SIZE)

        self.setProperty("tool_id", tool_id)

        self.small_d = 1.5

        self._draw_checked = True
        self.pixmap_checked = QPixmap(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.pixmap_checked.fill(Qt.transparent)
        painter = QPainter()
        painter.begin(self.pixmap_checked)
        painter.setRenderHint(QPainter.Antialiasing)
        self.draw_button(painter)
        painter.end()

        self._draw_checked = False
        self.pixmap = QPixmap(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.pixmap.fill(Qt.transparent)
        painter = QPainter()
        painter.begin(self.pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        self.draw_button(painter)
        painter.end()

        if tool_id in ["forwards", "backwards"]:
            self.setFixedWidth(int(self.BUTTON_SIZE/self.small_d))
            self.setFixedHeight(int(self.BUTTON_SIZE/self.small_d))

    def mouseReleaseEvent(self, event):
        select_window = self.parent().select_window
        if select_window and select_window.isVisible():
            select_window.hide()
        if event.button() == Qt.RightButton:
            self.right_clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        tool_id = self.property("tool_id")
        painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if self.underMouse() and tool_id not in ["forwards", "backwards"]:
            r = self.rect()
            if self.property("tool_id") == "done":
                RADIUS = 5
            else:
                RADIUS = 10
            path = QPainterPath()
            path.addRoundedRect(QRectF(r), RADIUS, RADIUS)
            painter.setPen(QPen(QColor(150, 150, 150), 1))

            gradient = QLinearGradient(self.rect().topLeft(), self.rect().bottomLeft())
            c1 = QColor(220, 142, 3)
            h = s = l = a = 0
            h, s, l, a = c1.getHsl()
            c1.setHsl(h, s, 150)
            c2 = QColor(253, 203, 54)
            gradient.setColorAt(1, c1)
            gradient.setColorAt(0, c2)
            painter.setPen(Qt.NoPen)
            brush = QBrush(gradient)
            painter.setBrush(brush)
            painter.drawPath(path)

        if tool_id in ["oval", "rect", "line"]:
            # ?????? ???????????? ???????????? ?????????????? ????-???? ????????,
            # ?????? ?????????????? ?????????????? Ctrl ???????????????????????? ???? ??????????????????
            self._draw_checked = self.isChecked()
            self.draw_button(painter)
        else:
            src_rect = QRect(0, 0, self.BUTTON_SIZE, self.BUTTON_SIZE)
            forwards_backwards_btns = tool_id in ["forwards", "backwards"]
            if forwards_backwards_btns:
                rect_w = int(self.BUTTON_SIZE/self.small_d)
                trgt_rect = QRect(0, 0, rect_w, rect_w)
                flag = self.isEnabled()
            elif tool_id == "done":
                trgt_rect = QRect(0, 0, self.BUTTON_SIZE, self.BUTTON_SIZE)
                flag = self.underMouse()
            else:
                trgt_rect = QRect(0, 0, self.BUTTON_SIZE, self.BUTTON_SIZE)
                flag = self.isChecked()
            pixmap = self.pixmap_checked if flag else self.pixmap
            if forwards_backwards_btns:
                if self.underMouse():
                    painter.setOpacity(1.0)
                else:
                    painter.setOpacity(.8)
            painter.drawPixmap(trgt_rect, pixmap, src_rect)
            painter.setOpacity(1.0)
        painter.end()

    def draw_button(self, painter):
        tool_id = self.property("tool_id")
        bf_buttons = tool_id in ["forwards", "backwards"]

        # draw back
        gradient = QLinearGradient(self.rect().topLeft(), self.rect().bottomLeft())
        if tool_id == "done":
            a = QColor(253, 203, 54)
            b = QColor(94, 203, 247)
            if self._draw_checked:
                gradient.setColorAt(1, QColor(220, 142, 3))
                gradient.setColorAt(0, a)
            else:
                gradient.setColorAt(1, QColor(25, 133, 175))
                gradient.setColorAt(0, b)

            painter.setPen(Qt.NoPen)
            if Globals.ENABLE_FLAT_EDITOR_UI:
                if self._draw_checked:
                    brush = QBrush(a)
                else:
                    brush = QBrush(b)
            else:
                brush = QBrush(gradient)
            painter.setBrush(brush)
        else:
            c = QColor(100, 121, 121)
            gradient.setColorAt(0, QColor(82, 82, 82))
            gradient.setColorAt(1, c)
            painter.setPen(Qt.NoPen)
            if Globals.ENABLE_FLAT_EDITOR_UI:
                brush = QBrush(c)
            else:
                brush = QBrush(gradient)
            painter.setBrush(brush)

        if tool_id == "done" or (self._draw_checked and not bf_buttons):
            r = self.rect()
            if self.property("tool_id") == "done":
                RADIUS = 5
            else:
                RADIUS = 10
            path = QPainterPath()
            path.addRoundedRect(QRectF(r), RADIUS, RADIUS)
            painter.drawPath(path)

        modifiers = QApplication.queryKeyboardModifiers()

        if bf_buttons:
            if self._draw_checked:
                main_color = QColor(220, 220, 220)
            else:
                main_color = QColor(80, 80, 80)
            second_color = Qt.gray
            second_color2 = QColor(220, 220, 220)
            second_color3 = QColor(220, 220, 220)
        elif tool_id == "done":
            main_color = QColor(255, 255, 255)
        else:
            if self._draw_checked:
                main_color = Qt.white
                second_color = Qt.gray
                second_color2 = QColor(100, 100, 100)
                second_color3 =  QColor(100, 100, 100)
            else:
                main_color = QColor(100, 100, 100)
                second_color = QColor(220, 220, 220)
                second_color2 = QColor(220, 220, 220)
                second_color3 = QColor(220, 220, 220)

        painter.setBrush(QBrush(main_color))
        painter.setPen(QPen(main_color))

        w = self.BUTTON_SIZE
        w2 = self.BUTTON_SIZE/2

        def set_font(pr, weight, pixel_size=50, family=None):
            font = pr.font()
            font.setPixelSize(pixel_size)
            font.setWeight(weight)
            if family:
                font.setFamily(family)
            pr.setFont(font)

        if tool_id == "drag":

            transform = QTransform()
            transform.translate(w2, w2)
            transform.rotate(45)
            painter.setTransform(transform)
            painter.drawLine(-w2, -w2, w, w)

        elif tool_id == "done":

            pen = QPen(main_color, 6)
            painter.setPen(pen)
            y_offset = 6
            x_offset = 3
            painter.drawLine(
                QPointF(w2-x_offset, w2+y_offset),
                QPointF(w2+15-x_offset, w2-15+y_offset)
            )
            painter.drawLine(
                QPointF(w2-x_offset, w2+y_offset),
                QPointF(w2-7-x_offset, w2-7+y_offset)
            )

        elif tool_id == "backwards":

            main_offset = QPointF(5, 0)
            pos3y = 20
            points = QPolygon([
                main_offset.toPoint() + QPoint(5, pos3y),
                main_offset.toPoint() + QPoint(15, pos3y-10),
                main_offset.toPoint() + QPoint(15, pos3y+10),
            ])
            painter.drawPolygon(points)

            offset = QPointF(-6, 6)
            bottom_point = QPointF(w2+5, w/4*3)
            points = [
                QPointF(15, pos3y-5),
                QPointF(w2, w2-15)+offset,
                QPointF(w2+15, w2-15)+offset,
                bottom_point
            ]
            points = [p + main_offset for p in points]
            start_point, c1, c2, end_point = points
            myPath = QPainterPath()
            myPath.moveTo(start_point)
            myPath.cubicTo(c1, c2, end_point)

            points = [
                QPointF(15, pos3y+9),
                QPointF(w2-10, w2-10)+offset,
                QPointF(w2+10, w2-10)+offset,
                bottom_point + QPointF(-1.0, 0.0)
            ]
            points = [p + main_offset for p in points]
            start_point, c1, c2, end_point = points
            myPath.lineTo(end_point)
            myPath.cubicTo(c2, c1, start_point)
            painter.drawPath(myPath)

        elif tool_id == "forwards":

            main_offset = QPointF(-5, 0)
            pos3y = 20
            offset = QPointF(6, 6)
            bottom_point = QPointF(w2-5, w/4*3)
            points = [
                QPointF(35, pos3y-5),
                QPointF(w2, w2-15)+offset,
                QPointF(w2-15, w2-15)+offset,
                bottom_point
            ]
            points = [p + main_offset for p in points]
            start_point, c1, c2, end_point = points
            myPath = QPainterPath()
            myPath.moveTo(start_point)
            myPath.cubicTo(c1, c2, end_point)

            points = [
                QPointF(35, pos3y+9),
                QPointF(w2+10, w2-10)+offset,
                QPointF(w2-10, w2-10)+offset,
                bottom_point + QPointF(1.0, 0.0)
            ]
            points = [p + main_offset for p in points]
            start_point, c1, c2, end_point = points
            myPath.lineTo(end_point)
            myPath.cubicTo(c2, c1, start_point)

            points = QPolygon([
                main_offset.toPoint() + QPoint(45, pos3y),
                main_offset.toPoint() + QPoint(35, pos3y-10),
                main_offset.toPoint() + QPoint(35, pos3y+10),
            ])
            painter.drawPolygon(points)

            painter.drawPath(myPath)

        elif tool_id == "transform":

            painter.setPen(QPen(main_color, 3))

            for a in [0, 90, 180, -90]:
                transform = QTransform()
                transform.translate(w2, w2)
                transform.rotate(a)
                painter.setTransform(transform)
                # arrow
                painter.drawLine(QPointF(0, 0), QPointF(w2/2, 0))
                painter.drawLine(QPointF(w2/3, 4), QPointF(w2/2, 0))
                painter.drawLine(QPointF(w2/3, -4), QPointF(w2/2, 0))

                painter.resetTransform()

            painter.setPen(QPen(main_color, 4))
            radius = 2
            painter.drawEllipse(int(w2-radius), int(w2-radius), radius*2, radius*2)

        elif tool_id == "pen":

            offset = self.BUTTON_SIZE/2
            painter.setPen(Qt.NoPen)
            _offset = 45
            pos1y = 6 - _offset
            pos2y = 15 - _offset
            pos3y = 40 - _offset
            # pos1y = 6
            # pos2y = 15
            # pos3y = 40
            # painter.translate(20,0)
            transform = QTransform()
            transform.translate(10, 40)
            transform.rotate(45)
            painter.setTransform(transform)
            painter.drawRect(-5, pos1y, 10, 6)
            painter.drawRect(-5, pos2y, 10, 20)
            points = QPolygon([
                QPoint(4, pos3y),
                QPoint(-4, pos3y),
                QPoint(0, pos3y+5),
                QPoint(0, pos3y+5),
            ])
            painter.drawPolygon(points)

        elif tool_id == "marker":

            offset = self.BUTTON_SIZE/2
            painter.setPen(Qt.NoPen)
            _offset = 45
            # _offset = 0
            pos1y = 6 - _offset
            pos2y = 15 - _offset
            pos3y = 45 - _offset

            transform = QTransform()
            transform.translate(12, 40)
            transform.rotate(45)
            painter.setTransform(transform)

            points = QPolygon([
                QPoint(-9, pos1y+25),
                QPoint(9, pos1y+25),
                QPoint(5, pos1y),
                QPoint(-5, pos1y),
            ])
            painter.drawPolygon(points)

            rectangle = QRectF(-9.0, pos1y+25.0, 18.0, 10.0)
            a = 150
            spanAngle =  (a+90) * 16
            startAngle = a * 16
            painter.drawChord(rectangle, startAngle, spanAngle)

            rectangle = QRectF(-4.0, pos1y+30.0, 8.0, 7.0)
            painter.drawRect(rectangle)

            points = QPolygon([
                QPoint(3, pos3y),
                QPoint(-3, pos3y),
                QPoint(-3, pos3y+5),
            ])
            painter.drawPolygon(points)

            painter.setPen(QPen(QColor(second_color), 3))
            painter.drawLine(QPoint(-5, pos1y+21), QPoint(-3, pos1y+3))

        elif tool_id == "line":

            r = self.rect()
            painter.setPen(QPen(QColor(main_color), 3))
            r.adjust(10, 10, -10, -10)
            if modifiers & Qt.ControlModifier:
                p1 = r.bottomLeft()
                p2 = p1 + QPoint(10, -20)
                p3 = p2 + QPoint(10, 10)
                p4 = r.topRight()
                painter.drawLine(p1, p2)
                painter.drawLine(p2, p3)
                painter.drawLine(p3, p4)
            else:
                painter.drawLine(r.bottomLeft(), r.topRight())

        elif tool_id == "arrow":

            r = self.rect()
            painter.setPen(QPen(QColor(main_color), 3))
            r.adjust(10, 10, -10, -10)
            painter.drawLine(r.bottomLeft(), r.topRight())
            painter.drawLine(r.bottomLeft(), r.topRight())
            radius = 1
            painter.drawEllipse(r.bottomLeft(), radius*2, radius*2)

            painter.setPen(Qt.NoPen)
            c = r.topRight()
            c -= QPoint(4, -4)
            points = QPolygon([
                c,
                c + QPoint(-13, 0),
                c + QPoint(8, -8),
                c + QPoint(0, 13),
            ])
            painter.drawPolygon(points)

        elif tool_id == "text":

            set_font(painter, 1900, pixel_size=30)
            painter.setPen(QPen(main_color))
            painter.drawText(self.rect().adjusted(5, 5, -5, -5), Qt.AlignCenter, "A")

        elif tool_id == "oval":

            if not modifiers & Qt.ControlModifier:
                painter.setBrush(Qt.NoBrush)

            painter.setPen(QPen(QColor(main_color), 3))
            painter.drawEllipse(self.rect().adjusted(10,10,-10,-10))

        elif tool_id == "rect":

            if not modifiers & Qt.ControlModifier:
                painter.setBrush(Qt.NoBrush)

            pen = QPen(QColor(main_color), 3)
            pen.setJoinStyle(Qt.MiterJoin)
            painter.setPen(pen)
            painter.drawRect(self.rect().adjusted(10, 10, -10, -10))

        elif tool_id == "numbering":

            painter.setPen(QPen(second_color2))
            r0 =  self.rect().adjusted(12, 12, -12, -12)
            r0.moveTop(15)

            r1 = r0.translated(4, -4)
            r1.adjust(0, 0, -3, -3)
            r2 = r0.translated(10, -8)
            r2.adjust(0, 0, -8, -8)

            painter.drawEllipse(r2)
            painter.drawEllipse(r1)

            painter.drawEllipse(r0)
            set_font(painter, 2000, pixel_size=20, family="Arial")
            painter.drawText(r0, Qt.AlignCenter, "1")

        elif tool_id == "blurring":

            offset = 6
            r = QRectF(w2, offset, w2-offset, w-offset*2)

            set_font(painter, 1900, pixel_size=30)

            painter.setClipping(True)
            painter.setClipRect(QRectF(0, 0, w2, w))

            painter.setPen(QPen(main_color))
            painter.drawText(self.rect().adjusted(5, 5, -5, -5), Qt.AlignCenter, "A")

            painter.setClipping(False)

            pppp = QPixmap(self.rect().width(), self.rect().height())
            not_blurred_pix = pppp
            not_blurred_pix.fill(Qt.transparent)
            p = QPainter(not_blurred_pix)
            set_font(p, 1900, pixel_size=30)
            p.setPen(QPen(main_color))
            p.drawText(self.rect().adjusted(5, 5, -5, -5), Qt.AlignCenter, "A")
            del p

            new_pixmap = QPixmap(self.rect().width(), self.rect().height())
            new_pixmap.fill(Qt.transparent)
            pix = self.apply_blur_effect(not_blurred_pix, new_pixmap)

            painter.drawPixmap(r, pix, r)

            painter.setBrush(Qt.NoBrush)
            pen = QPen(main_color)
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(r)

        elif tool_id == "darkening":

            r = self.rect().adjusted(5, 5, -5, -5)
            RADIUS = 5
            path = QPainterPath()
            path.addRoundedRect(QRectF(r), RADIUS, RADIUS)
            painter.drawPath(path)

            brush = QBrush(second_color3)
            painter.setBrush(brush)
            painter.setPen(Qt.NoPen)
            rect = r.adjusted(5, 3, -15, -25)
            painter.drawRect(rect)
            rect = r.adjusted(10, 8, -11, -15)
            painter.drawRect(rect)

        elif tool_id == "stamp":

            w_ = 4
            pen = QPen(main_color, w_)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            r = self.rect().adjusted(5, 5, -5, -5)
            painter.drawEllipse(r)
            c = r.center()
            half_w = w_/2-1
            painter.setClipping(True)
            path = QPainterPath()
            path.addRect(QRectF(self.rect().adjusted(17, 17, -17, -17)))
            path.addRect(QRectF(self.rect().adjusted(20, 20, -20, -20)))
            path.addRect(QRectF(self.rect()))
            painter.setClipPath(path)
            painter.drawLine(c+QPoint(int(half_w), int(-18)), c+QPoint(int(half_w), int(18)))
            painter.drawLine(c+QPoint(int(-18), int(half_w)), c+QPoint(int(18), int(half_w)))
            painter.setClipping(False)

        elif tool_id == "zoom_in_region":

            rect = self.rect().adjusted(5, 5, -20, -20)
            w_ = 3
            painter.setPen(QPen(main_color, w_))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(rect)
            painter.drawLine(
                rect.topLeft()/2 + rect.topRight()/2 + QPoint(0, 6),
                rect.bottomLeft()/2 + rect.bottomRight()/2 + QPoint(0, -6)
            )
            painter.drawLine(
                rect.topLeft()/2 + rect.bottomLeft()/2 + QPoint(6, 0),
                rect.topRight()/2 + rect.bottomRight()/2 + QPoint(-6, 0)
            )
            w_ = 6
            pen = QPen(main_color, w_)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.setClipping(True)
            path = QPainterPath()
            path.addRect(QRectF(self.rect()))
            path.addEllipse(QRectF(rect))
            painter.setClipPath(path)
            painter.drawLine(
                rect.bottomRight() - QPoint(10, 10),
                self.rect().bottomRight() - QPoint(8, 8)
            )
            painter.setClipping(False)

        elif tool_id == "copypaste":

            pen = QPen(main_color, 1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            set_font(painter, 1900, pixel_size=12)
            painter.drawText(QPoint(2, 25), "COPY")
            painter.drawText(QPoint(5, 36), "PASTE")

    def apply_blur_effect(self, src_pix, pix, blur_radius=5):
        effect = QGraphicsBlurEffect()
        effect.setBlurRadius(blur_radius)
        scene = QGraphicsScene()

        item = QGraphicsPixmapItem()
        item.setPixmap(src_pix)

        item.setGraphicsEffect(effect)
        scene.addItem(item)

        p = QPainter(pix)
        scene.render(p, QRectF(), QRectF(0, 0, src_pix.width(), src_pix.height()))
        del p
        del scene

        return pix

class StampSelectButton(QPushButton):
    def __init__(self, stamp_data, button_size, main_window, *args):
        super().__init__(*args)
        self.stamp_data = stamp_data
        self.main_window = main_window
        self.setFixedHeight(button_size)
        self.setFixedWidth(button_size)

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        painter.setRenderHint(QPainter.HighQualityAntialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 5, 5)
        painter.setClipping(True)
        painter.setClipPath(path)
        painter.fillRect(self.rect(), QBrush(Qt.gray))
        pixmap = self.stamp_data.display_pixmap
        w = self.rect().width()
        h = self.rect().height()
        x = (w - pixmap.width())/2
        y = (h - pixmap.height())/2
        painter.drawPixmap(QPoint(int(x), int(y)), pixmap)
        painter.end()

    def mouseReleaseEvent(self, event):
        if self.stamp_data.pixmap:
            main_window = self.main_window
            tools_window = main_window.tools_window
            if self.stamp_data.id == StampInfo.TYPE_FROM_FILE:
                path = QFileDialog.getOpenFileName(None, "???????????????? ????????", "")
                path = str(path[0])
                if path and os.path.exists(path):
                    main_window.current_stamp_pixmap = QPixmap(path)
                else:
                    main_window.current_stamp_pixmap = StampInfo.PIXMAP_BROKEN
            else:
                main_window.current_stamp_pixmap = self.stamp_data.pixmap
            main_window.current_stamp_id = self.stamp_data.id
            main_window.current_stamp_angle = 0
            tools_window.on_parameters_changed()
            tools_window.select_window.hide()
            main_window.activateWindow()

class StampInfo():
    TYPE_STAMP = "stamp"
    TYPE_DYN = "dyn"
    TYPE_STICKER = "sticker"
    TYPE_FROM_FILE = "from_file"
    BUTTON_SIZE = 100

    @classmethod
    def create_default_pixmaps(cls):
        if hasattr(cls, "PIXMAP_BROKEN"):
            return

        PIXMAP_BROKEN = QPixmap(cls.BUTTON_SIZE, cls.BUTTON_SIZE)
        PIXMAP_BROKEN.fill(Qt.transparent)
        painter = QPainter()
        painter.begin(PIXMAP_BROKEN)
        r = PIXMAP_BROKEN.rect()
        r.adjust(20, 20, -20, -20)
        painter.setPen(QPen(Qt.red, 10))
        painter.drawLine(r.topLeft(), r.bottomRight())
        painter.drawLine(r.bottomLeft(), r.topRight())
        painter.setPen(QPen(Qt.black, 10))
        font = painter.font()
        font.setPixelSize(18)
        font.setWeight(1900)
        painter.setFont(font)
        painter.drawText(PIXMAP_BROKEN.rect(), Qt.AlignCenter, "BROKEN")
        painter.end()

        PIXMAP_LOADING = QPixmap(cls.BUTTON_SIZE, cls.BUTTON_SIZE)
        PIXMAP_LOADING.fill(Qt.transparent)
        painter = QPainter()
        painter.begin(PIXMAP_LOADING)
        r = PIXMAP_LOADING.rect()
        painter.setPen(QPen(Qt.black, 10))
        font = painter.font()
        font.setPixelSize(18)
        font.setWeight(1900)
        painter.setFont(font)
        painter.drawText(r, Qt.AlignCenter, "LOADING")
        painter.end()

        cls.PIXMAP_BROKEN = PIXMAP_BROKEN
        cls.PIXMAP_LOADING = PIXMAP_LOADING

    APP_FOLDER = os.path.dirname(__file__)
    PIC_FOLDER = os.path.join(APP_FOLDER, "stamps", "pictures")
    SCRIPTS_FOLDERPATH = os.path.join(APP_FOLDER, "stamps", "python")
    STICKERS_FOLDER = os.path.join(APP_FOLDER, "stamps", "stickers")

    @classmethod
    def check_paths(cls):
        def create_if_not_exists(folder_path):
            prev_path = None
            folder_paths = []
            while prev_path != folder_path:
                prev_path = folder_path
                folder_path = os.path.dirname(folder_path)
                folder_paths.append(prev_path)
            folder_paths = list(reversed(folder_paths))
            for f_path in folder_paths:
                if not os.path.exists(f_path):
                    os.mkdir(f_path)
                    print(f_path, "created")
        for folder in [cls.PIC_FOLDER, cls.SCRIPTS_FOLDERPATH, cls.STICKERS_FOLDER]:
            create_if_not_exists(folder)

    def remove_prefix(self, path):
        prefix = os.path.dirname(__file__)
        return path[len(prefix):]

    def __init__(self, type_, data):
        super().__init__()
        self.type = type_
        self.id = None
        self.pixmap = None
        self.display_pixmap = self.PIXMAP_LOADING
        if self.type in [self.TYPE_STAMP, self.TYPE_STICKER]:
            self.filepath = data
            self.id = self.remove_prefix(self.filepath)
        elif self.type == self.TYPE_DYN:
            script_path, arg, draw_func = data
            self.arg = arg
            self.filepath = script_path
            self.draw_func = draw_func
            _filepath = self.remove_prefix(self.filepath)
            self.id = f"{_filepath},{self.arg}"
        elif self.type == self.TYPE_FROM_FILE:
            self.id = "from_file"
            self.filepath = ""
        else:
            print(self.type)
            raise Exception("Unknown stamp type")
        if self.id is None:
            raise Exception("id is None")

    def get_tooltip_text(self):
        if self.type == self.TYPE_DYN:
            return self.arg
        else:
            return self.id

    @classmethod
    def load_from_id(cls, stamp_id):
        cls.create_default_pixmaps()
        if stamp_id is None:
            return None
        elif "," in stamp_id:
            # dynamic
            rel_script_path, func_arg = stamp_id.split(",", 1)
            script_path = os.path.join(cls.APP_FOLDER, rel_script_path.strip("/").strip("\\"))
            if os.path.exists(script_path):
                script_filename = os.path.basename(script_path)
                m_func, d_func = cls.get_module_functions(script_filename, script_path)
                if m_func and d_func:
                    return StampInfo("dyn", (script_path, func_arg, d_func))
        else:
            # imagefile
            stamp_filepath = os.path.join(cls.APP_FOLDER, stamp_id.strip("/").strip("\\"))
            if os.path.exists(stamp_filepath):
                return StampInfo("stamp", stamp_filepath)
        return None

    def load_from_file(self):
        if self.type in [self.TYPE_STAMP, self.TYPE_STICKER]:
            self.pixmap = QPixmap(self.filepath)
        elif self.type == self.TYPE_DYN:
            dyn_pixmap = QPixmap(240, 240)
            dyn_pixmap.fill(Qt.transparent)
            painter = QPainter()
            painter.begin(dyn_pixmap)
            self.draw_func(dyn_pixmap, painter, self.arg)
            painter.end()
            del painter
            self.pixmap = dyn_pixmap
        elif self.type == self.TYPE_FROM_FILE:
            dyn_pixmap = QPixmap(80, 80)
            dyn_pixmap.fill(Qt.black)
            p = QPainter()
            p.begin(dyn_pixmap)
            r = dyn_pixmap.rect()
            p.setPen(QPen(Qt.white))
            p.drawText(r, Qt.AlignCenter, "????\n??????????")
            p.end()
            del p
            self.pixmap = dyn_pixmap
        invalid = self.pixmap.width() == 0 or self.pixmap.height() == 0
        if invalid:
            self.pixmap = None
            self.display_pixmap = self.PIXMAP_BROKEN
        if not invalid:
            self.display_pixmap = self.pixmap.scaled(
                self.BUTTON_SIZE, self.BUTTON_SIZE,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
        )

    @classmethod
    def get_module_functions(cls, script_filename, full_path):
        spec = importlib.util.spec_from_file_location(script_filename, full_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        menu_items_func = None
        try:
            menu_items_func = getattr(module, "menu_items")
        except AttributeError:
            pass
        draw_handler_func = None
        try:
            draw_handler_func = getattr(module, "draw_handler")
        except AttributeError:
            pass
        return menu_items_func, draw_handler_func

    @classmethod
    def scan(cls):
        cls.check_paths()
        stamps = []
        ############################################################
        # FROM FILE dialog
        ############################################################
        stamp_info = StampInfo("from_file", None)
        stamps.append(stamp_info)
        ############################################################
        # scan pictures
        ############################################################
        for cur_folder, folders, files in os.walk(cls.PIC_FOLDER):
            for filename in files:
                filepath = os.path.join(cur_folder, filename)
                if filepath.lower().endswith((".jpg", ".png", ".jpeg", ".webp")):
                    stamp_info = StampInfo("stamp", filepath)
                    stamps.append(stamp_info)
        ############################################################
        # scan scripts
        ############################################################
        scripts = []
        if cls.SCRIPTS_FOLDERPATH not in sys.path:
            sys.path.append(cls.SCRIPTS_FOLDERPATH)
        for cur_folder, folders, files in os.walk(cls.SCRIPTS_FOLDERPATH):
            for filename in files:
                script_path = os.path.join(cur_folder, filename)
                if script_path.lower().endswith(".py"):
                    script_filename = os.path.basename(script_path)
                    m_func, d_func = cls.get_module_functions(script_filename, script_path)
                    for func_arg in m_func():
                        stamp_info = StampInfo("dyn", (script_path, func_arg, d_func))
                        stamps.append(stamp_info)
        if cls.SCRIPTS_FOLDERPATH in sys.path:
            sys.path.remove(cls.SCRIPTS_FOLDERPATH)
        ############################################################
        # scan stickers
        ############################################################
        for cur_folder, folders, files in os.walk(cls.STICKERS_FOLDER):
            for filename in files:
                filepath = os.path.join(cur_folder, filename)
                if filepath.lower().endswith((".jpg", ".png", ".jpeg", ".webp")):
                    stamp_info = StampInfo("sticker", filepath)
                    stamps.append(stamp_info)
        ############################################################
        # end of scan
        ############################################################
        return stamps

class PreviewsThread(QThread):
    update_signal = pyqtSignal(object)
    def __init__(self, stamps, select_window):
        QThread.__init__(self)
        Globals.background_threads.append(self)
        self.stamps = stamps
        self.update_signal.connect(lambda data: select_window.content.update())

    def start(self):
        super().start(QThread.IdlePriority)

    def run(self):
        for stamp_info in self.stamps:
            stamp_info.load_from_file()
            self.msleep(1)
            self.update_signal.emit(None)

class StampSelectWindow(QWidget):

    def drag_rect(self):
        return QRect(10, 5, self.rect().width()-20, 15)

    def mousePressEvent(self, event):
        self.old_cursor_pos = event.globalPos()
        self.drag_flag = self.drag_rect().contains(event.pos())
        if self.drag_flag:
            self.auto_positioning = False

    def mouseMoveEvent(self, event):
        if self.drag_flag:
            delta = QPoint(event.globalPos() - self.old_cursor_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_cursor_pos = event.globalPos()
        if self.drag_rect().contains(event.pos()):
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self.drag_flag = False

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 5, 5)
        painter.setBrush(QBrush(Qt.black))
        painter.setOpacity(0.9)
        painter.drawPath(path)
        painter.setOpacity(1.0)
        # draw drag placeholder
        brush = QBrush(QColor(Qt.gray))
        brush.setStyle(Qt.Dense7Pattern)
        painter.setBrush(brush)
        painter.setPen(Qt.NoPen)
        r = self.drag_rect()
        painter.drawRect(r)
        painter.end()

    def keyPressEvent(self, event):
        # ?????? ???????????????? ?????? ????????, ?????????? ?????????? ?????????????????????????? ???????? ??????????????????
        # ?????????????????? ???????????? ?????????????? ?????????????????????? ???? ?????????????? Esc ?? Enter
        app = QApplication.instance()
        app.sendEvent(self.main_window, event)

    def __init__(self, *args, stamps=None):
        super().__init__(*args)
        self.main_window = self.parent()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.drag_flag = False
        self.old_cursor_pos = None
        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)
        self.setMouseTracking(True)
        self.auto_positioning = True

        scroll = QScrollArea(self)
        main_layout.addSpacing(20)
        main_layout.addWidget(scroll)
        scroll.setWidgetResizable(True)
        style = """
            QScrollArea:vertical {
                border: none;
                background: red;
                height: 15px;
            }
            QScrollArea::handle:vertical {
                background: red;
                min-width: 20px;
            }
        """
        scroll.setStyleSheet(style)
        scrollContent = QWidget(scroll)
        scrollContent.setStyleSheet("background: black; border: none;")
        self.content = scrollContent

        BUTTON_SIZE = 100
        from_file_stamp = 0
        len_stamp = len(stamps) + from_file_stamp
        COL_COUNT = min(15, len_stamp)
        SPACING = 5
        CONTENT_MARGIN = 5
        rows_count = math.ceil(len_stamp / COL_COUNT)

        width = BUTTON_SIZE*COL_COUNT+(SPACING*2)*(COL_COUNT)+CONTENT_MARGIN*2
        height = min(700, (BUTTON_SIZE+SPACING*2)*rows_count+30)

        grid_layout = QGridLayout(scrollContent)
        grid_layout.setColumnStretch(COL_COUNT, COL_COUNT)
        grid_layout.setRowStretch(COL_COUNT, COL_COUNT)
        grid_layout.setHorizontalSpacing(0)
        grid_layout.setVerticalSpacing(0)
        grid_layout.setSpacing(SPACING)
        grid_layout.setContentsMargins(CONTENT_MARGIN,
            CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN)
        scrollContent.setLayout(grid_layout)
        scroll.setWidget(scrollContent)
        self.buttons = []
        for n, stamp_data in enumerate(stamps):
            button = StampSelectButton(stamp_data, BUTTON_SIZE, self.main_window)
            button.setParent(self)
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip(stamp_data.get_tooltip_text())
            r = n // COL_COUNT
            c = n % COL_COUNT
            self.buttons.append(button)
            grid_layout.addWidget(button, r, c, Qt.AlignJustify)
        self.show()

        self.resize(width+5, height+30)
        scrollContent.resize(width, height)

        self.show_at()

    def show_at(self):
        for but in self.main_window.tools_window.tools_buttons:
            if but.property("tool_id") == "stamp":
                break
        if self.auto_positioning:
            pos = but.mapToGlobal(QPoint(0,0))
            pos -= QPoint(self.rect().width(), self.rect().height())
            pos += QPoint(but.rect().width(), 0)
            pos.setX(max(pos.x(), 0))
            pos.setY(max(pos.y(), 0))
            self.move(pos)
        self.show()
        self.activateWindow()

class DragQLabel(QWidget):
    def __init__(self, parent, *args):
        super().__init__(parent, *args)
        self.setFixedWidth(35)
        self.setCursor(Qt.SizeAllCursor)

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        painter.setRenderHint(QPainter.Antialiasing)
        brush = QBrush(QColor(Qt.black))
        brush.setStyle(Qt.Dense7Pattern)
        painter.setBrush(brush)
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())
        painter.end()

class ToolsWindow(QWidget):
    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # dark rect
        RADIUS = 4
        main_rect = self.rect()
        main_rect.adjust(0, 0, -75, 0)
        path = QPainterPath()
        path.addRoundedRect(QRectF(main_rect), RADIUS, RADIUS)
        painter.fillPath(path, QColor("#303940"))
        if not Globals.ENABLE_FLAT_EDITOR_UI:
            # bevel
            main_rect = self.button_layout.contentsRect()
            main_rect.adjust(-4, -4, 4, 4)
            main_rect.adjust(0, 0, 0, 4)
            main_rect.adjust(0, 0, -75, 0) # only for Done button
            path = QPainterPath()
            path.addRoundedRect(QRectF(main_rect), RADIUS, RADIUS)
            painter.fillPath(path, QColor(50, 50, 50))
            main_rect = self.button_layout.contentsRect()
            main_rect.adjust(-4, -4, 4, 4)
            main_rect.adjust(0, 0, 0, 1)
            main_rect.adjust(0, 0, -75, 0) # only for Done button
            path = QPainterPath()
            path.addRoundedRect(QRectF(main_rect), RADIUS, RADIUS)
            painter.fillPath(path, QColor(Qt.white))
        # bright rect
        main_rect = self.button_layout.contentsRect()
        main_rect.setHeight(main_rect.height())
        main_rect.adjust(-4, -4, 4, 4)
        main_rect.adjust(0, 0, -75, 0) # only for Done button
        path = QPainterPath()
        path.addRoundedRect(QRectF(main_rect), RADIUS, RADIUS)
        if Globals.ENABLE_FLAT_EDITOR_UI:
            painter.fillPath(path, QBrush(QColor(235, 235, 235)))
        else:
            gradient = QLinearGradient(main_rect.topLeft(), main_rect.bottomLeft())
            gradient.setColorAt(1, QColor(174, 174, 174))
            gradient.setColorAt(0, QColor(235, 235, 235))
            painter.fillPath(path, gradient)
        painter.end()

    def wheelEvent(self, event):
        self.parent().wheelEvent(event)

    def change_ui_text(self, _type):
        if _type == "zoom_in_region":
            self.chb_toolbool.setText("??????????")
        elif _type == "text":
            self.chb_toolbool.setText("????????????????")
        elif _type == "blurring":
            self.chb_toolbool.setText("????????????????????????")
        else:
            self.chb_toolbool.setText("?")

    def set_ui_on_toolchange(self, element_type=None):
        _type = element_type or self.current_tool
        self.chb_toolbool.setEnabled(False)
        self.color_slider.setEnabled(True)
        self.size_slider.setEnabled(True)
        if _type in ["blurring", "darkening", "stamp"]:
            self.color_slider.setEnabled(False)
            if _type in ['blurring']:
                self.chb_toolbool.setEnabled(True)
        if _type in ["text", "zoom_in_region"]:
            self.chb_toolbool.setEnabled(True)
        if _type in ["copypaste", "none"]:
            self.color_slider.setEnabled(False)
            self.size_slider.setEnabled(False)
            self.chb_toolbool.setEnabled(False)
        self.change_ui_text(_type)
        self.parent().update()

    def tool_data_dict_from_ui(self):
        if self.current_tool in ["text", "zoom_in_region"]:
            data =  {
                "color_slider_value": self.color_slider.value,
                "color_slider_palette_index": self.color_slider.palette_index,
                "size_slider_value": self.size_slider.value,
                "toolbool": self.chb_toolbool.isChecked(),
            }
        elif self.current_tool == "blurring":
            data = {
                "size_slider_value": self.size_slider.value,
                "toolbool": self.chb_toolbool.isChecked(),
            }
        elif self.current_tool == "stamp":
            data =  {
                "size_slider_value": self.size_slider.value,
                "stamp_id": self.parent().current_stamp_id,
                "stamp_angle": self.parent().current_stamp_angle,
            }
        else:
            data =  {
                "color_slider_value": self.color_slider.value,
                "color_slider_palette_index": self.color_slider.palette_index,
                "size_slider_value": self.size_slider.value,
            }
        return data

    def tool_data_dict_to_ui(self, data):
        DEFAULT_COLOR_SLIDER_VALUE = 0.01
        DEFAULT_COLOR_SLIDER_PALETTE_INDEX = 0
        if self.current_tool in ['oval', 'rect', 'numbering']:
            DEFAULT_SIZE_SLIDER_VALUE = 0.07
        else:
            DEFAULT_SIZE_SLIDER_VALUE = 0.4
        if self.current_tool in ['blurring']:
            DEFAULT_TOOLBOOL_VALUE = False
        else:
            DEFAULT_TOOLBOOL_VALUE = True
        self.color_slider.value = data.get("color_slider_value", DEFAULT_COLOR_SLIDER_VALUE)
        self.color_slider.palette_index = data.get("color_slider_palette_index", DEFAULT_COLOR_SLIDER_PALETTE_INDEX)
        self.size_slider.value = data.get("size_slider_value", DEFAULT_SIZE_SLIDER_VALUE)
        self.chb_toolbool.setChecked(data.get("toolbool", DEFAULT_TOOLBOOL_VALUE))
        if self.current_tool == "stamp":
            main_window = self.parent()
            DEFAULT_STAMP_ID = main_window.current_stamp_id
            DEFAULT_STAMP_ANGLE = main_window.current_stamp_angle
            if main_window.current_stamp_pixmap is None:
                stamp_id = data.get("stamp_id", DEFAULT_STAMP_ID)
                stamp_info = StampInfo.load_from_id(stamp_id)
                if stamp_info:
                    stamp_info.load_from_file()
                    main_window.current_stamp_pixmap = stamp_info.pixmap
                    main_window.current_stamp_id = stamp_info.id
                    main_window.current_stamp_angle = data.get("stamp_angle", DEFAULT_STAMP_ANGLE)
                    self.on_parameters_changed()
                else:
                    main_window.current_stamp_pixmap = None
                    main_window.current_stamp_id = None
                    main_window.current_stamp_angle = 0
        self.update() #??????????????????????!

    def set_tool_data(self):
        ts = self.parent().tools_settings
        # ?????????????????? ?????????????? ?????????????????? (???????????????? ?? ?????????????????????? ?????????????? ????????????????)
        values = ts.get("values", {})
        if not self.tool_init:
            values.update({self.current_tool: self.tool_data_dict_from_ui()})
            ts.update({"values": values})
        self.tool_init = False
        # ???????????? ?????????? ??????????
        old_tool = self.current_tool
        tb = self.sender()
        if tb.isChecked():
            self.current_tool = tb.property("tool_id")
            for but in self.tools_buttons:
                if but is not tb:
                    but.setChecked(False)
        else:
            # ?????????????? ??????????, ?????????? ?????????? ???????????? ???????????? ???? ????????
            # ???? ?????????????????????????????? ???????????????????? ??????????
            if self.current_tool != "stamp":
                self.current_tool = "none"
        transform_tool_activated = False
        if old_tool != "transform" and self.current_tool == "transform":
            transform_tool_activated = True
            self.parent().elementsOnTransformToolActivated()
        if old_tool == "transform" and self.current_tool != "transform":
            self.parent().elementsSetSelected(None)
        self.parent().elementsMakeSureTheresNoUnfinishedElement()
        if self.initialization:
            self.initialization = False
        elif self.current_tool == "stamp" and self.parent().current_stamp_pixmap is None:
            self.show_stamp_menu(do_ending=False)
        # tb.setChecked(True)
        self.parent().current_tool = self.current_tool
        # ?????????????????? ?????????????????? ?????? ???????????????? ??????????????????????
        if not transform_tool_activated:
            self.tool_data_dict_to_ui(values.get(self.current_tool, {}))
        ts.update({"active_tool": self.current_tool})
        if self.current_tool != "transform":
            self.set_ui_on_toolchange()

        p = self.parent()
        el = p.elementsGetLastElement()
        if el:
            el.fresh = False

    def update_timer_handler(self):
        for but in self.tools_buttons:
            but.update()

    def __init__(self, *args):
        super().__init__(*args)

        tooltip_style = """QToolTip {
            background-color: #303940;
            color: white;
            border: black solid 1px;
        }"""
        self.setStyleSheet(tooltip_style)

        checkbox_style = """
            QCheckBox {
                color: rgb(220, 220, 220);
                font-size: 17px;
                height: 35px;
                padding: 0px 10px;
                background: transparent;
            }
            QCheckBox::checked {
                color: orange;
            }
            QCheckBox::indicator:checked {
                color: orange;
            }
        """

        editor_buttons_data = [
            ["transform", "??????????????????????\n?? ????????????????????????", "???????????????????????? ?????????? <b>????????????</b>"],

            ["pen", "????????????????", "<b>+Shift</b> ??? ???????????? ????????????"],
            ["marker", "????????????", "<b>+Shift</b> ??? ???????????? ????????????"],

            ["line", "??????????", "<b>+Shift</b> ??? ???????????? ?????????? ?????? ?????????? 45??<br>"
                                "<b>+Ctrl</b> ??? ???????????? ???????????????? ??????????"],
            ["arrow", "??????????????", "<b>+Shift</b> ??? ???????????? ?????? ?????????? ?? 45??"],

            ["text", "??????????", "???????? ?????????? ???????????? ?????????????????????? ???????????? ?????????? ???????????? ????????<br>"
                    "?? ?????????????? ????????????, ?????????????????? ????, ?????????????????????????? ??????????<br>???????????????????? ??????????????,"
                    " ?????????????? ???????????? ?????????? ?? ?????????????????????? ????????????."
                    "<br>+F5/F6 ??? ???????????????? ????????????"],
            ["oval", "????????", "<b>+Shift</b> ??? ????????<br><b>+Ctrl</b> ??? ?????????????????????? ????????"],
            ["rect", "??????????????????????????", "<b>+Shift</b> ??? ??????????????<br><b>+Ctrl</b> ??? ???????????? "
                                                                                    "??????????????????????"],

            ["numbering", "??????????????????", "??????????????????"],
            ["blurring", "????????????????", "????????????????"],
            ["darkening", "????????????????????", "????????????????????"],

            ["stamp", "??????????", "???????????????????? ???????????????? ?????? ??????????????.<br>?????????? ?????????????? ????????????"
                        " ????????????/??????????, ?????????????? ???????????? ???????????? ????????<br>???????????? ???????? ??? ????????????<br>"
                        "<b>Ctrl</b> + ???????????? ???????? ??? ?????????????? ???? 1??<br><b>Ctrl</b>+<b>Shift</b>"
                        " + ???????????? ???????? ??? ?????????????? ???? 10??"],

            ["zoom_in_region", "????????", "?????????????????? ?????????????????????? ??????????"
                                                 " ?????????????????????? ?????????????? ?????????????????????? ?? ?????????? ??????????"],

            ["copypaste", "??????????????????", "???????????????? ?????????????? ??????????????????????"
                                                        " ?? ?????????? ?????????? ?????? ????????????????????"]
        ]

        self.drag_flag = False
        self.auto_positioning = True
        self.current_tool = "none"

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        main_layout = QVBoxLayout()
        tools = QHBoxLayout()
        self.button_layout = tools
        sliders = QHBoxLayout()
        checkboxes = QHBoxLayout()

        self.drag_placeholder = DragQLabel(self)
        tools.addWidget(self.drag_placeholder)
        # tools.addSpacing(30)
        tools.addSpacing(10)

        self.tools_buttons = []
        for ID, name, tip in editor_buttons_data:
            button = CustomPushButton(name, self, tool_id=ID, checkable=True, checked=False)
            self.tools_buttons.append(button)
            tooltip = f"<b>{name}</b><br>{tip}"
            button.setToolTip(tooltip)
            button.setCursor(QCursor(Qt.PointingHandCursor))
            button.setParent(self)
            button.installEventFilter(self)
            button.clicked.connect(self.set_tool_data)
            if ID == "stamp":
                button.right_clicked.connect(self.show_stamp_menu)
            tools.addWidget(button)
            tools.addSpacing(5)

        self.done_button = CustomPushButton("????????????", self, tool_id="done")
        self.done_button.mousePressEvent = self.on_done_clicked
        self.done_button.setAccessibleName("done_button")
        self.done_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.done_button.setToolTip("????????????")
        self.done_button.installEventFilter(self)
        # tools.addSpacing(30)
        tools.addSpacing(10)
        tools.addWidget(self.done_button)

        backwards_btn = CustomPushButton("??????\n??????????", self, tool_id="backwards")
        forwards_btn = CustomPushButton("??????\n????????????", self, tool_id="forwards")
        self.backwards_btn = backwards_btn
        self.forwards_btn = forwards_btn
        for hb in [backwards_btn, forwards_btn]:
            hb.setCursor(QCursor(Qt.PointingHandCursor))
            sliders.addWidget(hb)
            hb.setEnabled(False)
            hb.installEventFilter(self)
        self.backwards_btn.installEventFilter(self)
        self.forwards_btn.installEventFilter(self)
        forwards_btn.clicked.connect(self.on_forwards_clicked)
        backwards_btn.clicked.connect(self.on_backwars_clicked)
        forwards_btn.setToolTip("<b>???????????????? ?????? ??????????????</b><br>Ctrl+Shift+Z")
        backwards_btn.setToolTip("<b>???????????????????? ???? ?????? ??????????</b><br>Ctrl+Z")

        if Globals.USE_COLOR_PALETTE:
            _type = "PALETTE"
        else:
            _type = "COLOR"
        self.color_slider = CustomSlider(_type, 400, 0.01, Globals.ENABLE_FLAT_EDITOR_UI)
        self.color_slider.value_changed.connect(self.on_parameters_changed)
        self.color_slider.installEventFilter(self)
        sliders.addWidget(self.color_slider)

        self.chb_toolbool = CheckBoxCustom("????????????????")
        self.chb_toolbool.setStyleSheet(checkbox_style)
        self.chb_toolbool.setEnabled(False)
        self.chb_toolbool.installEventFilter(self)
        sliders.addWidget(self.chb_toolbool)

        self.size_slider = CustomSlider("SCALAR", 180, 0.2, Globals.ENABLE_FLAT_EDITOR_UI)
        self.size_slider.value_changed.connect(self.on_parameters_changed)
        self.size_slider.installEventFilter(self)
        sliders.addWidget(self.size_slider)

        tools_settings = self.parent().tools_settings

        self.chb_masked = CheckBoxCustom("????????????????")
        self.chb_masked.setToolTip((
            "<b>?????????????????? ?????????? ?? ??????????????????</b><br>"
            "<b>?????????????? H</b> ??? ?????????????? ?????????????? ?????????? ???? ???????????????????????????? ?? ????????????????"
        ))
        self.chb_masked.setStyleSheet(checkbox_style)
        self.chb_masked.installEventFilter(self)
        self.chb_masked.setChecked(tools_settings.get("masked", False))
        self.parent().hex_mask = tools_settings.get("hex_mask", False)
        checkboxes.addWidget(self.chb_masked)

        self.chb_draw_thirds = CheckBoxCustom("???????????????????? ??????????")
        self.chb_draw_thirds.setToolTip("<b>???????????????????? ?????????? ?? ?????????????? ?????????????? ?????? ????????????"
                                                                        " ????????????????????????????</b>")
        self.chb_draw_thirds.setStyleSheet(checkbox_style)
        self.chb_draw_thirds.installEventFilter(self)
        self.chb_draw_thirds.setChecked(tools_settings.get("draw_thirds", False))
        checkboxes.addWidget(self.chb_draw_thirds)

        self.chb_add_meta = CheckBoxCustom("???????????????? ????????????????")
        self.chb_add_meta.setToolTip("<b>???????????????? ???????????????? ?????????????????? ?????????????????? ???????? ?? ????????????????"
                                                                            " ??????????????????</b>")
        self.chb_add_meta.setStyleSheet(checkbox_style)
        self.chb_add_meta.installEventFilter(self)
        self.chb_add_meta.setChecked(tools_settings.get("add_meta", False))
        if os.name == 'nt':
            checkboxes.addWidget(self.chb_add_meta)

        spacing = 2
        cms = 2
        tools.setSpacing(spacing)
        tools.setContentsMargins(cms, cms, cms, cms)
        main_layout.setSpacing(spacing)
        main_layout.setContentsMargins(cms, cms, cms, cms)
        sliders.setSpacing(spacing)
        cms = 0
        sliders.setContentsMargins(cms, cms, cms, cms)
        checkboxes.setSpacing(spacing)
        checkboxes.setContentsMargins(cms, cms, cms, cms)
        checkboxes.setAlignment(Qt.AlignRight)

        main_layout.addLayout(tools)
        main_layout.addLayout(sliders)
        main_layout.addLayout(checkboxes)

        sliders.addSpacing(75)
        checkboxes.addSpacing(75)

        self.setLayout(main_layout)

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_timer_handler)
        self.update_timer.setInterval(100)
        self.update_timer.start()

        tool_id = tool_id_default = "pen"
        if tools_settings:
            tool_id = tools_settings.get("active_tool", tool_id_default)
        self.initialization = True
        self.set_current_tool(tool_id)

        self.select_window = None

        self.installEventFilter(self)

        #pylint
        self.tool_init = True
        self.old_cursor_pos = QCursor().pos()

    def eventFilter(self, obj, event):
        # print(event.__class__.__name__, obj.__class__.__name__)
        parent = self.parent()
        blocking = parent.elementsIsSpecialCase(parent.elementsGetLastElement())
        if obj.parent() == self and blocking and not isinstance(event, (QPaintEvent, QKeyEvent)):
            return True
        return False

    def set_current_tool(self, tool_name):
        if tool_name == "special":
            # deactivate current tool
            for btn in self.tools_buttons:
                if btn.property("tool_id") == self.current_tool:
                    btn.click()
        self.current_tool = tool_name
        self.tool_init = True
        self.parent().current_tool = tool_name
        for btn in self.tools_buttons:
            if btn.property("tool_id") == self.current_tool:
                btn.click() # calls set_tool_data
                self.initialization = False
                break

    def show_stamp_menu(self, do_ending=True):
        main_window = self.parent()
        tools_window = self
        if not self.select_window:
            StampInfo.create_default_pixmaps()
            stamps = StampInfo.scan()
            self.select_window = StampSelectWindow(main_window, stamps=stamps)
            PreviewsThread(stamps, self.select_window).start()
        else:
            self.select_window.show_at()
        if self.parent().current_tool != "stamp":
            if do_ending:
                self.set_current_tool("stamp")
        self.update()

    def on_done_clicked(self, event):
        # calling save_screenshot of main window
        # event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, 0, 0, 0)
        # app = QApplication.instance()
        # app.sendEvent(self.parent(), event)
        self.parent().editing_ready.emit(None)

    def mousePressEvent(self, event):
        self.old_cursor_pos = event.globalPos()
        self.drag_flag = self.drag_placeholder.rect().contains(event.pos())
        self.auto_positioning = False

    def mouseMoveEvent(self, event):
        if self.drag_flag:
            delta = QPoint(event.globalPos() - self.old_cursor_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_cursor_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.drag_flag = False

    def forwards_backwards_update(self):
        f, b = self.parent().elementsUpdateHisotryButtonsStatus()
        self.forwards_btn.setEnabled(f)
        self.backwards_btn.setEnabled(b)
        self.update()
        self.parent().update()

    def on_forwards_clicked(self):
        self.parent().elementsHistoryForwards()
        self.forwards_backwards_update()

    def on_backwars_clicked(self):
        self.parent().elementsHistoryBackwards()
        self.forwards_backwards_update()

    def on_parameters_changed(self):
        self.parent().elementsParametersChanged()
        # ???????????????????? ???????????????????? ????????????????????????
        ts = self.parent().tools_settings
        values = ts.get("values", {})
        values.update({self.current_tool: self.tool_data_dict_from_ui()})
        ts.update({"values": values})
        ts.update({
            "masked": self.chb_masked.isChecked(),
            "draw_thirds": self.chb_draw_thirds.isChecked(),
            "add_meta": self.chb_add_meta.isChecked(),
            "hex_mask": getattr(self.parent(), 'hex_mask', False),
        })
        self.parent().update()

    def keyPressEvent(self, event):
        # ?????? ???????????????? ?????? ????????, ?????????? ?????????? ?????????????????????????? ???????? ??????????????????
        # ?????????????????? ???????????? ?????????????? ?????????????????????? ???? ?????????????? Esc ?? Enter
        app = QApplication.instance()
        app.sendEvent(self.parent(), event)

    def do_autopositioning(self, screenshot_rect):
        if not self.auto_positioning:
            return
        if not screenshot_rect:
            return
        #                |   reserved    |
        #                |   corner 4    |
        #        --------d---------------f------------
        #                |               |
        #     reserved   |  screenshot   |    reserved
        #     corner 3   |  zone         |    corner 2
        #                |               |
        #        --------k-------------- m -----------
        #                                |
        #                   default      |    reserved
        #                   corner       |    corner 1
        #                                |
        all_rect = self.parent()._all_monitors_rect
        m_corner = screenshot_rect.bottomRight()
        k_corner = screenshot_rect.bottomLeft()
        d_corner = screenshot_rect.topLeft()
        offset = 10
        default_corner_space = build_valid_rect(m_corner + QPoint(-offset, offset),
            all_rect.bottomLeft())
        reserved_corner_1_space = build_valid_rect(m_corner + QPoint(offset, offset),
            all_rect.bottomRight())
        reserved_corner_2_space = build_valid_rect(m_corner + QPoint(offset, -offset),
            all_rect.topRight())
        reserved_corner_3_space = build_valid_rect(k_corner + QPoint(-offset, -offset),
            QPoint(0, 0))
        reserved_corner_4_space = build_valid_rect(d_corner + QPoint(offset, -offset),
            QPoint(screenshot_rect.right(), 0))
        # ?????? ?????????????????? ?? ?????????????????????? ???????????????????? ????????????
        self.parent().default_corner_space = default_corner_space
        self.parent().reserved_corner_1_space = reserved_corner_1_space
        self.parent().reserved_corner_2_space = reserved_corner_2_space
        self.parent().reserved_corner_3_space = reserved_corner_3_space
        self.parent().reserved_corner_4_space = reserved_corner_4_space
        self.parent().tools_space = self.frameGeometry()
        # ???????????????? ???? ????, ?????????????? ???? ???????? ?? ???????????????????????? ?????????????? ?????? ??????
        def check_rect(rect):
            # ?????????????????? ?????????? ???????????? ??????, ?????????? ?? ???????????????????? ???????????????? ???? ?????????????????? ???????? ??????????
            # ???????????????????????????? ?? ???????????? ?????????????????????????? ?????????? qrect.contains(self.frameGeometry())
            # ?????????? ?????? ?? ???????????????????? ?? ???????????????? ????????????.
            # ?????? ????-???? ????????, ?????? ?????????????????????????? ???????????? ???????? ???? ???????????????? ????????????????????
            # ???? ???????????? ????????????????,
            # ????????????????, ?????????? ?????????? ???????????????????????? ?????????? ????????????.
            # ?????????????????? ?????? ?????????? ????????????, ???????? ?????????????????? DEBUG_ANALYSE_CORNERS_SPACES ?? True
            # ?????????????? ??????????????????: ???????????? ?????????? ?????? ???????? ????-???? ????????,
            # ?????? ???????????????????? ?????????? ???????????? ?????????????? ?????????? ????????????, ?? ???? ?? mouseMoveEvent
            return (rect.width() > self.width()) and (rect.height() > self.height())
        fits_to_default_corner = check_rect(default_corner_space)
        fits_to_reserved_corner_1 = check_rect(reserved_corner_1_space)
        fits_to_reserved_corner_2 = check_rect(reserved_corner_2_space)
        fits_to_reserved_corner_3 = check_rect(reserved_corner_3_space)
        fits_to_reserved_corner_4 = check_rect(reserved_corner_4_space)
        if fits_to_default_corner:
            x_value = screenshot_rect.right() - self.width()
            y_value = screenshot_rect.bottom()
        elif fits_to_reserved_corner_1:
            x_value = screenshot_rect.right()
            y_value = screenshot_rect.bottom()
        elif fits_to_reserved_corner_2:
            x_value = screenshot_rect.right()
            y_value = screenshot_rect.bottom() - self.height()
        elif fits_to_reserved_corner_3:
            x_value = screenshot_rect.left() - self.width()
            y_value = screenshot_rect.bottom() - self.height()
        elif fits_to_reserved_corner_4:
            x_value = screenshot_rect.left()
            y_value = screenshot_rect.top() - self.height()
        else: #screenshot zone
            x_value = screenshot_rect.right() - self.width()
            y_value = screenshot_rect.bottom() - self.height()
        self.move(x_value, y_value)

class ScreenshotWindow(QWidget):

    editing_ready = pyqtSignal(object)

    def set_clipboard(self, data):
        # ???????????????????????????????????????? ??????????????,
        # ???? ?????????? ???????????????? ?????? ?????????????????? ???????????????? ??????????????,
        # ?????? ???? ???????????? ???? ??????????
            # # ???????????????????? ???????????? ???? ?????????????????? ???????? ?? ???????????? ????????????????????,
            # # ?????????? clip ?????????????? ?????????????? ?????????? ??????????????????, ?? ???? ?????? ?????????? ??????
            # with open("temp.txt", "w+", encoding="utf-16") as temp:
            #     temp.write(data)
            # os.system('clip < "%s"' % "temp.txt")
            # os.remove("temp.txt")
        pyperclip.copy(data)

    def circle_mask_image(self, pxm, size=64, scale=False):
        image = pxm.toImage().convertToFormat(QImage.Format_ARGB32)

        imgsize = min(image.width(), image.height())
        rect = QRect(
            int((image.width() - imgsize) / 2),
            int((image.height() - imgsize) / 2),
            imgsize,
            imgsize,
        )
        image = image.copy(rect)
        out_img = QImage(imgsize, imgsize, QImage.Format_ARGB32)
        out_img.fill(Qt.transparent)

        brush = QBrush(image)
        painter = QPainter(out_img)
        painter.setBrush(brush)
        painter.setPen(Qt.NoPen)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = QRect(0, 0, imgsize, imgsize)
        if self.hex_mask:
            painter.drawPolygon(self.build_hex_polygon(rect))
        else:
            painter.drawEllipse(rect)

        painter.end()

        # Convert the image to a pixmap and rescale it.  Take pixel ratio into
        # account to get a sharp image on retina displays:
        pr = QWindow().devicePixelRatio()
        pm = QPixmap.fromImage(out_img)
        pm.setDevicePixelRatio(pr)
        if scale:
            size *= pr
            pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return pm

    def set_size_and_position(self):
        desktop = QDesktopWidget()
        MAX = 1000000000
        left = MAX
        right = -MAX
        top = MAX
        bottom = -MAX
        for i in range(0, desktop.screenCount()):
            r = desktop.screenGeometry(screen=i)
            left = min(r.left(), left)
            right = max(r.right(), right)
            top = min(r.top(), top)
            bottom = max(r.bottom(), bottom)
        self.move(0,0)
        self.resize(right-left+1, bottom-top+1)
        self._all_monitors_rect = QRect(QPoint(left, top), QPoint(right+1, bottom+1))

    def _build_valid_rect(self, p1, p2):
        return build_valid_rect(p1, p2)

    def build_input_rect(self, cursor_pos):
        ip1 = self.input_POINT1 or cursor_pos
        ip2 = self.input_POINT2 or self.input_POINT1 or cursor_pos
        return self._build_valid_rect(ip1, ip2)

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)

        line_pen = QPen(QColor(127, 127, 127, 127), 1)
        text_white_pen = text_pen = QPen(QColor(255, 255, 255, 255), 1)
        # text_pen = QPen(QColor(255, 127, 127, 255), 1)
        font = painter.font()
        font.setPixelSize(15)
        painter.setFont(font)

        cursor_pos = self.mapFromGlobal(QCursor().pos())
        input_rect = self.build_input_rect(cursor_pos)

        if self.extended_editor_mode:
            old_brush = painter.brush()
            painter.setBrush(self.checkerboard_brush)
            painter.drawRect(self.rect())
            painter.setBrush(old_brush)

        self.draw_uncaptured_zones(painter, self.uncapture_draw_type, input_rect, step=1)

        # background image
        self.draw_capture_zone(painter, input_rect, shot=1)
        # elements
        self.elementsDrawMain(painter)
        # mask overlay
        self.draw_capture_zone(painter, input_rect, shot=2)

        self.draw_uncaptured_zones(painter, self.uncapture_draw_type, input_rect, step=2)

        self.draw_magnifier(painter, input_rect, cursor_pos, text_pen, text_white_pen)
        self.draw_wrapper_cyberpunk(painter)
        self.draw_wrapper_shadow(painter)
        self.draw_capture_zone_resolution_label(painter, text_pen, input_rect)

        # old_comp_mode = painter.compositionMode()
        # painter.setCompositionMode(QPainter.RasterOp_SourceXorDestination)
        self.draw_vertical_horizontal_lines(painter, line_pen, cursor_pos)
        # painter.setCompositionMode(old_comp_mode)

        self.draw_stamp_tool(painter, cursor_pos)
        self.draw_tool_size_and_color(painter, cursor_pos)
        self.draw_hint(painter, cursor_pos, text_white_pen)

        self.draw_uncapture_zones_mode_info(painter)

        if Globals.DEBUG:
            self.draw_analyse_corners(painter)
            self.elementsDrawFinalVersionDebug(painter)

        painter.end()

    def draw_tool_size_and_color(self, painter, cursor_pos):
        if not self.capture_region_rect:
            return
        if not self.tools_window:
            return
        if self.current_tool not in ['line', 'marker', 'pen']:
            return
        if not self.capture_region_rect.contains(cursor_pos):
            return
        temp = type('temp', (), {})
        temp.type = self.current_tool
        temp.color = self.tools_window.color_slider.get_color()
        temp.size = self.tools_window.size_slider.value
        pen, _, _ = self.elementsGetPenFromElement(temp)
        old_pen = painter.pen()
        painter.setPen(pen)
        painter.drawPoint(cursor_pos)
        painter.setPen(old_pen)

    def draw_stamp_tool(self, painter, cursor_pos):
        if self.current_tool != "stamp" or not self.current_stamp_pixmap:
            return
        if not self.capture_region_rect.contains(cursor_pos):
            return
        pixmap = self.current_stamp_pixmap
        rotation = self.current_stamp_angle
        painter.setOpacity(0.5)
        r = self.elementsStampRect(cursor_pos, self.tools_window.size_slider.value,
            self.current_stamp_pixmap)
        s = QRect(QPoint(0,0), pixmap.size())
        painter.translate(r.center())
        painter.rotate(rotation)
        r = QRect(int(-r.width()/2), int(-r.height()/2), r.width(), r.height())
        painter.drawPixmap(r, pixmap, s)
        painter.resetTransform()
        painter.setOpacity(1.0)

    def draw_uncapture_zones_mode_info(self, painter):
        info = {
            LayerOpacity.FullTransparent: '????????????????????????: 100%',
            LayerOpacity.HalfTransparent: '????????????????????????: 50%',
            LayerOpacity.Opaque: '????????????????????????: 0%',
        }
        if time.time() - self.uncapture_mode_label_tstamp < 1.5:
            text_info = info[self.uncapture_draw_type]
            text_info = "Tab ??? " + text_info
            font = painter.font()
            font.setPixelSize(30)
            painter.setFont(font)
            rect = painter.drawText(self.rect(), Qt.AlignLeft | Qt.AlignTop, text_info)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(50, 50, 50)))
            painter.drawRect(rect)
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignTop, text_info)

    def draw_uncaptured_zones(self, painter, type, input_rect, step=1):
        ###### OLD VERSION ONLY FOR STEP == 1:
        # if type == LayerOpacity.FullTransparent: # full transparent
        #   painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        # elif type == LayerOpacity.HalfTransparent: # ghost
        #   painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        #   painter.setOpacity(0.6)
        #   painter.drawImage(self.rect(), self.source_pixels)
        #   painter.setOpacity(1.0)
        # elif type == LayerOpacity.Opaque: # stay still
        #   painter.fillRect(self.rect(), Qt.black)
        #   painter.setOpacity(0.6)
        #   painter.drawImage(self.rect(), self.source_pixels)
        #   painter.setOpacity(1.0)
        ###### NEW VERSION FOR STEP == 1 AND STEP == 2:
        self_rect = QRect(self.rect())
        self_rect.moveCenter(self_rect.center() + self.elements_global_offset)
        if step == 1:
            if type == LayerOpacity.FullTransparent: # full transparent
                painter.fillRect(self_rect, QColor(0, 0, 0, 5))
            elif type == LayerOpacity.HalfTransparent: # ghost
                pass
            elif type == LayerOpacity.Opaque: # stay still
                painter.drawImage(self_rect, self.source_pixels)
        elif step == 2:
            painter.setClipping(True)
            path = QPainterPath()
            path.addRect(QRectF(self_rect))
            path.addRect(QRectF(input_rect))
            painter.setClipPath(path)
            if type == LayerOpacity.FullTransparent: # full transparent
                pass
            elif type == LayerOpacity.HalfTransparent: # ghost
                painter.fillRect(self_rect, QColor(0, 0, 0, 100))
                painter.setOpacity(0.6)
                painter.drawImage(self_rect, self.source_pixels)
                painter.setOpacity(1.0)
            elif type == LayerOpacity.Opaque: # stay still
                painter.fillRect(self_rect, QColor(0, 0, 0, 100))
            painter.setClipping(False)
        # if self.undermouse_region_rect:
        #   pen = painter.pen()
        #   brush = painter.brush()
        #   painter.setPen(Qt.NoPen)
        #   b = QBrush(Qt.green)
        #   b.setStyle(Qt.DiagCrossPattern)
        #   painter.setBrush(b)
        #   painter.setOpacity(0.06)
        #   self.define_regions_rects_and_set_cursor(write_data=False)
        #   painter.drawRect(self.undermouse_region_rect)
        #   painter.setOpacity(1.0)
        #   painter.setPen(pen)
        #   painter.setBrush(brush)

    def draw_magnifier(self, painter, input_rect, cursor_pos, text_pen, text_white_pen):
        MAGNIFIER_SIZE = self.magnifier_size
        MAGNIFIER_ADVANCED = True
        if self.capture_region_rect:
            return
        # ???????????????????????????????? ?? ?????????????????? ???? ???????????????????? ?????????? ?????????? ??????????????
        focus_point = input_rect.bottomRight() or cursor_pos
        # ?????????????? ?????????? ???????????? ???? ??????????????
        focus_rect = self._build_valid_rect(
            focus_point + QPoint(10, 10),
            focus_point + QPoint(10 + MAGNIFIER_SIZE, 10 + MAGNIFIER_SIZE)
        )
        if not self._all_monitors_rect.contains(focus_rect):
            # ?????????????? ???????????? ?????????? ???? ??????????????
            focus_rect = self._build_valid_rect(
                focus_point + -1*QPoint(10, 10),
                focus_point + -1*QPoint(10 + MAGNIFIER_SIZE, 10 + MAGNIFIER_SIZE)
            )
            # ???????? ???? ???????????? ?????????????????? ?? ?????????? ?????????????? ???????? ???? ??????????????
            t = self._build_valid_rect(QPoint(0, 0), cursor_pos)
            if not t.contains(focus_rect):
                focus_rect = self._build_valid_rect(
                    focus_point + QPoint(10, -10),
                    focus_point + QPoint(10 + MAGNIFIER_SIZE, -10-MAGNIFIER_SIZE)
                )
                # ???????? ???? ?????????????? ???? ?????????????? ???????????? ?????????????? ?????????????????? ????????????????????????
                t2 = self._build_valid_rect(cursor_pos, self._all_monitors_rect.topRight())
                if not t2.contains(focus_rect):
                    focus_rect = self._build_valid_rect(
                        focus_point + QPoint(-10, 10),
                        focus_point + QPoint(-10-MAGNIFIER_SIZE, 10+MAGNIFIER_SIZE)
                    )
        # magnifier
        magnifier_source_rect = QRect(cursor_pos - QPoint(10, 10), cursor_pos + QPoint(10, 10))
        mh = magnifier_source_rect.height()
        mw = magnifier_source_rect.width()
        if MAGNIFIER_ADVANCED:
            # ???????? ?? ????????????????
            magnifier_pixmap = QPixmap(mw, mh)
            magnifier_pixmap.fill(Qt.black)
            magnifier = QPainter()
            magnifier.begin(magnifier_pixmap)
            magnifier.drawImage(
                QRect(0, 0, mw, mh),
                self.source_pixels,
                magnifier_source_rect,
            )
            center = QPoint(int(mw/2), int(mh/2))
            magnifier.setPen(QPen(QColor(255, 255, 255, 40), 1))
            offset = 1
            magnifier.drawLine(center.x(), 0, center.x(), int(mh/2-offset))
            magnifier.drawLine(center.x(), int(mh/2+offset), center.x(), mh)
            magnifier.drawLine(0, center.y(), int(mw/2-offset), center.y())
            magnifier.drawLine(int(mw/2+offset), center.y(), mw, center.y())
            offset = 2
            magnifier.setPen(QPen(QColor(255, 255, 255, 20), 1))
            magnifier.drawLine(center.x(), 0, center.x(), int(mh/2-offset))
            magnifier.drawLine(center.x(), int(mh/2+offset), center.x(), mh)
            magnifier.drawLine(0, center.y(), int(mw/2-offset), center.y())
            magnifier.drawLine(int(mw/2+offset), center.y(), mw, center.y())
            magnifier.end()
            painter.drawPixmap(focus_rect, magnifier_pixmap, QRect(0, 0, mw, mh))
        else:
            # ???????? ?????? ??????????????
            painter.drawImage(focus_rect, self.source_pixels, magnifier_source_rect)
        # label for hex color value
        painter.setPen(text_pen)
        mag_text_rect = QRect(focus_rect)
        mag_text_rect.setTop(mag_text_rect.top() + int(mag_text_rect.height()*2/3))
        pad = 5
        mag_text_rect.setTopLeft(mag_text_rect.topLeft() + QPoint(pad, pad))
        mag_text_rect.setBottomRight(mag_text_rect.bottomRight() - QPoint(pad, pad))
        painter.setBrush(QBrush(Qt.black, Qt.SolidPattern))
        painter.setPen(Qt.NoPen)
        painter.setOpacity(0.6)
        painter.drawRect(mag_text_rect)
        painter.setOpacity(1.0)
        painter.setPen(text_white_pen)
        old_font = painter.font()
        font = QFont(old_font)
        font.setPixelSize(int(mag_text_rect.height()/2.0+5))
        painter.setFont(font)
        self.color_at_pixel = QColor(self.source_pixels.pixel(cursor_pos))
        color_hex_string = self.color_at_pixel.name()
        painter.drawText(mag_text_rect, Qt.AlignCenter, color_hex_string)
        painter.setFont(old_font)
        color_rect = QRect(focus_rect.bottomLeft()+QPoint(0, -5), QSize(focus_rect.width(), 6))
        painter.fillRect(color_rect, self.color_at_pixel)

    def draw_hint(self, painter, cursor_pos, text_white_pen):
        if self.input_POINT1 is None:
            lines = (
    " ?? ???????????? ?????????????? ?????????????? ??????????????:"
    "\n     ??? ???????????????????????? ?????? ????????:"
    "\n         + Shift - ??????????????;"
    "\n         + Ctrl - ?????????????? ????????????????????."
    "\n     ??? ?????????????? ??? ??? ??? ??? ?????? ???????????????????????????????? ?????????????? ???????? c ???????????????? ???? ??????????????:"
    "\n         + Shift - ?????????????????????? ???? 10 ????????????????, ?? ???? ???? 1;"
    "\n         + Ctrl - ???????????????? ?????????????? ???????????????? ?????????????????????? ???? 5;"
    "\n         Enter - ?????????????????????????? ?????????? ?????????????? ???????????????????? ?? ?????????????????? ?????????? ??????????????????????????"
                                                                                " ?????????????? ??????????????."
    "\n     ??? ????????:"
    "\n         ?????????????? ???????? ?????????? ???????????????? ???????????? ????????;"
    "\n         Ctrl + C - ???????????????????? ???????? ?????? ???????????????? ?? ?????????? ????????????;"
    "\n             ?????? ?????????????????????? ???????????????? ?????????? ?? ?????????? ???????????????????? ?????????? ?? ???????????????? ??????????."
    "\n     ??? ???????????????? ?????????????????????? ???????? ?????? ?????????????????????? ???????????? ???? ???????????????????? ?????? ????????????????????????"
                                                                                        " ????????."
    "\n"
    "\n ?? ???????????? ?????????????? ?????????????? ?????????????? ?? ?? ???????????? ???????????????????????????? ??????????????:"
    "\n     ??? Tab / Tab+Shift - ???????????????????????? ?????????? 3-???? ???????????????? ?????????????????????? ??????????????????????????"
                                                                                        " ??????????????."
    "\n     ??? ???????????????? ?????????????????????? ???????? ?????? ?????????????????????? ???????????? ???? ???????????????????? ?????? ????????????????????????"
                                                                                        " ????????."
            )
            if self.show_help_hint:
                hint_text = lines
            else:
                hint_text = "?????????????? F1 - ?????????????????? ??????????????"
            hint_pos = cursor_pos + QPoint(10, -8)
            hint_rect = self._build_valid_rect(hint_pos, hint_pos + QPoint(900, -400))
            painter.setPen(text_white_pen)
            # painter.setPen(QPen(Qt.white))
            painter.drawText(hint_rect, Qt.TextWordWrap | Qt.AlignBottom, hint_text)

    def draw_capture_zone_resolution_label(self, painter, text_pen, input_rect):
        if self.is_rect_redefined or (self.input_POINT2 and not self.is_rect_defined):
            painter.setPen(text_pen)
            text_pos = input_rect.bottomRight() + QPoint(10, -10)
            painter.drawText(text_pos, "%dx%d" % (input_rect.width(), input_rect.height()))

    def build_hex_polygon(self, outer_rect):
        x = (3**0.5 / 2)
        size = min(outer_rect.width(), outer_rect.height())
        # hexaPoints = [QPoint(int(size/4),0),
        #                 QPoint(int(size/4 + size/2),0),
        #                 QPoint(size, int(size*0.5*x)),
        #                 QPoint(int(size/4 + size/2),int(size*x)),
        #                 QPoint(int(size/4),int(size*x)),
        #                 QPoint(0,int(size*0.5*x))]
        hexaPointsF = [QPointF(int(size/4),0),
                        QPointF(int(size/4 + size/2),0),
                        QPointF(size,int(size*0.5*x)),
                        QPointF(int(size/4 + size/2),int(size*x)),
                        QPointF(int(size/4),int(size*x)),
                        QPointF(0,int(size*0.5*x))]
        hexaPointsF = [QPointF(p.y(), p.x()) for p in hexaPointsF]
        max_x = max([p.x() for p in hexaPointsF])
        hexaPointsF = [QPointF(p.x()+(size-max_x)/2, p.y()) for p in hexaPointsF]
        hexaPointsF = [QPointF(p.x()+outer_rect.x(), p.y()+outer_rect.y()) for p in hexaPointsF]
        hexaPointsF = [QPointF(p.x()+(outer_rect.width()-size)/2,
                                         p.y()+(outer_rect.height()-size)/2) for p in hexaPointsF]
        hexaF = QPolygonF(hexaPointsF)
        return hexaF

    def draw_capture_zone(self, painter, input_rect, shot=1):
        tw = self.tools_window
        if shot==1 and self.input_POINT1 and self.input_POINT2:
            input_rect_dest = input_rect
            input_rect_source = QRect(input_rect)
            input_rect_source.moveCenter(input_rect_source.center()-self.elements_global_offset)
            painter.drawImage(input_rect_dest, self.source_pixels, input_rect_source)

        if shot==2 and self.input_POINT1 and self.input_POINT2:
            if tw and tw.chb_masked.isChecked():
                imgsize = min(input_rect.width(), input_rect.height())
                rect = QRect(
                    input_rect.left() + int((input_rect.width() - imgsize) / 2),
                    input_rect.top() + int((input_rect.height() - imgsize) / 2),
                    imgsize,
                    imgsize,
                )
                painter.setRenderHint(QPainter.Antialiasing, True)
                pen = QPen(QColor(255, 0, 0), 1)
                painter.setPen(pen)
                painter.setBrush(QBrush(QColor(150, 0, 0),
                    # Qt.BDiagPattern,
                    Qt.DiagCrossPattern
                ))
                path = QPainterPath()
                path.addRect(QRectF(input_rect))

                if self.hex_mask:
                    path.addPolygon(self.build_hex_polygon(input_rect))
                else:
                    path.addEllipse(QRectF(rect))

                painter.drawPath(path)

    def draw_wrapper_shadow(self, painter):
        if self.capture_region_rect:
            draw_shadow(
                painter,
                self.capture_region_rect, 50,
                webRGBA(QColor(0, 0, 0, 100)),
                webRGBA(QColor(0, 0, 0, 0))
            )

    def draw_wrapper_cyberpunk(self, painter):
        tw = self.tools_window
        if tw and tw.chb_draw_thirds.isChecked() and self.capture_region_rect:
            draw_cyberpunk(painter, self.capture_region_rect)

    def draw_vertical_horizontal_lines(self, painter, line_pen, cursor_pos):
        if self.input_POINT1 and self.input_POINT2:
            painter.setPen(line_pen)
            left = self.input_POINT1.x()
            top = self.input_POINT1.y()
            right = self.input_POINT2.x()
            bottom = self.input_POINT2.y()
            # vertical left
            painter.drawLine(left, 0, left, self.height())
            # horizontal top
            painter.drawLine(0, top, self.width(), top)
            # vertical right
            painter.drawLine(right, 0, right, self.height())
            # horizontal bottom
            painter.drawLine(0, bottom, self.width(), bottom)
            if self.undermouse_region_rect and Globals.DEBUG_VIZ:
                painter.setBrush(QBrush(Qt.green, Qt.DiagCrossPattern))
                painter.drawRect(self.undermouse_region_rect)
        else:
            painter.setPen(line_pen)
            curpos = self.mapFromGlobal(cursor_pos)
            pos_x = curpos.x()
            pos_y = curpos.y()
            painter.drawLine(pos_x, 0, pos_x, self.height())
            painter.drawLine(0, pos_y, self.width(), pos_y)

    def draw_analyse_corners(self, painter):
        if Globals.DEBUG_ANALYSE_CORNERS_SPACES:
            if self.default_corner_space is not None:
                painter.setBrush(QBrush(Qt.red, Qt.DiagCrossPattern))
                painter.drawRect(self.default_corner_space.adjusted(10, 10, -10, -10))
            if self.reserved_corner_1_space is not None:
                painter.setBrush(QBrush(Qt.green, Qt.DiagCrossPattern))
                painter.drawRect(self.reserved_corner_1_space.adjusted(10, 10, -10, -10))
            if self.reserved_corner_2_space is not None:
                painter.setBrush(QBrush(Qt.yellow, Qt.DiagCrossPattern))
                painter.drawRect(self.reserved_corner_2_space.adjusted(10, 10, -10, -10))
            if self.tools_space is not None:
                painter.setBrush(QBrush(Qt.blue, Qt.DiagCrossPattern))
                painter.drawRect(self.tools_space.adjusted(10, 10, -10, -10))

    def __init__(self, screenshot_image, metadata, parent=None):
        super().__init__()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.set_size_and_position()

        self.setMouseTracking(True)

        self.source_pixels = screenshot_image
        self.metadata = metadata

        self.input_POINT1 = None
        self.input_POINT2 = None
        self.capture_region_rect = None

        self.user_input_started = False
        self.is_rect_defined = False
        self.is_rect_redefined = False

        self.undermouse_region_rect = None
        self.undermouse_region_info = None
        self.region_num = 0

        self.old_cursor_position = QPoint(0, 0)

        self.tools_window = None

        self.default_corner_space = None
        self.reserved_corner_1_space = None
        self.reserved_corner_2_space = None

        self.tools_space = None

        self._custom_cursor_data = None
        self._custom_cursor_cycle = 0

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.uncapture_draw_type = LayerOpacity.Opaque
        self.uncapture_types = itertools.cycle([
            (LayerOpacity.FullTransparent, LayerOpacity.Opaque),
            (LayerOpacity.HalfTransparent, LayerOpacity.HalfTransparent),
            (LayerOpacity.Opaque, LayerOpacity.FullTransparent)
        ])

        # ???????? ???????????????????? ?????????? ???????????? ???????? ?????? ?????????? ???????????????? ??
        # ???????????? ?????????? ???? ?????????? ???? ???????????? ?????????????? ??????????????,
        # ???? ???????????????? ?????????????????? ?????????????? ??????????????.
        # ?????????? ?????????????? ???????????????? - ???????????? ?????? ??????????????????????
        # ???????????? ?????????????????? ?????????????????? ?? ?????????? ?????? ????????????????????
        self.drag_inside_capture_zone = False
        # ???????????? ????????????
        self.setCursor(self.get_custom_cross_cursor())
        # ????????
        self.magnifier_size = 100
        self.color_at_pixel = QColor(Qt.black)
        self.colors_reprs = []
        # ???????????? F1
        self.show_help_hint = False
        # ?????? ?????????????????? ?????????????????? ???? ??????????????????
        self.elementsInit()

        self.setWindowTitle(f"Oxxxy Screenshoter {Globals.VERSION_INFO} {Globals.AUTHOR_INFO}")

        self.tools_settings = SettingsJson().get_data("TOOLS_SETTINGS")
        self.current_stamp_pixmap = None
        self.current_stamp_id = None
        self.current_stamp_angle = 0

        self.editing_ready.connect(self.editing_is_done_handler)

        self.hex_mask = False

        #pylint
        # self.drag_capture_zone = False
        # self.ocp = QCursor().pos()
        # self.elements = []
        # self.elements_history_index = -1
        # self.elements_final_output = None
        self.widget_activated = False
        self.selected_element = None
        self.transform_widget = None
        self.dialog = None

        self.uncapture_mode_label_tstamp = time.time()

        pixmap = QPixmap(40, 40)
        pixmap.fill(Qt.transparent)
        painter_ = QPainter()
        painter_.begin(pixmap)
        painter_.setOpacity(0.3)
        painter_.fillRect(QRect(0, 0, 40, 40), QBrush(Qt.white))
        painter_.setPen(Qt.NoPen)
        painter_.setBrush(QBrush(Qt.black))
        painter_.drawRect(QRect(0, 0, 20, 20))
        painter_.drawRect(QRect(20, 20, 20, 20))
        painter_.end()
        self.checkerboard_brush = QBrush()
        self.checkerboard_brush.setTexture(pixmap)

        self.extended_editor_mode = True

    def request_fullscreen_capture_region(self):
        self.input_POINT2 = QPoint(0, 0)
        self.input_POINT1 = self.frameGeometry().bottomRight()
        self.capture_region_rect = self._build_valid_rect(self.input_POINT1, self.input_POINT2)
        self.user_input_started = True
        self.is_rect_defined = True
        self.is_rect_redefined = False
        self.drag_inside_capture_zone = False
        self.get_region_info()
        self.update_tools_window()
        self.update()

    def request_editor_mode(self, filepaths):
        pixmaps = []
        pos = QPoint(0, 0)
        self.input_POINT2 = QPoint(0, 0)
        self.input_POINT1 = self.frameGeometry().bottomRight()
        self.user_input_started = True
        self.is_rect_defined = True
        self.is_rect_redefined = False
        self.drag_inside_capture_zone = False
        self.get_region_info()
        self.update_tools_window()
        tw = self.tools_window
        tw.initialization = True
        tw.set_current_tool('stamp')
        for filepath in filepaths:
            pixmap = QPixmap(filepath)
            if pixmap.width() != 0:
                element = self.elementsCreateNew('stamp')
                element.pixmap = pixmap
                element.angle = 0
                self.elementsSetStampElementPoints(element, pos, pos_as_center=False)
                pos += QPoint(pixmap.width(), 0)
                pixmaps.append(pixmap)
        if pixmaps:
            self.input_POINT2 = QPoint(0, 0)
            self.input_POINT1 = element.end_point
        else:
            self.input_POINT2 = QPoint(0, 0)
            self.input_POINT1 = self.frameGeometry().bottomRight()
        self.capture_region_rect = self._build_valid_rect(self.input_POINT1, self.input_POINT2)
        tw.set_current_tool('transform')
        tw.forwards_backwards_update()
        self.update_tools_window()
        self.update()

    def request_elements_debug_mode(self):
        self.input_POINT2 = QPoint(300, 200)
        self.input_POINT1 = QPoint(1400, 800)
        self.capture_region_rect = self._build_valid_rect(self.input_POINT1, self.input_POINT2)
        self.user_input_started = True
        self.is_rect_defined = True
        self.is_rect_redefined = False
        self.drag_inside_capture_zone = True
        self.get_region_info()
        self.update_tools_window()
        self.update()

    def define_class_Element(root_self):
        def __init__(self, _type, elements_list):
            self.textbox = None
            self.type = _type
            self.finished = False

            self.copy_pos = None
            self.zoom_second_input = False

            self.rotation = 0

            elements_list.append(self)

            n = 0
            for el in elements_list:
                if el.type == "numbering":
                    n += 1
            self.number = n

            if hasattr(type(self), "_counter"):
                type(self)._counter += 1
            else:
                type(self)._counter = 0
            self.unique_index = type(self)._counter

            self.fresh = True

            self.choose_default_subelement = True # for copypaste and zoom_in_region

        def __getattribute__(self, name):
            if name.startswith("f_"):
                ret_value = getattr(self, name[len("f_"):])
                ret_value = QPoint(ret_value) #copy
                if root_self.elementsIsFinalDrawing:
                    # ?????? ???????????????????????????? ???????????? ?????? QPoint,
                    # ?? ?????? QPainterPath ?????????? ???? ???? ???????????? ??????
                    # ?????????????????? ?? ?????????????? draw_transformed_path
                    ret_value -= root_self.elements_global_offset
                    ret_value -= root_self.get_capture_offset()
                return ret_value
            else:
                return object.__getattribute__(self, name)

        return type("Element", (), {
                "__init__": __init__,
                "__getattribute__": __getattribute__}
        )

    def elementsInit(self):
        self.current_tool = "none"
        self.drag_capture_zone = False
        self.ocp = self.mapFromGlobal(QCursor().pos())
        self.current_capture_zone_center = QPoint(0, 0)

        self.elements = []
        self.elements_history_index = 0
        self.elementsSetSelected(None)

        self.elements_final_output = None
        self.Element = self.define_class_Element()

        self.elements_global_offset = QPoint(0, 0)
        self.drag_global = False
        self.current_elements_global_offset = QPoint(0, 0)

        self.NUMBERING_WIDTH = 25

        self.elementsIsFinalDrawing = False

    def elementsSetElementParameters(self, element):
        tw = self.tools_window
        if tw:
            element.color = tw.color_slider.get_color()
            element.color_slider_value = tw.color_slider.value
            element.color_slider_palette_index = tw.color_slider.palette_index
            element.size = tw.size_slider.value
            element.toolbool = tw.chb_toolbool.isChecked()
            element.margin_value = 5
        elif element.type == 'stamp':
            element.size = 1.0
            element.color = QColor(Qt.red)
            element.color_slider_value = 0.01
            element.color_slider_palette_index = 0
            element.toolbool = False
            element.margin_value = 5
        if element.type == "text":
            self.elementsChangeTextbox(element)
        if element.type == "blurring":
            self.elementsSetBlurredPixmap(element)
        # ???????????? ?????? ?????????????????????? transform, ?????? ?????????? ???? ???????????????? ???? ?????????? ????????????
        if tw and element.type == "stamp" and tw.current_tool == "transform":
            if hasattr(element, "pixmap"):
                r_first = build_valid_rect(element.start_point, element.end_point)
                self.elementsSetStampElementPoints(element, r_first.center())
                # ???????? ?????????????????? ????????????
                self.elementsSetSelected(element)

    def elementsSetStampElementPoints(self, element, pos, pos_as_center=True):
        if pos_as_center:
            r = self.elementsStampRect(pos, element.size, element.pixmap)
            element.start_point = r.topLeft()
            element.end_point = r.bottomRight()
        else:
            element.start_point = QPoint(pos)
            w = element.pixmap.width()
            h = element.pixmap.height()
            element.end_point = pos + QPoint(w, h)

    def elementsActivateTransformTool(self):
        if not self.elements:
            return
        try:
            candidat = self.selected_element or self.elementsHistoryFilter()[-1]
            if candidat not in self.elementsHistoryFilter(): # for selected_element
                candidat = None
        except Exception:
            candidat = None
        if not candidat:
            return
        self.elementsSetSelected(candidat)
        tools_window = self.tools_window
        if tools_window:
            tools_window.set_current_tool("transform")
        self.update()

    def elementsRemoveElement(self):
        if not self.elements:
            return
        try:
            candidat = self.selected_element or self.elementsHistoryFilter()[-1]
            if candidat not in self.elementsHistoryFilter(): # for selected_element
                candidat = None
        except Exception:
            candidat = None
        if (not candidat) or candidat.type == "removing":
            return
        element = self.elementsCreateNew("removing")
        # element.source_index = self.elements.index(candidat)
        element.source_index = candidat.unique_index
        self.elementsSetSelected(None)
        self.update()

    def elementsGetLastElement(self):
        try:
            element = self.elementsHistoryFilter()[-1]
        except Exception:
            element = None
        return element

    def elementsGetLastElement1(self):
        try:
            element = self.elementsHistoryFilter()[-2]
        except Exception:
            element = None
        return element

    def elementsCopyElementData(self, element, source_element):
        attributes = source_element.__dict__.items()
        copy_textbox = None
        copy_textbox_value = None
        for attr_name, attr_value in attributes:
            if attr_name == "unique_index":
                continue
            type_class = type(attr_value)
            # if type_class is type(None):
            #     print(attr_name)
            #     print(attributes)
            if attr_value is None:
                final_value = attr_value
            else:
                final_value = type_class(attr_value)
            if attr_name == "textbox" and attr_value is not None:
                copy_textbox = type_class(attr_value)
                copy_textbox_value = attr_value.toPlainText()
            else:
                setattr(element, attr_name, final_value)
        if copy_textbox:
            self.elementsTextBoxInit(copy_textbox, self, element)
            copy_textbox.setText(copy_textbox_value)
            setattr(element, "textbox", copy_textbox)

    def elementsSelectedElementParamsToUI(self):
        if not self.selected_element:
            return
        self.elementsDeactivateTextElements()
        element = self.selected_element
        self.tools_window.color_slider.value = element.color_slider_value
        self.tools_window.color_slider.palette_index = element.color_slider_palette_index
        self.tools_window.size_slider.value = element.size
        self.tools_window.chb_toolbool.setChecked(element.toolbool)
        if element.type == "text":
            self.elementsActivateTextElement(element)
        self.tools_window.set_ui_on_toolchange(element_type=element.type)
        self.tools_window.update()
        self.update()

    def elementsMakeSureTheresNoUnfinishedElement(self):
        el = self.elementsGetLastElement()
        if el and el.type in ["zoom_in_region", "copypaste"] and not el.finished:
            self.elements.remove(el)

    def elementsOnTransformToolActivated(self):
        self.elementsSetSelected(self.elementsGetLastElement())
        self.elementsSelectedElementParamsToUI()
        self.update()
        self.activateWindow() # ?????????? ?????????? ???? ???????????????????? ???? ???????????? ??????????????????????

    def elementsActivateTextElement(self, element):
        element.textbox.setParent(self)
        element.textbox.show()
        element.textbox.setFocus()

    def elementsDeactivateTextElements(self):
        for element in self.elementsHistoryFilter():
            if element.type == "text" and element.textbox.parent():
                self.elementsOnTextChanged(element)
                element.textbox.hide()
                element.textbox.setParent(None)

    def elementsCreateNew(self, element_type, start_drawing=False):
        self.elementsDeactivateTextElements()
        # ???????????????? ???????????????????? (??????????????????) ?????????? ??????????????
        # ?????????? ?????????????????? ????????????????
        case1 = element_type == "removing"
        case2 = element_type == "TEMPORARY_TYPE_NOT_DEFINED"
        case3 = start_drawing
        is_removing = case1 or case2 or case3
        self.elements = self.elementsHistoryFilter(only_filter=is_removing)
        # ???????????????? ????????????????
        element = self.Element(element_type, self.elements)
        self.elementsSetElementParameters(element)
        # ???????????????????? ?????????????? ?????????? ???????????????? ????????????????
        self.elements_history_index = len(self.elements)
        return element

    def elementsHistoryFilter(self, only_filter=False):
        # ???????????????????? ???? ??????????????
        elements = self.elements[:self.elements_history_index]
        if only_filter:
            return elements
        # ???? ???????????????????? ?????????????????? ????????????????
        # ?????? ????????????????, ?????? ???????? ?????????????????????? ?????? ???????????????? ??????????????????
        remove_indexes = []
        for el in elements:
            if hasattr(el, "source_index"):
                remove_indexes.append(el.source_index)
        non_deleted_elements = []
        for index, el in enumerate(elements):
            # if index not in remove_indexes:
            if el.unique_index not in remove_indexes:
                non_deleted_elements.append(el)
        return non_deleted_elements

    def elementsBuildSubelementRect(self, element, copy_pos):
        _rect = build_valid_rect(element.f_start_point, element.f_end_point)
        if element.type == "zoom_in_region":
            factor = 1.0 + element.size*4.0
            _rect.setWidth(int(_rect.width()*factor))
            _rect.setHeight(int(_rect.height()*factor))
        _rect.moveCenter(copy_pos)
        return _rect

    def elementsGetElementsUnderMouse(self, cursor_pos):
        elements_under_mouse = []
        for el in self.elementsHistoryFilter():
            if el.type in ["removing",]:
                continue
            if hasattr(el, "path"):
                is_mouse_over = el.path.boundingRect().contains(cursor_pos)
            elif hasattr(el, "selection_path"):
                is_mouse_over = el.selection_path.contains(cursor_pos)
            elif el.type == "text":
                p = el.end_point - QPoint(0, el.pixmap.height())
                text_bounding_rect = QRect(p, QSize(el.pixmap.width(), el.pixmap.height()))
                is_mouse_over1 = text_bounding_rect.contains(cursor_pos)
                is_mouse_over2 = build_valid_rect(el.start_point, el.end_point).contains(cursor_pos)
                is_mouse_over = is_mouse_over1 or is_mouse_over2
            elif el.type == "stamp":
                is_mouse_over = build_valid_rect(el.start_point, el.end_point).contains(cursor_pos)
            elif el.type == "numbering":
                is_mouse_over1 = build_valid_rect(el.start_point, el.end_point).contains(cursor_pos)
                w = self.NUMBERING_WIDTH
                is_mouse_over2 = QRect(el.end_point - QPoint(int(w/2), int(w/2)),
                        QSize(w, w)).contains(cursor_pos)
                is_mouse_over = is_mouse_over1 or is_mouse_over2
            elif el.type in ["zoom_in_region", "copypaste"]:
                is_mouse_over1 = build_valid_rect(el.start_point, el.end_point).contains(cursor_pos)
                is_mouse_over2 = False
                if is_mouse_over1:
                    el.choose_default_subelement = True
                elif el.copy_pos:
                    sub_element_rect = self.elementsBuildSubelementRect(el, el.copy_pos)
                    is_mouse_over2 = sub_element_rect.contains(cursor_pos)
                    if is_mouse_over2:
                        el.choose_default_subelement = False
                is_mouse_over = is_mouse_over1 or is_mouse_over2
            else:
                is_mouse_over = build_valid_rect(el.start_point, el.end_point).contains(cursor_pos)
            if is_mouse_over:
                elements_under_mouse.append(el)
        return elements_under_mouse

    def elementsMousePressEventDefault(self, element, event):
        if element.type == "line" and event.modifiers() & Qt.ControlModifier:
            last_element = self.elementsGetLastElement1()
            if last_element and last_element.type == "line":
                element.start_point = QPointF(last_element.end_point).toPoint()
            else:
                element.start_point = event.pos()
        else:
            element.start_point = event.pos()
        element.end_point = event.pos()

    def elementsIsSpecialCase(self, element):
        special_case = element is not None
        special_case = special_case and element.type in ["zoom_in_region", "copypaste"]
        special_case = special_case and not element.finished
        return special_case

    def elementsFreshAttributeHandler(self, el):
        if el:
            if hasattr(el, 'finished'):
                if el.finished:
                    el.fresh = False
            else:
                el.fresh = False

    def elementsMousePressEvent(self, event):
        tool = self.current_tool

        isLeftButton = event.buttons() == Qt.LeftButton
        isAltOnly = event.modifiers() == Qt.AltModifier
        isCaptureZone = self.capture_region_rect is not None
        if self.current_tool == "none" and isLeftButton and isCaptureZone and not isAltOnly:
            self.current_capture_zone_center = self.capture_region_rect.center()
            self.ocp = event.pos()
            self.drag_capture_zone = True
            return
        else:
            self.drag_capture_zone = False

        if isAltOnly and isLeftButton:
            if self.extended_editor_mode:
                self.elementsInitMoveGlobalOffset()
                self.ocp = event.pos()
                self.drag_global = True
                return
            else:
                QMessageBox.critical(None, "????????????", "?????????????????????? ?????????? ?????????????????? ????????????????")
        else:
            self.drag_global = False

        if self.current_tool == "none":
            return
        if self.current_tool == "stamp" and not self.current_stamp_pixmap:
            self.tools_window.show_stamp_menu()
            return
        # ???????????????? ??????????
        el = self.elementsGetLastElement()
        self.elementsFreshAttributeHandler(el)
        if self.current_tool == "transform":
            element = None # ?????? ???????????? ???????????????? ????????
        elif self.elementsIsSpecialCase(el):
            # zoom_in_region and copypaste case, when it needs more additional clicks
            element = el
        else:
            # default case
            element = self.elementsCreateNew(self.current_tool, start_drawing=True)
        # #######
        if tool == "arrow":
            self.elementsMousePressEventDefault(element, event)
        elif tool in ["zoom_in_region", "copypaste"]:
            if not element.zoom_second_input:
                self.elementsMousePressEventDefault(element, event)
            elif not element.finished:
                element.copy_pos = event.pos()
        elif tool == "stamp":
            element.pixmap = self.current_stamp_pixmap
            element.angle = self.current_stamp_angle
            self.elementsSetStampElementPoints(element, event.pos())
        elif tool in ["pen", "marker"]:
            if event.modifiers() & Qt.ShiftModifier:
                element.straight = True
                self.elementsMousePressEventDefault(element, event)
            else:
                element.straight = False
                path = QPainterPath()
                path.moveTo(event.pos())
                element.path = path
                self.elementsMousePressEventDefault(element, event)
        elif tool == "line":
            self.elementsMousePressEventDefault(element, event)
        elif tool in ["oval", "rect", "numbering", "special"]:
            element.equilateral = event.modifiers() & Qt.ShiftModifier
            element.filled = event.modifiers() & Qt.ControlModifier
            self.elementsMousePressEventDefault(element, event)
        elif tool == "text":
            self.elementsMousePressEventDefault(element, event)
            element.pixmap = None
            element.modify_end_point = False
        elif tool in ["blurring", "darkening"]:
            self.elementsMousePressEventDefault(element, event)
            if tool == "blurring":
                element.finished = False
        elif tool == "transform":
            self.widget_activated = False
            if self.transform_widget:
                widget_control_point = None
                widget_control_point = self.transform_widget.control_point_under_mouse(event.pos())
                if widget_control_point and event.button() == Qt.LeftButton:
                    self.widget_activated = True
            if not self.widget_activated:
                ######################
                # selection code!
                ######################
                elements = self.elementsGetElementsUnderMouse(event.pos())
                if elements:
                    if self.selected_element in elements:
                        # ?????????????????????? ?????????? ???????????????????????????? ???????? ?????????? ??????????????????
                        # ?? ?????????????? ?????????????? ????????
                        elements = itertools.cycle(elements)
                        while next(elements) != self.selected_element:
                            pass
                        selected_element = next(elements)
                    else:
                        selected_element = elements[0]
                    self.elementsSetSelected(selected_element)
                else:
                    self.elementsSetSelected(None)
                self.elementsSelectedElementParamsToUI()
                ########################
                # end of selection code
                ########################
        if self.tools_window:
            self.tools_window.forwards_backwards_update()
        self.update()

    def equilateral_delta(self, delta):
        sign = math.copysign(1.0, delta.x())
        if delta.y() < 0:
            if delta.x() < 0:
                sign = 1.0
            else:
                sign = -1.0
        delta.setX(int(delta.y()*sign))
        return delta

    def elementsTextElementRotate(self, clockwise_rotation):
        element = None
        for el in self.elementsHistoryFilter():
            if el.type == "text":
                element = el
        if element:
            if clockwise_rotation:
                delta = 10
            else:
                delta = -10
            element.rotation += delta
        self.update()

    def elementsMoveElement(self, event):
        modifiers = QApplication.queryKeyboardModifiers()
        value = 1
        if modifiers & Qt.ShiftModifier:
            value = 10
        key = event.key()
        if key == Qt.Key_Up:
            delta = QPoint(0, -value)
        elif key == Qt.Key_Down:
            delta = QPoint(0, value)
        elif key == Qt.Key_Right:
            delta = QPoint(value, 0)
        elif key == Qt.Key_Left:
            delta = QPoint(-value, 0)
        element = None or self.selected_element
        if element:
            element = self.elementsCreateModificatedCopyOnNeed(element)
            if hasattr(element, "path"):
                element.path.translate(QPointF(delta))
            if hasattr(element, "start_point"):
                element.start_point += delta
            if hasattr(element, "end_point"):
                element.end_point += delta
            self.elementsSetSelected(element)
        self.update()

    def elementsDefineCursorShape(self):
        cursor_pos = self.mapFromGlobal(QCursor().pos())
        is_tool_transform = self.current_tool == "transform"
        any_element_under_mouse = self.elementsGetElementsUnderMouse(cursor_pos)
        if self.selected_element and self.transform_widget:
            pos = self.mapFromGlobal(QCursor().pos())
            cpum = self.transform_widget.control_point_under_mouse
            data = cpum(pos, delta_info=True)
            cur_point, center_point = data
            if cur_point:
                delta = cur_point.point - center_point.point
                if cur_point.type == "edge":
                    if delta.x() < 2 and delta.y() > 0:
                        return QCursor(Qt.SizeVerCursor)
                    if delta.x() < 2 and delta.y() < 0:
                        return QCursor(Qt.SizeVerCursor)
                    if delta.y() < 2 and delta.x() > 0:
                        return QCursor(Qt.SizeHorCursor)
                    if delta.y() < 2 and delta.x() < 0:
                        return QCursor(Qt.SizeHorCursor)
                if cur_point.type == "corner":
                    if delta.y() > 0 and delta.x() > 0:
                        return QCursor(Qt.SizeFDiagCursor)
                    if delta.y() < 0 and delta.x() < 0:
                        return QCursor(Qt.SizeFDiagCursor)
                    if delta.y() > 0 and delta.x() < 0:
                        return QCursor(Qt.SizeBDiagCursor)
                    if delta.y() < 0 and delta.x() > 0:
                        return QCursor(Qt.SizeBDiagCursor)
                if cur_point.type == "center":
                    return QCursor(Qt.SizeAllCursor)
            return self.get_custom_cross_cursor()
        elif is_tool_transform and any_element_under_mouse:
            return Qt.SizeAllCursor
        else:
            return self.get_custom_cross_cursor()

    def elementsInitMoveGlobalOffset(self):
        self.current_elements_global_offset = QPoint(self.elements_global_offset)
        self.current_capture_zone_center = self.capture_region_rect.center()
        for element in self.elements[:]:
            attributes = dict(element.__dict__).items()
            for attr_name, attr_value in attributes:
                if attr_name.startswith("_temp_"):
                    continue
                type_class = type(attr_value)
                # if type_class.__name__ in ['QPoint', 'QRect', 'QPainterPath']:
                if type_class.__name__ in ['QPoint', 'QPainterPath']:
                    final_value = type_class(attr_value)
                    attr_name = f'_temp_{attr_name}'
                    setattr(element, attr_name, final_value)
        self.update()

    def elementsMoveGlobalOffset(self, delta):
        self.elements_global_offset = self.current_elements_global_offset + delta
        for element in self.elements[:]:
            attributes = dict(element.__dict__).items()
            for attr_name, attr_value in attributes:
                if attr_name.startswith('_temp_'):
                    set_attr_name = attr_name[len('_temp_'):]
                    type_class = type(attr_value)
                    classname = type_class.__name__
                    if classname == 'QPoint':
                        final_value = attr_value + delta
                    # elif classname == 'QRect':
                    #     _temp = QRect(attr_value)
                    #     _temp.moveCenter(_temp.center() + delta)
                    #     final_value = _temp
                    elif classname == "QPainterPath":
                        _temp = QPainterPath(attr_value)
                        _temp.translate(delta)
                        final_value = _temp
                    else:
                        raise Exception("elementsMoveGlobalOffset Exception")
                    setattr(element, set_attr_name, final_value)
        self.move_capture_rect(delta)
        if self.input_POINT1 is not None:
            self.input_POINT1 = QPoint(self.capture_region_rect.topLeft())
        if self.input_POINT2 is not None:
            self.input_POINT2 = QPoint(self.capture_region_rect.bottomRight())
        if self.transform_widget:
            # refresh
            self.elementsSetSelected(self.selected_element)
        self.update()

    def move_capture_rect(self, delta):
        self.capture_region_rect.moveCenter(self.current_capture_zone_center + delta)
        self.input_POINT1 = QPoint(self.capture_region_rect.topLeft())
        self.input_POINT2 = QPoint(self.capture_region_rect.bottomRight())

    def elementsMouseMoveEvent(self, event):
        tool = self.current_tool
        isLeftButton = event.buttons() == Qt.LeftButton
        if self.drag_capture_zone and isLeftButton:
            delta = QPoint(event.pos() - self.ocp)
            self.move_capture_rect(delta)
        if self.drag_global and isLeftButton:
            delta = QPoint(event.pos() - self.ocp)
            self.elementsMoveGlobalOffset(delta)
            return
        if tool == "none":
            return
        # ???????????????? ??????????
        element = self.elementsGetLastElement()
        if element is None:
            return
        if tool == "arrow":
            element.end_point = event.pos()
            if event.modifiers() & Qt.ShiftModifier:
                element.end_point = elements45DegreeConstraint(element.start_point,
                                                                            element.end_point)
        elif tool in ["zoom_in_region", "copypaste"]:
            if not element.zoom_second_input:
                element.end_point = event.pos()
            elif not element.finished:
                element.copy_pos = event.pos()
        elif tool == "stamp":
            element.pixmap = self.current_stamp_pixmap
            element.angle = self.current_stamp_angle
            self.elementsSetStampElementPoints(element, event.pos())
        elif tool in ["pen", "marker"]:
            if element.straight:
                element.end_point = event.pos()
            else:
                element.path.lineTo(event.pos())
                element.end_point = event.pos()
        elif tool == "line":
            element.end_point = event.pos()
            if event.modifiers() & Qt.ShiftModifier:
                element.end_point = elements45DegreeConstraint(element.start_point,
                                                                            element.end_point)
        elif tool in ["oval", "rect", "numbering", "special"]:
            element.filled = event.modifiers() & Qt.ControlModifier
            element.equilateral = event.modifiers() & Qt.ShiftModifier
            if element.equilateral:
                delta = element.start_point - event.pos()
                delta = self.equilateral_delta(delta)
                element.end_point = element.start_point - delta
            else:
                element.end_point = event.pos()
        elif tool == "text":
            element.end_point = event.pos()
            element.modify_end_point = False
        elif tool in ["blurring", "darkening"]:
            element.equilateral = event.modifiers() & Qt.ShiftModifier
            if element.equilateral:
                delta = element.start_point - event.pos()
                delta = self.equilateral_delta(delta)
                element.end_point = element.start_point - delta
            else:
                element.end_point = event.pos()
            if tool == "blurring":
                pass
        elif tool == "transform":
            if self.transform_widget and self.widget_activated:
                element = self.elementsCreateModificatedCopyOnNeed(self.selected_element,
                                                                        keep_old_widget=True)
                self.transform_widget.retransform(event)
                sel_elem = self.selected_element
                if hasattr(sel_elem, "path"):
                    sel_elem.pApos = self.transform_widget.pA.point
                    sel_elem.pBpos = self.transform_widget.pB.point
                    current_topLeft = sel_elem.path.boundingRect().topLeft()
                    sel_elem.path.translate(-QPointF(current_topLeft))
                    sel_elem.path.translate(
                        QPointF(build_valid_rect(sel_elem.pApos, sel_elem.pBpos).topLeft())
                    )
                elif sel_elem.type == "blurring":
                    sel_elem.finished = False
                    sel_elem.start_point = self.transform_widget.pA.point
                    sel_elem.end_point = self.transform_widget.pB.point
                elif sel_elem.type == "text":
                    element.modify_end_point = True
                    # ?????? ?????????? ?????????????? ???????????????????? ???????? ?????? ????????????????????????????
                    self.elementsOnTextChanged(sel_elem)
                    sel_elem.start_point = self.transform_widget.pA.point
                    sel_elem.end_point = self.transform_widget.pB.point
                elif sel_elem.type in ["copypaste", "zoom_in_region"]:
                    if element.choose_default_subelement:
                        sel_elem.start_point = self.transform_widget.pA.point
                        sel_elem.end_point = self.transform_widget.pB.point
                    else:
                        sel_elem.copy_pos = self.transform_widget.pCenter.point
                else:
                    sel_elem.start_point = self.transform_widget.pA.point
                    sel_elem.end_point = self.transform_widget.pB.point
        self.update()

    def elementsMouseReleaseEvent(self, event):
        tool = self.current_tool
        if self.drag_global or self.drag_capture_zone:
            self.drag_capture_zone = False
            self.drag_global = False
            return
        element = self.elementsGetLastElement()
        if element is None:
            return
        if tool == "arrow":
            element.end_point = event.pos()
            if event.modifiers() & Qt.ShiftModifier:
                element.end_point = elements45DegreeConstraint(element.start_point,
                                                                            element.end_point)
        elif tool in ["zoom_in_region", "copypaste"]:
            if not element.zoom_second_input:
                # element.start_point = event.pos()
                element.end_point = event.pos()
                element.zoom_second_input = True
            elif not element.finished:
                element.copy_pos = event.pos()
                element.finished = True
        elif tool == "stamp":
            element.pixmap = self.current_stamp_pixmap
            element.angle = self.current_stamp_angle
            self.elementsSetStampElementPoints(element, event.pos())
        elif tool in ["pen", "marker"]:
            if element.straight:
                element.end_point = event.pos()
            else:
                element.end_point = event.pos()
                element.path.lineTo(event.pos())
        elif tool == "line":
            element.end_point = event.pos()
            if event.modifiers() & Qt.ShiftModifier:
                element.end_point = elements45DegreeConstraint(element.start_point,
                                                                            element.end_point)
        # ??????-???? ?????????? ???????? ?????????????? ????????????????, ???????? ?????????????????? ?? ???????????????? ?????????? ??????????????????
        elif tool in ["oval", "rect", "numbering", "special"]:
            if element.equilateral:
                delta = element.start_point - event.pos()
                delta = self.equilateral_delta(delta)
                element.end_point = element.start_point - delta
            else:
                element.end_point = event.pos()
        elif tool == "text":
            element.end_point = event.pos()
            element.modify_end_point = False
            self.elementsCreateTextbox(self, element)
        elif tool in ["blurring", "darkening"]:
            element.equilateral = event.modifiers() & Qt.ShiftModifier
            if element.equilateral:
                delta = element.start_point - event.pos()
                delta = self.equilateral_delta(delta)
                element.end_point = element.start_point - delta
            else:
                element.end_point = event.pos()
            if tool == "blurring":
                element.finished = True
                self.elementsSetBlurredPixmap(element)
        elif tool == "transform":
            if self.transform_widget:
                self.transform_widget.retransform_end(event)
                if self.selected_element.type == "blurring":
                    self.selected_element.finished = True
                    self.elementsSetBlurredPixmap(self.selected_element)
                if self.selected_element.type == "text":
                    self.selected_element.modify_end_point = True
        if tool != "transform":
            self.elementsSetSelected(None)
        self.elementsAutoDeleteInvisibleElement(element)
        tw = self.tools_window
        if tw:
            tw.forwards_backwards_update()
        self.update()

    def elementsAutoDeleteInvisibleElement(self, element):
        tool = self.current_tool
        if tool in ['line', 'pen', 'marker']:
            if element.end_point == element.start_point:
                self.elements.remove(element)

    def elementsSetBlurredPixmap(self, element):
        if not element.finished:
            return
        blur_radius = 30*element.size #30 is maximum
        input_rect = build_valid_rect(element.start_point, element.end_point)
        element.pixmap = QPixmap(input_rect.size())
        element.pixmap.fill(Qt.transparent)
        pr = QPainter()
        pr.begin(element.pixmap)
        target_rect = QRect(QPoint(0, 0), input_rect.size())
        pr.drawImage(target_rect, self.source_pixels, input_rect)
        offset_ = input_rect.topLeft()
        offset_.setX(-offset_.x())
        offset_.setY(-offset_.y())
        self.elementsDrawDarkening(pr, offset=offset_)
        pr.end()
        del pr
        blured = QPixmap(input_rect.size())
        blured.fill(Qt.transparent)
        if element.toolbool:
            pixel_size = int(element.size*60)+1
            orig_width = element.pixmap.width()
            orig_height = element.pixmap.height()
            element.pixmap = element.pixmap.scaled(
                orig_width//pixel_size,
                orig_height//pixel_size).scaled(orig_width, orig_height)
        else:
            blured = CustomPushButton.apply_blur_effect(None,
                    element.pixmap, blured, blur_radius=blur_radius)
            blured = CustomPushButton.apply_blur_effect(None,
                    blured, blured, blur_radius=2)
            blured = CustomPushButton.apply_blur_effect(None,
                    blured, blured, blur_radius=blur_radius)
            blured = CustomPushButton.apply_blur_effect(None,
                    blured, blured, blur_radius=5)
            element.pixmap = blured

    def elementsChangeTextbox(self, elem):
        if elem.toolbool:
            background_color = "rgb(200, 200, 200)"
        else:
            background_color = "transparent"
        style = """QTextEdit {
            border: none;
            font-size: %dpx;
            background-color: %s;
            padding: %dpx;
            border-radius: 5px;
            color: %s;
        }
        QTextEdit QMenu::item {
            color: rgb(100, 100, 100);
        }
        QTextEdit QMenu::item:selected{
            color: rgb(0, 0, 0);
        }
        """ % (
                self.elementsGetFontPixelSize(elem),
                background_color,
                elem.margin_value,
                elem.color.name()
        )
        if elem.textbox:
            elem.textbox.setStyleSheet(style)
            self.elementsOnTextChanged(elem)

    def elementsGetFontPixelSize(self, elem):
        return 20+10*elem.size

    def elementsOnTextChanged(self, elem):
        tb = elem.textbox
        size = tb.document().size().toSize()
        # correcting height
        new_height = size.height()+elem.margin_value*2
        tb.setFixedHeight(int(new_height))
        # correcting width
        max_width_limit = max(20, self.capture_region_rect.right() - elem.end_point.x())
        H, W = 100, max_width_limit+10
        pixmap = QPixmap(H, W)
        r = QRect(0, 0, H, W)
        p = QPainter()
        p.begin(pixmap)
        font = tb.currentFont()
        font_pixel_size = self.elementsGetFontPixelSize(elem)
        font.setPixelSize(int(font_pixel_size))
        p.setFont(font)
        brect = p.drawText(r.x(), r.y(), r.width(), r.height(), Qt.AlignCenter, tb.toPlainText())
        p.end()
        del p
        del pixmap
        new_width = min(max_width_limit, brect.width()+elem.margin_value*2+font_pixel_size*1.5)
        tb.setFixedWidth(int(new_width))
        tb.move(elem.end_point-QPoint(0, int(new_height)))
        # making screenshot
        r = tb.rect()
        cw = tb.cursorWidth()
        tb.setCursorWidth(0)
        elem.pixmap = tb.grab(r)
        tb.setCursorWidth(cw)
        if tb.parent():
            tb.parent().update()

    def elementsCreateTextbox(self, parent, elem):
        textbox = QTextEdit()
        self.elementsTextBoxInit(textbox, parent, elem)

    def elementsTextBoxInit(self, textbox, parent, elem):
        textbox.setParent(parent)
        elem.textbox = textbox
        textbox.move(elem.end_point)
        self.elementsChangeTextbox(elem)
        textbox.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        textbox.show()
        self.elementsOnTextChanged(elem) #call to adjust for empty string
        textbox.textChanged.connect(lambda x=elem: self.elementsOnTextChanged(x))
        textbox.setFocus()

    def elementsDrawDarkening(self, painter, offset=None):
        if self.capture_region_rect:
            darkening_value = 0.0
            darkening_zone = QPainterPath()
            darkening_zone.setFillRule(Qt.WindingFill)
            at_least_one_exists = False
            for element in self.elementsHistoryFilter():
                if element.type == "darkening":
                    at_least_one_exists = True
                    darkening_value = element.size
                    r = build_valid_rect(element.start_point, element.end_point)
                    piece = QPainterPath()
                    piece.addRect(QRectF(r))
                    darkening_zone = darkening_zone.united(piece)
            if at_least_one_exists:
                painter.setClipping(True)
                if offset:
                    painter.translate(offset)
                painter.setClipRect(QRectF(self.capture_region_rect))
                painter.setOpacity(0.1+0.9*darkening_value)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(Qt.black))
                capture_dark = QPainterPath()
                capture_dark.addRect(QRectF(self.capture_region_rect))
                capture_dark.addPath(darkening_zone)
                painter.drawPath(capture_dark)
                painter.setOpacity(1.0)
                painter.setClipping(False)

    def draw_transformed_path(self, element, path, painter, final):
        if hasattr(element, "pApos"):
            pApoint = element.pApos
            pBPoint = element.pBpos
            orig_bounding_rect = path.boundingRect()
            current_bounding_rect = build_valid_rect(pApoint, pBPoint)
            # ???????????????????? ????????????
            delta1 = orig_bounding_rect.topLeft() - orig_bounding_rect.bottomRight()
            delta2 = pApoint - pBPoint
            try:
                new_scale_x = delta1.x()/delta2.x()
                new_scale_x = 1/new_scale_x
            except ZeroDivisionError:
                new_scale_x = 0.0
            try:
                new_scale_y = delta1.y()/delta2.y()
                new_scale_y = 1/new_scale_y
            except ZeroDivisionError:
                new_scale_y = 0.0
            # ?????????????????????????? ???????????? ?????????????? ???????????????? ???? ????????
            new_pos = current_bounding_rect.topLeft()
            if new_scale_x < .0:
                new_pos.setX(new_pos.x()+current_bounding_rect.width())
            if new_scale_y < .0:
                new_pos.setY(new_pos.y()+current_bounding_rect.height())
            # ?????????????????? ????????
            # ???????????????? ?????????????? ?????????? ?????????? ???????? ?? ????????
            to_zero = -orig_bounding_rect.topLeft()
            if final:
                path = QPainterPath(path)
                path.translate(-self.elements_global_offset)
                path.translate(-self.get_capture_offset())
            path = path.translated(to_zero.x(), to_zero.y())
            # ???????????? ?????????????????????????? ??????????????
            transform = QTransform()
            transform.translate(new_pos.x(), new_pos.y())
            transform.scale(new_scale_x, new_scale_y)
            painter.setTransform(transform)
            # ???????????? ???????? ?? ???????????????? ??????????????????????????
            painter.drawPath(path)
            # ?????????????????? ??????????????????????????
            painter.resetTransform()
        else:
            path = element.path
            if final:
                path = QPainterPath(path)
                path.translate(-self.elements_global_offset)
                path.translate(-self.get_capture_offset())
            painter.drawPath(path)

    def elementsGetPenFromElement(self, element):
        color = element.color
        size = element.size
        if element.type in ["pen", "line"]:
            PEN_SIZE = 25
        elif element.type == "marker":
            PEN_SIZE = 40
            color.setAlphaF(0.3)
        else:
            PEN_SIZE = 25
        pen = QPen(color, 1+PEN_SIZE*size)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen, color, size

    def elementsDrawMain(self, painter, final=False):
        painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        old_brush = painter.brush()
        old_pen = painter.pen()
        # draw elements
        self.elementsIsFinalDrawing = final
        self.elementsDrawDarkening(painter)
        for element in self.elementsHistoryFilter():
            el_type = element.type
            pen, color, size = self.elementsGetPenFromElement(element)
            painter.setPen(pen)
            painter.setBrush(QBrush(color))
            if el_type == "arrow":
                painter.setPen(Qt.NoPen)
                self.elementsDrawArrow(painter, element.f_start_point,
                                                                element.f_end_point, size, True)
            elif el_type in ["pen", "marker"]:
                painter.setBrush(Qt.NoBrush)
                if element.straight:
                    painter.drawLine(element.f_start_point, element.f_end_point)
                else:
                    self.draw_transformed_path(element, element.path, painter, final)
            elif el_type == "line":
                painter.drawLine(element.f_start_point, element.f_end_point)
            elif el_type == 'special' and not final:
                _pen = painter.pen()
                _brush = painter.brush()
                painter.setPen(QPen(QColor(255, 0, 0), 1))
                painter.setBrush(Qt.NoBrush)
                cm = painter.compositionMode()
                painter.setCompositionMode(QPainter.RasterOp_NotDestination) #RasterOp_SourceXorDestination
                rect = build_valid_rect(element.f_start_point, element.f_end_point)
                painter.drawRect(rect)
                painter.setCompositionMode(cm)
                painter.setPen(_pen)
                painter.setBrush(_brush)
            elif el_type in ["oval", "rect", "numbering"]:
                cur_brush = painter.brush()
                if not element.filled:
                    painter.setBrush(Qt.NoBrush)
                rect = build_valid_rect(element.f_start_point, element.f_end_point)
                if el_type == "oval":
                    painter.drawEllipse(rect)
                else:
                    painter.drawRect(rect)
                if el_type == "numbering":
                    w = self.NUMBERING_WIDTH
                    end_point_rect = QRect(element.f_end_point - QPoint(int(w/2), int(w/2)),
                                                                                    QSize(w, w))
                    painter.setBrush(cur_brush)
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(end_point_rect)
                    if color == Qt.white:
                        painter.setPen(QPen(Qt.black))
                    else:
                        painter.setPen(QPen(Qt.white))
                    font = painter.font()
                    font.setFamily("Consolas")
                    font.setWeight(1600)
                    painter.setFont(font)
                    painter.drawText(end_point_rect.adjusted(-20, -20, 20, 20), Qt.AlignCenter,
                                                                            str(element.number))
            elif el_type == "text":
                if element.pixmap:
                    pixmap = QPixmap(element.pixmap.size())
                    pixmap.fill(Qt.transparent)
                    p = QPainter()
                    p.begin(pixmap)
                    p.setClipping(True)
                    path = QPainterPath()
                    pos = element.f_end_point - QPoint(0, element.pixmap.height())
                    text_rect = QRect(pos, element.pixmap.size())
                    text_rect = QRect(QPoint(0, 0), element.pixmap.size())
                    path.addRoundedRect(QRectF(text_rect), element.margin_value,
                            element.margin_value)
                    p.setClipPath(path)
                    p.drawPixmap(QPoint(0, 0), element.pixmap)
                    p.setClipping(False)
                    p.end()

                painter.setPen(Qt.NoPen)
                if element.f_start_point != element.f_end_point:
                    if element.modify_end_point:
                        modified_end_point = get_nearest_point_on_rect(
                            QRect(pos, QSize(element.pixmap.width(), element.pixmap.height())),
                            element.f_start_point
                        )
                    else:
                        modified_end_point = element.f_end_point
                    self.elementsDrawArrow(painter, modified_end_point, element.f_start_point,
                                                                                    size, False)
                if element.pixmap:
                    image_rect = QRect(pos, pixmap.size())
                    painter.translate(image_rect.center())
                    image_rect = QRectF(-image_rect.width()/2, -image_rect.height()/2,
                            image_rect.width(), image_rect.height()).toRect()
                    painter.rotate(element.rotation)
                    editing = not final and (element is self.selected_element or \
                                                    element is element.textbox.isVisible())
                    if editing:
                        painter.setOpacity(0.5)
                    painter.drawPixmap(image_rect, pixmap)
                    if editing:
                        painter.setOpacity(1.0)
                    painter.resetTransform()

            elif el_type in ["blurring", "darkening"]:
                rect = build_valid_rect(element.f_start_point, element.f_end_point)
                painter.setBrush(Qt.NoBrush)
                painter.setPen(Qt.NoPen)
                if el_type == "blurring":
                    if not element.finished:
                        painter.setBrush(QBrush(QColor(150, 0, 0), Qt.DiagCrossPattern))
                    else:
                        rect = build_valid_rect(element.f_start_point, element.f_end_point)
                        painter.drawPixmap(rect.topLeft(), element.pixmap)
                elif el_type == "darkening":
                    # painter.setBrush(QBrush(QColor(150, 150, 0), Qt.BDiagPattern))
                    pass
                painter.drawRect(rect)
            elif el_type == "stamp":
                pixmap = element.pixmap
                r = build_valid_rect(element.f_start_point, element.f_end_point)
                s = QRect(QPoint(0,0), pixmap.size())
                painter.translate(r.center())
                rotation = element.angle
                painter.rotate(rotation)
                r = QRect(int(-r.width()/2), int(-r.height()/2), r.width(), r.height())
                painter.drawPixmap(r, pixmap, s)
                painter.resetTransform()
            elif el_type == "removing":
                pass
                if Globals.CRUSH_SIMULATOR:
                    1 / 0
            elif el_type in ["zoom_in_region", "copypaste"]:
                f_input_rect = build_valid_rect(element.f_start_point, element.f_end_point)
                curpos = QCursor().pos()
                final_pos = element.f_copy_pos if element.finished else self.mapFromGlobal(curpos)
                final_version_rect = self.elementsBuildSubelementRect(element, final_pos)
                painter.setBrush(Qt.NoBrush)
                if el_type == "zoom_in_region":
                    painter.setPen(QPen(element.color, 1))
                if el_type == "copypaste":
                    painter.setPen(QPen(Qt.red, 1, Qt.DashLine))
                if el_type == "zoom_in_region" or \
                                (el_type == "copypaste" and not final):
                    painter.drawRect(f_input_rect)
                if element.zoom_second_input or element.finished:
                    if element.toolbool and el_type == "zoom_in_region":
                        points = []
                        attrs_names = ["topLeft", "topRight", "bottomLeft", "bottomRight"]
                        for corner_attr_name in attrs_names:
                            p1 = getattr(f_input_rect, corner_attr_name)()
                            p2 = getattr(final_version_rect, corner_attr_name)()
                            points.append(p1)
                            points.append(p2)
                        coords = convex_hull(points)
                        for n, coord in enumerate(coords[:-1]):
                            painter.drawLine(coord, coords[n+1])
                    source_pixels = self.source_pixels
                    # ?? ?????????????????????????????? ???????????????????????? ??????????????????????????, ?????????? ?????????????????????? ??????????????????????
                    # ?????????? ?????????????? ?? ?????????????????????? ???????? ???? ?????????????????????? ???? ???????????????????? ?????????????? 
                    if not final:
                        f_input_rect.moveCenter(f_input_rect.center() - self.elements_global_offset)
                    else:
                        # get_capture_offset ?????????????????? ???? ?????????? ???????????? build_valid_rect,
                        # ?? ?????????? ???????????????????????? ?????? ????????, ?????????? ?????? ???????????????? ?????? ????????
                        f_input_rect.moveCenter(f_input_rect.center() + self.get_capture_offset())
                    painter.drawImage(final_version_rect, source_pixels, f_input_rect)
                    if el_type == "zoom_in_region":
                        painter.drawRect(final_version_rect)
        if not final:
            self.draw_transform_widget(painter)
        if Globals.DEBUG and self.capture_region_rect:
            painter.setPen(QPen(QColor(Qt.white)))
            text = f"{self.elements_history_index} :: {self.current_tool}"
            painter.drawText(self.capture_region_rect, Qt.AlignCenter, text)
        painter.setBrush(old_brush)
        painter.setPen(old_pen)
        self.elementsIsFinalDrawing = False

    def elementsStampRect(self, center_point, size, pixmap):
        s = size
        s += 0.5
        r = QRect(0, 0, int(pixmap.width()*s), int(pixmap.height()*s))
        r.moveCenter(center_point)
        return r

    def elementsDrawFinalVersionDebug(self, painter):
        if self.capture_region_rect and self.elements_final_output:

            # draw final picture
            p = self.capture_region_rect.topRight()
            painter.setOpacity(0.6)
            painter.drawPixmap(p, self.elements_final_output)
            painter.setOpacity(1.0)
            painter.resetTransform()

            # draw debug elements' list
            if self.elements:
                all_elements = self.elements
                visible_elements = self.elementsHistoryFilter()
                info_rect = QRect(QPoint(0, 0),
                        self.capture_region_rect.bottomLeft()-QPoint(10, 10))
                painter.fillRect(QRect(QPoint(0, 0), self.capture_region_rect.bottomLeft()),
                                                                            QColor(0, 0, 0, 180))
                for index, element in reversed(list(enumerate(all_elements))):
                    painter.setPen(QPen(Qt.white))
                    info_text = ""
                    font = painter.font()
                    if element not in visible_elements:
                        painter.setPen(QPen(QColor(255, 100, 100)))
                        font.setStrikeOut(True)
                    else:
                        font.setStrikeOut(False)
                    if self.selected_element and self.selected_element == element:
                        painter.setPen(QPen(Qt.green))
                    if hasattr(element, "source_index"):
                        el = element
                        info_text += f"[{el.unique_index}] {el.type} from [{el.source_index}]"
                    else:
                        info_text += f"[{element.unique_index}] {element.type}"
                    font.setWeight(1900)
                    font.setPixelSize(20)
                    painter.setFont(font)
                    painter.drawText(info_rect.bottomRight() + QPoint(-200, -index*25), info_text)

    def elementsUpdateFinalPicture(self):
        if self.capture_region_rect:
            any_special_element = any(el.type == 'special' for el in self.elements)
            if any_special_element:
                self.specials_case = True
                specials = list((el for el in self.elementsHistoryFilter() if el.type == 'special'))
                max_width = -1
                total_height = 0
                specials_rects = []
                for el in specials:
                    el.bounding_rect = build_valid_rect(el.start_point, el.end_point)
                for el in specials:
                    max_width = max(max_width, el.bounding_rect.width())
                for el in specials:
                    br = el.bounding_rect
                    el.height = int(max_width/br.width()*br.height())
                    total_height += el.height
                _rect = QRect(QPoint(0, 0), QSize(max_width, total_height))
                self.elements_final_output = QPixmap(_rect.size())
                painter = QPainter()
                painter.begin(self.elements_final_output)
                cur_pos = QPoint(0, 0)
                for el in specials:
                    br = el.bounding_rect
                    dst_rect = QRect(cur_pos, QSize(max_width, el.height))
                    painter.drawImage(dst_rect, self.source_pixels, br)
                    cur_pos += QPoint(0, el.height)
                painter.end()
            else:
                self.specials_case = False
                if self.extended_editor_mode:
                    self.elements_final_output = QPixmap(self.capture_region_rect.size())
                    self.elements_final_output.fill(Qt.transparent)
                    painter = QPainter()
                    painter.begin(self.elements_final_output)
                    painter.drawImage(-self.get_capture_offset(), self.source_pixels)
                    self.elementsDrawMain(painter, final=True)
                    painter.end()
                else:
                    _rect = QRect(QPoint(0, 0), self.capture_region_rect.bottomRight())
                    self.elements_final_output = QPixmap(_rect.size())
                    painter = QPainter()
                    painter.begin(self.elements_final_output)
                    painter.drawImage(self.capture_region_rect, self.source_pixels,
                                                                        self.capture_region_rect)
                    self.elementsDrawMain(painter, final=True)
                    painter.end()

    def get_capture_offset(self):
        capture_offset = self.capture_region_rect.topLeft()
        capture_offset -= self.elements_global_offset
        return capture_offset

    def save_screenshot(self, grabbed_image=None, metadata=None):
        def copy_image_data_to_clipboard(fp):
            # ???????????????????? ???????????????????? ???????????????? ?? ??????????,
            # ?????????? ?????????? ???????? ???????????????? ?? ???????????????? ?????? ????????????
            if os.path.exists(fp):
                app = QApplication.instance()
                data = QMimeData()
                url = QUrl.fromLocalFile(fp)
                data.setUrls([url])
                app.clipboard().setMimeData(data)

        # ?????????????? ?????????? ?????? ??????????????????
        SettingsWindow.set_screenshot_folder_path()
        # ???????????????????? ??????????
        formated_datetime = datetime.datetime.now().strftime("%d-%m-%Y %H-%M-%S")
        if grabbed_image:
            # quick fullscreen
            filepath = get_screenshot_filepath(formated_datetime)
            grabbed_image.save(filepath)
            # copy_image_data_to_clipboard(filepath)
            save_meta_info(metadata, filepath)
        else:
            self.elementsUpdateFinalPicture()
            if self.specials_case:
                pix = self.elements_final_output
            else:
                if self.extended_editor_mode:
                    pix = self.elements_final_output
                else:
                    pix = self.elements_final_output.copy(self.capture_region_rect)
            if self.tools_window.chb_masked.isChecked():
                # fragment or fullscreen: masked version
                filepath = get_screenshot_filepath(f"{formated_datetime} masked")
                self.circle_mask_image(pix).save(filepath)
                if self.tools_window.chb_add_meta.isChecked():
                    save_meta_info(self.metadata, filepath)
            else:
                # fragment or fullscreen: default version
                filepath = get_screenshot_filepath(formated_datetime)
                pix.save(filepath)
                if self.tools_window.chb_add_meta.isChecked():
                    save_meta_info(self.metadata, filepath)
            copy_image_data_to_clipboard(filepath)
        restart_app_in_notification_mode(filepath)

    def elementsCreateModificatedCopyOnNeed(self, element, keep_old_widget=False):
        if element == self.elementsGetLastElement():# or element.type == "text":
            # ???????? ?????????????? ?????????????????? ?? ???????????? ??????????????????,
            # ???? ?????? ???????????????????? ?????????????????? ???? ??????????????????????
            return element
        else:
            new_element = self.elementsCreateNew("TEMPORARY_TYPE_NOT_DEFINED")
            self.elementsCopyElementData(new_element, element)
            # new_element.source_index = self.elements.index(element)
            new_element.source_index = element.unique_index
            self.elementsSetSelected(new_element, keep_old_widget=keep_old_widget)
            return new_element

    def init_transform_widget(self):
        se = self.selected_element
        if hasattr(se, "path"):
            r = se.path.boundingRect().toRect()
            return TransformWidget(r)
        if se.type in ["copypaste", "zoom_in_region"]:
            if se.choose_default_subelement:
                r = build_valid_rect(se.start_point, se.end_point)
                return TransformWidget(r, center_point_only=False)
            else:
                subelement_rect = self.elementsBuildSubelementRect(se, se.copy_pos)
                points = (subelement_rect.topLeft(), subelement_rect.bottomRight())
                return TransformWidget(points, center_point_only=True)
        else:
            delta = (se.start_point - se.end_point)
            if se.type == "numbering":
                cp_only = (abs(delta.x()) < 5 and abs(delta.y()) < 5)
                points = (se.start_point, se.end_point)
                return TransformWidget(points, center_point_only=cp_only)
            elif se.type in ["line", "arrow", "text"]:
                points = (se.start_point, se.end_point)
                return TransformWidget(points, center_point_only=False)
            elif se.type in ["marker", "pen"] and hasattr(se, "straight") and se.straight:
                points = (se.start_point, se.end_point)
                return TransformWidget(points, center_point_only=False)
            else:
                r = build_valid_rect(se.start_point, se.end_point)
                return TransformWidget(r, center_point_only=False)

    def draw_transform_widget(self, painter):
        if self.transform_widget:
            self.transform_widget.draw_widget(painter)

    def elementsSetSelected(self, element, keep_old_widget=False):
        if element:
            self.selected_element = element
            if not keep_old_widget:
                self.transform_widget = self.init_transform_widget()
        else:
            self.selected_element = None
            self.transform_widget = None

    def elementsParametersChanged(self):
        tw = self.tools_window
        if tw:
            element = self.selected_element or self.elementsGetLastElement()
            case1 = element and element.type == self.tools_window.current_tool and element.fresh
            case2 = element and tw.current_tool == 'transform'
            if case1 or case2:
                element = self.elementsCreateModificatedCopyOnNeed(element)
                self.elementsSetElementParameters(element)
            if Globals.DEBUG:
                self.elementsUpdateFinalPicture()
        self.update()
        self.activateWindow() # ?????????? ?????????? ???? ???????????????????? ???? ???????????? ??????????????????????

    def elementsDrawArrow(self, painter, start_point, tip_point, size, sharp):
        painter.translate(start_point)
        delta = start_point - tip_point
        radians_angle = math.atan2(delta.y(),delta.x())
        painter.rotate(180+180/3.14*radians_angle)
        arrow_length = math.sqrt(math.pow(delta.x(), 2) + math.pow(delta.y(), 2))
        tip = QPointF(arrow_length, 0)
        offset_x = 40
        offset_y = 19
        t = (arrow_length+5)/50 #???????????? ?????????????? ?????????????? ?????????????? ?????????????????? ???? ??????????
        t = min(1.5, t)
        t *= (0.5 + size)
        if sharp:
            p1 = QPointF(arrow_length-30, 5) - tip  #20, 4  #25, 6
            p1 = tip + p1*t
            p2 = QPointF(arrow_length-offset_x, offset_y) - tip
            p2 = tip + p2*t
            p12 = (p1 + p2)/2.0
            p3 = QPointF(arrow_length-offset_x, -offset_y) - tip
            p3 = tip + p3*t
            p4 = QPointF(arrow_length-30, -5) - tip #20, -4  #25, -6
            p4 = tip + p4*t
            p34 = (p3 + p4)/2.0
            path = QPainterPath()
            path.moveTo(QPointF(0, 1))
            m = 0.25
            inside = (p34 + (p12 - p34)/2.0)*m + (1-m)*(tip)
            path.lineTo(p1)
            path.lineTo(p12)
            path.cubicTo(
                inside,
                inside,
                tip
            )
            path.cubicTo(
                inside,
                inside,
                p34
            )
            path.lineTo(p4)
            path.lineTo(QPointF(0, -1))
            path.lineTo(QPointF(0, 1))
        else:
            rounded = True
            tip_factor=0.85
            t *= 0.15
            tip_point = QPointF(arrow_length, 0)
            start_point = QPointF(0,0)
            start_point_left = start_point + QPointF(0, -1)
            start_point_right = start_point + QPointF(0, 1)
            center = tip_point + QPointF(-80, 0)*t
            center_left = center + QPointF(0, -20)*t
            center_right = center + QPointF(0, 20)*t
            side_left = center_left + QPointF(-10, -40)*t
            side_right = center_right + QPointF(-10, 40)*t
            # building path
            path = QPainterPath()
            if rounded:
                path.moveTo(start_point_left)
                path.lineTo(center_left)
                path.lineTo(center_left*.5+side_left*.5)
                path.quadTo(
                    side_left,
                    side_left*tip_factor+tip_point*(1.0-tip_factor)
                )
                path.lineTo(
                    side_left*(1.0-tip_factor)+tip_point*tip_factor
                )
                path.quadTo(
                    tip_point,
                    side_right*(1.0-tip_factor)+tip_point*tip_factor
                )
                path.lineTo(
                    side_right*tip_factor+tip_point*(1.0-tip_factor)
                )
                path.quadTo(
                    side_right,
                    center_right*.5+side_right*.5
                )
                path.lineTo(center_right)
                path.lineTo(start_point_right)
                path.lineTo(start_point_left)
            else:
                path.moveTo(start_point_left)
                path.lineTo(center_left)
                path.lineTo(side_left)
                path.lineTo(tip_point)
                path.lineTo(side_right)
                path.lineTo(center_right)
                path.lineTo(start_point_right)
                path.lineTo(start_point_left)
        painter.drawPath(path)
        painter.resetTransform()

    def elementsHistoryForwards(self):
        self.elementsDeactivateTextElements()
        if self.elements_history_index < len(self.elements):
            self.elements_history_index += 1
        self.elementsSetSelected(None)

    def elementsHistoryBackwards(self):
        self.elementsDeactivateTextElements()
        if self.elements_history_index > 0:
            self.elements_history_index -= 1
        self.elementsSetSelected(None)

    def elementsUpdateHisotryButtonsStatus(self):
        # print(self.elements_history_index, len(self.elements))
        f = self.elements_history_index < len(self.elements)
        b = self.elements_history_index > 0
        return f, b

    def update_tools_window(self):
        if self.is_rect_defined:
            if not self.tools_window: # create window
                # ???????????? ???????? ???????????????? ??????????????????,
                # ?????????? ?????? ???? ?????????????????? ?? ???? ???????????? ???? ????????????????
                self.tools_window = ToolsWindow(self)
                self.tools_window.show()
        if self.tools_window:
            self.tools_window.do_autopositioning(self.capture_region_rect)

    def mouseMoveEvent(self, event):
        if self.tools_window:
            select_window = self.tools_window.select_window
            if select_window and select_window.isVisible():
                select_window.hide()

        if event.buttons() == Qt.LeftButton:
            self.setCursor(self.get_custom_cross_cursor())

        if event.buttons() == Qt.NoButton:
            # ???????????????????? ???????????? ??????, ?????????? ?????? ?????????????? ???????????????????????? ??????????
            # ???????????????? ???????????? ?????????????????? - ?????? ?????????? ???? ???????? ???????????? ???????? ???????? ????????????????
            self.get_region_info()

        elif event.buttons() == Qt.LeftButton:
            if not self.is_rect_defined:
                # ?????? ???????????????????? ?????????????? ?????????????? ??????????????
                if not self.input_POINT1:
                    self.user_input_started = True
                    self.input_POINT1 = event.pos()
                else:
                    modifiers = event.modifiers()
                    if modifiers == Qt.NoModifier:
                        self.input_POINT2 = event.pos()
                    else:
                        delta = self.input_POINT1 - event.pos()
                        if modifiers & Qt.ControlModifier:
                            delta.setX(delta.x() // 10 * 10 + 1)
                            delta.setY(delta.y() // 10 * 10 + 1)
                        if modifiers & Qt.ShiftModifier:
                            delta = self.equilateral_delta(delta)
                        self.input_POINT2 = self.input_POINT1 - delta

            elif self.undermouse_region_info and not self.drag_inside_capture_zone:
                # ?????? ?????????????????? ?????????????? ?????????????? ?????????? ???????????????????? ??????????????
                self.is_rect_redefined = True
                cursor_pos = event.pos()
                delta = QPoint(cursor_pos - self.old_cursor_position)
                set_func_attr = self.undermouse_region_info.setter
                data_id = self.undermouse_region_info.coords
                get_func_attr = self.undermouse_region_info.getter
                get_func = getattr(self.capture_region_rect, get_func_attr)
                set_func = getattr(self.capture_region_rect, set_func_attr)
                if data_id == "x":
                    set_func(get_func() + delta.x())
                if data_id == "y":
                    set_func(get_func() + delta.y())
                if data_id == "xy":
                    set_func(get_func() + delta)
                self.old_cursor_position = event.globalPos()
                self.capture_region_rect = self._build_valid_rect(
                    self.capture_region_rect.topLeft(),
                    self.capture_region_rect.bottomRight(),
                )
                if not self.extended_editor_mode:
                    # ?????????????????????? ??????????????????????, ?????????? ?????????????? ??????????????
                    # ???? ?????????????? ?? ???????????????? ??????????????
                    # ?? ?????? ?????????? ?? ???????????????? ???? ???????????? ??????????????
                    self.capture_region_rect = \
                                    self._all_monitors_rect.intersected(self.capture_region_rect)
                # topLeft() ???????????? PyQt'???????? QPoint, ?? ?????? ?????????? ???????? QPoint,
                # ?????????????? ???????????? ?? ???????????? ??????????. ???????? ?????????? ???? ?????????????? ?????????? ????????????????????,
                # ???? ?????????? ????????????????, ???????????? ?????? ??????, ???????????????????? ?? input_POINT1 ?? inputPOINT2
                # ?????????????????? ???? ????, ?????? bool(QPoint(0, 0)) ???????????? ???????????????? True,
                # ?? ???? ?????????????????? PyQt'???????? False
                self.input_POINT1 = QPoint(self.capture_region_rect.topLeft())
                self.input_POINT2 = QPoint(self.capture_region_rect.bottomRight())
            elif self.drag_inside_capture_zone:
                # ?????? ???????????????????? ?????????????????? ???????????? ??????????????????
                self.elementsMouseMoveEvent(event)

        elif event.buttons() == Qt.RightButton:
            pass

        self.update()
        self.update_tools_window()
        # super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_cursor_position = event.pos()
            self.get_region_info()
            if self.undermouse_region_info is None:
                self.drag_inside_capture_zone = True
                self.elementsMousePressEvent(event)
            else:
                self.drag_inside_capture_zone = False
        if event.button() == Qt.MidButton and self.tools_window:
            self.tools_window.size_slider.value = 0.5
            self.tools_window.on_parameters_changed()
            self.tools_window.update()

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.drag_inside_capture_zone:
                self.drag_inside_capture_zone = False
                self.elementsMouseReleaseEvent(event)
            if self.user_input_started:
                if not (self.input_POINT1 and self.input_POINT2):
                    # ?????? ???????????? ???????????? ???? ????????????
                    self.user_input_started = True
                    self.input_POINT1 = None
                    self.input_POINT2 = None
                    return
                self.is_rect_defined = True
                self.capture_region_rect = \
                                    self._build_valid_rect(self.input_POINT1, self.input_POINT2)
                if not self.extended_editor_mode:
                    # ?????????????????????? ??????????????????????, ?????????? ?????????????? ?????????????? ???? ?????????????? ?? ???????????????? ??????????????
                    # ?? ?????? ?????????? ?? ???????????????? ???? ???????????? ??????????????
                    self.capture_region_rect = \
                                    self._all_monitors_rect.intersected(self.capture_region_rect)
                self.is_rect_redefined = False
            self.get_region_info() # ?????????? ???????????? ?????? ?????????????????? ??????????????
        if Globals.DEBUG:
            self.elementsUpdateFinalPicture()
        self.update()
        self.update_tools_window()
        super().mouseReleaseEvent(event)

    def change_magnifier_size(self, delta_value):
        values = [80, 90, 100, 120, 150, 170, 200, 250, 300]
        try:
            index = values.index(self.magnifier_size)
        except Exception:
            index = 0
        if index == len(values)-1 and delta_value > 0:
            pass
        elif index == 0 and delta_value < 0:
            pass
        else:
            if delta_value < 0:
                index -=1
            if delta_value > 0:
                index +=1
        self.magnifier_size = values[index]

    def change_tools_params(self, delta_value, modifiers):
        delta_value = delta_value / 24000.0
        if self.tools_window:
            if modifiers == Qt.NoModifier:
                value = self.tools_window.size_slider.value
                value += delta_value * 10.0
                value = min(max(value, 0.0), 1.0)
                self.tools_window.size_slider.value = value
            elif modifiers & Qt.ShiftModifier and not modifiers & Qt.ControlModifier:
                if self.tools_window.color_slider.type == "COLOR":
                    value = self.tools_window.color_slider.value
                    value += delta_value * 2.6
                    value = min(max(value, 0.0), 1.0)
                    self.tools_window.color_slider.value = value
            elif modifiers & Qt.ControlModifier:
                value = self.current_stamp_angle
                if delta_value < 0.0:
                    delta_value = -1
                else:
                    delta_value = 1
                if modifiers & Qt.ShiftModifier:
                    delta_value *= 10
                value += delta_value
                self.current_stamp_angle = value
            self.tools_window.on_parameters_changed()
            self.tools_window.update()
            # ?????????? ?????? ???????????? ???????? ???????????? ???????????????????? ?? ??????????????!

    def wheelEvent(self, event):
        delta_value = event.angleDelta().y()
        if self.capture_region_rect:
            self.change_tools_params(delta_value, event.modifiers())
        else:
            self.change_magnifier_size(delta_value)
        self.update()

    def get_region_info(self):
        self.define_regions_rects_and_set_cursor()
        self.update()

    def contextMenuEvent(self, event):
        contextMenu = QMenu()
        contextMenu.setStyleSheet("""
        QMenu{
            padding: 0px;
            font-size: 20px;
            font-weight: bold;
            font-family: 'Consolas';
        }
        QMenu::item {
            padding: 15px 55px;
            background: #303940;
            color: rgb(230, 230, 230);
        }
        QMenu::item:selected {
            background-color: rgb(253, 203, 54);
            color: rgb(50, 50, 50);
            border-left: 2px dashed #303940;
        }""")
        minimize = contextMenu.addAction("???????????????? ???? ???????????? ??????????")
        cancel = contextMenu.addAction("???????????????? ???????????????? ??????????????????")
        special_tool = contextMenu.addAction("Activate Special Tool")
        reshot = contextMenu.addAction("?????????????????? ????????????????")
        halt = contextMenu.addAction("?????????? ?? ?????????????????? ???????????????????? ????????????????????")
        halt.setIconVisibleInMenu(False)
        cancel.setIconVisibleInMenu(False)
        minimize.setIconVisibleInMenu(False)
        action = contextMenu.exec_(self.mapToGlobal(event.pos()))
        if action == halt:
            sys.exit()
        elif action == minimize:
            self.showMinimized()
        elif action == special_tool:
            if self.tools_window:
                self.tools_window.set_current_tool("special")
        elif action == cancel:
            self.close_this()
        elif action == reshot:
            self.hide()
            if self.tools_window:
                self.tools_window.hide()
            self.source_pixels = make_screenshot_pyqt()
            # updating source-dependent elements
            for element in self.elements:
                if element.type in ['blurring']:
                    self.elementsSetBlurredPixmap(element)
            self.show()
            if self.tools_window:
                self.tools_window.show()

    def get_custom_cross_cursor(self):
        if True or not self._custom_cursor_data:
            w = 32
            w2 = w/2
            w4 = w/4
            self.pix = QPixmap(w, w)
            self.pix.fill(Qt.transparent)
            painter = QPainter(self.pix)
            self._custom_cursor_cycle = (self._custom_cursor_cycle + 1) % 3
            color_vars = {
                0: Qt.green,
                1: Qt.red,
                2: Qt.cyan,
            }
            color = color_vars[self._custom_cursor_cycle]
            painter.setPen(QPen(color, 1))
            painter.drawLine(int(w2), int(w4), int(w2), int(w-w4*2-3))
            painter.drawLine(int(w4), int(w2), int(w-w4*2-3), int(w2))
            painter.drawLine(int(w2), int(w4*3), int(w2), int(w-w4*2+3))
            painter.drawLine(int(w4*3), int(w2), int(w-w4*2+3), int(w2))
            painter.drawPoint(int(w2), int(w2))
            self._custom_cursor_data = QCursor(self.pix)
        return self._custom_cursor_data

    def define_regions_rects_and_set_cursor(self, write_data=True):

        # --------------------------------- #
        # 1         |2          |3          #
        #           |           |           #
        # ----------x-----------x---------- #
        # 4         |5 (sel)    |6          #
        #           |           |           #
        # ----------x-----------x---------- #
        # 7         |8          |9          #
        #           |           |           #
        # --------------------------------- #

        touching_move_data = {
            1: ("setTopLeft",       "xy",   "topLeft"       ),
            2: ("setTop",           "y",    "top"           ),
            3: ("setTopRight",      "xy",   "topRight"      ),
            4: ("setLeft",          "x",    "left"          ),
            5: (None,               None,   None            ),
            6: ("setRight",         "x",    "right"         ),
            7: ("setBottomLeft",    "xy",   "bottomLeft"    ),
            8: ("setBottom",        "y",    "bottom"        ),
            9: ("setBottomRight",   "xy",   "bottomRight"   ),
        }
        regions_cursors = {
            1: QCursor(Qt.SizeFDiagCursor),
            2: QCursor(Qt.SizeVerCursor),
            3: QCursor(Qt.SizeBDiagCursor),
            4: QCursor(Qt.SizeHorCursor),
            5: self.elementsDefineCursorShape(),
            # 5: QCursor(Qt.CrossCursor),
            6: QCursor(Qt.SizeHorCursor),
            7: QCursor(Qt.SizeBDiagCursor),
            8: QCursor(Qt.SizeVerCursor),
            9: QCursor(Qt.SizeFDiagCursor)
        }

        if not self.capture_region_rect:
            self.setCursor(self.elementsDefineCursorShape())
            return

        crr = self.capture_region_rect
        amr = self._all_monitors_rect
        regions = {
            1: QRect(QPoint(0, 0), crr.topLeft()),
            2: QRect(QPoint(crr.left(), 0), crr.topRight()),
            3: QRect(QPoint(crr.right(), 0), QPoint(amr.right(), crr.top())),
            4: QRect(QPoint(0, crr.top()), crr.bottomLeft()),
            5: crr,
            6: QRect(crr.topRight(), QPoint(amr.right(), crr.bottom())),
            7: QRect(QPoint(0, crr.bottom()), QPoint(crr.left(), amr.bottom())),
            8: QRect(crr.bottomLeft(), QPoint(crr.right(), amr.bottom())),
            9: QRect(crr.bottomRight(), amr.bottomRight())
        }
        cursor_pos = self.mapFromGlobal(QCursor().pos())
        for number, rect in regions.items():
            if rect.contains(cursor_pos):
                self.undermouse_region_rect = rect
                self.region_num = number
                if write_data:
                    self.setCursor(regions_cursors[number])
                # ?????????? ???? ???????????????? ??????????????
                # ???? ?????????????????????? ?????????? ???????????????????? ????????
                break
        if write_data:
            if self.region_num == 5:
                self.undermouse_region_info = None
            else:
                data = touching_move_data[self.region_num]
                self.undermouse_region_info = RegionInfo(*data)

    def close_this(self, save_settings=True):
        # ???????????????????? ???????????????? ????????
        if save_settings:
            SettingsJson().set_data("TOOLS_SETTINGS", self.tools_settings)
        if self.tools_window:
            self.tools_window.hide()
        self.close()

    def do_move_cursor(self, coords):
        c = QCursor()
        c.setPos(c.pos() + QPoint(*coords))

    def move_cursor_by_arrow_keys(self, key):
        modifiers = QApplication.queryKeyboardModifiers()
        value = 1
        if modifiers & Qt.ShiftModifier:
            value = 10
        if modifiers & Qt.ControlModifier:
            value *= 5
        if key == Qt.Key_Up:
            self.do_move_cursor((0, -value))
        elif key == Qt.Key_Down:
            self.do_move_cursor((0, value))
        elif key == Qt.Key_Right:
            self.do_move_cursor((value, 0))
        elif key == Qt.Key_Left:
            self.do_move_cursor((-value, 0))

    def emit_mouse_event(self, proc_type):
        def make_event_obj():
            event = QMouseEvent(
                QEvent.MouseButtonPress,
                self.mapFromGlobal(QCursor().pos()),
                Qt.LeftButton,
                Qt.LeftButton,
                Qt.NoModifier
            )
            return event
        if proc_type == "move":
            self.mouseMoveEvent(make_event_obj())
        elif proc_type == "release":
            self.mouseReleaseEvent(make_event_obj())
        elif proc_type == "press":
            self.mousePressEvent(make_event_obj())

    def editing_is_done_handler(self):
        self.close_this()
        app = QApplication.instance()
        app.processEvents()
        self.save_screenshot()

    def keyPressEvent(self, event):
        key = event.key()
        arrow_keys = [Qt.Key_Up, Qt.Key_Down, Qt.Key_Right, Qt.Key_Left]
        if key in arrow_keys:
            if not self.is_rect_defined:
                self.move_cursor_by_arrow_keys(key)
            if (not self.is_rect_defined) and self.user_input_started:
                self.emit_mouse_event("move")
            if self.is_rect_defined:
                self.elementsMoveElement(event)
        # Qt.Key_Return - ???????????????? ????????????????????
        # Qt.Key_Enter - ???????????????? ????????????????????
        if key in [Qt.Key_Return, Qt.Key_Enter]:
            if self.capture_region_rect:
                self.editing_is_done_handler()
            else:
                if self.user_input_started:
                    self.emit_mouse_event("release")
                else:
                    self.emit_mouse_event("press")
                    self.emit_mouse_event("move")
                    cursor = QCursor()
                    cursor.setPos(cursor.pos() + QPoint(100, 100))
                    self.emit_mouse_event("move")
        if key == Qt.Key_Escape:
            select_window = None
            show_quit_dialog = False
            if self.tools_window:
                select_window = self.tools_window.select_window
            if select_window and select_window.isVisible():
                select_window.hide()
            elif event.modifiers() & Qt.ShiftModifier:
                show_quit_dialog = True
            elif Globals.DEBUG:
                self.close_this()
            else:
                show_quit_dialog = True
            if show_quit_dialog:
                self.dialog = QuitDialog(self)
                self.dialog.show_at_center()
        if key == Qt.Key_Backtab: # Tab+Shift
            index = 1
            self.uncapture_draw_type = next(self.uncapture_types)[index]
            # show label
            self.uncapture_mode_label_tstamp = time.time()
        if key == Qt.Key_Tab:
            index = 0
            self.uncapture_draw_type = next(self.uncapture_types)[index]
            # show label
            self.uncapture_mode_label_tstamp = time.time()
        if key == Qt.Key_F1:
            self.show_help_hint = not self.show_help_hint
            self.update()
        if check_scancode_for(event, "C") and event.modifiers() & Qt.ControlModifier:
            color = self.color_at_pixel
            _hex = color.name()
            _r = color.red()
            _g = color.green()
            _b = color.blue()
            _rgb = f"rgb({_r}, {_g}, {_b})"
            color_repr = f"{_hex} {_rgb}"
            self.colors_reprs.append(color_repr)
            self.set_clipboard("\n".join(self.colors_reprs))
        if check_scancode_for(event, "Z"):
            mods = event.modifiers()
            ctrl = mods & Qt.ControlModifier
            shift = mods & Qt.ShiftModifier
              # - Ctrl+Z - ?????? ??????????, Ctrl+Shift+Z - ?????? ????????????
            if self.tools_window:
                if ctrl and shift:
                    self.tools_window.on_forwards_clicked()
                elif ctrl and not shift:
                    self.tools_window.on_backwars_clicked()
                self.update()
                self.tools_window.update()
        if key == Qt.Key_Delete:
            if self.elements:
                self.elementsRemoveElement()
        if check_scancode_for(event, "H"):
            if self.tools_window and self.tools_window.chb_masked.isChecked():
                self.hex_mask = not self.hex_mask
                self.tools_window.on_parameters_changed()
                self.update()
        if key in (Qt.Key_F5, Qt.Key_F6):
            clockwise_rot = key == Qt.Key_F5
            self.elementsTextElementRotate(clockwise_rot)
            self.update()
        if key in (Qt.Key_Space,):
            if self.is_rect_defined:
                self.elementsActivateTransformTool()
        if check_scancode_for(event, "V"):
            mods = event.modifiers()
            ctrl = mods & Qt.ControlModifier
            if ctrl and self.tools_window and self.tools_window.current_tool == "stamp":
                app = QApplication.instance()
                cb = app.clipboard()
                mdata = cb.mimeData()
                pixmap = None
                if mdata and mdata.hasText():
                    path = mdata.text()
                    qt_supported_exts = (
                        ".jpg", ".jpeg", ".jfif",
                        ".bmp",
                        ".gif",
                        ".png",
                        ".tif", ".tiff",
                        ".webp",
                    )
                    PREFIX = "file:///"
                    if path.startswith(PREFIX) and path.lower().endswith(qt_supported_exts):
                        pixmap = QPixmap(path[len(PREFIX):])
                elif mdata and mdata.hasImage():
                    pixmap = QPixmap().fromImage(mdata.imageData())
                if pixmap and pixmap.width() > 0:
                    capture_height = max(self.capture_region_rect.height(), 100)
                    if pixmap.height() > capture_height:
                        pixmap = pixmap.scaledToHeight(capture_height, Qt.SmoothTransformation)
                    self.current_stamp_id = StampInfo.TYPE_FROM_FILE
                    self.current_stamp_pixmap = pixmap
                    self.current_stamp_angle = 0
                    tools_window = self.tools_window
                    tools_window.on_parameters_changed()
                    self.activateWindow()

class StylizedUIBase():

    button_style = """QPushButton{
        font-size: 20px;
        color: #303940;
        text-align: center;
        border-radius: 5px;
        background: rgb(220, 220, 220);
        font-family: 'Consolas';
        font-weight: bold;
        border: 3px dashed #303940;
        padding: 5px;
        height: 40px;
    }
    QPushButton:hover{
        background-color: rgb(253, 203, 54);
        color: black;
    }
    QPushButton#bottom, QPushButton#quit{
        color: rgb(210, 210, 210);
        background-color: none;
        border: none;
        text-decoration: underline;
    }
    QPushButton#quit{
        color: rgb(200, 70, 70);
    }
    QPushButton#bottom:hover{
        color: rgb(200, 0, 0);
        color: white;
        background-color: rgba(200, 200, 200, 0.1);
    }
    QPushButton#quit:hover{
        color: rgb(220, 0, 0);
        background-color: rgba(220, 50, 50, 0.1);
    }
    """
    title_label_style = """
        font-weight: bold;
        font-size: 18px;
        color: white;
        margin-bottom: 14px;
        text-align: center;
        font-weight: bold;
        width: 100px;
    """
    info_label_style = """
        font-size: 15px;
        color: yellow;
        margin: 2px;
        text-align: center;
    """
    info_label_style_white = """
        font-size: 15px;
        color: white;
        margin: 2px;
        text-align: center;
    """
    info_label_style_settings = """
        font-size: 17px;
        color: yellow;
        margin: 2px;
        text-align: center;
    """

    settings_checkbox = """
        QCheckBox {
            font-size: 18px;
            font-family: 'Consolas';
            color: white;
            font-weight: normal;
        }
        QCheckBox::indicator:unchecked {
            background: gray;
        }
        QCheckBox::indicator:checked {
            background: green;
        }
        QCheckBox:checked {
            background-color: rgba(150, 150, 150, 50);
            color: rgb(100, 255, 100);
        }
        QCheckBox:unchecked {
            color: gray;
        }
    """

    CLOSE_BUTTON_RADIUS = 50

    def mouseMoveEvent(self, event):
        if self.inside_close_button():
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        self.update()

    def mouseReleaseEvent(self, event):
        if self.inside_close_button():
            if Globals.DEBUG:
                sys.exit()
            else:
                self.hide()

    def get_close_btn_rect(self):
        top_right_corner = self.rect().topRight()
        close_btn_rect = QRect(
            top_right_corner.x() - self.CLOSE_BUTTON_RADIUS,
            top_right_corner.y() - self.CLOSE_BUTTON_RADIUS,
            self.CLOSE_BUTTON_RADIUS * 2,
            self.CLOSE_BUTTON_RADIUS * 2,
        )
        return close_btn_rect

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        path = QPainterPath()
        painter.setClipping(True)
        path.addRoundedRect(QRectF(self.rect()), 10, 10)
        painter.setClipPath(path)
        painter.setPen(Qt.NoPen)
        color = QColor("#303940")
        color = QColor(48, 57, 64)
        painter.setBrush(QBrush(color))
        painter.drawPath(path)
        self.draw_close_button(painter)
        color = QColor(150, 30, 30)
        color = QColor(48, 57, 64)
        color = QColor(58, 67, 74)
        painter.setPen(QPen(color, 4))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        painter.end()

    def mapped_cursor_pos(self):
        return self.mapFromGlobal(QCursor().pos())

    def inside_close_button(self):
        close_btn_rect = self.get_close_btn_rect()
        top_right_corner = self.rect().topRight()
        diff = top_right_corner - self.mapped_cursor_pos()
        distance = math.sqrt(pow(diff.x(), 2) + pow(diff.y(), 2))
        size = close_btn_rect.width()/2
        client_area = QRect(QPoint(close_btn_rect.x(), 0), QSize(int(size), int(size)))
        return distance < self.CLOSE_BUTTON_RADIUS and \
            client_area.contains(self.mapped_cursor_pos())

    def draw_close_button(self, painter):
        if self.inside_close_button():
            painter.setOpacity(.6)
        else:
            painter.setOpacity(.3)
        painter.setBrush(QBrush(Qt.red, Qt.SolidPattern))
        painter.setPen(Qt.NoPen)
        close_btn_rect = self.get_close_btn_rect()
        top_right_corner = self.rect().topRight()
        painter.drawEllipse(close_btn_rect)
        w_ = int(self.CLOSE_BUTTON_RADIUS/2-5)
        cross_pos = top_right_corner + QPoint(-w_, w_)
        painter.setPen(QPen(Qt.white, 4, Qt.SolidLine))
        painter.setBrush(QBrush(Qt.white, Qt.SolidPattern))
        painter.setOpacity(1.0)
        painter.drawLine(
            cross_pos.x()-int(self.CLOSE_BUTTON_RADIUS/8),
            cross_pos.y()-int(self.CLOSE_BUTTON_RADIUS/8),
            cross_pos.x()+int(self.CLOSE_BUTTON_RADIUS/8),
            cross_pos.y()+int(self.CLOSE_BUTTON_RADIUS/8)
        )
        painter.drawLine(
            cross_pos.x()+int(self.CLOSE_BUTTON_RADIUS/8),
            cross_pos.y()-int(self.CLOSE_BUTTON_RADIUS/8),
            cross_pos.x()-int(self.CLOSE_BUTTON_RADIUS/8),
            cross_pos.y()+int(self.CLOSE_BUTTON_RADIUS/8)
        )

    def place_window(self):
        self.show()
        Y_OFFSET = 60
        desktop = QDesktopWidget()
        screen = desktop.screenNumber(QCursor().pos())
        screen_rect = desktop.screenGeometry(screen=screen)
        width = self.rect().width()
        height = self.rect().height()
        x = screen_rect.right()-screen_rect.left()-width
        y = screen_rect.bottom()-height-Y_OFFSET
        self.label.setFixedWidth(self.label.sizeHint().width())
        self.move(QPoint(x, y))
        if self.show_at_center:
            cp = QDesktopWidget().availableGeometry().center()
            qr = self.frameGeometry()
            qr.moveCenter(cp)
            self.move(qr.topLeft())

class SettingsWindow(QWidget, StylizedUIBase):
    WIDTH = 600
    PARTITION_SPACING = 10

    instance = None

    STARTUP_CONFIG = (
        'oxxxy_launcher',
        os.path.join(os.path.dirname(__file__), "launcher.pyw")
    )

    @classmethod
    def set_screenshot_folder_path_dialog(cls):
        msg = "???????????????? ??????????, ?? ?????????????? ?????????? ???????????????????????? ??????????????????"
        path = QFileDialog.getExistingDirectory(None, msg, Globals.SCREENSHOT_FOLDER_PATH)
        path = str(path)
        if path:
            Globals.SCREENSHOT_FOLDER_PATH = path
            SettingsJson().set_data("SCREENSHOT_FOLDER_PATH", Globals.SCREENSHOT_FOLDER_PATH)
        if hasattr(cls, 'instance'):
            cls.instance.label_1_path.setText(cls.get_path_for_label())

    @classmethod
    def set_screenshot_folder_path(cls, get_only=False):
        if not Globals.SCREENSHOT_FOLDER_PATH:
            npath = os.path.normpath
            sj_path = SettingsJson().get_data("SCREENSHOT_FOLDER_PATH")
            if sj_path:
                Globals.SCREENSHOT_FOLDER_PATH = npath(sj_path)
        if get_only:
            return
        while not Globals.SCREENSHOT_FOLDER_PATH:
            cls.set_screenshot_folder_path_dialog()

    @classmethod
    def get_path_for_label(cls):
        cls.set_screenshot_folder_path(get_only=True)
        if os.path.exists(Globals.SCREENSHOT_FOLDER_PATH):
            return f" ?????????????? ????????: {Globals.SCREENSHOT_FOLDER_PATH}"
        else:
            return "  ???????? ???? ??????????!"

    def __init__(self, menu=False, notification=False, filepath=None):
        super().__init__()

        if hasattr(SettingsWindow, "instance"):
            if SettingsWindow.instance:
                SettingsWindow.instance.hide()
        SettingsWindow.instance = self

        STYLE = "color: white; font-size: 18px;"

        self.show_at_center = False
        title = f"Oxxxy Settings {Globals.VERSION_INFO}"
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.layout = QVBoxLayout()
        margin = 5
        self.layout.setContentsMargins(margin, margin, margin, margin)

        self.label = QLabel()
        self.label.setText(title)
        self.label.setStyleSheet(self.title_label_style)

        label_1 = QLabel("<b>?????????? ?????? ???????????????????? ??????????????????</b>")
        label_1.setStyleSheet(self.info_label_style_settings)
        label_1_path = QLabel(SettingsWindow.get_path_for_label())
        label_1_path.setStyleSheet(STYLE)
        self.label_1_path = label_1_path
        path_change_btn = QPushButton("???????????????? ???????? ?? ??????????????????")
        path_change_btn.setObjectName("bottom")
        path_change_btn.setStyleSheet(self.button_style)
        path_change_btn.setCursor(Qt.PointingHandCursor)
        path_change_btn.clicked.connect(SettingsWindow.set_screenshot_folder_path_dialog)
        layout_1 = QVBoxLayout()
        layout_1.addWidget(label_1_path)
        layout_1.addWidget(path_change_btn)

        label_2 = QLabel("<b>???????????????????? ???????????? (?????????? ???????????????? ???????????? ???? ????????)</b>")
        label_2.setStyleSheet(self.info_label_style_settings)
        info_label_1 = "<b>CTRL+PRINT SCREEN</b><br>???????????????? ?? ???????????????? ?????????????????? ????????????"
        info_label_2 = "<b>CTRL+SHIFT+PRINT SCREEN</b><br>???????????????? ?? ???????????????? ?????????? ????????????"
        info_label_3 = "<b>SHIFT+PRINT SCREEN</b><br>?????????????? ???????????????? ?????????? ????????????"
        layout_2 = QVBoxLayout()
        for label_text in [info_label_1, info_label_2, info_label_3]:
            _label = QLabel("<center>%s</center>" % label_text)
            _label.setStyleSheet(self.info_label_style_white)
            _label.setWordWrap(True)
            layout_2.addWidget(_label)

        label_3 = QLabel("<b>???????????????????????????? ????????????</b>")
        label_3.setStyleSheet(self.info_label_style_settings)
        chbx_3 = QCheckBox("?????????????????? Oxxxy ?????? ???????????? Windows")
        chbx_3.setStyleSheet(self.settings_checkbox)
        chbx_3.setChecked(is_app_in_startup(self.STARTUP_CONFIG[0]))
        chbx_3.stateChanged.connect(lambda: self.handle_windows_startup_chbx(chbx_3))
        layout_3 = QVBoxLayout()
        layout_3.setAlignment(Qt.AlignCenter)
        layout_3.addWidget(chbx_3)

        label_4 = QLabel("<b>??????????/?????????????? ??????????</b>")
        label_4.setStyleSheet(self.info_label_style_settings)
        chbx_4 = QCheckBox("???????????????? ?????????? ?????????? ???? ?????????????? ????????????")
        chbx_4.setStyleSheet(self.settings_checkbox)
        use_color_palette = SettingsJson().get_data("USE_COLOR_PALETTE")
        chbx_4.setChecked(bool(use_color_palette))
        chbx_4.stateChanged.connect(lambda: self.handle_palette_chbx(chbx_4))
        layout_4 = QVBoxLayout()
        layout_4.setAlignment(Qt.AlignCenter)
        layout_4.addWidget(chbx_4)

        label_5 = QLabel("<b>?????????? ?????? ???????????? ????????????????????????</b>")
        label_5.setStyleSheet(self.info_label_style_settings)
        chbx_5 = QCheckBox("???????????????? ?????????? FLAT")
        chbx_5.setStyleSheet(self.settings_checkbox)
        use_flat_ui = SettingsJson().get_data("ENABLE_FLAT_EDITOR_UI")
        chbx_5.setChecked(bool(use_flat_ui))
        chbx_5.stateChanged.connect(lambda: self.handle_ui_style_chbx(chbx_5))
        layout_5 = QVBoxLayout()
        layout_5.setAlignment(Qt.AlignCenter)
        layout_5.addWidget(chbx_5)

        # ??????????????????
        self.layout.addSpacing(self.PARTITION_SPACING)
        self.layout.addWidget(self.label, Qt.AlignLeft)
        self.layout.addSpacing(self.PARTITION_SPACING)

        # ?????????? ?????? ???????????????????? ????????????????????
        self.layout.addWidget(label_1)
        self.layout.addLayout(layout_1)
        self.layout.addSpacing(self.PARTITION_SPACING)

        # ???????????????????????????? ????????????
        self.layout.addWidget(label_3)
        self.layout.addLayout(layout_3)
        self.layout.addSpacing(self.PARTITION_SPACING)

        # ???????????????????? ????????????
        self.layout.addWidget(label_2)
        self.layout.addLayout(layout_2)
        self.layout.addSpacing(self.PARTITION_SPACING)

        # ?????????????? ???????????? ?????????? ??????????
        self.layout.addWidget(label_4)
        self.layout.addLayout(layout_4)
        self.layout.addSpacing(self.PARTITION_SPACING)

        # ?????????????? ???????????? ?????????? ??????????
        self.layout.addWidget(label_5)
        self.layout.addLayout(layout_5)
        self.layout.addSpacing(self.PARTITION_SPACING)

        self.setLayout(self.layout)
        self.setMouseTracking(True)

    def handle_palette_chbx(self, sender):
        SettingsJson().set_data("USE_COLOR_PALETTE", sender.isChecked())
        Globals.USE_COLOR_PALETTE = sender.isChecked()

    def handle_ui_style_chbx(self, sender):
        SettingsJson().set_data("ENABLE_FLAT_EDITOR_UI", sender.isChecked())
        Globals.ENABLE_FLAT_EDITOR_UI = sender.isChecked()

    def handle_windows_startup_chbx(self, sender):
        if sender.isChecked():
            add_to_startup(*self.STARTUP_CONFIG)
        else:
            remove_from_startup(self.STARTUP_CONFIG[0])

class NotificationOrMenu(QWidget, StylizedUIBase):
    CLOSE_BUTTON_RADIUS = 50
    WIDTH = 300

    instance = None
    def __init__(self, menu=False, notification=False, filepath=None):
        super().__init__()
        if not (notification != menu):
            raise

        NotificationOrMenu.instance = self

        self.setWindowTitle(f"Oxxxy Screenshoter {Globals.VERSION_INFO} {Globals.AUTHOR_INFO}")
        self.show_at_center = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.layout = QVBoxLayout()
        margin = 5
        self.layout.setContentsMargins(margin, margin, margin, margin)

        if notification and not menu:
            self.widget_type = "notification"
            self.filepath = filepath

            self.timer = QTimer()
            self.timer.timeout.connect(self.countdown_handler)
            self.timer.setInterval(100)
            self.start_time = time.time()

            label = "???????????????? ??????????!"
            self.label = QLabel()
            self.label.setText(label)
            self.label.setStyleSheet(self.title_label_style)
            self.label.setFixedWidth(self.WIDTH - self.CLOSE_BUTTON_RADIUS)

            open_image_btn_gchr = QPushButton("?????????????? ?? ????????????????")
            open_image_btn_gchr.setStyleSheet(self.button_style)
            open_image_btn_gchr.setFixedWidth(self.WIDTH)
            open_image_btn_gchr.clicked.connect(self.open_image)
            open_image_btn_gchr.setFocusPolicy(Qt.NoFocus)
            open_image_btn_gchr.setCursor(Qt.PointingHandCursor)

            open_image_btn = QPushButton("??????????????")
            open_image_btn.setStyleSheet(self.button_style)
            open_image_btn.setFixedWidth(self.WIDTH)
            open_image_btn.clicked.connect(self.open_image_shell)
            open_image_btn.setFocusPolicy(Qt.NoFocus)
            open_image_btn.setCursor(Qt.PointingHandCursor)

            open_folder_btn = QPushButton("?????????????? ??????????")
            open_folder_btn.setStyleSheet(self.button_style)
            open_folder_btn.setFixedWidth(self.WIDTH)
            open_folder_btn.clicked.connect(self.open_folder)
            open_folder_btn.setFocusPolicy(Qt.NoFocus)
            open_folder_btn.setCursor(Qt.PointingHandCursor)

            self.layout.addSpacing(10)
            self.layout.addWidget(self.label)
            self.layout.addWidget(open_image_btn_gchr)
            self.layout.addSpacing(10)
            self.layout.addWidget(open_image_btn)
            self.layout.addSpacing(10)
            self.layout.addWidget(open_folder_btn)
            self.layout.addSpacing(10)

            self.timer.start()

        if menu and not notification:
            self.widget_type = "menu"

            self.label = QLabel()
            self.label.setText(f"Oxxxy {Globals.VERSION_INFO}")
            self.label.setStyleSheet(self.title_label_style)
            self.label.setFixedWidth(self.WIDTH - self.CLOSE_BUTTON_RADIUS)

            # ???????????? ????????????
            screenshot_fragment_btn = QPushButton("????????????????")
            screenshot_fullscreens_btn = QPushButton("??????????")
            # screenshot_remake_btn = QPushButton("???????????????????? ??????????????\n(??????????????????????????????????)")
            # ???????????? ????????????
            open_history_btn = QPushButton("??????????????")
            open_recent_screenshot_btn = QPushButton("????????????????\n??????????????????")
            open_recent_screenshot_btn.clicked.connect(self.open_recent_screenshot)

            editor_compile_btn = QPushButton('????????????')

            open_settings_btn = QPushButton("??????????????????")

            show_crushlog_btn = QPushButton("?????????????? crush.log")
            self.show_crushlog_btn = show_crushlog_btn

            # ?? ?????????????? ????????
            quit_btn = QPushButton("??????????")
            show_source_code_btn = QPushButton("????????\n???? GitHub")
            show_source_code_btn.clicked.connect(self.show_source_code)
            object_name_list = [
                # open_settings_btn,
                show_crushlog_btn,
                quit_btn,
                show_source_code_btn
            ]
            for btn in object_name_list:
                btn.setObjectName("bottom")

            quit_btn.setObjectName("quit")

            self.first_row = QHBoxLayout()
            self.first_row.addWidget(screenshot_fragment_btn)
            self.first_row.addWidget(screenshot_fullscreens_btn)

            self.second_row = QHBoxLayout()
            self.second_row.addWidget(open_history_btn)
            self.second_row.addWidget(open_recent_screenshot_btn)

            self.thrid_row = QVBoxLayout()
            self.thrid_row.addWidget(open_settings_btn)
            self.thrid_row.addWidget(show_crushlog_btn)

            self.bottom_row = QHBoxLayout()
            self.bottom_row.addWidget(quit_btn)
            self.bottom_row.addWidget(show_source_code_btn)

            self.layout.addSpacing(10)
            self.layout.addWidget(self.label)
            self.layout.addLayout(self.first_row)
            # self.layout.addWidget(screenshot_remake_btn)
            self.layout.addLayout(self.second_row)
            self.layout.addSpacing(10)
            self.layout.addWidget(editor_compile_btn)
            self.layout.addSpacing(20)
            self.layout.addLayout(self.thrid_row)
            self.layout.addLayout(self.bottom_row)
            self.layout.addSpacing(10)

            open_history_btn.clicked.connect(self.open_folder)
            editor_compile_btn.clicked.connect(self.start_editor_in_compile_mode)
            screenshot_fragment_btn.clicked.connect(self.start_screenshot_editor_fragment)
            screenshot_fullscreens_btn.clicked.connect(self.start_screenshot_editor_fullscreen)
            open_settings_btn.clicked.connect(self.open_settings_window)
            show_crushlog_btn.clicked.connect(show_crush_log)
            quit_btn.clicked.connect(self.app_quit)
            btn_list = [
                screenshot_fragment_btn,
                screenshot_fullscreens_btn,
                # screenshot_remake_btn,
                editor_compile_btn,
                open_history_btn,
                open_recent_screenshot_btn,
                open_settings_btn,
                show_crushlog_btn,
                quit_btn,
                show_source_code_btn
            ]
            for btn in btn_list:
                btn.setStyleSheet(self.button_style)
                btn.setCursor(Qt.PointingHandCursor)
            for btn in [
                    screenshot_fragment_btn,
                    screenshot_fullscreens_btn,
                    # screenshot_remake_btn,
                    open_history_btn,
                    open_recent_screenshot_btn
                ]:
                btn.setFixedHeight(80)
        self.setFixedWidth(self.WIDTH+margin*2)
        self.setLayout(self.layout)
        self.setMouseTracking(True)

    def open_settings_window(self):
        SettingsWindow().place_window()
        self.hide()

    def show_menu(self):
        if self.isVisible():
            self.hide()
        if self.widget_type == "menu":
            if os.path.exists(get_crushlog_filepath()):
                self.show_crushlog_btn.setVisible(True)
            else:
                self.show_crushlog_btn.setVisible(False)
            self.place_window()

    def open_recent_screenshot(self):
        SettingsWindow.set_screenshot_folder_path(get_only=True)

        recent_filepath = None
        timestamp = 0.0
        _path = Globals.SCREENSHOT_FOLDER_PATH
        if _path and os.path.exists(_path):
            for file_name in os.listdir(_path):
                filepath = os.path.join(_path, file_name)
                creation_date = get_creation_date(filepath)
                if creation_date > timestamp:
                    timestamp = creation_date
                    recent_filepath = filepath

        if recent_filepath:
            self.filepath = recent_filepath
            self.open_image()
        else:
            txt = """???????????????????? ?????????????????? ??????????????.
            ?????????????????? ??????????????:
            1) ?? ?????????? ?????? ?????? ????????????
            2) ?????????? ?????? ???? ????????????
            3) ???????????????? ?????????? ???? ????????????????????.

            !!! ?????????? ?????????? ???????? ???????????? ?????? ???????????????????? ??????????????????, ???????? ?????? ???? ???????? ????????????.
            """
            QMessageBox.critical(None, "????????????", txt.replace("\t", ""))
        self.hide()

    def show_source_code(self):
        open_link_in_browser("https://github.com/sergkrumas/oxxxy")

    def open_image_shell(self):
        os.startfile(self.filepath)
        self.close_notification_window_and_quit()

    def open_image(self):
        open_in_google_chrome(self.filepath)
        self.close_notification_window_and_quit()

    def start_screenshot_editor_fragment(self):
        self.hide()
        invoke_screenshot_editor(request_type=RequestType.Fragment)

    def start_screenshot_editor_fullscreen(self):
        self.hide()
        invoke_screenshot_editor(request_type=RequestType.Fullscreen)

    def start_editor_in_compile_mode(self):
        self.hide()
        invoke_screenshot_editor(request_type=RequestType.Editor)

    def open_folder(self):
        SettingsWindow.set_screenshot_folder_path(get_only=True)
        args = ["explorer.exe", '{}'.format(Globals.SCREENSHOT_FOLDER_PATH)]
        # QMessageBox.critical(None, "Debug info", "{}".format(args))
        subprocess.Popen(args)
        # os.system("start {}".format(Globals.SCREENSHOT_FOLDER_PATH))
        self.close_notification_window_and_quit()

    def countdown_handler(self):
        if self.underMouse():
            self.timer.stop()
            return
        if time.time() - self.start_time > 4.5:
            self.close_notification_window_and_quit()

    def close_notification_window_and_quit(self):
        if self.widget_type == "notification":
            self.timer.stop()
            app = QApplication.instance()
            app.exit()

    def hide(self):
        super().hide()
        if self.widget_type == "notification":
            self.close_notification_window_and_quit()

    def app_quit(self):
        Globals.FULL_STOP = True
        app = QApplication.instance()
        app.quit()

class QuitDialog(QWidget, StylizedUIBase):
    WIDTH = 500

    def __init__(self, *args, **kwargs):
        super().__init__( *args, **kwargs)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowModality(Qt.WindowModal)
        main_layout = QVBoxLayout()
        self.button = QPushButton("????")
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setStyleSheet(self.button_style)
        self.button.clicked.connect(self.yes_handler)

        self.setWindowTitle(f"Oxxxy Screenshoter {Globals.VERSION_INFO}")

        self.label = QLabel()
        self.label.setText("???? ?????????????????????????? ???????????? ?????????? ?????? ???????????????????? ???????????????????")
        self.label.setStyleSheet(self.title_label_style)
        self.label.setFixedWidth(self.WIDTH - self.CLOSE_BUTTON_RADIUS)
        self.label.setWordWrap(True)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_handler)
        self.timer.setInterval(100)
        self.timer.start()
        main_layout.addWidget(self.label)
        main_layout.addWidget(self.button)
        self.setLayout(main_layout)
        self.resize(self.WIDTH, 200)
        self.setMouseTracking(True)

    def yes_handler(self):
        app = QApplication.instance()
        app.exit()

    def update_handler(self):
        self.update()

    def show_at_center(self):
        self.show()
        cp = QDesktopWidget().availableGeometry().center()
        qr = self.frameGeometry()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        self.activateWindow()

    def mouseReleaseEvent(self, event):
        if self.inside_close_button():
            self.close()

def global_hotkey_listener(callback=None):

    # ?????? ???????????????????? ?????????? ?????? ????????, ?????????? ?????? ???????????????????????? *make_fullscreen*
    # ???? ?????????????????????? ?????????? ?????????? ?????? ?? *make_fragment*, ?? *make_it_quick*.
    # ?????? ?????? ???????????? ???????? ?????????????? ????-???? ???????????????????????? pynput.
    # ?????????? ???? ???????????????????? ??????, ?????? *make_fullscreen* ????????????????????????
    # ????????????, ?????? *make_fragment* ?? *make_it_quick*.
    # ???? ????????, ???????????? ???? ?????? ?????????? ???????????????????????????? ?? ?????????? ??????????????
    # ?????? ?????????? ????????????????????. ?????????????? ???????? - ?????? ?? ??????,
    # ?????????????????? ?????? ?????? ??????????. ?????????? ???????? - ?????????????????? ??????-???????????? ????????????.
    _fragment = False
    _quick = False

    def make_fragment():
        nonlocal _fragment
        if _fragment:
            _fragment = False
            return
        if callback:
            callback.hotkey_pressed.emit(RequestType.Fragment)

    def make_fullscreen():
        nonlocal _fragment
        nonlocal _quick
        _fragment = True
        _quick = True
        if callback:
            callback.hotkey_pressed.emit(RequestType.Fullscreen)

    def make_it_quick():
        nonlocal _quick
        if _quick:
            _quick = False
            return
        if callback:
            callback.hotkey_pressed.emit(RequestType.QuickFullscreen)

    settings = {
        '<ctrl>+<shift>+<print_screen>': make_fullscreen,
        '<ctrl>+<print_screen>': make_fragment,
        '<shift>+<print_screen>': make_it_quick,
    }
    with keyboard.GlobalHotKeys(settings) as h:
        h.join()

def restart_app_in_notification_mode(filepath):
    args = [sys.executable, __file__, filepath, "-notification"]
    subprocess.Popen(args)

def show_system_tray(app, icon):
    sti = QSystemTrayIcon(app)
    sti.setIcon(icon)
    sti.setToolTip(f"Oxxxy {Globals.VERSION_INFO} {Globals.AUTHOR_INFO}")
    app.setProperty("stray_icon", sti)
    @pyqtSlot()
    def on_trayicon_activated(reason):
        if reason == QSystemTrayIcon.Trigger: # ???????? ?????????????? ?????????? - ???? ???????????? ???????????????? ??????????????????
            invoke_screenshot_editor(request_type=RequestType.Fragment)
        if reason == QSystemTrayIcon.Context: # ???????? ???????????? - ???????????????? ????????-????????
            if NotificationOrMenu.instance:
                NotificationOrMenu.instance.show_menu()
            else:
                NotificationOrMenu(menu=True).show_menu()
    sti.activated.connect(on_trayicon_activated)
    sti.show()
    return sti

# def get_fucking_focus_win32():
#     from ctypes import windll, Structure, c_long, byref, wintypes
#     class POINT(Structure):
#         _fields_ = [("x", c_long), ("y", c_long)]

#     pos = POINT()
#     pos.x = c_long(100)
#     pos.y = c_long(100)
#     hwnd = windll.user32.WindowFromPoint(pos)

#     import win32gui
#     win32gui.SetForegroundWindow(hwnd)

def invoke_screenshot_editor(request_type=None):
    global screenshot_editor
    if request_type is None:
        raise Exception("Unknown request type")
    # ???????? ???????? ?????????????? ????????-???????? ?????????? ???????? - ???????????? ??????
    if NotificationOrMenu.instance:
        NotificationOrMenu.instance.hide()
    if SettingsWindow.instance:
        SettingsWindow.instance.hide()

    metadata = generate_metainfo()
    # started_time = time.time()

    screenshot_image = make_screenshot_pyqt()
    if request_type == RequestType.Fragment:
        screenshot_editor = ScreenshotWindow(screenshot_image, metadata)
        screenshot_editor.show()
        # print("^^^^^^", time.time() - started_time)
        if Globals.DEBUG and Globals.DEBUG_ELEMENTS:
            screenshot_editor.request_elements_debug_mode()
        # ?????????? activateWindow ?????????? ???????????????? ?? ???????? ?????????? ??????????
        QApplication.instance().processEvents()
        screenshot_editor.activateWindow()

    if request_type == RequestType.Fullscreen:
        screenshot_editor = ScreenshotWindow(screenshot_image, metadata)
        screenshot_editor.request_fullscreen_capture_region()
        screenshot_editor.show()
        # ?????????? activateWindow ?????????? ???????????????? ?? ???????? ?????????? ??????????
        QApplication.instance().processEvents()
        screenshot_editor.activateWindow()

    if request_type == RequestType.Editor:
        filepaths = get_filepaths_dialog()
        if filepaths:
            screenshot_editor = ScreenshotWindow(screenshot_image, metadata)
            screenshot_editor.request_editor_mode(filepaths)
            screenshot_editor.show()
            # ?????????? activateWindow ?????????? ???????????????? ?? ???????? ?????????? ??????????
            QApplication.instance().processEvents()
            screenshot_editor.activateWindow()

    if request_type == RequestType.QuickFullscreen:
        ScreenshotWindow.save_screenshot(None, grabbed_image=screenshot_image, metadata=metadata)
        app = QApplication.instance()
        app.exit()

class ListenHotkeyThread(QThread):
    hotkey_pressed = pyqtSignal(object)
    def __init__(self):
        super().__init__()
        self.hotkey_pressed.connect(self.callback_function, Qt.QueuedConnection)
        self.allowed = True #?????? ???????????????????????? ???????????? ???????? ??????

    def callback_function(self, i):
        if self.allowed:
            invoke_screenshot_editor(request_type=i)
            self.allowed = False

    def run(self):
        global_hotkey_listener(callback=self)

def show_crush_log():
    path = get_crushlog_filepath()
    if os.path.exists(path):
        open_link_in_browser(path)
    else:
        QMessageBox.critical(None, "??????????????????",
                "?????????? ???? ??????????????, ???????????? ?????????????????? ?????? ???? ??????????????????.")

def get_crushlog_filepath():
    if Globals.DEBUG:
        root = os.path.dirname(__file__)
    else:
        root = os.path.expanduser("~")
    path = os.path.normpath(os.path.join(root, "oxxxy_crush.log"))
    return path

def excepthook(exc_type, exc_value, exc_tb):
    # ?????????? ???????? ?? ??????????
    if isinstance(exc_tb, str):
        traceback_lines = exc_tb
    else:
        traceback_lines = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    locale.setlocale(locale.LC_ALL, "russian")
    datetime_string = time.strftime("%A, %d %B %Y %X").capitalize()
    dt = "{0} {1} {0}".format(" "*15, datetime_string)
    dt_framed = "{0}\n{1}\n{0}\n".format("-"*len(dt), dt)
    with open(get_crushlog_filepath(), "a+", encoding="utf8") as crush_log:
        crush_log.write("\n"*10)
        crush_log.write(dt_framed)
        crush_log.write("\n")
        crush_log.write(traceback_lines)
    print("*** excepthook info ***")
    print(traceback_lines)
    app = QApplication.instance()
    if app:
        stray_icon = app.property("stray_icon")
        if stray_icon:
            stray_icon.hide()
    if (not Globals.DEBUG) and (not Globals.RUN_ONCE):
        _restart_app(aftercrush=True)
    sys.exit()

def get_filepaths_dialog():
    file_name = QFileDialog()
    file_name.setFileMode(QFileDialog.ExistingFiles)
    title = ""
    path = ""
    filter_data = "All files (*.*)"
    data = file_name.getOpenFileNames(None, title, path, filter_data)
    return data[0]

def exit_threads():
    # ?????????????????????????? ???????????? ?????? ????????????, ?????? ?????? ????????????????
    for thread in Globals.background_threads:
        thread.terminate()
        # ?????????? ???????????????? terminate ???????????? exit

def _restart_app(aftercrush=False):
    # ???????????????????????? ???????????????????? ?????????? ???????????????????? ?????????????????? ?????? ????????????!
    if aftercrush:
        subprocess.Popen([sys.executable, sys.argv[0], "-aftercrush"])
    else:
        subprocess.Popen([sys.executable, sys.argv[0]])

def read_settings_file():
    SettingsJson().init(Globals)
    Globals.ENABLE_FLAT_EDITOR_UI = SettingsJson().get_data("ENABLE_FLAT_EDITOR_UI")
    Globals.USE_COLOR_PALETTE = SettingsJson().get_data("USE_COLOR_PALETTE")

def _main():

    os.chdir(os.path.dirname(__file__))
    sys.excepthook = excepthook

    if Globals.CRUSH_SIMULATOR:
        1 / 0

    RERUN_ARG = '-rerun'
    if (RERUN_ARG not in sys.argv) and ("-aftercrush" not in sys.argv):
        subprocess.Popen([sys.executable, *sys.argv, RERUN_ARG])
        sys.exit()

    # ???????????? ????????????????????
    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs='?', default=None)
    # ???????????????? ???????????????????? this_filepath ????????
    parser.add_argument('-user_mode', help="", action="store_true")
    parser.add_argument('-notification', help="", action="store_true")
    parser.add_argument('-aftercrush', help="", action="store_true")
    parser.add_argument('-rerun', help="", action="store_true")
    args = parser.parse_args(sys.argv[1:])
    if args.path:
        path = args.path
    if args.user_mode:
        Globals.DEBUG = False
    if args.aftercrush:
        Globals.AFTERCRUSH = True

    read_settings_file()

    app = QApplication(sys.argv)
    app.aboutToQuit.connect(exit_threads)
    app.setAttribute(Qt.AA_DontShowIconsInMenus, True)
    # ?????????????? ???????????? ?????? ????????????????
    if os.name == 'nt':
        appid = 'sergei_krumas.oxxxy_screenshoter.client.1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
    path_icon = os.path.abspath(os.path.join(os.path.dirname(__file__), "icon.png"))
    icon = QIcon(path_icon)
    app.setProperty("keep_ref_to_icon", icon)
    app.setWindowIcon(icon)
    # tooltip effects
    app.setEffectEnabled(Qt.UI_AnimateTooltip, False)
    app.setEffectEnabled(Qt.UI_FadeTooltip, False)

    if Globals.AFTERCRUSH:
        filepath = get_crushlog_filepath()
        msg0 = f"???????????????????? ?????????????????? ?? ????????\n\t{filepath}"
        msg = f"???????????????????? Oxxxy ????????.\n{msg0}\n\n?????????????????????????? Oxxxy?"
        ret = QMessageBox.question(None,'????????',
            msg,
            QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            _restart_app()
        sys.exit(0)

    thread_instance = None
    if args.notification:
        # notification mode
        notification = NotificationOrMenu(notification=True, filepath=args.path)
        notification.place_window()
    else:
        # editor mode
        if Globals.DEBUG or Globals.RUN_ONCE:
            invoke_screenshot_editor(request_type=RequestType.Fragment)
            # invoke_screenshot_editor(request_type=RequestType.Fullscreen)
            # NotificationOrMenu(menu=True).place_window()
        else:
            thread_instance = ListenHotkeyThread()
            thread_instance.start()
            stray_icon = show_system_tray(app, icon)
    # ???????? ?? ?????????? ??????????????????
    app.exec_()
    # ?????????? ???????????????? ????????????????
    stray_icon = app.property("stray_icon")
    if stray_icon:
        stray_icon.hide()
    if thread_instance:
        thread_instance.exit()
    if not Globals.FULL_STOP:
        if not args.notification and not Globals.DEBUG and not Globals.RUN_ONCE:
            _restart_app()
    sys.exit(0)

def main():
    # try ... except needed for crush reports into the file
    try:
        _main()
    except Exception as e:
        excepthook(type(e), e, traceback.format_exc())

if __name__ == '__main__':
    main()
