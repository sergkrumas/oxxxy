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

from pyqtkeybind import keybinder

from PyQt5.QtWidgets import (QSystemTrayIcon, QWidget, QMessageBox, QMenu, QFileDialog,
    QHBoxLayout, QCheckBox, QVBoxLayout, QTextEdit, QGridLayout, QWidgetAction,
    QPushButton, QLabel, QApplication, QScrollArea, QDesktopWidget, QActionGroup, QSpinBox)
from PyQt5.QtCore import (pyqtSignal, QPoint, QPointF, pyqtSlot, QRect, QEvent,
    QTimer, Qt, QSize, QSizeF, QRectF, QThread, QAbstractNativeEventFilter,
    QAbstractEventDispatcher, QFile, QDataStream, QIODevice)
from PyQt5.QtGui import (QPainterPath, QColor, QKeyEvent, QMouseEvent, QBrush, QPixmap,
    QPaintEvent, QPainter, QWindow, QPolygon, QImage, QTransform, QPen, QLinearGradient,
    QIcon, QFont, QCursor, QPolygonF, QVector2D, QFontDatabase)

from image_viewer_lite import ViewerWindow
from key_seq_edit import KeySequenceEdit

from _utils import (convex_hull, check_scancode_for, SettingsJson,
     generate_metainfo, build_valid_rect, build_valid_rectF, dot,
     get_creation_date, copy_image_file_to_clipboard, get_nearest_point_on_rect,
     find_browser_exe_file, open_link_in_browser, open_in_google_chrome, save_meta_info,
     make_screenshot_pyqt, webRGBA, generate_gradient, draw_shadow, draw_cyberpunk,
     get_bounding_points, load_svg, is_webp_file_animated, apply_blur_effect,
     get_bounding_pointsF, generate_datetime_stamp)

from _sliders import (CustomSlider,)
from on_windows_startup import is_app_in_startup, add_to_startup, remove_from_startup
from elements import ElementsMixin, ToolID

