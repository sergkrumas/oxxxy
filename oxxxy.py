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


from functools import partial

from pyqtkeybind import keybinder
from key_seq_edit import KeySequenceEdit

from PyQt5.QtWidgets import (QSystemTrayIcon, QWidget, QMessageBox, QMenu, QFileDialog,
    QCheckBox, QWidgetAction, QApplication, QDesktopWidget, QActionGroup, QSpinBox)
from PyQt5.QtCore import (pyqtSignal, QPoint, QPointF, pyqtSlot, QRect, QEvent,
    Qt, QSize, QRectF, QAbstractNativeEventFilter, QAbstractEventDispatcher)
from PyQt5.QtGui import (QPainterPath, QColor, QKeyEvent, QMouseEvent, QBrush, QPixmap,
    QPainter, QWindow, QImage, QPen, QIcon, QFont, QCursor, QPolygonF, QFontDatabase)

from _utils import (check_scancode_for, SettingsJson, generate_metainfo, build_valid_rect,
    build_valid_rectF, copy_image_file_to_clipboard, open_link_in_browser, save_meta_info,
    make_screenshot_pyqt, webRGBA, draw_shadow, draw_cyberpunk, get_bounding_pointsF,
    generate_datetime_stamp, get_work_area_rect)

from elements import ElementsMixin, ToolID
from editor_autotest import EditorAutotestMixin
from image_viewer_lite import ViewerWindow

from oxxxy_aux_ui import (SettingsWindow, NotificationOrMenu, NotifyDialog, QuitDialog)
from oxxxy_editor_ui import (PictureInfo, ToolsWindow)



class Globals():
    DEBUG = True
    DEBUG_SETTINGS_WINDOW = False
    DEBUG_TRAY_MENU_WINDOW = False
    DEBUG_ELEMENTS = True
    DEBUG_ELEMENTS_PICTURE_FRAMING = True
    DEBUG_ELEMENTS_COLLAGE = False
    DEBUG_UNCAPTURED_ZONES = False
    CRASH_SIMULATOR = False

    DEBUG_VIZ = False
    DEBUG_ANALYSE_CORNERS_SPACES = False

    AFTERCRASH = False
    RUN_ONCE = False
    FULL_STOP = False

    ELEMENT_SIZE_RANGE_OFFSET = 0.5

    SLICE_ROWS = 1
    SLICE_COLS = 2

    # saved settings
    ENABLE_FLAT_EDITOR_UI = False
    ENABLE_CBOR2 = True
    BLOCK_KEYSEQ_HANDLING_AFTER_FIRST_CALL = True
    SCREENSHOT_FOLDER_PATH = ""
    USE_PRINT_KEY = True

    USE_PIXMAP_PROXY_FOR_TEXT_ELEMENTS = True

    ANTIALIASING_AND_SMOOTH_PIXMAP_TRANSFORM = True

    ICON_PATH = None

    DEFAULT_FRAGMENT_KEYSEQ = "Ctrl+Print"
    DEFAULT_FULLSCREEN_KEYSEQ = "Ctrl+Shift+Print"
    DEFAULT_QUICKFULLSCREEN_KEYSEQ = "Shift+Print"

    save_to_memory_mode = False
    images_in_memory = []

    dasPictureMagazin = []

    close_editor_on_done = True

    handle_global_hotkeys = True
    registred_key_seqs = []

    VERSION_INFO = "v0.94"
    AUTHOR_INFO = "by Sergei Krumas"

    background_threads = []

    COPY_SELECTED_CANVAS_ITEMS_STR = '~#~OXXXY:SCREENSHOTER:COPY:SELECTED:CANVAS:ITEMS~#~'

    @classmethod
    def load_fonts(cls):
        folder_path = os.path.dirname(__file__)
        font_filepath = os.path.join(folder_path, 'resources', '7segment.ttf')
        ID = QFontDatabase.addApplicationFont(font_filepath)
        family = QFontDatabase.applicationFontFamilies(ID)[0]
        cls.SEVEN_SEGMENT_FONT = QFont(family)

    @staticmethod
    def get_checkerboard_brush():
        pixmap = QPixmap(40, 40)
        pixmap.fill(Qt.transparent)
        painter_ = QPainter()
        painter_.begin(pixmap)
        painter_.setOpacity(0.3)
        painter_.fillRect(QRect(0, 0, 40, 40), QBrush(Qt.black))
        painter_.setPen(Qt.NoPen)
        painter_.setBrush(QBrush(Qt.black))
        painter_.drawRect(QRect(0, 0, 20, 20))
        painter_.drawRect(QRect(20, 20, 20, 20))
        painter_.end()
        brush = QBrush()
        brush.setTexture(pixmap)
        return brush

    @classmethod
    def generate_icons(cls):

        bitmap_cancel = QPixmap(50, 50)
        bitmap_cancel.fill(Qt.transparent)
        painter = QPainter()
        painter.begin(bitmap_cancel)
        inner_rect = bitmap_cancel.rect().adjusted(13, 13, -13, -13)
        pen = QPen(QColor(200, 100, 0), 10)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(inner_rect.topLeft(), inner_rect.bottomRight())
        painter.drawLine(inner_rect.bottomLeft(), inner_rect.topRight())
        painter.end()

        bitmap_halt = QPixmap(50, 50)
        bitmap_halt.fill(Qt.transparent)
        painter = QPainter()
        painter.begin(bitmap_halt)
        inner_rect = bitmap_halt.rect().adjusted(13, 13, -13, -13)
        painter.setBrush(QBrush(QColor(200, 0, 0)))
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, 50, 50), 10, 10)
        painter.drawPath(path)
        painter.setPen(Qt.NoPen)
        pen = QPen(Qt.white, 10)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(inner_rect.topLeft(), inner_rect.bottomRight())
        painter.drawLine(inner_rect.bottomLeft(), inner_rect.topRight())
        painter.end()

        bitmap_refresh = QPixmap(50, 50)
        bitmap_refresh.fill(Qt.transparent)
        painter = QPainter()
        painter.begin(bitmap_refresh)
        pen = painter.pen()
        pen.setWidth(5)
        pen.setColor(Qt.white)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        rectangle = QRectF(bitmap_refresh.rect().adjusted(13, 13, -13, -13))
        painter.setBrush(QBrush(Qt.white))
        startAngle = 60 * 16
        spanAngle = (180-60) * 16
        painter.drawArc(rectangle, startAngle, spanAngle)
        startAngle = (180+60) * 16
        spanAngle = (360-180-60) * 16
        painter.drawArc(rectangle, startAngle, spanAngle)
        w = bitmap_refresh.rect().width()
        points = [
            QPointF(50, 50) - QPointF(44, w/2),
            QPointF(50, 50) - QPointF(31, w/2),
            QPointF(50, 50) - QPointF(37.5, w/2-8),
        ]
        poly = QPolygonF(points)
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(poly, fillRule=Qt.WindingFill)
        points = [
            QPointF(44, w/2),
            QPointF(31, w/2),
            QPointF(37.5, w/2-8),
        ]
        poly = QPolygonF(points)
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(poly, fillRule=Qt.WindingFill)
        painter.end()

        cls.icon_cancel = QIcon(bitmap_cancel)
        cls.icon_halt = QIcon(bitmap_halt)
        path = os.path.join(os.path.dirname(__file__), "icon.png")
        cls.icon_multiframing = QIcon(path)
        cls.icon_refresh = QIcon(bitmap_refresh)

    @staticmethod
    def get_screenshot_filepath(params):
        return os.path.join(Globals.SCREENSHOT_FOLDER_PATH, f"{params}.png")


RegionInfo = namedtuple('RegionInfo', 'setter coords getter')

class LayerOpacity(Enum):
    FullTransparent = 1
    HalfTransparent = 2
    Opaque = 3

class RequestType(Enum):
    Fragment = 0
    Fullscreen = 1
    QuickFullscreen = 2
    Editor = 3

