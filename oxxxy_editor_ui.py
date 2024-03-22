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
import random
import json
from functools import partial

from PyQt5.QtWidgets import (QSystemTrayIcon, QWidget, QMessageBox, QMenu, QFileDialog,
    QHBoxLayout, QCheckBox, QVBoxLayout, QTextEdit, QGridLayout, QWidgetAction,
    QPushButton, QLabel, QApplication, QScrollArea, QDesktopWidget, QActionGroup, QSpinBox)
from PyQt5.QtCore import (pyqtSignal, QPoint, QPointF, pyqtSlot, QRect, QEvent,
    QTimer, Qt, QSize, QSizeF, QRectF, QThread, QAbstractNativeEventFilter,
    QAbstractEventDispatcher, QFile, QDataStream, QIODevice)
from PyQt5.QtGui import (QPainterPath, QColor, QKeyEvent, QMouseEvent, QBrush, QPixmap,
    QPaintEvent, QPainter, QWindow, QPolygon, QImage, QTransform, QPen, QLinearGradient,
    QIcon, QFont, QCursor, QPolygonF, QVector2D, QFontDatabase)

from _utils import (convex_hull, check_scancode_for, SettingsJson,
     generate_metainfo, build_valid_rect, build_valid_rectF, dot,
     get_creation_date, copy_image_file_to_clipboard, get_nearest_point_on_rect,
     find_browser_exe_file, open_link_in_browser, open_in_google_chrome, save_meta_info,
     make_screenshot_pyqt, webRGBA, generate_gradient, draw_shadow, draw_cyberpunk,
     get_bounding_points, load_svg, is_webp_file_animated, apply_blur_effect,
     get_bounding_pointsF, generate_datetime_stamp, get_work_area_rect)


class CheckBoxCustom(QCheckBox):

    def __init__(self, *args):
        super().__init__(*args)

    def paintEvent(self, event):
        if self.isEnabled():
            super(type(self), self).paintEvent(event)