class Globals():
    DEBUG = True
    DEBUG_SETTINGS_WINDOW = False
    DEBUG_TRAY_MENU_WINDOW = False
    DEBUG_ELEMENTS = False
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

    ANTIALIASING_AND_SMOOTH_PIXMAP_TRANSFORM = True

    DEFAULT_FRAGMENT_KEYSEQ = "Ctrl+Print"
    DEFAULT_FULLSCREEN_KEYSEQ = "Ctrl+Shift+Print"
    DEFAULT_QUICKFULLSCREEN_KEYSEQ = "Shift+Print"

    save_to_memory_mode = False
    images_in_memory = []

    dasPictureMagazin = []

    close_editor_on_done = True

    handle_global_hotkeys = True
    registred_key_seqs = []

    VERSION_INFO = "v0.93"
    AUTHOR_INFO = "by Sergei Krumas"

    background_threads = []

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
    edit_style_white = """QLineEdit {
        font-size: 17px;
        margin: 2px;
        color: white;
        font-weight: bold;
        text-align: center;
        background-color: transparent;
        border: 1px solid gray;
        border-radius: 5px;
    }
    QLineEdit:focus {
        border: 1px solid yellow;
        background-color: rgba(10, 10, 10, 100);
    }
    """
    info_label_style_settings = """
        font-size: 17px;
        margin: 2px;
        background: rgb(230, 230, 230);
        color: #303940;
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

    temp_v = 0

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
        v = self.temp_v
        color = QColor(48+v, 57+v, 64+v)
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
        distance = QVector2D(diff).length()
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
        msg = "Выберите папку, в которую будут складываться скриншоты"
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
            return f" Текущий путь: {Globals.SCREENSHOT_FOLDER_PATH}"
        else:
            return "  Путь не задан!"

    def show(self):
        # register_settings_window_global_hotkeys()
        super().show()

    def hide(self):
        register_user_global_hotkeys()
        super().hide()

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

        label_1 = QLabel("<b>➜ МЕСТО ДЛЯ СОХРАНЕНИЯ СКРИНШОТОВ</b>")
        label_1.setStyleSheet(self.info_label_style_settings)
        label_1_path = QLabel(SettingsWindow.get_path_for_label())
        label_1_path.setStyleSheet(STYLE)
        self.label_1_path = label_1_path
        path_change_btn = QPushButton("Изменить путь к хранилищу")
        path_change_btn.setObjectName("bottom")
        path_change_btn.setStyleSheet(self.button_style)
        path_change_btn.setCursor(Qt.PointingHandCursor)
        path_change_btn.clicked.connect(SettingsWindow.set_screenshot_folder_path_dialog)
        layout_1 = QVBoxLayout()
        layout_1.addWidget(label_1_path)
        layout_1.addWidget(path_change_btn)

        label_2 = QLabel("<b>➜ КОМБИНАЦИИ КЛАВИШ</b>")
        label_2.setStyleSheet(self.info_label_style_settings)
        layout_2 = QVBoxLayout()
        keyseq_data = [
            ("скриншот с захватом фрагмента экрана", "FRAGMENT_KEYSEQ"),
            ("скриншот с захватом всего экрана", "FULLSCREEN_KEYSEQ"),
            ("быстрый скриншот всего экрана", "QUICKFULLSCREEN_KEYSEQ"),
        ]
        def on_changed_callback(attr_name, value):
            setattr(Globals, attr_name, value)
            SettingsJson().set_data(attr_name, value)
        for text, attr_name in keyseq_data:
            _label = QLabel("<center>%s</center>" % text)
            _label.setStyleSheet(self.info_label_style_white)
            _label.setWordWrap(True)
            current_keyseq = getattr(Globals, attr_name)
            default_keyseq = getattr(Globals, f'DEFAULT_{attr_name}')
            _field = KeySequenceEdit(current_keyseq, default_keyseq,
                    partial(on_changed_callback, attr_name[:]),
                    register_settings_window_global_hotkeys,
                    register_user_global_hotkeys
            )
            _field.setStyleSheet(self.edit_style_white)
            _field.setFixedWidth(200)
            layout_2.addWidget(_label)
            layout_2.addWidget(_field, alignment=Qt.AlignCenter)
        #######################################################################
        chbx_21 = QCheckBox("Также вызывать скриншот фрагмента\n через клавишу Print Screen")
        chbx_21.setStyleSheet(self.settings_checkbox)
        chbx_21.setChecked(Globals.USE_PRINT_KEY)
        chbx_21.stateChanged.connect(lambda: self.handle_print_screen_for_fragment(chbx_21))
        layout_2.addWidget(chbx_21, alignment=Qt.AlignCenter)
        #######################################################################
        chbx_22 = QCheckBox(("Блокировать срабатывание комбинаций\n"
                                "клавиш после первого срабатывания\n"
                                "и до сохранения скриншота"))
        chbx_22.setStyleSheet(self.settings_checkbox)
        chbx_22.setChecked(Globals.BLOCK_KEYSEQ_HANDLING_AFTER_FIRST_CALL)
        chbx_22.stateChanged.connect(lambda: self.handle_block_option(chbx_22))
        layout_2.addWidget(chbx_22, alignment=Qt.AlignCenter)
        #######################################################################

        label_3 = QLabel("<b>➜ АВТОМАТИЧЕСКИЙ ЗАПУСК</b>")
        label_3.setStyleSheet(self.info_label_style_settings)
        chbx_3 = QCheckBox("Запускать Oxxxy при старте Windows")
        chbx_3.setStyleSheet(self.settings_checkbox)
        chbx_3.setChecked(is_app_in_startup(self.STARTUP_CONFIG[0]))
        chbx_3.stateChanged.connect(lambda: self.handle_windows_startup_chbx(chbx_3))
        layout_3 = QVBoxLayout()
        layout_3.setAlignment(Qt.AlignCenter)
        layout_3.addWidget(chbx_3)

        label_4 = QLabel("<b>➜ СЛАЙДЕР ЦВЕТА</b>")
        label_4.setStyleSheet(self.info_label_style_settings)
        chbx_4 = QCheckBox("Заменить на палитру цветов")
        chbx_4.setStyleSheet(self.settings_checkbox)
        use_color_palette = SettingsJson().get_data("USE_COLOR_PALETTE")
        chbx_4.setChecked(bool(use_color_palette))
        chbx_4.stateChanged.connect(lambda: self.handle_palette_chbx(chbx_4))
        layout_4 = QVBoxLayout()
        layout_4.setAlignment(Qt.AlignCenter)
        layout_4.addWidget(chbx_4)

        label_5 = QLabel("<b>➜ ОБЩИЙ ВИД ПАНЕЛИ ИНСТРУМЕНТОВ</b>")
        label_5.setStyleSheet(self.info_label_style_settings)
        chbx_5 = QCheckBox("Включить стиль FLAT")
        chbx_5.setStyleSheet(self.settings_checkbox)
        use_flat_ui = SettingsJson().get_data("ENABLE_FLAT_EDITOR_UI")
        chbx_5.setChecked(bool(use_flat_ui))
        chbx_5.stateChanged.connect(lambda: self.handle_ui_style_chbx(chbx_5))
        layout_5 = QVBoxLayout()
        layout_5.setAlignment(Qt.AlignCenter)
        layout_5.addWidget(chbx_5)

        label_6 = QLabel("<b>➜ ФОРМАТ СОХРАНЕНИЯ ПРОЕКТОВ</b>")
        label_6.setStyleSheet(self.info_label_style_settings)
        chbx_6 = QCheckBox("CBOR2 вместо JSON")
        chbx_6.setStyleSheet(self.settings_checkbox)
        use_cbor2 = SettingsJson().get_data("ENABLE_CBOR2")
        chbx_6.setChecked(bool(use_cbor2))
        chbx_6.stateChanged.connect(lambda: self.handle_cbor2_chbx(chbx_6))
        layout_6 = QVBoxLayout()
        layout_6.setAlignment(Qt.AlignCenter)
        layout_6.addWidget(chbx_6)


        # заголовок
        self.layout.addSpacing(self.PARTITION_SPACING)
        self.layout.addWidget(self.label, Qt.AlignLeft)
        self.layout.addSpacing(self.PARTITION_SPACING)

        # место для сохранения скриншотов
        self.layout.addWidget(label_1)
        self.layout.addLayout(layout_1)
        self.layout.addSpacing(self.PARTITION_SPACING)

        # автоматический запуск
        self.layout.addWidget(label_3)
        self.layout.addLayout(layout_3)
        self.layout.addSpacing(self.PARTITION_SPACING)

        # комбинации клавиш
        self.layout.addWidget(label_2)
        self.layout.addLayout(layout_2)
        self.layout.addSpacing(self.PARTITION_SPACING)

        # палитра вместо шкалы цвета
        self.layout.addWidget(label_4)
        self.layout.addLayout(layout_4)
        self.layout.addSpacing(self.PARTITION_SPACING)

        # палитра вместо шкалы цвета
        self.layout.addWidget(label_5)
        self.layout.addLayout(layout_5)
        self.layout.addSpacing(self.PARTITION_SPACING)

        # использование cbor
        self.layout.addWidget(label_6)
        self.layout.addLayout(layout_6)
        self.layout.addSpacing(self.PARTITION_SPACING)


        self.setLayout(self.layout)
        self.setMouseTracking(True)

    def handle_block_option(self, sender):
        SettingsJson().set_data("BLOCK_KEYSEQ_HANDLING_AFTER_FIRST_CALL", sender.isChecked())
        Globals.BLOCK_KEYSEQ_HANDLING_AFTER_FIRST_CALL = sender.isChecked()

    def handle_print_screen_for_fragment(self, sender):
        SettingsJson().set_data("USE_PRINT_KEY", sender.isChecked())
        Globals.USE_PRINT_KEY = sender.isChecked()

    def handle_palette_chbx(self, sender):
        SettingsJson().set_data("USE_COLOR_PALETTE", sender.isChecked())
        Globals.USE_COLOR_PALETTE = sender.isChecked()

    def handle_ui_style_chbx(self, sender):
        SettingsJson().set_data("ENABLE_FLAT_EDITOR_UI", sender.isChecked())
        Globals.ENABLE_FLAT_EDITOR_UI = sender.isChecked()

    def handle_cbor2_chbx(self, sender):
        SettingsJson().set_data("ENABLE_CBOR2", sender.isChecked())
        Globals.ENABLE_CBOR2 = sender.isChecked()

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

            label = "Скриншот готов!"
            filename = os.path.basename(self.filepath)
            label += f"\n\n{filename}"
            self.label = QLabel()
            self.label.setText(label)
            self.label.setStyleSheet(self.title_label_style)
            self.label.setFixedWidth(self.WIDTH - self.CLOSE_BUTTON_RADIUS)

            open_image_btn_gchr = QPushButton("Открыть в браузере")
            open_image_btn_gchr.setStyleSheet(self.button_style)
            open_image_btn_gchr.setFixedWidth(self.WIDTH)
            open_image_btn_gchr.clicked.connect(self.open_image)
            open_image_btn_gchr.setFocusPolicy(Qt.NoFocus)
            open_image_btn_gchr.setCursor(Qt.PointingHandCursor)

            open_image_btn = QPushButton("Открыть")
            open_image_btn.setStyleSheet(self.button_style)
            open_image_btn.setFixedWidth(self.WIDTH)
            open_image_btn.clicked.connect(self.open_image_shell)
            open_image_btn.setFocusPolicy(Qt.NoFocus)
            open_image_btn.setCursor(Qt.PointingHandCursor)

            open_folder_btn = QPushButton("Открыть папку")
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

            self.setAcceptDrops(True)

            self.label = QLabel()
            self.label.setText(f"Oxxxy {Globals.VERSION_INFO}")
            self.label.setStyleSheet(self.title_label_style)
            self.label.setFixedWidth(self.WIDTH - self.CLOSE_BUTTON_RADIUS)

            # первый раздел
            screenshot_fragment_btn = QPushButton("Фрагмент")
            screenshot_fullscreens_btn = QPushButton("Экран")
            # screenshot_remake_btn = QPushButton("Переделать прошлый\n(экспериментальная)")
            # второй раздел
            open_history_btn = QPushButton("История")
            open_recent_screenshot_btn = QPushButton("Показать\nпоследний")
            open_recent_screenshot_btn.clicked.connect(self.open_recent_screenshot)

            image_editor_btn = QPushButton('Редактор коллажей')

            open_settings_btn = QPushButton("Настройки")

            show_crashlog_btn = QPushButton("Открыть crash.log")
            self.show_crashlog_btn = show_crashlog_btn

            # в подвале окна
            quit_btn = QPushButton("Выход")
            show_source_code_btn = QPushButton("Доки\nна GitHub")
            show_source_code_btn.clicked.connect(self.show_source_code)
            object_name_list = [
                # open_settings_btn,
                show_crashlog_btn,
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
            self.thrid_row.addWidget(show_crashlog_btn)

            self.bottom_row = QHBoxLayout()
            self.bottom_row.addWidget(quit_btn)
            self.bottom_row.addWidget(show_source_code_btn)

            self.layout.addSpacing(10)
            self.layout.addWidget(self.label)
            self.layout.addLayout(self.first_row)
            # self.layout.addWidget(screenshot_remake_btn)
            self.layout.addLayout(self.second_row)
            self.layout.addSpacing(10)
            self.layout.addWidget(image_editor_btn)
            self.layout.addSpacing(20)
            self.layout.addLayout(self.thrid_row)
            self.layout.addLayout(self.bottom_row)
            self.layout.addSpacing(10)

            open_history_btn.clicked.connect(self.open_folder)
            image_editor_btn.clicked.connect(self.start_editor_in_compile_mode)
            screenshot_fragment_btn.clicked.connect(self.start_screenshot_editor_fragment)
            screenshot_fullscreens_btn.clicked.connect(self.start_screenshot_editor_fullscreen)
            open_settings_btn.clicked.connect(self.open_settings_window)
            show_crashlog_btn.clicked.connect(show_crash_log)
            quit_btn.clicked.connect(self.app_quit)
            btn_list = [
                screenshot_fragment_btn,
                screenshot_fullscreens_btn,
                # screenshot_remake_btn,
                image_editor_btn,
                open_history_btn,
                open_recent_screenshot_btn,
                open_settings_btn,
                show_crashlog_btn,
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

    def dragEnterEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasUrls() or mime_data.hasImage():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
            paths = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = str(url.toLocalFile())
                    # if not os.path.isdir(path):
                    #     path = os.path.dirname(path)
                    paths.append(path)
                else:
                    pass
                    # url = url.url()
                    # download_file(url)
            if Globals.DEBUG:
                to_print = f'Drop Event Data Local Paths: {paths}'
                print(to_print)
            self.start_editor_in_compile_mode(filepaths=paths)
        else:
            event.ignore()

    def contextMenuEvent(self, event):
        menu = QMenu()
        restart_app = menu.addAction('Перезапустить приложение')
        menu.addSeparator()
        crash_app = menu.addAction('Крашнуть приложение')
        action = menu.exec_(QCursor().pos())
        if action is None:
            pass
        elif action == restart_app:
            _restart_app()
            self.app_quit()
        elif action == crash_app:
            result = 1/0

    def open_settings_window(self):
        SettingsWindow().place_window()
        self.hide()

    def show_menu(self):
        if self.isVisible():
            self.hide()
        if self.widget_type == "menu":
            if os.path.exists(get_crashlog_filepath()):
                self.show_crashlog_btn.setVisible(True)
            else:
                self.show_crashlog_btn.setVisible(False)
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
            txt = """Невозможно выполнить команду.
            Возможные причины:
            1) В папке ещё нет файлов
            2) Папка ещё не задана
            3) Заданной папки не существует.

            !!! Папка может быть задана при сохранении скриншота, если ещё не была задана.
            """
            QMessageBox.critical(None, "Ошибка", txt.replace("\t", ""))
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

    def start_editor_in_compile_mode(self, filepaths=None):
        self.hide()
        invoke_screenshot_editor(request_type=RequestType.Editor, filepaths=filepaths)

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

class NotifyDialog(QWidget, StylizedUIBase):
    WIDTH = 1500

    def __init__(self, *args, label_text=None, **kwargs):
        super().__init__( *args, **kwargs)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowModality(Qt.WindowModal)
        main_layout = QVBoxLayout()
        self.button = QPushButton("Ок (пробел)")
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setStyleSheet(self.button_style)
        self.button.clicked.connect(self.yes_handler)

        self.setWindowTitle(f"Oxxxy Screenshoter {Globals.VERSION_INFO}")

        self.label = QLabel()
        self.label.setText(label_text)
        self.label.setStyleSheet(self.title_label_style)
        self.label.setFixedWidth(self.WIDTH - self.CLOSE_BUTTON_RADIUS)
        self.label.setWordWrap(True)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_handler)
        self.timer.setInterval(10)
        self.timer.start()
        main_layout.addWidget(self.label)
        main_layout.addWidget(self.button)
        self.setLayout(main_layout)
        self.resize(self.WIDTH, 200)
        self.setMouseTracking(True)

    def yes_handler(self):
        self.close()

    def update_handler(self):
        self.update()
        self.temp_v = int(math.sin(time.time()*10)*5)

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

class QuitDialog(QWidget, StylizedUIBase):
    WIDTH = 500

    def __init__(self, *args, **kwargs):
        super().__init__( *args, **kwargs)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowModality(Qt.WindowModal)
        main_layout = QVBoxLayout()
        self.button = QPushButton("Да (пробел)")
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setStyleSheet(self.button_style)
        self.button.clicked.connect(self.yes_handler)

        self.setWindowTitle(f"Oxxxy Screenshoter {Globals.VERSION_INFO}")

        self.label = QLabel()
        self.label.setText("Вы действительно хотите выйти без сохранения скриншота?")
        self.label.setStyleSheet(self.title_label_style)
        self.label.setFixedWidth(self.WIDTH - self.CLOSE_BUTTON_RADIUS)
        self.label.setWordWrap(True)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_handler)
        self.timer.setInterval(10)
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
        self.temp_v = int(math.sin(time.time()*10)*5)

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
        if _type == ToolID.zoom_in_region:
            self.chb_toolbool.setText("Кружки")
        elif _type == ToolID.text:
            self.chb_toolbool.setText("Подложка")
        elif _type == ToolID.blurring:
            self.chb_toolbool.setText("Пикселизация")
        else:
            self.chb_toolbool.setText("?")

    def set_ui_on_toolchange(self, element_type=None, hide=False):
        if hide:
            self.chb_toolbool.setEnabled(False)
            self.color_slider.setEnabled(False)
            self.size_slider.setEnabled(False)
            self.opacity_slider.setEnabled(False)
            return
        _type = element_type or self.current_tool
        self.chb_toolbool.setEnabled(False)
        self.color_slider.setEnabled(True)
        self.size_slider.setEnabled(True)
        self.opacity_slider.setEnabled(False)
        if _type in [ToolID.blurring, ToolID.darkening]:
            self.color_slider.setEnabled(False)
            if _type in [ToolID.blurring]:
                self.chb_toolbool.setEnabled(True)
        if _type in [ToolID.text, ToolID.zoom_in_region]:
            self.chb_toolbool.setEnabled(True)
        if _type in [ToolID.copypaste, ToolID.none]:
            self.color_slider.setEnabled(False)
            self.size_slider.setEnabled(False)
            self.chb_toolbool.setEnabled(False)
        if _type in [ToolID.transform, ToolID.picture]:
            self.opacity_slider.setEnabled(True)
            self.size_slider.setEnabled(False)
        self.change_ui_text(_type)
        self.parent().update()

    def tool_data_dict_from_ui(self):
        if self.current_tool in [ToolID.text, ToolID.zoom_in_region]:
            data =  {
                "color_slider_value": self.color_slider.value,
                "color_slider_palette_index": self.color_slider.palette_index,
                "size_slider_value": self.size_slider.value,
                "toolbool": self.chb_toolbool.isChecked(),
            }
        elif self.current_tool == ToolID.blurring:
            data = {
                "size_slider_value": self.size_slider.value,
                "toolbool": self.chb_toolbool.isChecked(),
            }
        elif self.current_tool == ToolID.picture:
            data =  {
                "picture_id": self.parent().current_picture_id,
                "picture_angle": self.parent().current_picture_angle,
                "opacity_slider_value": self.opacity_slider.value,
            }
        else:
            data =  {
                "color_slider_value": self.color_slider.value,
                "color_slider_palette_index": self.color_slider.palette_index,
                "size_slider_value": self.size_slider.value,
                "opacity_slider_value": self.opacity_slider.value,
            }
        return data

    def tool_data_dict_to_ui(self, data):
        DEFAULT_COLOR_SLIDER_VALUE = 0.01
        DEFAULT_COLOR_SLIDER_PALETTE_INDEX = 0
        DEFAULT_OPACITY_SLIDER_VALUE = 1.0
        if self.current_tool in [ToolID.oval, ToolID.rect, ToolID.numbering]:
            DEFAULT_SIZE_SLIDER_VALUE = 0.07
        else:
            DEFAULT_SIZE_SLIDER_VALUE = 0.4
        if self.current_tool in [ToolID.blurring]:
            DEFAULT_TOOLBOOL_VALUE = False
        else:
            DEFAULT_TOOLBOOL_VALUE = True
        self.parent().disable_callbacks = True
        self.color_slider.value = data.get("color_slider_value", DEFAULT_COLOR_SLIDER_VALUE)
        self.color_slider.palette_index = data.get("color_slider_palette_index",
                                                                DEFAULT_COLOR_SLIDER_PALETTE_INDEX)
        self.size_slider.value = data.get("size_slider_value", DEFAULT_SIZE_SLIDER_VALUE)
        self.opacity_slider.value = data.get("opacity_slider_value", DEFAULT_OPACITY_SLIDER_VALUE)
        self.chb_toolbool.setChecked(data.get("toolbool", DEFAULT_TOOLBOOL_VALUE))
        if self.current_tool == ToolID.picture:
            main_window = self.parent()
            DEFAULT_PICTURE_ID = main_window.current_picture_id
            DEFAULT_PICTURE_ANGLE = main_window.current_picture_angle
            if main_window.current_picture_pixmap is None:
                picture_id = data.get("picture_id", DEFAULT_PICTURE_ID)
                picture_info = PictureInfo.load_from_id(picture_id)
                if picture_info:
                    picture_info.load_from_file()
                    main_window.current_picture_pixmap = picture_info.pixmap
                    main_window.current_picture_id = picture_info.id
                    main_window.current_picture_angle = data.get("picture_angle", DEFAULT_PICTURE_ANGLE)
                    self.on_parameters_changed()
                else:
                    # для случаев, когда pixmap генерируется на лету, а потом при перезапуске генерация уже не существует
                    main_window.current_picture_pixmap = PictureInfo.PIXMAP_BROKEN
                    main_window.current_picture_id = PictureInfo.TYPE_STAMP
                    main_window.current_picture_angle = 0
                    self.on_parameters_changed()
        self.parent().disable_callbacks = False
        self.update() #обязательно!

    def set_tool_data(self):
        ts = self.parent().tools_settings
        # сохранить текущие настройки (дубликат в обработчике каждого элемента)
        values = ts.get("values", {})
        if not self.tool_init:
            values.update({self.current_tool: self.tool_data_dict_from_ui()})
            ts.update({"values": values})
        self.tool_init = False
        # задаём новую тулзу
        old_tool = self.current_tool
        tb = self.sender()
        if tb.isChecked():
            self.current_tool = tb.property("tool_id")
            for but in self.tools_buttons:
                if but is not tb:
                    but.setChecked(False)
        else:
            # условие нужно, чтобы после выбора штампа из меню
            # не деактивировался инструмент штамп
            if self.current_tool != ToolID.picture:
                self.current_tool = ToolID.none
        transform_tool_activated = False
        if old_tool != ToolID.transform and self.current_tool == ToolID.transform:
            transform_tool_activated = True
            self.parent().elementsOnTransformToolActivated()
        if old_tool == ToolID.transform and self.current_tool != ToolID.transform:
            self.parent().elementsSetSelected(None)
        self.parent().elementsMakeSureTheresNoUnfinishedElement()
        if self.initialization:
            self.initialization = False
        elif self.current_tool == ToolID.picture and self.parent().current_picture_pixmap is None:
            self.show_picture_menu(do_ending=False)
        # tb.setChecked(True)
        self.parent().current_tool = self.current_tool
        # загрузить настройки для текущего инструмента
        if not transform_tool_activated:
            self.tool_data_dict_to_ui(values.get(self.current_tool, {}))
        ts.update({"active_tool": self.current_tool})
        if self.current_tool != ToolID.transform:
            self.set_ui_on_toolchange()

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
            [ToolID.transform, "Выделение\nи трасформации", "Активируется через <b>Пробел</b><br>"
                        "<b>Правая кнопка мыши</b> ➜ изменение фильтрации для выделения<br>"
                        "<b>Масштабирование</b><br>"
                        "<b>+Alt</b> ➜ Относительно центра<br>"
                        "<b>+Shift</b> ➜ Пропорционально<br>"
                        "<b>Вращение<br>"
                        "<b>+Alt</b> ➜ Вращение вокруг противоположного угла<br>"
                        "<b>+Ctrl</b> ➜ Шаговое вращение по 45°"],

            [ToolID.pen, "Карандаш", "<b>+Shift</b> ➜ Рисует прямую"],
            [ToolID.marker, "Маркер", "<b>+Shift</b> ➜ Рисует прямую"],

            [ToolID.line, "Линия", "<b>+Shift</b> ➜ Рисует линию под углом 45°<br>"
                                "<b>+Ctrl</b> ➜ Рисует ломанную линию"],
            [ToolID.arrow, "Стрелка", "<b>+Shift</b> ➜ Рисует под углом в 45°"],

            [ToolID.text, "Текст", "Если после выбора инструмента нажать левую кнопку мыши<br>"
                    "и двигать курсор, удерживая её, автоматически будет<br>нарисована стрелка,"
                    " которая свяжет текст и описываемый объект."
                    "<br>+F5/F6 ➜ вращение текста"],
            [ToolID.oval, "Овал", "<b>+Shift</b> ➜ круг<br><b>+Ctrl</b> ➜ закрашивает овал"],
            [ToolID.rect, "Прямоугольник", "<b>+Shift</b> ➜ квадрат<br><b>+Ctrl</b> ➜ рисует "
                                                                                    "закрашенный"],

            [ToolID.numbering, "Нумерация", "Нумерация"],
            [ToolID.blurring, "Размытие", "Размытие"],
            [ToolID.darkening, "Затемнение", "Затемнение"],

            [ToolID.picture, "Картинка (ранее Штамп)", "Помогает разместить картинку или штамп.<br>"
                        "Чтобы выбрать нужную картинку или штамп, "
                        "нажмите правую кнопку мыши<br>"
                        "<b>Колесо мыши</b> ➜ задать размер<br>"
                        "<b>Ctrl</b> + <b>Колесо мыши</b> ➜ поворот на 1°<br>"
                        "<b>Ctrl</b>+<b>Shift</b> + <b>Колесо мыши</b> ➜ поворот на 10°"],

            [ToolID.zoom_in_region, "Лупа", "Размещает увеличенную копию"
                                                 " необходимой области изображения в любом месте"],

            [ToolID.copypaste, "Копипейст", "Копирует область изображения"
                                                        " в любое место без увеличения"]
        ]

        self.drag_flag = False
        self.auto_positioning = True
        self.current_tool = ToolID.none

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        main_layout = QVBoxLayout()
        tools = QHBoxLayout()
        self.button_layout = tools
        first_row = QHBoxLayout()
        second_row = QHBoxLayout()

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
            if ID == ToolID.picture:
                button.right_clicked.connect(self.show_picture_menu)
            if ID == ToolID.transform:
                button.right_clicked.connect(self.parent().selection_filter_menu)
            tools.addWidget(button)
            tools.addSpacing(5)

        self.done_button = CustomPushButton("Готово", self, tool_id=ToolID.DONE)
        self.done_button.mousePressEvent = self.on_done_clicked
        self.done_button.setAccessibleName("done_button")
        self.done_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.done_button.setToolTip("Готово")
        self.done_button.installEventFilter(self)
        tools.addSpacing(10)
        tools.addWidget(self.done_button)

        backwards_btn = CustomPushButton("Шаг\nназад", self, tool_id=ToolID.BACKWARDS)
        forwards_btn = CustomPushButton("Шаг\nвперёд", self, tool_id=ToolID.FORWARDS)
        self.backwards_btn = backwards_btn
        self.forwards_btn = forwards_btn
        for hb in [backwards_btn, forwards_btn]:
            hb.setCursor(QCursor(Qt.PointingHandCursor))
            first_row.addWidget(hb)
            hb.setEnabled(False)
            hb.installEventFilter(self)
        self.backwards_btn.installEventFilter(self)
        self.forwards_btn.installEventFilter(self)
        forwards_btn.clicked.connect(self.on_forwards_clicked)
        backwards_btn.clicked.connect(self.on_backwars_clicked)
        forwards_btn.setToolTip("<b>Накатить шаг обратно</b><br>Ctrl+Shift+Z")
        backwards_btn.setToolTip("<b>Откатиться на шаг назад</b><br>Ctrl+Z")



        def set_callbacks_for_sliders(widget):
            widget.value_changed.connect(self.on_parameters_changed)
            widget.value_changing_initiated.connect(partial(self.parent().elementsAcquireStampForOngoingElementsModification, 'sliders'))
            widget.value_changing_finished.connect(self.parent().elementsDeacquireStampForFinishedElementsModification)

        # для пометок
        if Globals.USE_COLOR_PALETTE:
            _type = "PALETTE"
        else:
            _type = "COLOR"
        self.color_slider = CustomSlider(_type, 400, 0.01, Globals.ENABLE_FLAT_EDITOR_UI)
        set_callbacks_for_sliders(self.color_slider)
        self.color_slider.installEventFilter(self)
        self.color_slider.setToolTip("Слайдер цвета")
        first_row.addWidget(self.color_slider)

        self.chb_toolbool = CheckBoxCustom("Подложка")
        self.chb_toolbool.setStyleSheet(checkbox_style)
        self.chb_toolbool.setEnabled(False)
        self.chb_toolbool.installEventFilter(self)

        self.chb_toolbool.stateChanged.connect(partial(self.parent().special_change_handler, self.on_parameters_changed))
        first_row.addWidget(self.chb_toolbool)

        self.size_slider = CustomSlider("SCALAR", 180, 0.2, Globals.ENABLE_FLAT_EDITOR_UI)
        set_callbacks_for_sliders(self.size_slider)
        self.size_slider.installEventFilter(self)
        self.size_slider.setToolTip("Слайдер размера")
        first_row.addWidget(self.size_slider)

        self.opacity_slider = CustomSlider("SCALAR", 180, 1.0, Globals.ENABLE_FLAT_EDITOR_UI)
        set_callbacks_for_sliders(self.opacity_slider)
        self.opacity_slider.installEventFilter(self)
        self.opacity_slider.setToolTip("Слайдер прозрачности")



        # общие для скриншота
        tools_settings = self.parent().tools_settings

        self.chb_datetimestamp = CheckBoxCustom("ДатаВремя")
        self.chb_datetimestamp.setToolTip((
            "<b>Отобразить дату в правом нижнем углу</b>"
        ))
        self.chb_datetimestamp.setStyleSheet(checkbox_style)
        self.chb_datetimestamp.installEventFilter(self)
        self.chb_datetimestamp.setChecked(tools_settings.get('datetimestamp', False))
        self.chb_datetimestamp.stateChanged.connect(self.on_screenshot_parameters_changed)
        self.parent().draw_datetimestamp = tools_settings.get('datetimestamp', False)
        second_row.addWidget(self.chb_datetimestamp)


        self.chb_savecaptureframe = CheckBoxCustom("Запомнить")
        self.chb_savecaptureframe.setToolTip((
            "<b>Запоминает положение и размеры области захвата</b>"
        ))
        self.chb_savecaptureframe.setStyleSheet(checkbox_style)
        self.chb_savecaptureframe.installEventFilter(self)
        self.chb_savecaptureframe.setChecked(tools_settings.get('savecaptureframe', False))
        self.chb_savecaptureframe.stateChanged.connect(self.on_screenshot_parameters_changed)
        second_row.addWidget(self.chb_savecaptureframe)

        self.chb_masked = CheckBoxCustom("Маска")
        self.chb_masked.setToolTip((
            "<b>Применить маску к скриншоту</b><br>"
            "<b>Клавиша H</b> ➜ сменить круглую маску на гексагональную и наоборот"
        ))
        self.chb_masked.setStyleSheet(checkbox_style)
        self.chb_masked.installEventFilter(self)
        self.chb_masked.setChecked(tools_settings.get("masked", False))
        self.chb_masked.stateChanged.connect(self.on_screenshot_parameters_changed)
        self.parent().hex_mask = tools_settings.get("hex_mask", False)
        second_row.addWidget(self.chb_masked)

        self.chb_draw_thirds = CheckBoxCustom("Трети")
        self.chb_draw_thirds.setToolTip("<b>Отображать трети в области захвата для режима"
                                                                        " редактирования</b>")
        self.chb_draw_thirds.setStyleSheet(checkbox_style)
        self.chb_draw_thirds.installEventFilter(self)
        self.chb_draw_thirds.setChecked(tools_settings.get("draw_thirds", False))
        self.chb_draw_thirds.stateChanged.connect(self.on_screenshot_parameters_changed)
        second_row.addWidget(self.chb_draw_thirds)

        self.chb_add_meta = CheckBoxCustom("Мета")
        self.chb_add_meta.setToolTip("<b>Добавить название заголовка активного окна в метатеги"
                                                                            " скриншота</b>")
        self.chb_add_meta.setStyleSheet(checkbox_style)
        self.chb_add_meta.installEventFilter(self)
        self.chb_add_meta.setChecked(tools_settings.get("add_meta", False))
        if os.name == 'nt':
            self.chb_add_meta.stateChanged.connect(self.on_screenshot_parameters_changed)
            second_row.addWidget(self.chb_add_meta)

        self.chb_draw_cursor = CheckBoxCustom("Курсор")
        self.chb_draw_cursor.setToolTip("<b>Отображать курсор на скриншоте</b>")
        self.chb_draw_cursor.setStyleSheet(checkbox_style)
        self.chb_draw_cursor.installEventFilter(self)
        self.chb_draw_cursor.setChecked(tools_settings.get("draw_cursor", False))
        self.chb_draw_cursor.stateChanged.connect(self.on_screenshot_parameters_changed)
        second_row.addWidget(self.chb_draw_cursor)

        # добавлять его надо здесь, после чекбоксов. не переносить выше!
        second_row.addWidget(self.opacity_slider)


        spacing = 2
        cms = 2
        tools.setSpacing(spacing)
        tools.setContentsMargins(cms, cms, cms, cms)
        main_layout.setSpacing(spacing)
        main_layout.setContentsMargins(cms, cms, cms, cms)
        first_row.setSpacing(spacing)
        cms = 0
        first_row.setContentsMargins(cms, cms, cms, cms)
        second_row.setSpacing(spacing)
        second_row.setContentsMargins(cms, cms, cms, cms)
        second_row.setAlignment(Qt.AlignRight)

        main_layout.addLayout(tools)
        main_layout.addLayout(first_row)
        main_layout.addLayout(second_row)

        first_row.addSpacing(75)
        second_row.addSpacing(75)

        self.setLayout(main_layout)

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_timer_handler)
        self.update_timer.setInterval(100)
        self.update_timer.start()

        tool_id = tool_id_default = ToolID.pen
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
        # блокировка событий для кнопок панели управления,
        # если не завершён процесс нанесения меток
        if obj.parent() == self and blocking and not isinstance(event, (QPaintEvent, QKeyEvent)):
            return True
        return False

    def set_current_tool(self, tool_name):
        if tool_name == ToolID.multiframing:
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

    def show_picture_menu(self, do_ending=True):
        main_window = self.parent()
        tools_window = self
        if not self.select_window:
            PictureInfo.create_default_pixmaps()
            pictures = PictureInfo.scan()
            self.select_window = PictureSelectWindow(main_window, pictures=pictures)
            PreviewsThread(pictures, self.select_window).start()
        else:
            self.select_window.show_at()
        if self.parent().current_tool != ToolID.picture:
            if do_ending:
                self.set_current_tool(ToolID.picture)
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
        f, b = self.parent().elementsUpdateEditHistoryButtonsStatus()
        self.forwards_btn.setEnabled(f)
        self.backwards_btn.setEnabled(b)
        self.update()
        self.parent().update()

    def on_forwards_clicked(self):
        self.parent().elementsEditHistoryForwards()
        self.forwards_backwards_update()

    def on_backwars_clicked(self):
        self.parent().elementsEditHistoryBackwards()
        self.forwards_backwards_update()

    def on_screenshot_parameters_changed(self):
        ts = self.parent().tools_settings
        ts.update({
            "masked": self.chb_masked.isChecked(),
            "draw_thirds": self.chb_draw_thirds.isChecked(),
            "add_meta": self.chb_add_meta.isChecked(),
            "hex_mask": getattr(self.parent(), 'hex_mask', False),
            "savecaptureframe": self.chb_savecaptureframe.isChecked(),
            "draw_cursor": self.chb_draw_cursor.isChecked(),
            "datetimestamp": self.chb_datetimestamp.isChecked(),
        })
        self.draw_datetimestamp = self.chb_datetimestamp.isChecked()
        if self.chb_savecaptureframe.isChecked():
            self.parent().update_saved_capture()
        if Globals.DEBUG:
            self.parent().save_tools_settings()
        self.parent().update()

    def on_parameters_changed(self):
        self.parent().elementsParametersChanged()
        # обновление параметров инструментов
        ts = self.parent().tools_settings
        # инструменты и их параметры
        values = ts.get("values", {})
        values.update({self.current_tool: self.tool_data_dict_from_ui()})
        ts.update({"values": values})
        self.parent().update()
        if Globals.DEBUG:
            self.parent().save_tools_settings()

    def keyPressEvent(self, event):
        # это делается для того, чтобы после использования окна редактора
        # программа нужным образом реагировала на нажатие Esc и Enter
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
        default_corner_space = build_valid_rectF(m_corner + QPointF(-offset, offset),
            all_rect.bottomLeft())
        reserved_corner_1_space = build_valid_rectF(m_corner + QPointF(offset, offset),
            all_rect.bottomRight())
        reserved_corner_2_space = build_valid_rectF(m_corner + QPointF(offset, -offset),
            all_rect.topRight())
        reserved_corner_3_space = build_valid_rectF(k_corner + QPointF(-offset, -offset),
            QPointF(0, 0))
        reserved_corner_4_space = build_valid_rectF(d_corner + QPointF(offset, -offset),
            QPointF(screenshot_rect.right(), 0))
        # для отрисовки в специальном отладочном режиме
        self.parent().default_corner_space = default_corner_space
        self.parent().reserved_corner_1_space = reserved_corner_1_space
        self.parent().reserved_corner_2_space = reserved_corner_2_space
        self.parent().reserved_corner_3_space = reserved_corner_3_space
        self.parent().reserved_corner_4_space = reserved_corner_4_space
        self.parent().debug_tools_space = self.frameGeometry()
        # проверка на то, влезает ли окно в определяемую область или нет
        def check_rect(rect):
            # Проверять нужно именно так, иначе в результате проверки на вхождение всех точек
            # прямоугольника в другой прямоугольник через qrect.contains(self.frameGeometry())
            # будет баг с залипанием в ненужных местах.
            # Всё из-за того, что прямоугольник самого окна не является актуальным
            # по разным причинам,
            # например, когда мышка перемещается очень быстро.
            # Визуально это можно видеть, если выставить DEBUG_ANALYSE_CORNERS_SPACES в True
            # Позднее замечание: скорее всего это было из-за того,
            # что координаты мышки раньше брались через таймер, а не в mouseMoveEvent
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
        self.move(int(x_value), int(y_value))

class ScreenshotWindow(QWidget, ElementsMixin):

    editing_ready = pyqtSignal(object)

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
        self.move(0,0)
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
        canvas_input_rect = self.build_input_rectF(self.elementsMapFromViewportToCanvas(cursor_pos))
        viewport_input_rect = self.elementsMapFromCanvasToViewportRectF(canvas_input_rect)

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

        painter.end()

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
        self._ted.element_position = self.elementsMapFromViewportToCanvas(cursor_pos)
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
        crr_viewport = self.elementsMapFromCanvasToViewportRectF(crr_canvas)
        if not crr_viewport.contains(cursor_pos):
            return

        self._tei.element_rotation = self.current_picture_angle
        self._tei.pixmap = self.current_picture_pixmap
        self._tei.element_position = self.elementsMapFromViewportToCanvas(cursor_pos)
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
        self_rect = self.elementsMapFromCanvasToViewportRectF(self_rect)
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
            capture_region_rect = self.elementsMapFromCanvasToViewportRectF(self.capture_region_rect)
            draw_shadow(
                painter,
                capture_region_rect, 50,
                webRGBA(QColor(0, 0, 0, 100)),
                webRGBA(QColor(0, 0, 0, 0))
            )

    def draw_wrapper_cyberpunk(self, painter):
        tw = self.tools_window
        if tw and tw.chb_draw_thirds.isChecked() and self.capture_region_rect:
            capture_region_rect = self.elementsMapFromCanvasToViewportRectF(self.capture_region_rect)
            draw_cyberpunk(painter, capture_region_rect)

    def draw_vertical_horizontal_lines(self, painter, cursor_pos):
        painter.save()
        line_pen = QPen(QColor(127, 127, 127, 172), 2, Qt.DashLine)
        painter.setCompositionMode(QPainter.RasterOp_SourceXorDestination)

        if self.is_input_points_set():
            painter.setPen(line_pen)
            input_POINT1 = self.elementsMapFromCanvasToViewport(self.input_POINT1)
            input_POINT2 = self.elementsMapFromCanvasToViewport(self.input_POINT2)
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
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
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
            color: white;
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

        # для временного отображения текста в левом верхнем углу
        self.uncapture_mode_label_tstamp = time.time()


    def animated_tool_drawing(self, tool_id, a, b, randomize=True):
        if self.tools_window.current_tool != tool_id:
            self.tools_window.set_current_tool(tool_id)

        points = []
        count = 10
        delta = b - a
        for n in range(count+1):
            ratio = n/count
            pos = a + delta*ratio
            points.append(self.elementsMapFromCanvasToViewport(pos))

        for n, pos in enumerate(points):
            time.sleep(0.01)
            if n == 0:
                self.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
            if randomize:
                value_x = 50-100*random.random()
                value_y = 50-100*random.random()
                pos += QPointF(value_x, value_y)
            self.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
            self.update()
            app = QApplication.instance()
            app.processEvents()
        self.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        self.update()

    def animated_debug_drawing(self):
        if self.tools_window:

            tl = self.capture_region_rect.topLeft()
            rb = self.capture_region_rect.bottomRight()

            a = tl + QPointF(20, 20)
            b = rb
            self.animated_tool_drawing(ToolID.line, a, b)

            a = tl + QPointF(20, 20)
            b = rb
            self.animated_tool_drawing(ToolID.marker, a, b)

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

    def save_screenshot(self, grabbed_image=None, metadata=None):
        close_all_windows()

        # задание папки для скриншота
        SettingsWindow.set_screenshot_folder_path()
        # сохранение файла
        formated_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        filepath = get_screenshot_filepath(formated_datetime)
        if grabbed_image:
            # QUICK FULLSCREEN
            grabbed_image.save(filepath)
            # copy_image_file_to_clipboard(filepath)
            save_meta_info(metadata, filepath)
        else:
            self.elementsUpdateFinalPicture(force_no_datetime_stamp=Globals.save_to_memory_mode)
            pix = self.elements_final_output
            if Globals.save_to_memory_mode:
                Globals.images_in_memory.append(pix)
            else:
                pix.save(filepath)
                if self.tools_window.chb_add_meta.isChecked():
                    save_meta_info(self.metadata, filepath)
                copy_image_file_to_clipboard(filepath)
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
            capture_region_rect = self.elementsMapFromCanvasToViewportRectF(self.capture_region_rect)
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
        self.elementsAcquireStampForOngoingElementsModification('checkbox')
        callback()
        self.elementsDeacquireStampForFinishedElementsModification()

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
                event_pos = self.elementsMapFromViewportToCanvas(event.pos())
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
                delta = self.elementsMapFromViewportToCanvas(QPointF(event.pos())) - self.start_cursor_position
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
            self.start_cursor_position = self.elementsMapFromViewportToCanvas(QPointF(event.pos()))
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

    def change_tools_params(self, delta_value, modifiers):
        tools_window = self.tools_window
        if self.active_element and tools_window.current_tool == ToolID.transform and \
                not self.active_element in self.elementsGetElementsUnderMouse(event.pos()):
            return
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
                value = self.current_picture_angle
                if delta_value < 0.0:
                    delta_value = -1
                else:
                    delta_value = 1
                if modifiers & Qt.ShiftModifier:
                    delta_value *= 10
                value += delta_value
                self.current_picture_angle = value
            self.tools_window.on_parameters_changed()
            self.tools_window.update()
            # здесь ещё должна быть запись параметров в словарь!
                # TODO: кстати, а где она, блядь?!

    def wheelEvent(self, event):
        delta_value = event.angleDelta().y()

        scroll_value = event.angleDelta().y()/240
        ctrl = event.modifiers() & Qt.ControlModifier
        shift = event.modifiers() & Qt.ShiftModifier
        alt = event.modifiers() & Qt.AltModifier
        no_mod = event.modifiers() == Qt.NoModifier

        stamp_size_change_activated = event.buttons() == Qt.RightButton and self.current_tool == ToolID.picture

        if ctrl:
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

    def toggle_show_background(self):
        self.show_background = not self.show_background
        self.update()

    def toggle_transform_widget_debug_mode(self):
        self.canvas_debug_transform_widget = not self.canvas_debug_transform_widget
        self.update()

    def toggle_debug_mode(self):
        Globals.DEBUG = not Globals.DEBUG
        self.update()

    def toggle_capture_region_widget(self):
        self.capture_region_widget_enabled = not self.capture_region_widget_enabled
        self.update()

    def toggle_dark_pictures(self):
        self.dark_pictures = not self.dark_pictures
        self.elementsUpdateFinalPicture()
        self.update()

    def toggle_close_on_done(self):
        Globals.close_editor_on_done = not Globals.close_editor_on_done
        self.update()

    def toggle_antialiasing(self):
        Globals.ANTIALIASING_AND_SMOOTH_PIXMAP_TRANSFORM = not Globals.ANTIALIASING_AND_SMOOTH_PIXMAP_TRANSFORM
        self.update()

    def contextMenuEvent(self, event):
        if self.cancel_context_menu:
            self.cancel_context_menu = False
            return

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

        render_elements_to_background = add_item("Нарисовать содержимое на фоне и удалить содержимое")
        slice_background = add_item("Нарезать фон на куски")
        special_tool = add_item(Globals.icon_multiframing, "Активировать инструмент мультикадрирования")
        reshot = add_item(Globals.icon_refresh, "Переснять скриншот")
        autocollage = add_item("Автоколлаж")
        fit_images_to_size = add_item("Подогнать все картинки по размеру под одну")
        get_toolwindow_in_view = add_item("Подтянуть панель инструментов")
        autocapturezone = add_item("Задать область захвата")
        reset_capture = add_item("Сбросить область захвата")

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

        contextMenu.addSeparator()

        if Globals.images_in_memory:
            finish_save_to_memory_mode = add_item("Разложить на холсте все готовые изображения из памяти")
        else:
            finish_save_to_memory_mode = None

        checkboxes = (
            ("Сохранить результат в память", Globals.save_to_memory_mode, self.elementsStartSaveToMemoryMode),
            ("Виджет области захвата", self.capture_region_widget_enabled, self.toggle_capture_region_widget),
            ("Фон", self.show_background, self.toggle_show_background),
            ("Затемнять после отрисовки пометок", self.dark_pictures, self.toggle_dark_pictures),
            ("Закрывать редактор после нажатия кнопки «Готово»", Globals.close_editor_on_done, self.toggle_close_on_done),
            ("Показывать дебаг-отрисовку для виджета трансформации", self.canvas_debug_transform_widget, self.toggle_transform_widget_debug_mode),
            ("Антиальясинг и сглаживание пиксмапов", Globals.ANTIALIASING_AND_SMOOTH_PIXMAP_TRANSFORM, self.toggle_antialiasing),
            ("DEBUG", Globals.DEBUG, self.toggle_debug_mode),
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
        elif action == special_tool:
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

        crr = self.elementsMapFromCanvasToViewportRectF(self.capture_region_rect)
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

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            # сюда попадём только когда отпускается клавиша,
            # во вне условия будет срабатывать постоянно пока зажата клавиша
            self.elementsDeacquireStampForFinishedElementsModification()

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
                self.show_view_window(self.get_final_picture)
        if check_scancode_for(event, "V") and event.modifiers() & Qt.ControlModifier:
            self.elementsPasteImageFromBuffer(event)
        if check_scancode_for(event, "A") and event.modifiers() & Qt.ControlModifier:
            self.elementsSelectDeselectAll()
        if check_scancode_for(event, "F"):
            if event.modifiers() & Qt.ControlModifier:
                self.elementsFitCaptureZoneOnScreen()
            else:
                self.elementsFitSelectedItemsOnScreen()
        if key == (Qt.Key_F2):
            self.animated_debug_drawing()



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
    global screenshot_editor
    if request_type is None:
        raise Exception("Unknown request type")
    # если было открыто окно-меню около трея - прячем его
    # hide_all_windows()

    metadata = generate_metainfo()
    datetime_stamp = generate_datetime_stamp()
    # started_time = time.time()

    ScreenshotWindow.screenshot_cursor_position = QCursor().pos()
    cursor_filepath = os.path.join(os.path.dirname(__file__), 'resources', 'cursor.png')
    ScreenshotWindow.cursor_pixmap = QPixmap(cursor_filepath).scaled(25, 25, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    screenshot_image = make_screenshot_pyqt()
    if request_type == RequestType.Fragment:
        # print("^^^^^^", time.time() - started_time)
        if Globals.DEBUG and Globals.DEBUG_ELEMENTS and not Globals.DEBUG_ELEMENTS_COLLAGE:
            screenshot_editor = ScreenshotWindow(screenshot_image, metadata, datetime_stamp)
            screenshot_editor.set_saved_capture_frame()
            screenshot_editor.show()
            screenshot_editor.request_elements_debug_mode()
        elif Globals.DEBUG and Globals.DEBUG_ELEMENTS_COLLAGE:
            path = SettingsJson().get_data("SCREENSHOT_FOLDER_PATH")
            if not path:
                path = ""
            filepaths = get_filepaths_dialog(path=path)
            screenshot_editor = ScreenshotWindow(screenshot_image, metadata, datetime_stamp)
            screenshot_editor.request_images_editor_mode(filepaths)
            screenshot_editor.show()
        else:
            screenshot_editor = ScreenshotWindow(screenshot_image, metadata, datetime_stamp)
            screenshot_editor.set_saved_capture_frame()
            screenshot_editor.show()
        # чтобы activateWindow точно сработал и взял фокус ввода
        QApplication.instance().processEvents()
        screenshot_editor.activateWindow()

    if request_type == RequestType.Fullscreen:
        screenshot_editor = ScreenshotWindow(screenshot_image, metadata, datetime_stamp)
        screenshot_editor.request_fullscreen_capture_region()
        screenshot_editor.show()
        # чтобы activateWindow точно сработал и взял фокус ввода
        QApplication.instance().processEvents()
        screenshot_editor.activateWindow()

    if request_type == RequestType.Editor:
        if not filepaths:
            path = SettingsJson().get_data("SCREENSHOT_FOLDER_PATH")
            if not path:
                path = ""
            filepaths = get_filepaths_dialog(path=path)
        if filepaths:
            screenshot_editor = ScreenshotWindow(screenshot_image, metadata, datetime_stamp)
            screenshot_editor.request_images_editor_mode(filepaths)
            screenshot_editor.show()
            # чтобы activateWindow точно сработал и взял фокус ввода
            QApplication.instance().processEvents()
            screenshot_editor.activateWindow()



    if request_type == RequestType.QuickFullscreen:
        ScreenshotWindow.save_screenshot(None, grabbed_image=screenshot_image, metadata=metadata)
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
    path_icon = os.path.abspath(os.path.join(os.path.dirname(__file__), "icon.png"))
    icon = QIcon(path_icon)
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
