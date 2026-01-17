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

import sys
import os
import subprocess
import time
import math
from functools import partial

from PyQt5.QtWidgets import (QWidget, QMessageBox, QMenu, QFileDialog, QHBoxLayout, QCheckBox,
                                    QVBoxLayout, QPushButton, QLabel, QApplication, QDesktopWidget)
from PyQt5.QtCore import (QPoint, QRect, QTimer, Qt, QSize, QRectF)
from PyQt5.QtGui import (QPainterPath, QColor, QBrush, QPainter, QPen, QCursor, QVector2D,
                                                                                    QFontMetrics)

from _utils import (SettingsJson, get_creation_date, open_link_in_browser, open_in_google_chrome)

from key_seq_edit import KeySequenceEdit
from on_windows_startup import (add_to_startup, is_app_in_startup, remove_from_startup)


__all__ = (
    'SettingsWindow',
    'NotificationOrMenu',
    'NotifyDialog',
    'QuitDialog',
)


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
            if self.Globals.DEBUG:
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
        path = QFileDialog.getExistingDirectory(None, msg, cls.Globals.SCREENSHOT_FOLDER_PATH)
        path = str(path)
        if path:
            cls.Globals.SCREENSHOT_FOLDER_PATH = path
            SettingsJson().set_data("SCREENSHOT_FOLDER_PATH", cls.Globals.SCREENSHOT_FOLDER_PATH)
        if hasattr(cls, 'instance'):
            cls.instance.label_1_path.setText(cls.get_path_for_label())

    @classmethod
    def set_screenshot_folder_path(cls, get_only=False):
        if not cls.Globals.SCREENSHOT_FOLDER_PATH:
            npath = os.path.normpath
            sj_path = SettingsJson().get_data("SCREENSHOT_FOLDER_PATH")
            if sj_path:
                cls.Globals.SCREENSHOT_FOLDER_PATH = npath(sj_path)
        if get_only:
            return
        while not cls.Globals.SCREENSHOT_FOLDER_PATH:
            cls.set_screenshot_folder_path_dialog()

    @classmethod
    def get_path_for_label(cls):
        cls.set_screenshot_folder_path(get_only=True)
        if os.path.exists(cls.Globals.SCREENSHOT_FOLDER_PATH):
            return f" Текущий путь: {cls.Globals.SCREENSHOT_FOLDER_PATH}"
        else:
            return "  Путь не задан!"

    def show(self):
        # self.gf.register_settings_window_global_hotkeys()
        super().show()

    def hide(self):
        self.gf.register_user_global_hotkeys()
        super().hide()

    def __init__(self, menu=False, notification=False, filepath=None):
        super().__init__()

        if hasattr(SettingsWindow, "instance"):
            if SettingsWindow.instance:
                SettingsWindow.instance.hide()
        SettingsWindow.instance = self

        STYLE = "color: white; font-size: 18px;"

        self.show_at_center = False
        title = f"Oxxxy Settings {self.Globals.VERSION_INFO}"
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
            setattr(self.Globals, attr_name, value)
            SettingsJson().set_data(attr_name, value)
        for text, attr_name in keyseq_data:
            _label = QLabel("<center>%s</center>" % text)
            _label.setStyleSheet(self.info_label_style_white)
            _label.setWordWrap(True)
            current_keyseq = getattr(self.Globals, attr_name)
            default_keyseq = getattr(self.Globals, f'DEFAULT_{attr_name}')
            _field = KeySequenceEdit(current_keyseq, default_keyseq,
                    partial(on_changed_callback, attr_name[:]),
                    self.gf.register_settings_window_global_hotkeys,
                    self.gf.register_user_global_hotkeys
            )
            _field.setStyleSheet(self.edit_style_white)
            _field.setFixedWidth(200)
            layout_2.addWidget(_label)
            layout_2.addWidget(_field, alignment=Qt.AlignCenter)
        #######################################################################
        chbx_21 = QCheckBox("Также вызывать скриншот фрагмента\n через клавишу Print Screen")
        chbx_21.setStyleSheet(self.settings_checkbox)
        chbx_21.setChecked(self.Globals.USE_PRINT_KEY)
        chbx_21.stateChanged.connect(lambda: self.handle_print_screen_for_fragment(chbx_21))
        layout_2.addWidget(chbx_21, alignment=Qt.AlignCenter)
        #######################################################################
        chbx_22 = QCheckBox(("Блокировать срабатывание комбинаций\n"
                                "клавиш после первого срабатывания\n"
                                "и до сохранения скриншота"))
        chbx_22.setStyleSheet(self.settings_checkbox)
        chbx_22.setChecked(self.Globals.BLOCK_KEYSEQ_HANDLING_AFTER_FIRST_CALL)
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
        self.Globals.BLOCK_KEYSEQ_HANDLING_AFTER_FIRST_CALL = sender.isChecked()

    def handle_print_screen_for_fragment(self, sender):
        SettingsJson().set_data("USE_PRINT_KEY", sender.isChecked())
        self.Globals.USE_PRINT_KEY = sender.isChecked()

    def handle_palette_chbx(self, sender):
        SettingsJson().set_data("USE_COLOR_PALETTE", sender.isChecked())
        self.Globals.USE_COLOR_PALETTE = sender.isChecked()

    def handle_ui_style_chbx(self, sender):
        SettingsJson().set_data("ENABLE_FLAT_EDITOR_UI", sender.isChecked())
        self.Globals.ENABLE_FLAT_EDITOR_UI = sender.isChecked()

    def handle_cbor2_chbx(self, sender):
        SettingsJson().set_data("ENABLE_CBOR2", sender.isChecked())
        self.Globals.ENABLE_CBOR2 = sender.isChecked()

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

        self.setWindowTitle(f"Oxxxy Screenshoter {self.Globals.VERSION_INFO} {self.Globals.AUTHOR_INFO}")
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

            open_in_oxxxy_btn = QPushButton("Открыть в Oxxxy")
            open_in_oxxxy_btn.setStyleSheet(self.button_style)
            open_in_oxxxy_btn.setFixedWidth(self.WIDTH)
            open_in_oxxxy_btn.clicked.connect(self.open_in_oxxxy)
            open_in_oxxxy_btn.setFocusPolicy(Qt.NoFocus)
            open_in_oxxxy_btn.setCursor(Qt.PointingHandCursor)

            self.layout.addSpacing(10)
            self.layout.addWidget(self.label)
            self.layout.addWidget(open_image_btn_gchr)
            self.layout.addSpacing(10)
            self.layout.addWidget(open_image_btn)
            self.layout.addSpacing(10)
            self.layout.addWidget(open_folder_btn)
            self.layout.addSpacing(10)
            self.layout.addWidget(open_in_oxxxy_btn)
            self.layout.addSpacing(10)


            self.timer.start()

        if menu and not notification:
            self.widget_type = "menu"

            self.setAcceptDrops(True)

            self.label = QLabel()
            self.label.setText(f"Oxxxy {self.Globals.VERSION_INFO}")
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
            show_crashlog_btn.clicked.connect(self.gl.show_crash_log)
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
            if self.Globals.DEBUG:
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
            self.gl._restart_app()
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
            if os.path.exists(self.gl.get_crashlog_filepath()):
                self.show_crashlog_btn.setVisible(True)
            else:
                self.show_crashlog_btn.setVisible(False)
            self.place_window()

    def open_recent_screenshot(self):
        SettingsWindow.set_screenshot_folder_path(get_only=True)

        recent_filepath = None
        timestamp = 0.0
        _path = self.Globals.SCREENSHOT_FOLDER_PATH
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
        self.gl.invoke_screenshot_editor(request_type=self.RequestType.Fragment)

    def start_screenshot_editor_fullscreen(self):
        self.hide()
        self.gl.invoke_screenshot_editor(request_type=self.RequestType.Fullscreen)

    def start_editor_in_compile_mode(self, filepaths=None):
        self.hide()
        self.gl.invoke_screenshot_editor(request_type=self.RequestType.Editor, filepaths=filepaths)

    def open_folder(self):
        SettingsWindow.set_screenshot_folder_path(get_only=True)
        args = ["explorer.exe", '{}'.format(self.Globals.SCREENSHOT_FOLDER_PATH)]
        # QMessageBox.critical(None, "Debug info", "{}".format(args))
        subprocess.Popen(args)
        # os.system("start {}".format(self.Globals.SCREENSHOT_FOLDER_PATH))
        self.close_notification_window_and_quit()

    def open_in_oxxxy(self):
        self.Globals.DEBUG = False
        self.gl.invoke_screenshot_editor(request_type=self.RequestType.Editor, filepaths=[self.filepath])

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
        self.Globals.FULL_STOP = True
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

        self.setWindowTitle(f"Oxxxy Screenshoter {self.Globals.VERSION_INFO}")

        self.label = QLabel()
        self.label.setText(label_text)
        self.label.setStyleSheet(self.title_label_style)
        font = self.label.font()
        font.setPixelSize(18) # according to css rule in self.title_label_style
        fm = QFontMetrics(font)
        text_rect = fm.boundingRect(QRect(), Qt.AlignLeft | Qt.AlignTop, label_text)
        self.label.setFixedWidth(text_rect.width()+200)
        self.label.setWordWrap(True)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_handler)
        self.timer.setInterval(10)
        self.timer.start()
        main_layout.addWidget(self.label)
        main_layout.addWidget(self.button)
        self.setLayout(main_layout)

        self.resize(min(self.WIDTH, text_rect.width()+200), 200)
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

        self.setWindowTitle(f"Oxxxy Screenshoter {self.Globals.VERSION_INFO}")

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



# для запуска программы прямо из этого файла при разработке и отладке
if __name__ == '__main__':
    import subprocess
    subprocess.Popen([sys.executable, "-u", "oxxxy.py"])
    sys.exit()