class CustomPushButton(QPushButton):
    right_clicked = pyqtSignal()
    def __init__(self, *args, tool_id=False, checkable=False, checked=True):
        super().__init__(*args)

        self.setCheckable(checkable)
        self.setChecked(checked)

        if tool_id == ToolID.DONE:
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

        if tool_id in [ToolID.FORWARDS, ToolID.BACKWARDS]:
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
        if self.underMouse() and tool_id not in [ToolID.FORWARDS, ToolID.BACKWARDS]:
            r = self.rect()
            if self.property("tool_id") == ToolID.DONE:
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

        if tool_id in [ToolID.oval, ToolID.rect, ToolID.line]:
            # эти кнопки рисуем наживую из-за того,
            # что нажатая клавиша Ctrl модифицирует их отрисовку
            self._draw_checked = self.isChecked()
            self.draw_button(painter)
        elif tool_id in [ToolID.DONE]:
            # это нужно здесь для поддержки измеенения цвета в режиме Globals.save_to_memory_mode
            self._draw_checked = self.underMouse()
            self.draw_button(painter)
        else:
            src_rect = QRect(0, 0, self.BUTTON_SIZE, self.BUTTON_SIZE)
            forwards_backwards_btns = tool_id in [ToolID.FORWARDS, ToolID.BACKWARDS]
            if forwards_backwards_btns:
                rect_w = int(self.BUTTON_SIZE/self.small_d)
                trgt_rect = QRect(0, 0, rect_w, rect_w)
                flag = self.isEnabled()
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
        bf_buttons = tool_id in [ToolID.FORWARDS, ToolID.BACKWARDS]

        # draw background
        gradient = QLinearGradient(self.rect().topLeft(), self.rect().bottomLeft())
        if tool_id == ToolID.DONE:
            y_base = QColor(253, 203, 54)
            y_secondary = QColor(220, 142, 3)
            if Globals.save_to_memory_mode:
                b_base = QColor(227, 72, 43)
                b_secondary = QColor(175, 48, 25)
            else:
                b_base = QColor(94, 203, 247)
                b_secondary = QColor(25, 133, 175)
            if self._draw_checked:
                gradient.setColorAt(1, y_secondary)
                gradient.setColorAt(0, y_base)
            else:
                gradient.setColorAt(1, b_secondary)
                gradient.setColorAt(0, b_base)

            painter.setPen(Qt.NoPen)
            if Globals.ENABLE_FLAT_EDITOR_UI:
                if self._draw_checked:
                    brush = QBrush(y_base)
                else:
                    brush = QBrush(b_base)
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

        if tool_id == ToolID.DONE or (self._draw_checked and not bf_buttons):
            r = self.rect()
            if self.property("tool_id") == ToolID.DONE:
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
        elif tool_id == ToolID.DONE:
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

        # draw face
        if tool_id == ToolID.DRAG:

            transform = QTransform()
            transform.translate(w2, w2)
            transform.rotate(45)
            painter.setTransform(transform)
            painter.drawLine(-w2, -w2, w, w)

        elif tool_id == ToolID.DONE:

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

        elif tool_id == ToolID.BACKWARDS:

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

        elif tool_id == ToolID.FORWARDS:

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

        elif tool_id == ToolID.transform:

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

        elif tool_id == ToolID.pen:

            offset = self.BUTTON_SIZE/2
            painter.setPen(Qt.NoPen)
            _offset = 45
            pos1y = 6 - _offset
            pos2y = 15 - _offset
            pos3y = 40 - _offset
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

        elif tool_id == ToolID.marker:

            offset = self.BUTTON_SIZE/2
            painter.setPen(Qt.NoPen)
            _offset = 45
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

        elif tool_id == ToolID.line:

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

        elif tool_id == ToolID.arrow:

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

        elif tool_id == ToolID.text:

            set_font(painter, 1900, pixel_size=30)
            painter.setPen(QPen(main_color))
            painter.drawText(self.rect().adjusted(5, 5, -5, -5), Qt.AlignCenter, "A")

        elif tool_id == ToolID.oval:

            if not modifiers & Qt.ControlModifier:
                painter.setBrush(Qt.NoBrush)

            painter.setPen(QPen(QColor(main_color), 3))
            painter.drawEllipse(self.rect().adjusted(10,10,-10,-10))

        elif tool_id == ToolID.rect:

            if not modifiers & Qt.ControlModifier:
                painter.setBrush(Qt.NoBrush)

            pen = QPen(QColor(main_color), 3)
            pen.setJoinStyle(Qt.MiterJoin)
            painter.setPen(pen)
            painter.drawRect(self.rect().adjusted(10, 10, -10, -10))

        elif tool_id == ToolID.numbering:

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

        elif tool_id == ToolID.blurring:

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
            pix = apply_blur_effect(not_blurred_pix, new_pixmap)

            painter.drawPixmap(r, pix, r)

            painter.setBrush(Qt.NoBrush)
            pen = QPen(main_color)
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(r)

        elif tool_id == ToolID.darkening:

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

        elif tool_id == ToolID.picture:

            pen = QPen(QColor(main_color), 3)
            pen.setJoinStyle(Qt.MiterJoin)
            painter.setPen(pen)
            adj = self.rect().adjusted(7, 7, -7, -7)
            painter.drawRect(adj)
            adj2 = adj.adjusted(1, 1, -0, -0)
            points = [
                adj2.topLeft(),
                adj2.topRight(),
                adj2.bottomRight() + QPoint(0, -7),

                adj2.bottomRight() + QPoint(-8, -25), #fisrt top
                adj2.bottomRight() + QPoint(-15, -10),
                adj2.bottomRight() + QPoint(-21, -18), #second top
                adj2.bottomLeft() + QPoint(5, -7),

                adj2.bottomLeft() + QPoint(0, -7),
            ]
            poly = QPolygon(points)
            painter.setBrush(second_color3)
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(poly)
            painter.setBrush(brush)
            adj3 = adj2.adjusted(3, 3, 0, 0)
            r = QRect(adj3.topLeft(), adj3.topLeft()+QPoint(9, 9))
            painter.drawEllipse(r)

        elif tool_id == "TOOLID.UNUSED":

            # aim icon
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

        elif tool_id == ToolID.zoom_in_region:

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

        elif tool_id == ToolID.copypaste:

            pen = QPen(main_color, 1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            set_font(painter, 1900, pixel_size=12)
            painter.drawText(QPoint(2, 25), "COPY")
            painter.drawText(QPoint(5, 36), "PASTE")

        elif tool_id == ToolID.arrowstree:

            painter.setPen(Qt.NoPen)
            painter.setBrush(main_color)

            path = QPainterPath()

            path.moveTo(QPointF(5, 5))
            path.lineTo(QPointF(30, 12))
            path.lineTo(QPointF(19, 15))

            ep = QPointF(25, 45)
            c1 = QPointF(22, 20)
            c2 = QPointF(32, 25)
            path.cubicTo(c1, c2, ep)
            path.lineTo(10, 45)

            ep = QPointF(15, 19)
            c1 = QPointF(25, 35)
            c2 = QPointF(20, 25)
            path.cubicTo(c1, c2, ep)

            path.lineTo(QPointF(12, 30))
            path.lineTo(QPointF(5, 5))

            painter.drawPath(path)

            # при редактировании координат
            # pen = QPen(main_color, 1)
            # painter.setPen(pen)
            # painter.setBrush(Qt.NoBrush)

            path = QPainterPath()

            path.moveTo(QPointF(45, 20))
            path.lineTo(QPointF(40, 35))
            path.lineTo(QPointF(37, 30))

            c1 = QPointF(29, 38)
            c2 = QPointF(29, 38)

            ep = QPointF(25, 45)
            path.cubicTo(c1, c2, ep)
            path.lineTo(10, 45)

            c1 = QPointF(20, 35)
            c2 = QPointF(20, 35)

            ep = QPointF(34, 27)
            path.cubicTo(c1, c2, ep)

            path.lineTo(QPointF(29, 24))
            path.lineTo(QPointF(45, 20))

            painter.drawPath(path)

class PictureSelectButton(QPushButton):
    def __init__(self, picture_data, button_size, main_window, *args):
        super().__init__(*args)
        self.picture_data = picture_data
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
        pixmap = self.picture_data.display_pixmap
        w = self.rect().width()
        h = self.rect().height()
        x = (w - pixmap.width())/2
        y = (h - pixmap.height())/2
        painter.drawPixmap(QPoint(int(x), int(y)), pixmap)
        painter.end()

    def mouseReleaseEvent(self, event):
        if self.picture_data.pixmap:
            main_window = self.main_window
            tools_window = main_window.tools_window
            if self.picture_data.id == PictureInfo.TYPE_FROM_FILE:
                path = QFileDialog.getOpenFileName(None, "Выберите файл", "")
                path = str(path[0])
                if path and os.path.exists(path):
                    main_window.current_picture_pixmap = QPixmap(path)
                else:
                    main_window.current_picture_pixmap = PictureInfo.PIXMAP_BROKEN
            else:
                main_window.current_picture_pixmap = self.picture_data.pixmap
            main_window.current_picture_id = self.picture_data.id
            main_window.current_picture_angle = 0
            tools_window.on_parameters_changed()
            tools_window.select_window.hide()
            main_window.activateWindow()

class PictureInfo():
    TYPE_STAMP = "stamp"
    TYPE_DYN = "dyn"
    TYPE_STICKER = "sticker"
    TYPE_FROM_FILE = "from_file"
    TYPE_FROM_MAGAZIN = "from_magazin"
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
    PICTURE_TOOL_FOLDERNAME = "picture_tool"
    PIC_FOLDER = os.path.join(APP_FOLDER, PICTURE_TOOL_FOLDERNAME, "pictures")
    SCRIPTS_FOLDERPATH = os.path.join(APP_FOLDER, PICTURE_TOOL_FOLDERNAME, "python")
    STICKERS_FOLDER = os.path.join(APP_FOLDER, PICTURE_TOOL_FOLDERNAME, "stickers")

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
                    print(f_path, "created (picture info)")
        for folder in [cls.PIC_FOLDER, cls.SCRIPTS_FOLDERPATH, cls.STICKERS_FOLDER]:
            create_if_not_exists(folder)

    def remove_prefix(self, path):
        prefix = os.path.dirname(__file__)
        return path[len(prefix):]

    def __init__(self, picture_type, data):
        super().__init__()
        self.picture_type = picture_type
        self.id = None
        self.pixmap = None
        self.display_pixmap = self.PIXMAP_LOADING
        if self.picture_type in [self.TYPE_STAMP, self.TYPE_STICKER]:
            self.filepath = data
            self.id = self.remove_prefix(self.filepath)
        elif self.picture_type == self.TYPE_DYN:
            script_path, arg, draw_func = data
            self.arg = arg
            self.filepath = script_path
            self.draw_func = draw_func
            _filepath = self.remove_prefix(self.filepath)
            self.id = f"{_filepath},{self.arg}"
        elif self.picture_type == self.TYPE_FROM_FILE:
            self.id = "from_file"
            self.filepath = ""
        else:
            print(self.picture_type)
            raise Exception("Unknown picture type")
        if self.id is None:
            raise Exception("id is None")

    def get_tooltip_text(self):
        if self.picture_type == self.TYPE_DYN:
            return self.arg
        else:
            return self.id

    @classmethod
    def load_from_id(cls, picture_id):
        cls.create_default_pixmaps()
        if picture_id is None:
            return None
        elif "," in picture_id:
            # dynamic
            rel_script_path, func_arg = picture_id.split(",", 1)
            script_path = os.path.join(cls.APP_FOLDER, rel_script_path.strip("/").strip("\\"))
            if os.path.exists(script_path):
                script_filename = os.path.basename(script_path)
                m_func, d_func = cls.get_module_functions(script_filename, script_path)
                if m_func and d_func:
                    return PictureInfo(cls.TYPE_DYN, (script_path, func_arg, d_func))
        else:
            # imagefile
            picture_filepath = os.path.join(cls.APP_FOLDER, picture_id.strip("/").strip("\\"))
            if os.path.exists(picture_filepath):
                return PictureInfo(cls.TYPE_STAMP, picture_filepath)
        return None

    def load_from_file(self):
        if self.picture_type in [self.TYPE_STAMP, self.TYPE_STICKER]:
            self.pixmap = QPixmap(self.filepath)
        elif self.picture_type == self.TYPE_DYN:
            dyn_pixmap = QPixmap(240, 240)
            dyn_pixmap.fill(Qt.transparent)
            painter = QPainter()
            painter.begin(dyn_pixmap)
            self.draw_func(dyn_pixmap, painter, self.arg)
            painter.end()
            del painter
            self.pixmap = dyn_pixmap
        elif self.picture_type == self.TYPE_FROM_FILE:
            dyn_pixmap = QPixmap(80, 80)
            dyn_pixmap.fill(Qt.black)
            p = QPainter()
            p.begin(dyn_pixmap)
            r = dyn_pixmap.rect()
            p.setPen(QPen(Qt.white))
            p.drawText(r, Qt.AlignCenter, "ИЗ\nФАЙЛА")
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
        pictures = []
        ############################################################
        # FROM FILE dialog
        ############################################################
        picture_info = PictureInfo(cls.TYPE_FROM_FILE, None)
        pictures.append(picture_info)
        ############################################################
        # scan pictures
        ############################################################
        for cur_folder, folders, files in os.walk(cls.PIC_FOLDER):
            for filename in files:
                filepath = os.path.join(cur_folder, filename)
                if filepath.lower().endswith((".jpg", ".png", ".jpeg", ".webp")):
                    picture_info = PictureInfo(cls.TYPE_STAMP, filepath)
                    pictures.append(picture_info)
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
                        picture_info = PictureInfo(cls.TYPE_DYN, (script_path, func_arg, d_func))
                        pictures.append(picture_info)
        if cls.SCRIPTS_FOLDERPATH in sys.path:
            sys.path.remove(cls.SCRIPTS_FOLDERPATH)
        ############################################################
        # scan stickers
        ############################################################
        for cur_folder, folders, files in os.walk(cls.STICKERS_FOLDER):
            for filename in files:
                filepath = os.path.join(cur_folder, filename)
                if filepath.lower().endswith((".jpg", ".png", ".jpeg", ".webp")):
                    picture_info = PictureInfo(cls.TYPE_STICKER, filepath)
                    pictures.append(picture_info)
        ############################################################
        # end of scan
        ############################################################
        return pictures

class PreviewsThread(QThread):
    update_signal = pyqtSignal(object)
    def __init__(self, pictures, select_window):
        QThread.__init__(self)
        Globals.background_threads.append(self)
        self.pictures = pictures
        self.update_signal.connect(lambda data: select_window.content.update())

    def start(self):
        super().start(QThread.IdlePriority)

    def run(self):
        for picture_info in self.pictures:
            picture_info.load_from_file()
            self.msleep(1)
            self.update_signal.emit(None)

class PictureSelectWindow(QWidget):

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
        # это делается для того, чтобы после использования окна редактора
        # программа нужным образом реагировала на нажатие Esc и Enter
        app = QApplication.instance()
        app.sendEvent(self.main_window, event)

    def __init__(self, *args, pictures=None):
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

        scroll_area = QScrollArea(self)
        main_layout.addSpacing(20)
        main_layout.addWidget(scroll_area)
        scroll_area.setWidgetResizable(True)
        scroll_area.verticalScrollBar().setStyleSheet("""
            QScrollBar {
                border-radius: 5px;
                background: rgb(40, 40, 40);
            }

            QScrollBar:vertical {
                width: 10px;
                border-radius: 5px;
            }

            QScrollBar::handle {
                background: rgb(210, 210, 210);
                border-radius: 5px;
            }

            QScrollBar::handle:vertical {
                width: 10px;
                min-height: 10px;
                border-radius: 5px;
            }

             QScrollBar::add-line:vertical {
                 background: transparent;
             }

             QScrollBar::sub-line:vertical {
                 background: transparent;
             }
             QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                 background: transparent;
             }

             QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                 background: transparent;
             }

            """)

        scroll_area.setStyleSheet("""
            QScrollArea:vertical {
                height: 15px;
                background-color: transparent;
                border: none;
            }
            """)

        scrollContent = QWidget(scroll_area)
        scrollContent.setStyleSheet("background: black; border: none;")
        self.content = scrollContent

        BUTTON_SIZE = 100
        len_pictures = len(pictures)
        COL_COUNT = min(15, len_pictures)
        SPACING = 5
        CONTENT_MARGIN = 5
        rows_count = math.ceil(len_pictures / COL_COUNT)

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
        scroll_area.setWidget(scrollContent)
        self.buttons = []
        for n, picture_data in enumerate(pictures):
            button = PictureSelectButton(picture_data, BUTTON_SIZE, self.main_window)
            button.setParent(self)
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip(picture_data.get_tooltip_text())
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
            if but.property("tool_id") == ToolID.picture:
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