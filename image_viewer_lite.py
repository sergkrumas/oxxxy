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

import os
import sys
import time
import math
from collections import namedtuple
import time

from PyQt5.QtWidgets import (QApplication, QMenu, QFileDialog, QWidget, QDesktopWidget)
from PyQt5.QtCore import (QTimer, Qt, QRect, QRectF, QPoint, QPointF)
from PyQt5.QtGui import (QPixmap, QPainterPath, QPainter, QCursor, QBrush, QPicture,
                                                                QPen, QColor, QTransform)

from _utils import *

__all__ = (
    'ViewerWindow',
)

class Globals:
    DEBUG_VIZ = False


RegionInfo = namedtuple('RegionInfo', 'setter coords getter')



class ViewerWindow(QWidget):

    UPPER_SCALE_LIMIT = 100.0
    LOWER_SCALE_LIMIT = 0.01

    def set_window_style(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowModality(Qt.WindowModal)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def mapped_cursor_pos(self):
        # этот маппинг нужен для того, чтобы всё работало
        # правильно и на втором экране тоже
        return self.mapFromGlobal(QCursor().pos())

    def cursor_in_rect(self, r):
        return r.contains(self.mapped_cursor_pos())

    def __init__(self, *args, main_window=None, _type="", data=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.main_window = main_window

        self.frameless_mode = True
        self.set_window_style()
        self.tranformations_allowed = True
        self.image_translating = False
        self.image_center_position = QPoint(0, 0)
        self.image_rotation = 0
        self.image_scale = 1.0
        self.pixmap = None

        self.CENTER_LABEL_TIME_LIMIT = 2
        self.center_label_time = time.time() - self.CENTER_LABEL_TIME_LIMIT - 1
        self.center_label_info_type = "scale" #["scale", "playspeed", "framenumber"]

        self.timer = QTimer()
        self.timer.timeout.connect(self.on_timer)
        self.timer.start(10)

        self.show_center_point = False
        self.invert_image = False
        self.show_thirds = False

        self.contextMenuActivated = False

        self.INPUT_POINT1 = self.INPUT_POINT2 = None
        self.input_rect = None
        self.type = _type

        self.frame_data = data
        self.frame_data_backup = data

        self.user_input_started = False
        self.is_rect_defined = False

        self.capture_region_rect = None

        self._custom_cursor_data = None

        self.undermouse_region_info = None

        self.drag_inside_capture_zone = False

        self._custom_cursor_cycle = 0

        self.is_rect_being_redefined = False

        self.undermouse_region_rect = None
        self.undermouse_region_info = None
        self.region_num = 0

        self.set_size_and_position()

        self.setMouseTracking(True)

    def no_frame_data(self):
        self.INPUT_POINT1 = self.INPUT_POINT2 = None
        self.input_rect = None

        self.frame_data = self.frame_data_backup

        self.user_input_started = False
        self.is_rect_defined = False

        self.capture_region_rect = None

        self._custom_cursor_data = None

        self.undermouse_region_info = None

        self.drag_inside_capture_zone = False

        self._custom_cursor_cycle = 0

        self.is_rect_being_redefined = False

        self.undermouse_region_rect = None
        self.undermouse_region_info = None
        self.region_num = 0


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

    def equilateral_delta(self, delta):
        sign = math.copysign(1.0, delta.x())
        if delta.y() < 0:
            if delta.x() < 0:
                sign = 1.0
            else:
                sign = -1.0
        delta.setX(int(delta.y()*sign))
        return delta

    def _build_valid_rect(self, p1, p2):
        return build_valid_rect(p1, p2)

    def is_point_set(self, p):
        return p is not None

    def get_first_set_point(self, points, default):
        for point in points:
            if self.is_point_set(point):
                return point
        return default

    def is_input_points_set(self):
        return self.is_point_set(self.INPUT_POINT1) and self.is_point_set(self.INPUT_POINT2)

    def build_input_rect2(self, cursor_pos):
        ip1 = self.get_first_set_point([self.INPUT_POINT1], cursor_pos)
        ip2 = self.get_first_set_point([self.INPUT_POINT2, self.INPUT_POINT1], cursor_pos)
        return self._build_valid_rect(ip1, ip2)

    def get_region_info(self):
        self.define_regions_rects_and_set_cursor()
        self.update()

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

    def elementsDefineCursorShape(self):
        return self.get_custom_cross_cursor()


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
                # чтобы не глитчили курсоры
                # на пограничных зонах прекращаем цикл
                break
        if write_data:
            if self.region_num == 5:
                self.undermouse_region_info = None
            else:
                data = touching_move_data[self.region_num]
                self.undermouse_region_info = RegionInfo(*data)


    def draw_vertical_horizontal_lines(self, painter, cursor_pos):
        if True:
            line_pen = QPen(QColor(127, 127, 127, 172), 2, Qt.DashLine)
            old_comp_mode = painter.compositionMode()
            painter.setCompositionMode(QPainter.RasterOp_SourceXorDestination)

        if self.is_input_points_set():
            painter.setPen(line_pen)
            left = self.INPUT_POINT1.x()
            top = self.INPUT_POINT1.y()
            right = self.INPUT_POINT2.x()
            bottom = self.INPUT_POINT2.y()
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
        # else:
        #     painter.setPen(line_pen)
        #     curpos = self.mapFromGlobal(cursor_pos)
        #     pos_x = curpos.x()
        #     pos_y = curpos.y()
        #     painter.drawLine(pos_x, 0, pos_x, self.height())
        #     painter.drawLine(0, pos_y, self.width(), pos_y)

        if True:
            painter.setCompositionMode(old_comp_mode)


    def close(self):
        if self.main_window:
            self.main_window.view_window = None
        else:
            app = QApplication.instance()
            app.exit()
        super().close()

    def update_for_center_label_fade_effect(self):
        delta = time.time() - self.center_label_time
        if delta < self.CENTER_LABEL_TIME_LIMIT:
            self.update()

    def restore_image_transformations(self, correct=True):
        self.image_rotation = 0
        self.image_scale = 1.0
        self.image_center_position = self.get_center_position()
        if correct:
            self.correct_scale()

    def viewer_reset(self, simple=False):
        self.pixmap = None
        self.tranformations_allowed = False
        self.rotated_pixmap = None

    def show_image(self, pixmap):
        self.viewer_reset(simple=True)
        self.pixmap = pixmap
        self.tranformations_allowed = True
        self.get_rotated_pixmap()
        self.restore_image_transformations()
        self.update()

    def get_rotated_pixmap(self, force_update=True):
        if self.rotated_pixmap is None or force_update:
            rm = QTransform()
            rm.rotate(self.image_rotation)
            self.rotated_pixmap = self.pixmap.transformed(rm)
        return self.rotated_pixmap

    def get_image_viewport_rect(self, debug=False):
        image_rect = QRect()
        if self.pixmap:
            pixmap = self.get_rotated_pixmap()
            orig_width = pixmap.rect().width()
            orig_height = pixmap.rect().height()
        else:
            orig_width = orig_height = 1000
        image_rect.setLeft(0)
        image_rect.setTop(0)
        image_scale = self.image_scale
        new_width = orig_width*image_scale
        new_height = orig_height*image_scale
        icp = self.image_center_position
        pos = QPointF(icp).toPoint() - QPointF(new_width/2, new_height/2).toPoint()
        if debug:
            print(pos, new_width, new_height)
        image_rect.moveTo(pos)
        image_rect.setWidth(int(new_width))
        image_rect.setHeight(int(new_height))
        return image_rect

    def on_timer(self):
        self.update_for_center_label_fade_effect()

    def is_cursor_over_image(self):
        return self.cursor_in_rect(self.get_image_viewport_rect())

    def get_image_frame_info(self):
        rect = self.input_rect
        image_rect = self.get_image_viewport_rect()

        assert rect is not None
        assert image_rect is not None

        screen_delta1 = rect.topLeft() - image_rect.topLeft()
        screen_delta2 = rect.bottomRight() - image_rect.topLeft()

        left = screen_delta1.x()/image_rect.width()
        top = screen_delta1.y()/image_rect.height()

        right = screen_delta2.x()/image_rect.width()
        bottom = screen_delta2.y()/image_rect.height()

        return left, top, right, bottom

    def build_input_rect(self):
        if self.is_point_set(self.INPUT_POINT1) and self.is_point_set(self.INPUT_POINT2):
            self.input_rect = build_valid_rect(self.INPUT_POINT1, self.INPUT_POINT2)



    def get_frame_rect_to_draw(self):

        image_rect = self.get_image_viewport_rect()

        base_point = image_rect.topLeft()
        left, top, right, bottom = self.frame_data

        screen_left = base_point.x() + image_rect.width()*left
        screen_top = base_point.y() + image_rect.height()*top

        screen_right = base_point.x() + image_rect.width()*right
        screen_bottom = base_point.y() + image_rect.height()*bottom

        frame_rect = QRectF(
            QPointF(screen_left, screen_top), QPointF(screen_right, screen_bottom)).toRect()

        return frame_rect

    def draw_image_frame(self, painter):
        if self.frame_data:

            image_rect = self.get_image_viewport_rect()

            frame_rect = self.get_frame_rect_to_draw()

            old_pen = painter.pen()
            old_brush = painter.brush()

            painter.setPen(QPen(Qt.white, 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(frame_rect)

            painter.setPen(QPen(Qt.red, 1))
            painter.setBrush(QBrush(Qt.red, Qt.DiagCrossPattern))

            darkening_zone = QPainterPath()
            darkening_zone.addRect(QRectF(image_rect))
            framed_piece = QPainterPath()
            framed_piece.addRect(QRectF(frame_rect))
            darkening_zone = darkening_zone.subtracted(framed_piece)
            painter.setOpacity(0.4)
            old_comp_mode = painter.compositionMode()
            painter.setCompositionMode(QPainter.RasterOp_SourceXorDestination)
            painter.drawPath(darkening_zone)
            painter.setCompositionMode(old_comp_mode)
            painter.setOpacity(1.0)

            painter.setPen(old_pen)
            painter.setBrush(old_brush)

    def get_frame_rect(self):
        image_rect = self.pixmap.rect()
        base_point = image_rect.topLeft()
        left, top, right, bottom = self.get_image_frame_info()

        screen_left = base_point.x() + image_rect.width()*left
        screen_top = base_point.y() + image_rect.height()*top

        screen_right = base_point.x() + image_rect.width()*right
        screen_bottom = base_point.y() + image_rect.height()*bottom

        frame_rect = QRectF(
            QPointF(screen_left, screen_top), QPointF(screen_right, screen_bottom)).toRect()
        return frame_rect

    def frame_image(self):
        if self.frame_data:
            self.main_window.elementsFramePicture(frame_rect=self.get_frame_rect(),
                                                        frame_data=self.get_image_frame_info())

    def framedfinal_to_imagetool(self):
        if self.frame_data:
            self.main_window.elementsFramedFinalToImageTool(self.get_frame_rect())









    def mousePressEvent(self, event):

        if event.button() == Qt.LeftButton:
            if event.modifiers() & Qt.ControlModifier:
                if self.isInEditorMode() or True:
                    self.mousePressEventCaptureRect(event)

                    self.calculate_image_frame_info()
            elif self.tranformations_allowed:
                if self.is_cursor_over_image():
                    self.image_translating = True
                    self.oldCursorPos = self.mapped_cursor_pos()
                    self.oldElementPos = self.image_center_position
                    self.update()

        self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):

        if event.buttons() == Qt.NoButton:
            # определяем только тут, иначе при быстрых перемещениях мышки при зажатой кнопке мыши
            # возможна потеря удержания - как будто бы если кнопка мыши была отпущена
            self.get_region_info()

        if event.buttons() == Qt.LeftButton:
            if event.modifiers() & Qt.ControlModifier:
                if self.isInEditorMode() or True:

                    self.mouseMoveEventCaptureRect(event)
                    self.calculate_image_frame_info()
            elif self.tranformations_allowed and self.image_translating:
                new = self.oldElementPos - (self.oldCursorPos - self.mapped_cursor_pos())
                old = QPoint(self.image_center_position)
                self.image_center_position = new

                delta =  new - old
                if self.is_point_set(self.INPUT_POINT1) and self.is_point_set(self.INPUT_POINT2):
                    self.INPUT_POINT1 += delta
                    self.INPUT_POINT2 += delta
                    self.capture_region_rect = build_valid_rect(self.INPUT_POINT1, self.INPUT_POINT2)

        self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.mouseReleaseEventCaptureRect(event)

        if event.button() == Qt.LeftButton:
            if event.modifiers() & Qt.ControlModifier:
                if self.isInEditorMode() or True:
                    self.calculate_image_frame_info()
            elif self.tranformations_allowed:
                self.image_translating = False
                self.update()

        self.update()
        super().mouseReleaseEvent(event)


    def calculate_image_frame_info(self):
        self.build_input_rect()
        if self.input_rect and self.input_rect.width() > 50 and self.input_rect.height() > 50:
            self.input_rect = self.input_rect.intersected(self.get_image_viewport_rect())
            self.frame_data = self.get_image_frame_info()
            self.hide_center_label()
        else:
            self.input_rect = None
            self.frame_data = None
            self.show_center_label("Задаваемая область слишком мала")




    def mouseMoveEventCaptureRect(self, event):

        if event.buttons() == Qt.LeftButton:
            if not self.is_rect_defined:
                # для первичного задания области захвата
                self.user_input_started = True
                if not self.is_point_set(self.INPUT_POINT1):
                    self.INPUT_POINT1 = event.pos()
                else:
                    self.INPUT_POINT2 = event.pos()


                    # modifiers = event.modifiers()
                    # if modifiers == Qt.NoModifier:
                    #     self.INPUT_POINT2 = event.pos()
                    # else:
                    #     delta = self.INPUT_POINT1 - event.pos()
                    #     if modifiers & Qt.ControlModifier:
                    #         delta.setX(delta.x() // 10 * 10 + 1)
                    #         delta.setY(delta.y() // 10 * 10 + 1)
                    #     if modifiers & Qt.ShiftModifier:
                    #         delta = self.equilateral_delta(delta)
                    #     self.INPUT_POINT2 = self.INPUT_POINT1 - delta

            elif self.undermouse_region_info and not self.drag_inside_capture_zone:
                # для изменения области захвата после первичного задания
                self.is_rect_being_redefined = True
                cursor_pos = event.pos()
                delta = QPoint(cursor_pos - self.old_cursor_position)
                uri = self.undermouse_region_info
                set_func_attr = uri.setter
                data_id = uri.coords
                get_func_attr = uri.getter
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

                self.INPUT_POINT1 = self.capture_region_rect.topLeft()
                self.INPUT_POINT2 = self.capture_region_rect.bottomRight()

            elif self.drag_inside_capture_zone and self.capture_region_rect:
                pass

        elif event.buttons() == Qt.RightButton:
            pass

        if event.buttons() == Qt.LeftButton and not self.is_rect_being_redefined:
            self.setCursor(self.get_custom_cross_cursor())

        self.update()

        # super().mouseMoveEvent(event)

    def mousePressEventCaptureRect(self, event):
        isLeftButton = event.button() == Qt.LeftButton
        if not self.capture_region_rect:
            self.INPUT_POINT1 = event.pos()
        if isLeftButton:
            self.old_cursor_position = event.pos()
            self.get_region_info()
            if self.undermouse_region_info is None:
                self.drag_inside_capture_zone = True
            else:
                self.drag_inside_capture_zone = False

        # super().mousePressEvent(event)
        self.update()

    def mouseReleaseEventCaptureRect(self, event):
        if event.button() == Qt.LeftButton:
            if self.drag_inside_capture_zone:
                self.drag_inside_capture_zone = False
            if self.user_input_started:
                if not self.is_input_points_set():
                    # это должно помочь от крашей
                    self.INPUT_POINT1 = None
                    self.INPUT_POINT2 = None
                    return
                self.is_rect_defined = True
                self.capture_region_rect = \
                                    self._build_valid_rect(self.INPUT_POINT1, self.INPUT_POINT2)
            self.get_region_info() # здесь только для установки курсора
        self.is_rect_being_redefined = False
        self.user_input_started = False

        # super().mouseReleaseEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        painter.setOpacity(0.8)
        painter.setBrush(QBrush(Qt.black, Qt.SolidPattern))
        painter.drawRect(self.rect())
        painter.setOpacity(1.0)
        self.draw_content(painter)


        cursor_pos = self.mapFromGlobal(QCursor().pos())
        input_rect = self.build_input_rect2(cursor_pos)

        self.draw_vertical_horizontal_lines(painter, cursor_pos)

        painter.end()





    def get_center_position(self):
        return QPoint(
            int(self.frameGeometry().width()/2),
            int(self.frameGeometry().height()/2)
        )

    def is_wheel_allowed(self):
        return not (self.user_input_started or self.is_rect_being_redefined)

    def wheelEvent(self, event):
        scroll_value = event.angleDelta().y()/240
        ctrl = event.modifiers() & Qt.ControlModifier
        shift = event.modifiers() & Qt.ShiftModifier
        no_mod = event.modifiers() == Qt.NoModifier
        if no_mod and self.is_wheel_allowed():
            self.do_scale_image(scroll_value)
            self.show_center_label("scale")

    def set_original_scale(self):
        self.image_scale = 1.0
        self.update()

    def do_scale_image(self, scroll_value, cursor_pivot=True, override_factor=None):

        if not self.tranformations_allowed:
            return

        if self.image_scale >= self.UPPER_SCALE_LIMIT-0.001:
            if scroll_value > 0.0:
                return

        if self.image_scale <= self.LOWER_SCALE_LIMIT:
            if scroll_value < 0.0:
                return

        before_scale = self.image_scale

        # эти значения должны быть вычислены до изменения self.image_scale
        r = self.get_image_viewport_rect()
        p1 = r.topLeft()
        p2 = r.bottomRight()

        if not override_factor:
            if self.image_scale > 1.0: # если масштаб больше нормального
                factor = self.image_scale/self.UPPER_SCALE_LIMIT
                if scroll_value < 0.0:
                    self.image_scale -= 0.1 + 8.5*factor #0.2
                else:
                    self.image_scale += 0.1 + 8.5*factor #0.2

            else: # если масштаб меньше нормального
                if scroll_value < 0.0:
                    self.image_scale -= 0.05 #0.1
                else:
                    self.image_scale += 0.05 #0.1

        delta = before_scale - self.image_scale
        self.image_scale = min(max(self.LOWER_SCALE_LIMIT, self.image_scale),
                                                                    self.UPPER_SCALE_LIMIT)
        pixmap = self.get_rotated_pixmap()
        width = pixmap.rect().width()
        height = pixmap.rect().height()

        if override_factor:
            pivot = QPointF(self.rect().center())
        else:
            if cursor_pivot:
                if r.contains(self.mapped_cursor_pos()):
                    pivot = QPointF(self.mapped_cursor_pos())
                else:
                    pivot = QPointF(self.rect().center())
            else:
                pivot = QPointF(self.image_center_position)

        p1 = p1 - pivot
        p2 = p2 - pivot

        if False:
            factor = (1.0 - delta)
            # delta  -->  factor
            #  -0.1  -->  1.1: больше 1.0
            #  -0.2  -->  1.2: больше 1.0
            #   0.2  -->  0.8: меньше 1.0
            #   0.1  -->  0.9: меньше 1.0
            # Единственный недостаток factor = (1.0 - delta) в том,
            # что он увеличивает намного больше, чем должен:
            # из-за этого постоянно по факту превышается UPPER_SCALE_LIMIT.
            # Вариант ниже как раз призван устранить этот недостаток.
            # Хотя прелесть factor = (1.0 - delta) в том,
            # что не нужно создавать хитровыебанные дельты с множителями,
            # как это сделано чуть выше.
        else:
            w = p2.x() - p1.x()
            factor = 1.0 - (before_scale - self.image_scale)*width/w

        if override_factor:
            factor = override_factor

        p1 = QPointF(p1.x()*factor, p1.y()*factor)
        p2 = QPointF(p2.x()*factor, p2.y()*factor)

        p1 = p1 + pivot
        p2 = p2 + pivot

        # здесь задаём размер и положение
        new_width = abs(p2.x() - p1.x())
        new_height = abs(p2.y() - p1.y())

        image_scale = new_width / width
        image_center_position = (p1 + p2)/2

        if override_factor:
            return image_scale, image_center_position.toPoint()
        else:
            if self.image_scale == 100.0 and image_scale < 100.0 and scroll_value > 0.0:
                # Предохранитель от постепенного заплыва картинки в сторону верхнего левого угла
                # из-за кручения колеса мыши в область ещё большего увеличения
                # Так происходит, потому что переменная image_scale при этом чуть меньше 100.0
                pass
            else:
                self.image_scale = image_scale
            self.image_center_position = image_center_position.toPoint()


        if self.capture_region_rect:
            rect = self.get_frame_rect_to_draw()
            self.INPUT_POINT1 = rect.topLeft()
            self.INPUT_POINT2 = rect.bottomRight()
            self.capture_region_rect = rect
        self.update()

    def scale_label_opacity(self):
        delta = time.time() - self.center_label_time
        if delta < self.CENTER_LABEL_TIME_LIMIT:
            d = 6 # remap 1.0 to 0.0 in time, make it faster
            d1 = 1.0/d
            d2 = 1.0*d
            value = min(max(0.0, self.CENTER_LABEL_TIME_LIMIT-delta), d1) * d2
            return value
        else:
            return 0.0

    def scale_label_color(self):
        delta = time.time() - self.center_label_time
        if delta < 0.5:
            return fit(delta, 0.0, 0.5, 0.0, 1.0)
        else:
            return 1.0

    def draw_center_label(self, painter, text, large=False):
        painter.resetTransform()
        def set_font(pr):
            font = pr.font()
            old_font = pr.font() #copy
            if large:
                font.setPixelSize(self.rect().height()//8)
            else:
                font.setPixelSize(17)
            font.setWeight(1900)
            pr.setFont(font)
            return old_font

        pic = QPicture()
        p = QPainter(pic)
        set_font(p)
        r = self.rect()
        brect = p.drawText(r.x(), r.y(), r.width(), r.height(), Qt.AlignCenter, text)
        p.end()
        del p
        del pic

        opacity = self.scale_label_opacity()
        if not large:
            painter.setOpacity(0.6*opacity)
            # calculate rect of the backplate
            RADIUS = 5
            path = QPainterPath()
            offset = 5
            r = brect.adjusted(-offset, -offset+2, offset, offset-2)
            r = QRectF(r)
            path.addRoundedRect(r, RADIUS, RADIUS)
            # draw rounded backplate
            c = QColor(80, 80, 80)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(c))
            painter.drawPath(path)
            # back to normal
            painter.setOpacity(1.0*opacity)

        old_font = set_font(painter)

        if large:
            # c = QColor("#e1db74")
            # c.setAlphaF(0.4)
            c = QColor(Qt.white)
            c.setAlphaF(0.9)
            painter.setPen(QPen(c))
            painter.setOpacity(1.0)
        else:
            color = interpolate_values(
                QColor(0xFF, 0xA0, 0x00),
                QColor(Qt.white),
                self.scale_label_color()
            )
            painter.setPen(color)
            painter.setOpacity(opacity)
        painter.drawText(brect, Qt.AlignCenter, text)
        painter.setOpacity(1.0)

        painter.setFont(old_font)



    def draw_content(self, painter):
        # draw image
        if self.pixmap:
            image_rect = self.get_image_viewport_rect()

            # 1. DRAW SHADOW
            OFFSET = 15
            shadow_rect = QRect(image_rect)
            shadow_rect = shadow_rect.adjusted(OFFSET, OFFSET, -OFFSET, -OFFSET)
            draw_shadow(
                painter,
                shadow_rect, 30,
                webRGBA(QColor(0, 0, 0, 140)),
                webRGBA(QColor(0, 0, 0, 0))
            )

            # 2. DRAW CHECKERBOARD
            checkerboard_br = QBrush()
            pixmap = QPixmap(40, 40)
            painter_ = QPainter()
            painter_.begin(pixmap)
            painter_.fillRect(QRect(0, 0, 40, 40), QBrush(Qt.white))
            painter_.setPen(Qt.NoPen)
            painter_.setBrush(QBrush(Qt.gray))
            painter_.drawRect(QRect(0, 0, 20, 20))
            painter_.drawRect(QRect(20, 20, 20, 20))
            painter_.end()
            checkerboard_br.setTexture(pixmap)
            painter.setBrush(checkerboard_br)
            painter.drawRect(image_rect)
            painter.setBrush(Qt.NoBrush)

            # 3. DRAW IMAGE
            pixmap = self.get_rotated_pixmap()
            painter.drawPixmap(image_rect, pixmap, pixmap.rect())
            if self.invert_image:
                cm = painter.compositionMode()
                painter.setCompositionMode(QPainter.RasterOp_NotDestination)
                                                                #RasterOp_SourceXorDestination
                painter.setPen(Qt.NoPen)
                # painter.setBrush(Qt.green)
                # painter.setBrush(Qt.red)
                # painter.setBrush(Qt.yellow)
                painter.setBrush(Qt.white)
                painter.drawRect(image_rect)
                painter.setCompositionMode(cm)

            # draw thirds
            if self.show_thirds:
                draw_thirds(self, painter, image_rect)
            # draw image center
            if self.show_center_point:
                self.draw_center_point(painter, self.image_center_position)
            # draw scale label
            if self.image_center_position:
                if self.center_label_info_type == "scale":
                    value = math.ceil(self.image_scale*100)
                    text = f"{value:,}%".replace(',', ' ')
                else:
                    text = self.center_label_info_type
                self.draw_center_label(painter, text)

            # draw_image_frame
            self.draw_image_frame(painter)

        elif __name__ == '__main__':
            painter.setPen(QPen(Qt.white))
            font = painter.font()
            font.setPixelSize(20)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignHCenter | Qt.AlignVCenter, "Image Viewer Lite")


    def draw_center_point(self, painter, pos):
        painter.setPen(QPen(Qt.green, 5, Qt.SolidLine))
        painter.drawPoint(pos)

    def show_center_label(self, info_type):
        self.center_label_info_type = info_type
        # show center label on screen
        self.center_label_time = time.time()

    def hide_center_label(self):
        self.center_label_time = time.time() - self.CENTER_LABEL_TIME_LIMIT

    def mirror_current_image(self):
        if self.pixmap:
            tm = QTransform().scale(-1, 1)
            self.rotated_pixmap = self.get_rotated_pixmap().transformed(tm)
            self.update()

    def keyReleaseEvent(self, event):
        key = event.key()
        if key == Qt.Key_Up:
            self.do_scale_image(0.05, cursor_pivot=False)
            self.show_center_label("scale")
        elif key == Qt.Key_Down:
            self.do_scale_image(-0.05, cursor_pivot=False)
            self.show_center_label("scale")

        self.update()

    def isInEditorMode(self):
        return self.type == "edit"

    def keyPressEvent(self, event):
        key = event.key()
        if check_scancode_for(event, ("W", "S", "A", "D")):
            length = 1.0
            if event.modifiers() & Qt.ShiftModifier:
                length *= 20.0
            if check_scancode_for(event, "W"):
                delta =  QPoint(0, 1) * length
            elif check_scancode_for(event, "S"):
                delta =  QPoint(0, -1) * length
            elif check_scancode_for(event, "A"):
                delta =  QPoint(1, 0) * length
            elif check_scancode_for(event, "D"):
                delta =  QPoint(-1, 0) * length
            self.image_center_position += delta
            self.update()
        elif check_scancode_for(event, "C"):
            self.show_center_point = not self.show_center_point
            self.update()
        elif check_scancode_for(event, "T"):
            self.show_thirds = not self.show_thirds
            self.update()
        elif check_scancode_for(event, "I"):
            self.invert_image = not self.invert_image
            self.update()
        elif check_scancode_for(event, "M"):
            self.mirror_current_image()
        elif check_scancode_for(event, "R"):
            self.rotate_clockwise()
        elif check_scancode_for(event, "P"):
            self.close()
        elif key == Qt.Key_Escape:
            self.close()
        elif key in [Qt.Key_Return, Qt.Key_Enter]:
            if self.isInEditorMode():
                self.frame_image()
            else:
                self.framedfinal_to_imagetool()
            self.close()
        self.update()

    def contextMenuEvent(self, event):
        contextMenu = QMenu()
        contextMenu.setStyleSheet("""
        QMenu{
            padding: 0px;
            font-size: 18px;
            font-weight: bold;
            font-family: 'Consolas';
        }
        QMenu::item {
            padding: 15px 15px;
            background: #303940;
            color: rgb(230, 230, 230);
        }
        QMenu::icon {
            padding-left: 15px;
        }
        QMenu::item:selected {
            background-color: rgb(253, 203, 54);
            color: rgb(50, 50, 50);
            border-left: 2px dashed #303940;
        }
        QMenu::separator {
            height: 1px;
            background: gray;
        }
        QMenu::item:checked {
        }
        """)
        self.contextMenuActivated = True

        close_app = contextMenu.addAction("Закрыть")
        contextMenu.addSeparator()
        info_text = f'{self.pixmap.width()} x {self.pixmap.height()}'
        info = contextMenu.addAction(info_text)
        info.setEnabled(False)
        contextMenu.addSeparator()
        unset_capture_rect = contextMenu.addAction("Сбросить область захвата")
        maximize = contextMenu.addAction("Максимально увеличить")
        set_original_scale = contextMenu.addAction("Задать масштаб 1:1")
        zoom_in = contextMenu.addAction("Увеличить масштаб")
        zoom_out = contextMenu.addAction("Уменьшить масштаб")
        rotate_clockwise = contextMenu.addAction("Повернуть по часовой стрелке")
        rotate_counterclockwise = contextMenu.addAction("Повернуть против часовой стрелки")
        contextMenu.addSeparator()
        place_at_center = contextMenu.addAction("Вернуь в центр")

        action = contextMenu.exec_(self.mapToGlobal(event.pos()))
        self.contextMenuActivated = False
        if action is None:
            pass
        elif action == unset_capture_rect:
            self.no_frame_data()
        elif action == close_app:
            self.close()
        elif action == maximize:
            self.restore_image_transformations()
            self.correct_scale()
        elif action == set_original_scale:
            self.set_original_scale()
        elif action == zoom_in:
            self.zoom_in()
        elif action == zoom_out:
            self.zoom_out()
        elif action == rotate_clockwise:
            self.rotate_clockwise()
        elif action == rotate_counterclockwise:
            self.rotate_counterclockwise()
        elif action == place_at_center:
            self.restore_image_transformations()
        self.update()

    def correct_scale(self):
        # корректировка скейла для всех картинок таким образом
        # чтобы каждая занимала максимум экранного пространства
        # и при этом умещалась полностью независимо от размера
        size_rect = self.get_rotated_pixmap().rect()
        target_rect = self.rect()
        target_rect.adjust(0, 50, 0, -50)
        projected_rect = fit_rect_into_rect(size_rect, target_rect)
        self.image_scale = projected_rect.width()/size_rect.width()
        self.update()

    def set_original_scale(self):
        self.image_scale = 1.0
        self.show_center_label("scale")
        self.update()

    def zoom_in(self):
        self.do_scale_image(0.05, cursor_pivot=False)
        self.show_center_label("scale")
        self.update()

    def zoom_out(self):
        self.do_scale_image(-0.05, cursor_pivot=False)
        self.show_center_label("scale")
        self.update()

    def rotate_clockwise(self):
        angles = [0, 90, 180, 270, 0]
        new_index = angles.index(self.image_rotation) + 1
        self.image_rotation = angles[new_index]
        self.get_rotated_pixmap(force_update=True)
        self.update()

    def rotate_counterclockwise(self):
        angles = [0, 270, 180, 90, 0]
        new_index = angles.index(self.image_rotation) + 1
        self.image_rotation = angles[new_index]
        self.get_rotated_pixmap(force_update=True)
        self.update()

def get_filepaths_dialog(path=""):
    dialog = QFileDialog()
    dialog.setFileMode(QFileDialog.ExistingFiles)
    title = ""
    filter_data = "All files (*.*)"
    data = dialog.getOpenFileNames(None, title, path, filter_data)
    return data[0]

if __name__ == '__main__':

    app = QApplication(sys.argv)



    filepath = os.path.join(os.path.dirname(__file__), "image_viewer_test_path.txt")
    path = ""
    if os.path.exists(filepath):
        data = None
        with open(filepath, "r", encoding="utf8") as file:
            data = file.read()
            path = data.split("\n")[0]


    if not path:
        images = get_filepaths_dialog(path)
        path = images[0]
    if path:
        window = ViewerWindow()
        window.resize(2200, 1000)
        # window.show()
        window.showMaximized()
        window.show_image(QPixmap(path))
        app.exec()