class CanvasEditor(QWidget, ElementsMixin, EditorAutotestMixin):

    editing_ready = pyqtSignal(object)
    save_current_editing = pyqtSignal()

    # для поддержки миксинов
    Globals = Globals
    SettingsWindow = SettingsWindow
    NotifyDialog = NotifyDialog
    PictureInfo = PictureInfo

    def set_clipboard(self, text):
        cb = QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(text, mode=cb.Clipboard)

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
        painter = QPainter()
        painter.begin(out_img)
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
        if self.working_area_rect is not None:
            war = self.working_area_rect
            self.move(war.left(), war.top())
            self.resize(right-left+1-war.left(), war.height())
        else:
            self.move(0, 0)
            self.resize(right-left+1, bottom-top+1)
        self._all_monitors_rect = QRect(QPoint(left, top), QPoint(right+1, bottom+1))

    def is_point_set(self, p):
        return p is not None

    def get_first_set_point(self, points, default):
        for point in points:
            if self.is_point_set(point):
                return point
        return default

    def is_input_points_set(self):
        return self.is_point_set(self.input_POINT1) and self.is_point_set(self.input_POINT2)

    def build_input_rectF(self, cursor_pos):
        ip1 = self.get_first_set_point([self.input_POINT1], cursor_pos)
        ip2 = self.get_first_set_point([self.input_POINT2, self.input_POINT1], cursor_pos)
        return build_valid_rectF(ip1, ip2)

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)

        text_white_pen = text_pen = QPen(QColor(255, 255, 255, 255), 1)
        font = painter.font()
        font.setPixelSize(15)
        painter.setFont(font)

        cursor_pos = self.mapFromGlobal(QCursor().pos())
        canvas_input_rect = self.build_input_rectF(self.elementsMapToCanvas(cursor_pos))
        viewport_input_rect = self.elementsMapToViewportRectF(canvas_input_rect)

        self.draw_checkerboard(painter)

        self.draw_uncaptured_zones(painter, self.uncapture_draw_type, QRectF(viewport_input_rect), step=1)

        # background image
        self.draw_capture_zone(painter, QRectF(viewport_input_rect), shot=1)
        # elements
        self.elementsDrawMain(painter)
        # mask overlay
        self.draw_capture_zone(painter, QRectF(viewport_input_rect), shot=2)

        self.draw_uncaptured_zones(painter, self.uncapture_draw_type, QRectF(viewport_input_rect), step=2)

        self.draw_magnifier(painter, QRectF(viewport_input_rect), cursor_pos, text_pen, text_white_pen)
        self.draw_wrapper_cyberpunk(painter)
        self.draw_wrapper_shadow(painter)
        self.draw_capture_zone_resolution_label(painter, text_pen, QRectF(viewport_input_rect))

        self.draw_vertical_horizontal_lines(painter, cursor_pos)

        self.draw_picture_tool(painter, cursor_pos)

        self.draw_tool_size_and_color(painter, cursor_pos)
        self.draw_hint(painter, cursor_pos, text_white_pen)

        self.draw_uncapture_zones_mode_info(painter)

        pos = viewport_input_rect.bottomRight().toPoint()
        self.elementsDrawDateTime(painter, pos)

        if Globals.DEBUG:
            self.draw_canvas_origin(painter)
            self.draw_analyse_corners(painter)
            self.elementsDrawDebugInfo(painter, QRectF(viewport_input_rect))

            # self.draw_warning_deactivated(painter)

        painter.end()

    def draw_warning_deactivated(self, painter):

        deactivated = not self.isActiveWindow()
        if self.tools_window:
            deactivated = deactivated and not self.tools_window.isActiveWindow()

        if deactivated:
            painter.save()
            font = painter.font()
            font.setPixelSize(40)
            painter.setFont(font)
            painter.setPen(QPen(Qt.white))
            desktop = QDesktopWidget()
            painter.fillRect(self.rect(), QColor(80, 80, 80))
            painter.setBrush(self.checkerboard_brush)
            painter.drawRect(self.rect())
            for i in range(0, desktop.screenCount()):
                r = desktop.screenGeometry(screen=i)
                painter.drawText(r, Qt.AlignHCenter | Qt.AlignVCenter, "Редактор потерял фокус ввода!\nНадо щёлкнуть левой или правой кнопкой мыши")
            painter.restore()

    def draw_checkerboard(self, painter):
        painter.save()
        painter.setBrush(self.checkerboard_brush)
        painter.drawRect(self.rect())
        painter.restore()

    def draw_canvas_origin(self, painter):
        pen = QPen(Qt.magenta, 4)
        painter.setPen(pen)
        painter.drawPoint(self.canvas_origin)

    def draw_tool_size_and_color(self, painter, cursor_pos):
        if not self.capture_region_rect:
            return
        if not self.tools_window:
            return
        if self.current_tool not in [ToolID.line, ToolID.marker, ToolID.pen]:
            return
        if not self.capture_region_rect.contains(cursor_pos):
            return

        self._ted.type = self.current_tool
        self._ted.color = self.tools_window.color_slider.get_color()
        self._ted.size = self.tools_window.size_slider.value
        self._ted.element_position = self.elementsMapToCanvas(cursor_pos)
        self._ted.start_point = self._ted.element_position
        self._ted.end_point = self._ted.element_position
        self._ted.straight = True
        self._ted.preview = True
        self._ted.element_scale_x = 1.0
        self._ted.element_scale_y = 1.0
        self._ted.calc_local_data()

        painter.save()
        painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.elementsDrawMainElement(painter, self._ted, False, [])
        painter.restore()

    def draw_picture_tool(self, painter, cursor_pos):
        if self.current_tool != ToolID.picture or not self.current_picture_pixmap:
            return
        if self.capture_region_rect is None:
            # для случая, когда рамка захвата обнулена из контекстного меню
            # и активирован этот тулз
            return
        crr_canvas = self.capture_region_rect
        crr_viewport = self.elementsMapToViewportRectF(crr_canvas)
        if not crr_viewport.contains(cursor_pos):
            return

        self._tei.element_rotation = self.current_picture_angle
        self._tei.pixmap = self.current_picture_pixmap
        self._tei.element_position = self.elementsMapToCanvas(cursor_pos)
        self._tei.calc_local_data()
        # нет смысла в этом задании размера здесь,
        # потому что слайдер ограничен диапазоном 0.5 до 1.5
        # size = self.tools_window.size_slider.value
        # self._tei.element_scale_x = size
        # self._tei.element_scale_y = size

        painter.save()
        painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        painter.setOpacity(0.5)
        self.elementsDrawMainElement(painter, self._tei, True, [])
        painter.setOpacity(1.0)

        # счётчик оставшихся изображений в магазине
        if Globals.dasPictureMagazin:
            count = len(Globals.dasPictureMagazin)
            count_str = str(count)

            r = QRect(0, 0, 25, 25)
            rect = painter.drawText(r, Qt.AlignCenter | Qt.AlignVCenter, count_str)
            rect = r
            rect.moveTopLeft(cursor_pos)
            painter.setBrush(QBrush(Qt.red))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(rect)

            painter.setPen(Qt.white)
            painter.save()
            font = painter.font()
            font.setFamily("Consolas")
            font.setWeight(1600)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter | Qt.AlignVCenter, count_str)
            painter.restore()

        painter.restore()

    def draw_uncapture_zones_mode_info(self, painter):
        painter.save()
        info = {
            LayerOpacity.FullTransparent: 'Прозрачность фона: 100%',
            LayerOpacity.HalfTransparent: 'Прозрачность фона: 50%',
            LayerOpacity.Opaque: 'Прозрачность фона: 0%',
        }
        if time.time() - self.uncapture_mode_label_tstamp < 1.5:
            text_info = info[self.uncapture_draw_type]
            text_info = "Tab ➜ " + text_info
            font = painter.font()
            font.setPixelSize(30)
            painter.setFont(font)
            rect = painter.drawText(self.rect(), Qt.AlignLeft | Qt.AlignTop, text_info)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(50, 50, 50)))
            painter.drawRect(rect)
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignTop, text_info)
        painter.restore()

    def draw_magnifier(self, painter, input_rect, cursor_pos, text_pen, text_white_pen):
        MAGNIFIER_SIZE = self.magnifier_size
        if self.capture_region_rect:
            return

        _cursor_pos = cursor_pos

        # позиционирование в завимости от свободного места около курсора
        focus_point = input_rect.bottomRight() or _cursor_pos
        # позиция внизу справа от курсора
        focus_rect = build_valid_rect(
            focus_point + QPoint(10, 10),
            focus_point + QPoint(10 + MAGNIFIER_SIZE, 10 + MAGNIFIER_SIZE)
        )
        if not self._all_monitors_rect.contains(focus_rect):
            # позиция вверху слева от курсора
            focus_rect = build_valid_rect(
                focus_point + -1*QPoint(10, 10),
                focus_point + -1*QPoint(10 + MAGNIFIER_SIZE, 10 + MAGNIFIER_SIZE)
            )
            # зона от начала координат в левом верхнем углу до курсора
            t = build_valid_rect(QPoint(0, 0), _cursor_pos)
            if not t.contains(focus_rect):
                focus_rect = build_valid_rect(
                    focus_point + QPoint(10, -10),
                    focus_point + QPoint(10 + MAGNIFIER_SIZE, -10-MAGNIFIER_SIZE)
                )
                # зона от курсора до верхней правой границы экранного пространства
                t2 = build_valid_rect(_cursor_pos, self._all_monitors_rect.topRight())
                if not t2.contains(focus_rect):
                    focus_rect = build_valid_rect(
                        focus_point + QPoint(-10, 10),
                        focus_point + QPoint(-10-MAGNIFIER_SIZE, 10+MAGNIFIER_SIZE)
                    )
        # magnifier
        cp = QPoint(_cursor_pos)
        cp -= self.canvas_origin
        cp = QPointF(
            cp.x()/self.source_pixels.width()/self.canvas_scale_x,
            cp.y()/self.source_pixels.height()/self.canvas_scale_y
        )

        x = int(cp.x()*self.source_pixels.width())
        y = int(cp.y()*self.source_pixels.height())
        cp = QPointF(
            min(max(0, x), self.source_pixels.width()),
            min(max(0, y), self.source_pixels.height())
        ).toPoint()

        magnifier_source_rect = QRect(cp - QPoint(10, 10), cp + QPoint(10, 10))
        mh = int(magnifier_source_rect.height())
        mw = int(magnifier_source_rect.width())

        # лупа с прицелом
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
        magnifier_image = magnifier_pixmap.toImage()

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
        painter.save()
        font = painter.font()
        font.setPixelSize(int(mag_text_rect.height()/2.0+5))
        painter.setFont(font)
        cp = QPoint(magnifier_source_rect.width()//2, magnifier_source_rect.height()//2)
        # self.color_at_pixel = QColor(self.source_pixels.pixel(cursor_pos))
        self.color_at_pixel = QColor(magnifier_image.pixel(cp))
        color_hex_string = self.color_at_pixel.name()
        painter.drawText(mag_text_rect, Qt.AlignCenter, color_hex_string)
        painter.restore()
        color_rect = QRect(focus_rect.bottomLeft()+QPoint(0, -5), QSize(focus_rect.width(), 6))
        painter.fillRect(color_rect, self.color_at_pixel)

        # draw copied color values
        painter.save()
        max_width = 0
        data = list(enumerate(reversed(self.colors_values_copied)))
        for n, (color, color_represenation) in data:
            max_width = max(max_width, painter.boundingRect(QRect(), Qt.AlignLeft, color_represenation).width())
        for n, (color, color_represenation) in data:
            pos = _cursor_pos + QPointF(-max_width, 25*(n+1))
            painter.drawText(pos, color_represenation)
        for n, (color, color_represenation) in data:
            pos = _cursor_pos + QPointF(-max_width-10, 25*(n+1))
            rect = build_valid_rectF(pos, pos+QPointF(-10, -10))
            painter.setPen(QPen(Qt.black, 1))
            painter.setBrush(QBrush(color))
            painter.drawRect(rect)
        painter.restore()

    def draw_hint(self, painter, cursor_pos, text_white_pen):
        if not self.is_point_set(self.input_POINT1):
            lines = (
    " В режиме задания области захвата:"
    "\n     ➜ Модификаторы для мыши:"
    "\n         + Shift - квадрат;"
    "\n         + Ctrl - шаговое приращение."
    "\n     ➜ Стрелки ← ↑ → ↓ для позиционирования курсора мыши c точносью до пикселя:"
    "\n         + Shift - перемещение на 10 пикселей, а не на 1;"
    "\n         + Ctrl - умножает текущую величину перемещения на 5;"
    "\n         Enter - подтверждение ввода позиций начального и конечного углов прямоугольной"
                                                                                " области захвата."
    "\n     ➜ Зажатое колесо мыши - перенос холста;"
    "\n     ➜ Крутить колесо мыши - зумить холст;"
    "\n     ➜ Лупа:"
    "\n         Ctrl + колесо мыши - задать размер лупы;"
    "\n         Ctrl + C - копировать цвет под прицелом в буфер обмена;"
    "\n             При копировании текущего цвета в буфер копируются также и прыдущие цвета."
    "\n     ➜ Доступно контекстное меню для возможности выхода из приложения или сворачивания"
                                                                                        " окна."
    "\n"
    "\n В режиме задания области захвата и в режиме редактирования пометок:"
    "\n     ➜ Tab / Tab+Shift - переключение между 3-мя режимами отображения незахваченной"
                                                                                        " области."
    "\n     ➜ Доступно контекстное меню для возможности выхода из приложения или сворачивания"
                                                                                        " окна."
            )
            if self.show_help_hint:
                hint_text = lines
            else:
                hint_text = "Клавиша F1 - подробная справка"
            hint_pos = cursor_pos + QPoint(10, -8)
            hint_rect = build_valid_rect(hint_pos, hint_pos + QPoint(900, -400))
            painter.setPen(text_white_pen)
            # painter.setPen(QPen(Qt.white))
            painter.drawText(hint_rect, Qt.TextWordWrap | Qt.AlignBottom, hint_text)

    def draw_capture_zone_resolution_label(self, painter, text_pen, input_rect):
        case1 = self.is_point_set(self.input_POINT2) and not self.is_rect_defined
        case2 = self.is_rect_being_redefined
        if case2 or case1:
            painter.setPen(text_pen)
            text_pos = input_rect.bottomRight() + QPoint(10, -10)
            input_r = build_valid_rectF(self.input_POINT1, self.input_POINT2)
            painter.drawText(text_pos, "%dx%d" % (input_r.width(), input_r.height()))

    def build_hex_polygon(self, outer_rect):
        x = 3**0.5 / 2
        size = min(outer_rect.width(), outer_rect.height())
        hexaPointsF = [QPointF(size/4, 0.0),
                        QPointF(size/4 + size/2, 0.0),
                        QPointF(size, size*0.5*x),
                        QPointF(size/4 + size/2, size*x),
                        QPointF(size/4, size*x),
                        QPointF(0.0, size*0.5*x)]
        hexaPointsF = [QPointF(p.y(), p.x()) for p in hexaPointsF]
        max_x = max([p.x() for p in hexaPointsF])
        hexaPointsF = [QPointF(p.x()+(size-max_x)/2, p.y()) for p in hexaPointsF]
        hexaPointsF = [QPointF(p.x()+outer_rect.x(), p.y()+outer_rect.y()) for p in hexaPointsF]
        hexaPointsF = [QPointF(p.x()+(outer_rect.width()-size)/2,
                                         p.y()+(outer_rect.height()-size)/2) for p in hexaPointsF]
        hexaF = QPolygonF(hexaPointsF)
        return hexaF

    def draw_uncaptured_zones(self, painter, opacity_type, input_rect, step=1):
        # поправочка нужна для случая, когда использована команда "Содержимое в фон"
        # и после неё габариты получившегося изображения уже не равны
        # габаритам скриншота монитора(ов)
        self_rect = QRectF(self.source_pixels.rect()) # self_rect = QRectF(self.rect())
        self_rect = self.elementsMapToViewportRectF(self_rect)
        if step == 1:
            if opacity_type == LayerOpacity.FullTransparent: # full transparent
                self.elementsDrawBackgroundGhost(painter, self_rect)
            elif opacity_type == LayerOpacity.HalfTransparent: # ghost
                pass
            elif opacity_type == LayerOpacity.Opaque: # stay still
                self.elementsDrawMainBackgroundOnlyNotFinal(painter)
        elif step == 2:

            if self.capture_region_widget_enabled:
                painter.setClipping(True)
                path = QPainterPath()
                path.addRect(QRectF(self.rect()))
                path.addRect(QRectF(input_rect))
                painter.setClipPath(path)
                if opacity_type == LayerOpacity.FullTransparent: # full transparent
                    pass
                elif opacity_type == LayerOpacity.HalfTransparent: # ghost
                    painter.fillRect(self_rect, QColor(0, 0, 0, 100))
                    painter.setOpacity(0.6)
                    self.elementsDrawMainBackgroundOnlyNotFinal(painter)
                    painter.setOpacity(1.0)
                elif opacity_type == LayerOpacity.Opaque: # stay still
                    painter.fillRect(self_rect, QColor(0, 0, 0, 100))
                painter.setClipping(False)

                if Globals.DEBUG_UNCAPTURED_ZONES and self.undermouse_region_rect:
                    pen = painter.pen()
                    brush = painter.brush()
                    painter.setPen(Qt.NoPen)
                    b = QBrush(Qt.green)
                    b.setStyle(Qt.DiagCrossPattern)
                    painter.setBrush(b)
                    painter.setOpacity(0.06)
                    self.define_regions_rects_and_set_cursor(write_data=False)
                    painter.drawRect(self.undermouse_region_rect)
                    painter.setOpacity(1.0)
                    painter.setPen(pen)
                    painter.setBrush(brush)

    def draw_capture_zone(self, painter, input_rect, shot=1):
        tw = self.tools_window
        if shot == 1 and self.is_input_points_set():
            if self.show_background:
                painter.setClipping(True)
                path = QPainterPath()
                path.addRect(QRectF(input_rect))
                painter.setClipPath(path)
                self.elementsDrawMainBackgroundOnlyNotFinal(painter)
                painter.setClipping(False)

        if shot == 2 and self.is_input_points_set():
            if tw and tw.chb_masked.isChecked():
                imgsize = min(input_rect.width(), input_rect.height())
                rect = QRectF(
                    input_rect.left() + (input_rect.width() - imgsize) / 2,
                    input_rect.top() + (input_rect.height() - imgsize) / 2,
                    imgsize,
                    imgsize,
                )
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
                    path.addEllipse(rect)

                painter.drawPath(path)

    def draw_wrapper_shadow(self, painter):
        if self.capture_region_rect:
            capture_region_rect = self.elementsMapToViewportRectF(self.capture_region_rect)
            draw_shadow(
                painter,
                capture_region_rect, 50,
                webRGBA(QColor(0, 0, 0, 100)),
                webRGBA(QColor(0, 0, 0, 0))
            )

    def draw_wrapper_cyberpunk(self, painter):
        tw = self.tools_window
        if tw and tw.chb_draw_thirds.isChecked() and self.capture_region_rect:
            capture_region_rect = self.elementsMapToViewportRectF(self.capture_region_rect)
            draw_cyberpunk(painter, capture_region_rect)

    def draw_vertical_horizontal_lines(self, painter, cursor_pos):
        painter.save()
        line_pen = QPen(QColor(127, 127, 127, 172), 2, Qt.DashLine)
        painter.setCompositionMode(QPainter.RasterOp_SourceXorDestination)

        if self.is_input_points_set():
            painter.setPen(line_pen)
            input_POINT1 = self.elementsMapToViewport(self.input_POINT1)
            input_POINT2 = self.elementsMapToViewport(self.input_POINT2)
            left = input_POINT1.x()
            top = input_POINT1.y()
            right = input_POINT2.x()
            bottom = input_POINT2.y()
            # vertical left
            painter.drawLine(QPointF(left, 0), QPointF(left, self.height()))
            # horizontal top
            painter.drawLine(QPointF(0, top), QPointF(self.width(), top))
            # vertical right
            painter.drawLine(QPointF(right, 0), QPointF(right, self.height()))
            # horizontal bottom
            painter.drawLine(QPointF(0, bottom), QPointF(self.width(), bottom))
            if self.undermouse_region_rect and Globals.DEBUG_VIZ:
                painter.setBrush(QBrush(Qt.green, Qt.DiagCrossPattern))
                painter.drawRect(self.undermouse_region_rect)
        else:
            painter.setPen(line_pen)
            pos_x = cursor_pos.x()
            pos_y = cursor_pos.y()
            painter.drawLine(pos_x, 0, pos_x, self.height())
            painter.drawLine(0, pos_y, self.width(), pos_y)
        painter.restore()

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
            if self.debug_tools_space is not None:
                painter.setBrush(QBrush(Qt.blue, Qt.DiagCrossPattern))
                painter.drawRect(self.debug_tools_space.adjusted(10, 10, -10, -10))

    def __init__(self, screenshot_image, metadata, datetime_stamp, parent=None):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowMinimizeButtonHint)
        self.working_area_rect = get_work_area_rect()
        self.set_size_and_position()

        self.setWindowTitle(f"Oxxxy Screenshoter {Globals.VERSION_INFO} {Globals.AUTHOR_INFO}")

        self.context_menu_stylesheet = """
        QMenu, QCheckBox{
            padding: 0px;
            font-size: 16px;
            font-weight: normal;
            font-family: 'Consolas';
        }
        QMenu::item, QCheckBox{
            padding: 10px;
            background: #303940;
            color: rgb(230, 230, 230);
        }
        QMenu::icon{
            padding-left: 15px;
        }
        QMenu::item:selected, QCheckBox:hover{
            background-color: rgb(253, 203, 54);
            color: rgb(50, 50, 50);
            border-left: 2px dashed #303940;
        }
        QMenu::item:checked, QCheckBox:checked{
            font-weight: bold;
            color: white;
            background: #304550;
        }
        QMenu::item:unchecked, QCheckBox:unchecked{
            background: #304550;
        }
        QMenu::item:checked:selected, QCheckBox:checked:hover{
            font-weight: bold;
            color: rgb(50, 50, 50);
            background-color: rgb(253, 203, 54);
        }
        QMenu::item:unchecked:selected, QCheckBox:unchecked:hover{
            color: rgb(50, 50, 50);
            background-color: rgb(253, 203, 54);
        }
        QMenu::item:disabled {
            background-color: #303940;
            color: black;
            border-left: 2px dashed #303940;
        }
        QMenu::separator {
            height: 1px;
            background: gray;
        }
        QMenu::indicator {
            left: 6px;
        }
        QMenu::indicator:non-exclusive:unchecked {
            image: url(resources/unchecked.png);
        }
        QMenu::indicator:non-exclusive:unchecked:selected {
            image: url(resources/unchecked.png);
        }
        QMenu::indicator:non-exclusive:checked {
            image: url(resources/checked.png);
        }
        QMenu::indicator:non-exclusive:checked:selected {
            image: url(resources/checked_selected.png);
        }
        QMenu::indicator:exclusive:unchecked {
            image: url(resources/rb_unchecked.png);
        }
        QMenu::indicator:exclusive:unchecked:selected {
            image: url(resources/rb_unchecked.png);
        }
        QMenu::indicator:exclusive:checked {
            image: url(resources/checked.png);
        }
        QMenu::indicator:exclusive:checked:selected {
            image: url(resources/checked_selected.png);
        }
        """



        self.source_pixels = screenshot_image
        self.metadata = metadata
        self.datetime_stamp = datetime_stamp

        self.input_POINT1 = None
        self.input_POINT2 = None
        self.capture_region_rect = None

        self.user_input_started = False
        self.is_rect_defined = False
        self.is_rect_being_redefined = False

        self.undermouse_region_rect = None
        self.undermouse_region_info = None
        self.region_num = 0

        self.start_cursor_position = QPointF(0, 0)

        self.tools_window = None
        self.view_window = None
        self.dialog = None
        self.cancel_context_menu = False

        self.default_corner_space = None
        self.reserved_corner_1_space = None
        self.reserved_corner_2_space = None

        self.debug_tools_space = None

        self._custom_cursor_data = None
        self._custom_cursor_cycle = 0

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.uncapture_draw_type = LayerOpacity.Opaque
        self.uncapture_types = itertools.cycle([
            (LayerOpacity.FullTransparent, LayerOpacity.Opaque),
            (LayerOpacity.HalfTransparent, LayerOpacity.HalfTransparent),
            (LayerOpacity.Opaque, LayerOpacity.FullTransparent)
        ])

        # Если удерживать левую кнопку мыши над пятой областью и
        # тащить мышку до одной из границ области захвата,
        # то начнётся изменение области захвата.
        # Этого хочется избежать - именно для исправления
        # такого ненужного поведения и нужна эта переменная
        self.drag_inside_capture_zone = False
        # задаём курсор
        self.setCursor(self.get_custom_cross_cursor())
        # лупа задания области захвата
        self.magnifier_size = 100
        self.color_at_pixel = QColor(Qt.black)
        self.colors_values_copied = []
        # помощь F1
        self.show_help_hint = False

        # для рисования пометок на скриншоте
        self.checkerboard_brush = Globals.get_checkerboard_brush()
        self.tools_settings = SettingsJson().get_data("TOOLS_SETTINGS")
        self.current_picture_pixmap = None
        self.current_picture_id = None
        self.current_picture_angle = 0
        self.elementsInit()
        self.elementsCreateBackgroundPictures(self.CreateBackgroundOption.Initial)
        self.hex_mask = False

        self.setMouseTracking(True)
        self.editing_ready.connect(self.editing_is_done_handler)
        self.save_current_editing.connect(self.save_current_editing_handler)

        # для временного отображения текста в левом верхнем углу
        self.uncapture_mode_label_tstamp = time.time()

    def set_saved_capture_frame(self):
        if self.tools_settings.get("savecaptureframe", False):
            rect_params = self.tools_settings.get("capture_frame", None)
            if rect_params:
                rect = QRectF(*rect_params)
                self.input_POINT2 = rect.topLeft()
                self.input_POINT1 = rect.bottomRight()
                self.capture_region_rect = build_valid_rectF(self.input_POINT1,
                                                                                self.input_POINT2)
                self.user_input_started = False
                self.is_rect_defined = True
                self.drag_inside_capture_zone = False
                self.get_region_info()
                self.update_tools_window()
                self.update()

    def request_fullscreen_capture_region(self):
        self.input_POINT2 = QPoint(0, 0)
        self.input_POINT1 = self.frameGeometry().bottomRight()
        self.capture_region_rect = build_valid_rectF(self.input_POINT1, self.input_POINT2)
        self.user_input_started = False
        self.is_rect_defined = True
        self.drag_inside_capture_zone = False
        self.get_region_info()
        self.update_tools_window()
        self.update()

    def request_images_editor_mode(self, paths_or_pixmaps):
        pixmaps = []
        self.input_POINT2 = QPoint(0, 0)
        self.input_POINT1 = self.frameGeometry().bottomRight()
        self.user_input_started = False
        self.is_rect_defined = True
        self.drag_inside_capture_zone = False
        self.get_region_info()
        self.update_tools_window()
        tw = self.tools_window
        tw.initialization = True
        tw.set_current_tool(ToolID.picture)
        points = []
        elementTopLeft = QPointF(0, 0)
        elementBottomRight = QPointF(0, 0)
        for path_or_pix in paths_or_pixmaps:
            if isinstance(path_or_pix, QPixmap):
                pixmap = path_or_pix
            else:
                pixmap = QPixmap(path_or_pix)
            if pixmap.width() != 0:
                element = self.elementsCreateNew(ToolID.picture)
                element.pixmap = pixmap
                elementBottomRight = elementTopLeft + QPointF(pixmap.width(), pixmap.height())
                points.append(QPointF(elementTopLeft))
                points.append(QPointF(elementBottomRight))
                element.element_position = (elementTopLeft + elementBottomRight) / 2.0
                element.calc_local_data()
                elementTopLeft += QPointF(pixmap.width(), 0)
                pixmaps.append(pixmap)
        if pixmaps:
            self.input_POINT2, self.input_POINT1 = get_bounding_pointsF(points)
        else:
            self.input_POINT2 = QPointF(0, 0)
            self.input_POINT1 = QPointF(self.frameGeometry().bottomRight())
        self.capture_region_rect = build_valid_rectF(self.input_POINT1, self.input_POINT2)
        tw.set_current_tool(ToolID.transform)
        tw.forwards_backwards_update()
        self.update_tools_window()
        self.update()

    def request_elements_debug_mode(self):
        self.input_POINT2 = QPoint(300, 200)
        self.input_POINT1 = QPoint(1400, 800)
        self.capture_region_rect = build_valid_rectF(self.input_POINT1, self.input_POINT2)
        self.user_input_started = False
        self.is_rect_defined = True
        self.drag_inside_capture_zone = False
        self.get_region_info()
        self.update_tools_window()
        if Globals.DEBUG_ELEMENTS_PICTURE_FRAMING:
            folder_path = os.path.dirname(__file__)
            filepath = os.path.join(folder_path, "docs", "3.png")
            pixmap = QPixmap(filepath)
            element = self.elementsCreateNew(ToolID.picture)
            element.pixmap = pixmap
            element.calc_local_data()
            element.element_position = self.input_POINT2
            element.element_position += QPointF(pixmap.width()/2, pixmap.height()/2)
            self.elementsSetSelected(element)
        self.update()

    def place_view_window(self):
        self.view_window.show()
        # показываем только на первом мониторе слева
        self.view_window.move(0, 0)
        desktop_rect = QDesktopWidget().screenGeometry(screen=0)
        self.view_window.resize(desktop_rect.width(), desktop_rect.height())

    def show_view_window(self, get_pixmap_callback_func, _type="final", data=None):
        if self.view_window:
            self.view_window.show()
            self.view_window.activateWindow()
        else:
            self.view_window = ViewerWindow(self, main_window=self, _type=_type, data=data)
            self.place_view_window()
            pixmap = get_pixmap_callback_func()
            self.view_window.show_image_default(pixmap)
            self.view_window.activateWindow()

    def show_view_window_for_animated(self, filepath):
        self.view_window = ViewerWindow(self, main_window=self, _type="final", data=None)
        self.place_view_window()
        self.view_window.show_image(filepath)
        self.view_window.activateWindow()

    def update_sys_tray_icon(self, *args, **kwargs):
        update_sys_tray_icon(*args, **kwargs)

    def save_screenshot(self, grabbed_image=None, metadata=None, restart=True):
        if restart:
            close_all_windows()

        # задание папки для скриншота
        SettingsWindow.set_screenshot_folder_path()
        # сохранение файла
        formated_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        filepath = Globals.get_screenshot_filepath(formated_datetime)
        if grabbed_image:
            # QUICK FULLSCREEN
            grabbed_image.save(filepath)
            # copy_image_file_to_clipboard(filepath)
            save_meta_info(metadata, filepath)
        else:
            pix = self.elementsRenderFinal(force_no_datetime_stamp=Globals.save_to_memory_mode)
            if Globals.save_to_memory_mode:
                Globals.images_in_memory.append(pix)
                update_sys_tray_icon(len(Globals.images_in_memory))
            else:
                pix.save(filepath)
                if self.tools_window.chb_add_meta.isChecked():
                    save_meta_info(self.metadata, filepath)
                copy_image_file_to_clipboard(filepath)
                if not restart:
                    return filepath
        if restart:
            # restart
            if grabbed_image or not Globals.save_to_memory_mode:
                restart_app_in_notification_mode(filepath)

    def create_tools_window_if_needed(self):
        if not self.tools_window:
            self.tools_window = ToolsWindow(self)
            self.tools_window.show()

    def update_tools_window(self):
        if self.is_rect_defined:
            if not self.tools_window: # create window
                # делаем окно ребёнком основного,
                # чтобы оно не пропадало и не падало за основное
                self.create_tools_window_if_needed()
                # так как в историю действий записывается создание фона,
                # то после задания рамки придётся сразу выставить
                # кнопки истории в актуальное состояние
                self.tools_window.forwards_backwards_update()
        self.autopos_tools_window()

    def autopos_tools_window(self):
        if self.tools_window and self.capture_region_rect:
            capture_region_rect = self.elementsMapToViewportRectF(self.capture_region_rect)
            self.tools_window.do_autopositioning(capture_region_rect)

    def selection_filter_menu(self, main_menu=None):
        if main_menu is not None:
            menu = QMenu(main_menu)
        else:
            menu = QMenu()
        title = 'Доступные к выделению'
        menu.setTitle(title)
        menu.setStyleSheet(self.context_menu_stylesheet)
        def add_item(*args):
            action = menu.addAction(*args)
            action.setCheckable(True)
            return action

        if not main_menu:
            title = menu.addAction(title)
            title.setEnabled(False)

        _all = add_item("И пометки, и фон")
        _content_only = add_item("Только пометки")
        _background_only = add_item("Только фон")

        ag = QActionGroup(menu)
        for a in (_all, _content_only, _background_only):
            a.setActionGroup(ag)

        _all.setChecked(False)
        _content_only.setChecked(False)
        _background_only.setChecked(False)
        if self.selection_filter == self.SelectionFilter.all:
            _all.setChecked(True)
        elif self.selection_filter == self.SelectionFilter.content_only:
            _content_only.setChecked(True)
        elif self.selection_filter == self.SelectionFilter.background_only:
            _background_only.setChecked(True)

        def click_handler(a):
            if a == None:
                return True
            else:
                if a.parent() == menu:
                    if a == _all:
                        self.selection_filter = self.SelectionFilter.all
                    elif a == _content_only:
                        self.selection_filter = self.SelectionFilter.content_only
                    elif a == _background_only:
                        self.selection_filter = self.SelectionFilter.background_only
                    self.elementsSelectionFilterChangedCallback()
                    return True
            return False

        if main_menu:
            return menu, click_handler

        action = menu.exec_(QCursor().pos())
        click_handler(action)

    def special_change_handler(self, callback):
        self.elementsStartModificationProcess('checkbox')
        callback()
        self.elementsStopModificationProcess()

    def update_saved_capture(self):
        ts = self.tools_settings
        if ts.get("savecaptureframe", False):
            if self.capture_region_rect:
                x = self.capture_region_rect.left()
                y = self.capture_region_rect.top()
                w = self.capture_region_rect.width()
                h = self.capture_region_rect.height()

            else:
                rect = build_valid_rect(self.input_POINT1, self.input_POINT2)
                x = rect.left()
                y = rect.top()
                w = rect.width()
                h = rect.height()
            ts.update({'capture_frame': (x, y, w, h)})

    def mouseMoveEvent(self, event):
        if self.tools_window:
            select_window = self.tools_window.select_window
            if select_window and select_window.isVisible():
                select_window.hide()

        drawing_outside_capture_widget_allowed = \
                        not self.drag_inside_capture_zone \
                        and self.capture_region_rect \
                        and not self.capture_region_widget_enabled

        if event.buttons() == Qt.NoButton:
            # определяем только тут, иначе при быстрых перемещениях мышки при зажатой кнопке мыши
            # возможна потеря удержания - как будто бы если кнопка мыши была отпущена
            self.get_region_info()

        elif event.buttons() == Qt.LeftButton:
            if not self.is_rect_defined:
                # для первичного задания области захвата
                event_pos = self.elementsMapToCanvas(event.pos())
                if not self.is_point_set(self.input_POINT1):
                    self.user_input_started = True
                    self.input_POINT1 = event_pos
                else:
                    modifiers = event.modifiers()
                    if modifiers == Qt.NoModifier:
                        self.input_POINT2 = event_pos
                    else:
                        delta = self.input_POINT1 - event_pos
                        if modifiers & Qt.ControlModifier:
                            delta.setX(delta.x() // 10 * 10 + 1)
                            delta.setY(delta.y() // 10 * 10 + 1)
                        if modifiers & Qt.ShiftModifier:
                            delta = self.equilateral_delta(delta)
                        self.input_POINT2 = self.input_POINT1 - delta
                    self.update_saved_capture()

            elif self.undermouse_region_info and not self.drag_inside_capture_zone \
                                                         and self.capture_region_widget_enabled:
                # для изменения области захвата после первичного задания
                self.is_rect_being_redefined = True
                delta = self.elementsMapToCanvas(QPointF(event.pos())) - self.start_cursor_position
                set_func_attr = self.undermouse_region_info.setter
                data_id = self.undermouse_region_info.coords
                get_func_attr = self.undermouse_region_info.getter
                get_func = getattr(self.capture_region_rect, get_func_attr)
                set_func = getattr(self.capture_region_rect, set_func_attr)
                if self.capture_redefine_start_value is None:
                    self.capture_redefine_start_value = get_func()
                if data_id == "x":
                    set_func(self.capture_redefine_start_value + delta.x())
                if data_id == "y":
                    set_func(self.capture_redefine_start_value + delta.y())
                if data_id == "xy":
                    set_func(self.capture_redefine_start_value + delta)

                # необходимо для нормальной работы
                self.capture_region_rect = build_valid_rectF(
                    self.capture_region_rect.topLeft(), self.capture_region_rect.bottomRight()
                )

                self.input_POINT1 = self.capture_region_rect.topLeft()
                self.input_POINT2 = self.capture_region_rect.bottomRight()

                self.update_saved_capture()

            elif (self.drag_inside_capture_zone and self.capture_region_rect) or \
                                                    drawing_outside_capture_widget_allowed:
                # для добавления элементов поверх скриншота
                self.elementsMouseMoveEvent(event)

        elif event.buttons() == Qt.RightButton:
            pass

        elif event.buttons() == Qt.MiddleButton:
            delta = QPoint(event.pos() - self.ocp)
            self.canvas_origin = self.start_canvas_origin + delta
            self.autopos_tools_window()
            self.update_selection_bouding_box()

        if event.buttons() == Qt.LeftButton:
            if any((self.translation_ongoing, self.rotation_ongoing, self.scaling_ongoing)):
                self.setCursor(self.define_transform_tool_cursor())
            elif not self.is_rect_being_redefined:
                self.setCursor(self.get_custom_cross_cursor())

        self.update()
        self.update_tools_window()
        # super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.start_canvas_origin = QPointF(self.canvas_origin)
            self.ocp = event.pos()
            return

        starting_drawing_outside_allowed = self.capture_region_rect \
                                                and not self.capture_region_widget_enabled

        if event.button() == Qt.LeftButton:
            self.start_cursor_position = self.elementsMapToCanvas(QPointF(event.pos()))
            self.capture_redefine_start_value = None
            self.get_region_info()
            if self.undermouse_region_info is None:
                self.drag_inside_capture_zone = True
                if self.capture_region_rect:
                    self.elementsMousePressEvent(event)
            else:
                self.drag_inside_capture_zone = False
                if starting_drawing_outside_allowed:
                    self.elementsMousePressEvent(event)
        if event.button() == Qt.MidButton and self.tools_window:
            self.tools_window.size_slider.value = 0.5
            self.tools_window.on_parameters_changed()
            self.tools_window.update()

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.drag_inside_capture_zone:
                self.drag_inside_capture_zone = False
                if self.is_rect_defined:
                    self.elementsMouseReleaseEvent(event)
            if self.user_input_started:
                if not self.is_input_points_set():
                    # это должно помочь от крашей
                    self.user_input_started = False
                    self.input_POINT1 = None
                    self.input_POINT2 = None
                    return
                self.is_rect_defined = True
                self.capture_region_rect = build_valid_rectF(self.input_POINT1, self.input_POINT2)
                self.is_rect_being_redefined = False
            self.get_region_info() # здесь только для установки курсора

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

    def get_center_position_and_screen_rect(self):
        if False:
            # не подходит в системе с двумя пониторами,
            # потому что центрируется в середине пространства, формируемоего двумя мониторами
            return QPointF(
                self.frameGeometry().width()/2,
                self.frameGeometry().height()/2
            )
        else:
            desktop = QDesktopWidget()
            screen = desktop.screenNumber(QCursor().pos())
            screen_rect = desktop.screenGeometry(screen=screen)
            return screen_rect.center(), screen_rect

    def wheelEvent(self, event):
        delta_value = event.angleDelta().y()

        scroll_value = event.angleDelta().y()/240
        ctrl = event.modifiers() & Qt.ControlModifier
        shift = event.modifiers() & Qt.ShiftModifier
        alt = event.modifiers() & Qt.AltModifier
        no_mod = event.modifiers() == Qt.NoModifier

        stamp_size_change_activated = event.buttons() == Qt.RightButton and self.current_tool == ToolID.picture

        if ctrl and self.capture_region_rect is None:
            self.change_magnifier_size(delta_value)
        elif stamp_size_change_activated:
            self.current_picture_angle += delta_value/10
            self.cancel_context_menu = True
        else:
            self.elementsDoScaleCanvas(scroll_value, ctrl, shift, no_mod)
            self.autopos_tools_window()
        self.update()

    def get_region_info(self):
        self.define_regions_rects_and_set_cursor()
        self.update()

    def slice_background_menu(self):
        menu = QMenu()

        spinboxes = (
            ('Количество по вертикали', 'SLICE_ROWS'),
            ('Количество по горизонтали', 'SLICE_COLS'),
        )

        def callback(sb, attr):
            setattr(self.Globals, attr, sb.value())

        for title, attr in spinboxes:
            wa = QWidgetAction(menu)
            sb = QSpinBox()
            sb.setToolTip(title)

            sb.setValue(getattr(self.Globals, attr))
            sb.valueChanged.connect(partial(callback, sb, attr))
            wa.setDefaultWidget(sb)
            menu.addAction(wa)

        menu.addSeparator()
        do_action = menu.addAction('Нарезать')
        cancel_action = menu.addAction('Отмена')

        action = menu.exec_(QCursor().pos())
        if action == None:
            pass
        elif action == do_action:
            self.elementsSliceBackgroundsIntoPieces()
        elif action == cancel_action:
            pass

    def toggle_dark_pictures(self):
        self.dark_pictures = not self.dark_pictures
        self.update()

    def contextMenuEvent(self, event):
        if self.cancel_context_menu:
            self.cancel_context_menu = False
            return

        def toggle_boolean_var_generic(obj, attr_name):
            setattr(obj, attr_name, not getattr(obj, attr_name))
            self.update()

        contextMenu = QMenu()
        contextMenu.setStyleSheet(self.context_menu_stylesheet)

        def add_item(*args):
            return contextMenu.addAction(*args)

        reset_image_frame = None
        set_image_frame = None
        sel_elem = self.active_element
        if sel_elem and sel_elem.type == ToolID.picture:
            if sel_elem.backup_pixmap is not None:
                reset_image_frame = add_item("Отменить обрезку выделенного изображения")
            set_image_frame = add_item("Обрезать выделенное изображение")
            contextMenu.addSeparator()

        capture_is_set = self.capture_region_rect is not None

        render_elements_to_background = add_item("Нарисовать содержимое на фоне и удалить содержимое")
        render_elements_to_background.setEnabled(capture_is_set)

        slice_background = add_item("Нарезать фон на куски")

        activate_multifraing_tool = add_item(Globals.icon_multiframing, "Активировать инструмент мультикадрирования")
        activate_multifraing_tool.setEnabled(capture_is_set)

        reshot = add_item(Globals.icon_refresh, "Переснять скриншот")

        autocollage = add_item("Автоколлаж")
        autocollage.setEnabled(capture_is_set)

        fit_images_to_size = add_item("Подогнать все картинки по размеру под одну")
        fit_images_to_size.setEnabled(capture_is_set)

        get_toolwindow_in_view = add_item("Подтянуть панель инструментов")
        get_toolwindow_in_view.setEnabled(capture_is_set)

        autocapturezone = add_item("Задать область захвата по содержимому")

        reset_capture = add_item("Сбросить область захвата")
        reset_capture.setEnabled(capture_is_set)

        contextMenu.addSeparator()

        reset_panzoom = add_item("Сбросить смещение и зум")
        reset_pan = add_item("Сбросить только смещение")
        reset_zoom = add_item("Сбросить только зум")

        contextMenu.addSeparator()

        sub_menu, sub_menu_handler = self.selection_filter_menu(main_menu=contextMenu)
        sub_menu.setTitle(sub_menu.title())
        contextMenu.addMenu(sub_menu)

        contextMenu.addSeparator() ###############################################################

        open_project = add_item("Открыть проект...")
        save_project = add_item("Сохранить проект")
        save_project.setEnabled(capture_is_set)

        contextMenu.addSeparator()

        if Globals.images_in_memory:
            count = len(Globals.images_in_memory)
            finish_save_to_memory_mode = add_item(f"Разложить на холсте все изображения из лукошка ({count})")
        else:
            finish_save_to_memory_mode = None

        checkboxes = (
            ("Сохранить результат в лукошко", Globals.save_to_memory_mode, self.elementsStartSaveToMemoryMode),
            ("Виджет области захвата", self.capture_region_widget_enabled, partial(toggle_boolean_var_generic, self, 'capture_region_widget_enabled')),
            ("Фон", self.show_background, partial(toggle_boolean_var_generic, self, 'show_background')),
            ("Затемнять после отрисовки пометок", self.dark_pictures, self.toggle_dark_pictures),
            ("Закрывать редактор после нажатия кнопки «Готово»", Globals.close_editor_on_done, partial(toggle_boolean_var_generic, Globals, 'close_editor_on_done')),
            ("Показывать дебаг-отрисовку для виджета трансформации", self.canvas_debug_transform_widget, partial(toggle_boolean_var_generic, self, 'canvas_debug_transform_widget')),
            ("Антиальясинг и сглаживание пиксмапов", Globals.ANTIALIASING_AND_SMOOTH_PIXMAP_TRANSFORM, partial(toggle_boolean_var_generic, Globals, 'ANTIALIASING_AND_SMOOTH_PIXMAP_TRANSFORM')),
            ("Pixmap-прокси для пометок типа «Текст»", Globals.USE_PIXMAP_PROXY_FOR_TEXT_ELEMENTS, partial(toggle_boolean_var_generic, Globals, 'USE_PIXMAP_PROXY_FOR_TEXT_ELEMENTS')),
            ("DEBUG", Globals.DEBUG, partial(toggle_boolean_var_generic, Globals, 'DEBUG')),
        )

        for title, value, callback in checkboxes:
            wa = QWidgetAction(contextMenu)
            chb = QCheckBox(title)
            chb.setStyleSheet(self.context_menu_stylesheet)
            chb.setChecked(value)
            chb.stateChanged.connect(callback)
            wa.setDefaultWidget(chb)
            contextMenu.addAction(wa)

        contextMenu.addSeparator() ###############################################################

        minimize = add_item("Свернуть на панель задач")
        cancel = add_item(Globals.icon_cancel, "Отменить создание скриншота")
        halt = add_item(Globals.icon_halt, "Отменить создание скриншота и вырубить приложение")

        action = contextMenu.exec_(self.mapToGlobal(event.pos()))
        if action == None:
            pass
        elif sub_menu_handler(action):
            pass
        elif action == save_project:
            self.save_project()
        elif action == slice_background:
            self.slice_background_menu()
        elif action == reset_panzoom:
            self.elementsResetPanZoom()
        elif action == reset_pan:
            self.elementsResetPanZoom(reset_zoom=False)
        elif action == reset_zoom:
            self.elementsResetPanZoom(reset_pan=False)
        elif action == open_project:
            self.open_project()
        elif action == fit_images_to_size:
            self.elementsFitImagesToSize()
        elif action == render_elements_to_background:
            self.elementsDoRenderToBackground()
        elif action == autocapturezone:
            self.elementsSetCaptureFromContent()
            self.update()
        elif action == autocollage:
            self.elementsAutoCollagePictures()
            self.update()
        elif action == halt:
            sys.exit()
        elif action == reset_image_frame:
            self.elementsFramePicture()
            self.update()
        elif action == set_image_frame:
            if sel_elem.backup_pixmap is None:
                pixmap = sel_elem.pixmap
            else:
                pixmap = sel_elem.backup_pixmap
            self.show_view_window(lambda: pixmap, _type="edit", data=sel_elem.frame_info)
        elif action == finish_save_to_memory_mode:
            self.elementsFinishSaveToMemoryMode()
        elif action == get_toolwindow_in_view:
            tw = self.tools_window
            if tw:
                tw.auto_positioning = False
                tw.move(self.mapFromGlobal(QCursor().pos()))
        elif action == reset_capture:
            self.elementsResetCapture()
        elif action == minimize:
            self.showMinimized()
        elif action == activate_multifraing_tool:
            if self.tools_window:
                self.tools_window.set_current_tool(ToolID.multiframing)
        elif action == cancel:
            self.close_this(force_close=True)
        elif action == reshot:
            self.hide()
            if self.tools_window:
                self.tools_window.hide()
            self.source_pixels = make_screenshot_pyqt()
            self.elementsCreateBackgroundPictures(self.CreateBackgroundOption.Reshoot)
            self.elementsUpdateDependentElementsAfterReshot()
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

        if not self.capture_region_widget_enabled:
            self.setCursor(self.elementsSetCursorShapeInsideCaptureZone())
            return

        if not self.capture_region_rect:
            self.setCursor(self.elementsSetCursorShapeInsideCaptureZone())
            return

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
            5: self.elementsSetCursorShapeInsideCaptureZone(),
            # 5: QCursor(Qt.CrossCursor),
            6: QCursor(Qt.SizeHorCursor),
            7: QCursor(Qt.SizeBDiagCursor),
            8: QCursor(Qt.SizeVerCursor),
            9: QCursor(Qt.SizeFDiagCursor)
        }

        crr = self.elementsMapToViewportRectF(self.capture_region_rect)
        amr = self._all_monitors_rect
        regions = {
            1: QRectF(QPointF(0, 0), crr.topLeft()),
            2: QRectF(QPointF(crr.left(), 0), crr.topRight()),
            3: QRectF(QPointF(crr.right(), 0), QPointF(amr.right(), crr.top())),
            4: QRectF(QPointF(0, crr.top()), crr.bottomLeft()),
            5: crr,
            6: QRectF(crr.topRight(), QPointF(amr.right(), crr.bottom())),
            7: QRectF(QPointF(0, crr.bottom()), QPointF(crr.left(), amr.bottom())),
            8: QRectF(crr.bottomLeft(), QPointF(crr.right(), amr.bottom())),
            9: QRectF(crr.bottomRight(), amr.bottomRight())
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

    def save_tools_settings(self):
        SettingsJson().set_data("TOOLS_SETTINGS", self.tools_settings)

    def close_this(self, save_settings=True, force_close=False):
        # сохранение настроек тулз
        if save_settings:
            self.save_tools_settings()
        if Globals.close_editor_on_done or force_close:
            if self.tools_window:
                self.tools_window.update_timer.stop()
                self.tools_window.hide()
            self.close()
        else:
            if self.tools_window:
                self.tools_window.done_button.setEnabled(False)

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
        app = QApplication.instance()
        app.setQuitOnLastWindowClosed(not Globals.save_to_memory_mode)
        self.close_this()
        app.processEvents()
        self.save_screenshot()
        if not Globals.close_editor_on_done:
            if self.tools_window:
                self.tools_window.done_button.setEnabled(True)

    def save_current_editing_handler(self):
        filepath = self.save_screenshot(restart=False)
        msg_text = f'Файл сохранён и доступен по этому пути:\n{filepath}'
        self.show_notify_dialog(msg_text)

    def copy_magnifier_color_to_clipboard(self):
        color = self.color_at_pixel
        _hex = color.name()
        _r = color.red()
        _g = color.green()
        _b = color.blue()
        _rgb = f"rgb({_r}, {_g}, {_b})"
        color_repr = f"{_hex} {_rgb}"
        self.colors_values_copied.append((color, color_repr))
        color_reprs = [t[1] for t in self.colors_values_copied]
        self.set_clipboard("\n".join(color_reprs))
        self.update()

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            # сюда попадём только когда отпускается клавиша,
            # во вне условия будет срабатывать постоянно пока зажата клавиша
            if not (self.translation_ongoing or self.rotation_ongoing or self.scaling_ongoing):
                # если не сделать эту проверку, то приложение
                # будет крашится при отпускании клавиш-модификаторов
                # во время переноса, вращения и масштабирования

                # по идее тут ещё надо проверять на клавиши вверх, вниз, влево и вправо,
                # чтобы точно быть уверенным в правильности вызова
                arrow_keys = [Qt.Key_Up, Qt.Key_Down, Qt.Key_Right, Qt.Key_Left]
                if event.key() in arrow_keys:
                    self.elementsStopModificationProcess()

    def keyPressEvent(self, event):
        key = event.key()
        if self.elementsIsTextFieldInputEvent(event):
            self.elementsTextFieldInputEvent(event)
            return
        arrow_keys = [Qt.Key_Up, Qt.Key_Down, Qt.Key_Right, Qt.Key_Left]
        if key in arrow_keys:
            if not self.is_rect_defined:
                self.move_cursor_by_arrow_keys(key)
            if (not self.is_rect_defined) and self.user_input_started:
                self.emit_mouse_event("move")
            if self.is_rect_defined:
                self.elementsMoveElement(event)
        # Qt.Key_Return - основная клавиатура
        # Qt.Key_Enter - цифровая клавиатура
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
            if self.start_translation_pos or self.translation_ongoing:
                self.canvas_CANCEL_selected_elements_TRANSLATION()
                return
            elif self.rotation_ongoing:
                self.canvas_CANCEL_selected_elements_ROTATION()
                return
            elif self.scaling_ongoing:
                self.canvas_CANCEL_selected_elements_SCALING()
                return
            elif self.elementsDeactivateTextField():
                return
            elif self.tools_window:
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
            if self.capture_region_rect is None:
                self.copy_magnifier_color_to_clipboard()
            elif self.selected_items:
                cb = QApplication.clipboard()
                cb.clear(mode=cb.Clipboard)
                cb.setText(Globals.COPY_SELECTED_CANVAS_ITEMS_STR, mode=cb.Clipboard)
        if check_scancode_for(event, "V") and event.modifiers() & Qt.ControlModifier:
            app = QApplication.instance()
            cb = app.clipboard()
            text = cb.text()
            mdata = cb.mimeData()
            if text and text == Globals.COPY_SELECTED_CANVAS_ITEMS_STR:
                self.elementsPasteSelectedItems()
            else:
                self.elementsPasteImageFromBuffer(event)
        if check_scancode_for(event, "Z"):
            mods = event.modifiers()
            ctrl = mods & Qt.ControlModifier
            shift = mods & Qt.ShiftModifier
              # - Ctrl+Z - шаг назад, Ctrl+Shift+Z - шаг вперёд
            if self.tools_window:
                if ctrl and shift:
                    self.tools_window.on_forwards_clicked()
                elif ctrl and not shift:
                    self.tools_window.on_backwars_clicked()
                self.update()
                self.tools_window.update()
        if key == Qt.Key_Delete:
            if self.selected_items:
                self.elementsRemoveSelectedElements()
                if self.tools_window:
                    self.tools_window.forwards_backwards_update()
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
        if check_scancode_for(event, "P"):
            if self.capture_region_rect is not None:
                self.show_view_window(self.elementsRenderFinal)
        if check_scancode_for(event, "A") and event.modifiers() & Qt.ControlModifier:
            self.elementsSelectDeselectAll()
        if check_scancode_for(event, "F"):
            if event.modifiers() & Qt.ControlModifier:
                self.elementsFitCaptureZoneOnScreen()
            else:
                self.elementsFitSelectedItemsOnScreen()
        if key == (Qt.Key_F2):
            self.animated_debug_drawing()
        if key == (Qt.Key_F3):
            self.show_notify_dialog('Test text.................... !')








class WinEventFilter(QAbstractNativeEventFilter):
    def __init__(self, kb):
        self.keybinder = kb
        super().__init__()

    def nativeEventFilter(self, eventType, message):
        ret = self.keybinder.handler(eventType, message)
        return ret, 0

def is_settings_window_visible():
    value = False
    if hasattr(SettingsWindow, "instance"):
        if SettingsWindow.instance:
            value = SettingsWindow.instance.isVisible()
    return value

def global_hotkey_handler(request):
    if (Globals.handle_global_hotkeys or Globals.save_to_memory_mode):
                                                        # \ and not is_settings_window_visible():
        if Globals.BLOCK_KEYSEQ_HANDLING_AFTER_FIRST_CALL:
            if not Globals.save_to_memory_mode:
                Globals.handle_global_hotkeys = False
        invoke_screenshot_editor(request_type=request)

def special_hotkey_handler(request):
    if is_settings_window_visible():
        widget = QApplication.focusWidget()
        if widget and isinstance(widget, KeySequenceEdit):
            widget.keyPressEvent_handler(QKeyEvent(
                QEvent.KeyPress,
                Qt.Key_Print,
                QApplication.queryKeyboardModifiers(),
            ))
            widget.keyReleaseEvent_handler(QKeyEvent(
                QEvent.KeyRelease,
                Qt.Key_Print,
                QApplication.queryKeyboardModifiers(),
            ))
    else:
        global_hotkey_handler(request)

def init_global_hotkeys_base():
    keybinder.init()
    win_event_filter = WinEventFilter(keybinder)
    event_dispatcher = QAbstractEventDispatcher.instance()
    event_dispatcher.installNativeEventFilter(win_event_filter)
    # если не сохранить куда-нибудь ссылки на event_dispatcher и win_event_filter,
    # то не будет работать вообще и придётся засовыать код всей функции в main
    Globals.event_dispatcher = event_dispatcher
    Globals.win_event_filter = win_event_filter

def register_settings_window_global_hotkeys():
    # print('register_settings_window_global_hotkeys', flush=True)
    unregister_global_hotkeys()

    modifiers = [
                    "", # для случая, когда Print Screen нажата без клавиш-модификаторов.

                    # Все последующие модификаторы нужны, чтобы отлавливать клавишу Print Screen
                    # когда она нажата вместе с этими же модификаторами.
                    # Отслеживать её здесь пришлось потому, что ОС не даёт событию этой клавиши
                    # дойти до программы. И для этого пришлось бы использовать функцию API Windows.
                    # Мне лень лезть в API каждый раз, поэтому я решил задачу вот таким перебором
                    # разных модификаторов.
                    "Ctrl+",
                    "Ctrl+Shift+",
                    "Ctrl+Alt+",
                    "Alt+",
                    "Alt+Shift+",
                    "Shift+",
                ]
    for modifier in modifiers:
        keyseq = f'{modifier}Print'
        if keybinder.register_hotkey(0,
                keyseq,
                lambda: special_hotkey_handler(RequestType.Fragment)):
            Globals.registred_key_seqs.append(keyseq)

def register_user_global_hotkeys():
    # print('register_user_global_hotkeys', flush=True)
    unregister_global_hotkeys()

    if Globals.USE_PRINT_KEY:
        if keybinder.register_hotkey(0,
                "Print",
                lambda: special_hotkey_handler(RequestType.Fragment)):
            Globals.registred_key_seqs.append("Print")

    if keybinder.register_hotkey(0,
            Globals.FRAGMENT_KEYSEQ,
            lambda: global_hotkey_handler(RequestType.Fragment)):
        Globals.registred_key_seqs.append(Globals.FRAGMENT_KEYSEQ)
    if keybinder.register_hotkey(0,
            Globals.FULLSCREEN_KEYSEQ,
            lambda: global_hotkey_handler(RequestType.Fullscreen)):
        Globals.registred_key_seqs.append(Globals.FULLSCREEN_KEYSEQ)
    if keybinder.register_hotkey(0,
            Globals.QUICKFULLSCREEN_KEYSEQ,
            lambda: global_hotkey_handler(RequestType.QuickFullscreen)):
        Globals.registred_key_seqs.append(Globals.QUICKFULLSCREEN_KEYSEQ)

def unregister_global_hotkeys():
    try:
        for key_seq in Globals.registred_key_seqs:
            keybinder.unregister_hotkey(0, key_seq)
    except:
        pass
    Globals.registred_key_seqs.clear()

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
        if reason == QSystemTrayIcon.Trigger: # если кликнул левой - то делаем скриншот фрагмента
            invoke_screenshot_editor(request_type=RequestType.Fragment)
        if reason == QSystemTrayIcon.Context: # если правой - вызываем окно-меню
            if NotificationOrMenu.instance:
                NotificationOrMenu.instance.show_menu()
            else:
                NotificationOrMenu(menu=True).show_menu()
    sti.activated.connect(on_trayicon_activated)
    sti.show()
    return sti

def close_all_windows():
    if NotificationOrMenu.instance:
        NotificationOrMenu.instance.close()
    if SettingsWindow.instance:
        SettingsWindow.instance.close()

def hide_all_windows():
    if NotificationOrMenu.instance:
        NotificationOrMenu.instance.hide()
    if SettingsWindow.instance:
        SettingsWindow.instance.hide()

def invoke_screenshot_editor(request_type=None, filepaths=None):
    if request_type is None:
        raise Exception("Unknown request type")
    # если было открыто окно-меню около трея - прячем его
    # hide_all_windows()

    metadata = generate_metainfo()
    datetime_stamp = generate_datetime_stamp()
    # started_time = time.time()

    CanvasEditor.screenshot_cursor_position = QCursor().pos()
    cursor_filepath = os.path.join(os.path.dirname(__file__), 'resources', 'cursor.png')
    CanvasEditor.cursor_pixmap = QPixmap(cursor_filepath).scaled(25, 25, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    screenshot_image = make_screenshot_pyqt()
    if request_type == RequestType.Fragment:
        # print("^^^^^^", time.time() - started_time)
        if Globals.DEBUG and Globals.DEBUG_ELEMENTS and not Globals.DEBUG_ELEMENTS_COLLAGE:
            Globals._canvas_editor = CanvasEditor(screenshot_image, metadata, datetime_stamp)
            Globals._canvas_editor.set_saved_capture_frame()
            Globals._canvas_editor.show()
            Globals._canvas_editor.request_elements_debug_mode()
        elif Globals.DEBUG and Globals.DEBUG_ELEMENTS_COLLAGE:
            path = SettingsJson().get_data("SCREENSHOT_FOLDER_PATH")
            if not path:
                path = ""
            filepaths = get_filepaths_dialog(path=path)
            Globals._canvas_editor = CanvasEditor(screenshot_image, metadata, datetime_stamp)
            Globals._canvas_editor.request_images_editor_mode(filepaths)
            Globals._canvas_editor.show()
        else:
            Globals._canvas_editor = CanvasEditor(screenshot_image, metadata, datetime_stamp)
            Globals._canvas_editor.set_saved_capture_frame()
            Globals._canvas_editor.show()
        # чтобы activateWindow точно сработал и взял фокус ввода
        QApplication.instance().processEvents()
        Globals._canvas_editor.activateWindow()

    if request_type == RequestType.Fullscreen:
        Globals._canvas_editor = CanvasEditor(screenshot_image, metadata, datetime_stamp)
        Globals._canvas_editor.request_fullscreen_capture_region()
        Globals._canvas_editor.show()
        # чтобы activateWindow точно сработал и взял фокус ввода
        QApplication.instance().processEvents()
        Globals._canvas_editor.activateWindow()

    if request_type == RequestType.Editor:
        if not filepaths:
            path = SettingsJson().get_data("SCREENSHOT_FOLDER_PATH")
            if not path:
                path = ""
            filepaths = get_filepaths_dialog(path=path)
        if filepaths:
            Globals._canvas_editor = CanvasEditor(screenshot_image, metadata, datetime_stamp)
            Globals._canvas_editor.request_images_editor_mode(filepaths)
            Globals._canvas_editor.show()
            # чтобы activateWindow точно сработал и взял фокус ввода
            QApplication.instance().processEvents()
            Globals._canvas_editor.activateWindow()



    if request_type == RequestType.QuickFullscreen:
        CanvasEditor.save_screenshot(None, grabbed_image=screenshot_image, metadata=metadata)
        if not Globals.save_to_memory_mode:
            app = QApplication.instance()
            app.exit()

def show_crash_log(alert=True):
    path = get_crashlog_filepath()
    if os.path.exists(path):
        open_link_in_browser(path)
    elif alert:
        QMessageBox.critical(None, "Сообщение",
                "Файла не нашлось, видимо программа ещё не крашилась.")

def get_crashlog_filepath():
    if Globals.DEBUG:
        root = os.path.dirname(__file__)
    else:
        root = os.path.expanduser("~")
    path = os.path.normpath(os.path.join(root, "oxxxy_crash.log"))
    return path

def update_sys_tray_icon(value, reset=False):
    app = QApplication.instance()
    stray_icon = app.property("stray_icon")
    if stray_icon:
        pixmap = QPixmap(Globals.ICON_PATH)
        if not reset:
            painter = QPainter()
            painter.begin(pixmap)
            font = painter.font()
            divider = 1.4
            height = int(pixmap.height()/divider)
            font.setPixelSize(height)
            font.setWeight(1900)
            painter.setFont(font)
            value_string = f'{value}'
            text_rect = painter.boundingRect(QRect(), Qt.AlignLeft, value_string)
            text_rect.moveTopRight(QPoint(pixmap.width(), 0))
            painter.setPen(Qt.NoPen)
            painter.fillRect(text_rect, Qt.black)
            painter.setPen(QPen(Qt.white))
            painter.drawText(pixmap.rect(), Qt.AlignRight | Qt.AlignTop, value_string)
            painter.end()
        icon = QIcon(pixmap)
        stray_icon.setIcon(icon)

def excepthook(exc_type, exc_value, exc_tb):
    # пишем инфу о краше
    if isinstance(exc_tb, str):
        traceback_lines = exc_tb
    else:
        traceback_lines = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    locale.setlocale(locale.LC_ALL, "russian")
    datetime_string = time.strftime("%A, %d %B %Y %X").capitalize()
    dt = "{0} {1} {0}".format(" "*15, datetime_string)
    dt_framed = "{0}\n{1}\n{0}\n".format("-"*len(dt), dt)
    with open(get_crashlog_filepath(), "a+", encoding="utf8") as crash_log:
        crash_log.write("\n"*10)
        crash_log.write(dt_framed)
        crash_log.write("\n")
        crash_log.write(traceback_lines)
    print("*** excepthook info ***")
    print(traceback_lines)
    app = QApplication.instance()
    if app:
        stray_icon = app.property("stray_icon")
        if stray_icon:
            stray_icon.hide()
    if (not Globals.DEBUG) and (not Globals.RUN_ONCE):
        _restart_app(aftercrash=True)
    sys.exit()

def get_filepaths_dialog(path=""):
    dialog = QFileDialog()
    dialog.setFileMode(QFileDialog.ExistingFiles)
    title = ""
    filter_data = "All files (*.*)"
    data = dialog.getOpenFileNames(None, title, path, filter_data)
    return data[0]

def exit_threads():
    # принудительно глушим все потоки, что ещё работают
    for thread in Globals.background_threads:
        thread.terminate()
        # нужно вызывать terminate вместо exit

def _restart_app(aftercrash=False):
    # Обязательный перезапуск после созданного скриншота или отмены!
    if aftercrash:
        subprocess.Popen([sys.executable, sys.argv[0], "-aftercrash"])
    else:
        subprocess.Popen([sys.executable, sys.argv[0]])

def read_settings_file():
    SettingsJson().init(Globals)
    SJ = SettingsJson()
    Globals.ENABLE_FLAT_EDITOR_UI = SJ.get_data("ENABLE_FLAT_EDITOR_UI")
    Globals.ENABLE_CBOR2 = SJ.get_data("ENABLE_CBOR2", Globals.ENABLE_CBOR2)
    SJ.set_reading_file_on_getting_value(False)
    Globals.USE_COLOR_PALETTE = SJ.get_data("USE_COLOR_PALETTE")

    Globals.USE_PRINT_KEY = SJ.get_data("USE_PRINT_KEY", Globals.USE_PRINT_KEY)
    Globals.FRAGMENT_KEYSEQ = SJ.get_data("FRAGMENT_KEYSEQ", Globals.DEFAULT_FRAGMENT_KEYSEQ)
    Globals.FULLSCREEN_KEYSEQ = SJ.get_data("FULLSCREEN_KEYSEQ", Globals.DEFAULT_FULLSCREEN_KEYSEQ)
    Globals.QUICKFULLSCREEN_KEYSEQ = SJ.get_data("QUICKFULLSCREEN_KEYSEQ",
                                                            Globals.DEFAULT_QUICKFULLSCREEN_KEYSEQ)
    SJ.set_reading_file_on_getting_value(True)





SettingsWindow.Globals = Globals
NotificationOrMenu.Globals = Globals
NotificationOrMenu.RequestType = RequestType
NotificationOrMenu.gl = type('global', (), {})
NotificationOrMenu.gl.invoke_screenshot_editor = invoke_screenshot_editor
NotificationOrMenu.gl._restart_app = _restart_app
NotificationOrMenu.gl.show_crash_log = show_crash_log
NotificationOrMenu.gl.get_crashlog_filepath = get_crashlog_filepath
NotifyDialog.Globals = Globals
QuitDialog.Globals = Globals

SettingsWindow.gf = type('global_functions', (), {})
SettingsWindow.gf.register_settings_window_global_hotkeys = register_settings_window_global_hotkeys
SettingsWindow.gf.register_user_global_hotkeys = register_user_global_hotkeys


ToolsWindow.Globals = Globals




def _main():

    os.chdir(os.path.dirname(__file__))
    sys.excepthook = excepthook

    if Globals.CRASH_SIMULATOR:
        1 / 0

    RERUN_ARG = '-rerun'
    if not Globals.DEBUG:
        if (RERUN_ARG not in sys.argv) and ("-aftercrash" not in sys.argv):
            subprocess.Popen([sys.executable, *sys.argv, RERUN_ARG])
            sys.exit()

    # разбор аргументов
    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs='?', default=None)
    # введения переменной this_filepath ниже
    parser.add_argument('-user_mode', help="", action="store_true")
    parser.add_argument('-notification', help="", action="store_true")
    parser.add_argument('-aftercrash', help="", action="store_true")
    parser.add_argument('-rerun', help="", action="store_true")
    args = parser.parse_args(sys.argv[1:])
    if args.path:
        path = args.path
    if args.user_mode:
        Globals.DEBUG = False
    if args.aftercrash:
        Globals.AFTERCRASH = True
    read_settings_file()

    app = QApplication(sys.argv)
    Globals.generate_icons()
    Globals.load_fonts()
    app.aboutToQuit.connect(exit_threads)
    # app.setAttribute(Qt.AA_DontShowIconsInMenus, True)
    # задание иконки для таскбара
    if os.name == 'nt':
        appid = 'sergei_krumas.oxxxy_screenshoter.client.1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
    Globals.ICON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "icon.png"))
    icon = QIcon(QPixmap(Globals.ICON_PATH))
    app.setProperty("keep_ref_to_icon", icon)
    app.setWindowIcon(icon)
    # tooltip effects
    app.setEffectEnabled(Qt.UI_AnimateTooltip, False)
    app.setEffectEnabled(Qt.UI_FadeTooltip, False)

    if Globals.AFTERCRASH:
        filepath = get_crashlog_filepath()
        show_crash_log(alert=False)
        msg0 = f"Информация сохранена в файл\n\t{filepath}"
        msg = f"Скриншотер Oxxxy упал.\n{msg0}\n\nПерезапустить Oxxxy?"
        ret = QMessageBox.question(None, 'Сбой',
            msg,
            QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            _restart_app()
        sys.exit(0)

    registred_hotkeys = False
    if args.notification:
        # notification mode
        notification = NotificationOrMenu(notification=True, filepath=args.path)
        notification.place_window()
    else:
        # editor mode
        if Globals.DEBUG or Globals.RUN_ONCE:
            if Globals.DEBUG_TRAY_MENU_WINDOW:
                NotificationOrMenu(menu=True).place_window()
            elif Globals.DEBUG_SETTINGS_WINDOW:
                init_global_hotkeys_base()
                sw = SettingsWindow()
                sw.show()
                sw.place_window()
            else:
                invoke_screenshot_editor(request_type=RequestType.Fragment)
            # invoke_screenshot_editor(request_type=RequestType.Fullscreen)
        else:
            registred_hotkeys = True
            init_global_hotkeys_base()
            register_user_global_hotkeys()
            stray_icon = show_system_tray(app, icon)
    # вход в петлю сообщений
    app.exec_()
    # после закрытия апликухи
    stray_icon = app.property("stray_icon")
    if stray_icon:
        stray_icon.hide()
    if registred_hotkeys:
        unregister_global_hotkeys()
    if not Globals.FULL_STOP:
        if not args.notification and not Globals.DEBUG and not Globals.RUN_ONCE:
            _restart_app()
    sys.exit(0)

def main():
    # try ... except needed for crash reports into the file
    try:
        _main()
    except Exception as e:
        excepthook(type(e), e, traceback.format_exc())

if __name__ == '__main__':
    main()
