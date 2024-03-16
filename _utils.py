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


from functools import lru_cache
import sys
import os
import subprocess
import platform
import ctypes
import math
import json
import webbrowser
import random
import datetime

import psutil
from PIL import Image, ImageGrab, PngImagePlugin

from PyQt5.QtWidgets import (QWidget, QMessageBox, QDesktopWidget, QApplication,
    QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene)
from PyQt5.QtCore import (QRectF, QPoint, pyqtSignal, QSizeF, Qt, QPointF, QSize, QRect,
                                                                    QMimeData, QUrl)
from PyQt5.QtGui import (QPixmap, QBrush, QRegion, QImage, QRadialGradient, QColor,
                    QGuiApplication, QPen, QPainterPath, QPolygon, QLinearGradient, QPainter,
                    QCursor, QImageReader, QTransform, QPolygonF, QVector2D)
from PyQt5.QtSvg import  QSvgRenderer

win32process = None
if os.name == 'nt': # only for win32
    try:
        win32process = __import__("win32process")
    except ModuleNotFoundError:
        pass

__all__ = (
    # 'ch_left_index',
    # 'ch_orientation',

    'convex_hull',

    'check_scancode_for',

    'SettingsJson',

    'generate_metainfo',
    'generate_datetime_stamp',

    'get_bounding_points',
    'get_bounding_pointsF',

    'build_valid_rectF',
    'build_valid_rect',
    'build_valid_rectF',
    'dot',
    'get_nearest_point_on_rect',
    'get_creation_date',
    'find_browser_exe_file',
    'open_link_in_browser',
    'open_in_google_chrome',
    'save_meta_info',

    # 'make_screenshot_ImageGrab',
    'make_screenshot_pyqt',

    'load_svg',

    'webRGBA',
    'generate_gradient',
    'draw_shadow',
    'draw_cyberpunk',
    'constraint45Degree',

    # for image_viewer_lite.py
    'fit_rect_into_rect',
    'draw_thirds',
    'interpolate_values',
    'fit',
    'fit01',

    'load_image_respect_orientation',
    'is_webp_file_animated',

    'apply_blur_effect',

    'capture_rotated_rect_from_pixmap',

    'copy_image_file_to_clipboard',

    'squarize_rect',
    'calculate_tangent_points',
)

# Python3 program to find convex hull of a set of points. Refer
# https://www.geeksforgeeks.org/orientation-3-ordered-points/
# for explanation of orientation()
def ch_left_index(points):
    # Finding the left most point
    minn = 0
    for i in range(1,len(points)):
        if points[i].x() < points[minn].x():
            minn = i
        elif points[i].x() == points[minn].x():
            if points[i].y() > points[minn].y():
                minn = i
    return minn

def ch_orientation(p, q, r):
    # To find orientation of ordered triplet (p, q, r).
    # The function returns following values
    # 0 --> p, q and r are collinear
    # 1 --> Clockwise
    # 2 --> Counterclockwise
    val = (q.y() - p.y()) * (r.x() - q.x()) - (q.x() - p.x()) * (r.y() - q.y())

    if val == 0:
        return 0
    elif val > 0:
        return 1
    else:
        return 2

def convex_hull(points):
    n = len(points)

    # there must be at least 3 points
    if n < 3:
        return None

    # find the leftmost point
    l = ch_left_index(points)

    hull = []

    # start from leftmost point, keep moving counterclockwise
    # until reach the start point again. This loop runs O(h)
    # times where h is number of points in result or output.

    p = l
    q = 0

    length = len(points)
    loops = 0
    while True:
        loops += 1

        # add current point to result
        hull.append(p)

        # search for a point 'q' such that ch_orientation(p, q,
        # x) is counterclockwise for all points 'x'. The idea
        # is to keep track of last visited most counterclock-
        # wise point in q. If any point 'i' is more counterclock-
        # wise than q, then update q.

        q = (p + 1) % n

        for i in range(n):
            # if i is more counterclockwise
            # than current q, then update q
            if ch_orientation(points[p], points[i], points[q]) == 2:
                q = i

        # now q is the most counterclockwise with respect to p.
        # set p as q for next iteration, so that q is added to
        # result 'hull'

        p = q

        # while we don't come to first point
        if p == l:
            break
        # этого предохранителя не было, но я решил его вставить на всякий случай
        if loops > length*2:
            # print('!break from convex_hull')
            break


    return [points[each] for each in hull]

# def convex_hull_example():
    # points = [
    #     QPoint(0, 3),
    #     QPoint(2, 2),
    #     QPoint(1, 1),
    #     QPoint(2, 1),
    #     QPoint(3, 0),
    #     QPoint(0, 0),
    #     QPoint(3, 3),
    # ]
    # print(convex_hull(points))

SCANCODES_FROM_LATIN_CHAR = {
    "Q": 16,
    "W": 17,
    "E": 18,
    "R": 19,
    "T": 20,
    "Y": 21,
    "U": 22,
    "I": 23,
    "O": 24,
    "P": 25,
    "A": 30,
    "S": 31,
    "D": 32,
    "F": 33,
    "G": 34,
    "H": 35,
    "J": 36,
    "K": 37,
    "L": 38,
    "Z": 44,
    "X": 45,
    "C": 46,
    "V": 47,
    "B": 48,
    "N": 49,
    "M": 50,
    "[": 26,
    "]": 27,
}

def check_scancode_for(event, data):
    if data is None:
        return False
    code = event.nativeScanCode()
    if isinstance(data, str):
        data = data.upper()[0]
        return SCANCODES_FROM_LATIN_CHAR[data] == code
    elif isinstance(data, (list, tuple)):
        return any(SCANCODES_FROM_LATIN_CHAR[ch] == code for ch in data)

class SettingsJson():

    def init(self, Globals):
        self.debug_mode = Globals.DEBUG

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(SettingsJson, cls).__new__(cls)
            cls.instance.debug_mode = False
            cls.instance.force_reading_from_file = True
            cls.instance.data = {}
        return cls.instance

    def set_reading_file_on_getting_value(self, value):
        self.force_reading_from_file = value

    def get_filepath(self):
        if self.debug_mode:
            root = os.path.dirname(__file__)
        else:
            root = os.path.expanduser("~")
        return os.path.join(root, "oxxxy_settings.json")

    def set_data(self, key, value):
        self.read_data()
        self.data.update({key:value})
        filepath = self.get_filepath()
        if os.path.exists(filepath):
            os.remove(filepath)
        with open(filepath, 'w+', encoding="utf8") as file:
            json.dump(self.data, file, indent=True)

    def read_data(self):
        filepath = self.get_filepath()
        if not os.path.exists(filepath):
            self.data = {}
        else:
            with open(filepath, "r", encoding="utf8") as file:
                try:
                    self.data = json.load(file)
                except Exception:
                    self.data = {}

    def get_data(self, key, default_value={}):
        if self.force_reading_from_file:
            self.read_data()
        return self.data.get(key, default_value)

def generate_metainfo():
    if win32process:
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            tid, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            window_title = buff.value
            if window_title:
                process_name = process.name()
                return window_title, process_name
        except Exception:
            pass
    return "Not defined", "Not defined"

def generate_datetime_stamp():
    return datetime.datetime.now().strftime("%Y %m %d %H:%M:%S")

def get_bounding_points(points):
    MAX = sys.maxsize
    left = MAX
    right = -MAX
    top = MAX
    bottom = -MAX
    if not points:
        raise Exception("Empty list!")
    for p in points:
        left = min(int(p.x()), left)
        right = max(int(p.x()), right)
        top = min(int(p.y()), top)
        bottom = max(int(p.y()), bottom)
    return QPoint(left, top), QPoint(right, bottom)

def get_bounding_pointsF(points):
    MAX = float(sys.maxsize)
    left = MAX
    right = -MAX
    top = MAX
    bottom = -MAX
    if not points:
        raise Exception("Empty list!")
    for p in points:
        left = min(p.x(), left)
        right = max(p.x(), right)
        top = min(p.y(), top)
        bottom = max(p.y(), bottom)
    return QPointF(left, top), QPointF(right, bottom)

def build_valid_rect(p1, p2):
    return QRect(*get_bounding_points((p1, p2)))

def build_valid_rectF(p1, p2):
    return QRectF(*get_bounding_pointsF((p1, p2)))

def dot(p1, p2):
    return p1.x()*p2.x() + p1.y()*p2.y()

def get_nearest_point_on_rect(r, cursor):
    def distance_length(a, b):
        return QVector2D(a - b).length()
    def create_points(a, b):
        a = QPointF(a)
        b = QPointF(b)
        ps = []
        count = int(distance_length(a, b)/10)
        for i in range(count+1):
            if i == 0:
                continue
            t = i/count
            p = a*t + b*(1-t)
            ps.append(p)
        return ps
    points = []
    points.extend(create_points(r.topLeft(), r.bottomLeft()))
    points.extend(create_points(r.topRight(), r.topLeft()))
    points.extend(create_points(r.bottomRight(), r.topRight()))
    points.extend(create_points(r.bottomLeft(), r.bottomRight()))
    nearest_point = QPoint(0, 0)
    l = 100000.0
    for p in points:
        delta_length = distance_length(cursor, p)
        if delta_length < l:
            l = delta_length
            nearest_point = p
    return nearest_point

def get_creation_date(path_to_file):
    if platform.system() == 'Windows':
        return os.path.getctime(path_to_file)
    else:
        stat = os.stat(path_to_file)
        try:
            return stat.st_birthtime
        except AttributeError: # it's brobably Linux
            return stat.st_mtime

def find_browser_exe_file(exe_filename="chrome.exe"):
    exe_filepath = None
    for proc in psutil.process_iter():
        try:
            if proc.name() == exe_filename:
                exe_filepath = proc.cmdline()[0]
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        except Exception:
            pass
    return exe_filepath

def open_link_in_browser(link):
    webbrowser.open(link)

def open_in_google_chrome(filepath):
    CHROME_EXE = find_browser_exe_file()
    if CHROME_EXE:
        args = [CHROME_EXE, filepath]
        subprocess.Popen(args)
    else:
        msg = "Невозможно открыть в браузере.\nСначала откройте браузер Google Chrome!"
        QMessageBox.critical(None, "Error", msg)

def save_meta_info(metadata, filepath):
    m0 = metadata[0]
    m1 = metadata[1]
    metastring = f"Screenshot metadata: {m0} {m1}"
    info = PngImagePlugin.PngInfo()
    info.add_text("text", metastring)
    im = Image.open(filepath)
    im.save(filepath, "PNG", pnginfo=info)

def load_svg(path, scale_factor=20):
    renderer =  QSvgRenderer(path)
    size = renderer.defaultSize()
    rastered_image = QImage(
        size.width()*scale_factor,
        size.height()*scale_factor,
        QImage.Format_ARGB32
    )
    rastered_image.fill(Qt.transparent)
    painter = QPainter(rastered_image)
    renderer.render(painter)
    painter.end()
    return QPixmap.fromImage(rastered_image)

def PIL_to_QImage(im):
    if isinstance(im, QImage):
        return None, im
    else:
        if im.mode == "RGB":
            r, g, b = im.split()
            im = Image.merge("RGB", (b, g, r))
        elif  im.mode == "RGBA":
            r, g, b, a = im.split()
            im = Image.merge("RGBA", (b, g, r, a))
        elif im.mode == "L":
            im = im.convert("RGBA")
        im2 = im.convert("RGBA")
        data = im2.tobytes("raw", "RGBA")
        return QImage(data, im.size[0], im.size[1], QImage.Format_ARGB32)

def make_screenshot_ImageGrab():
    return PIL_to_QImage(ImageGrab.grab(all_screens=True))

def make_screenshot_pyqt():
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
    all_monitors_zone = QRect(QPoint(left, top), QPoint(right+1, bottom+1))

    # print(all_monitors_zone)
    qimage = QImage(
        all_monitors_zone.width(),
        all_monitors_zone.height(),
        QImage.Format_RGB32
    )
    qimage.fill(Qt.black)

    painter = QPainter()
    painter.begin(qimage)
    screens = QGuiApplication.screens()
    for n, screen in enumerate(screens):
        p = screen.grabWindow(0)
        source_rect = QRect(QPoint(0, 0), screen.geometry().size())
        painter.drawPixmap(screen.geometry(), p, source_rect)
    painter.end()
    return qimage

def webRGBA(qcolor_value):
    _a = qcolor_value.alpha()
    _r = qcolor_value.red()
    _g = qcolor_value.green()
    _b = qcolor_value.blue()
    return f"#{_a:02x}{_r:02x}{_g:02x}{_b:02x}"

@lru_cache(maxsize=8)
def generate_gradient(_type, shadow_size, color1_hex, color2_hex):
    # hex colors for hashability of the function
    color1 = QColor(color1_hex)
    color2 = QColor(color2_hex)
    # https://doc.qt.io/qtforpython-5/PySide2/QtGui/QGradient.html
    # https://doc.qt.io/qtforpython-5/PySide2/QtGui/QConicalGradient.html
    # https://doc.qt.io/qtforpython-5/PySide2/QtGui/QRadialGradient.html
    # https://doc.qt.io/qt-5/qlineargradient.html
    gradients = [
        ("top_left",        (shadow_size, shadow_size), ),
        ("bottom_right",    (shadow_size, shadow_size), ),
        ("bottom_left",     (shadow_size, shadow_size), ),
        ("top_right",       (shadow_size, shadow_size), ),
        ("top",             (1, shadow_size),           ),
        ("bottom",          (1, shadow_size),           ),
        ("left",            (shadow_size, 1),           ),
        ("right",           (shadow_size, 1),           ),
    ]
    current_gradient_info = None
    for gradient_info in gradients:
        if _type == gradient_info[0]:
            current_gradient_info = gradient_info
    if not current_gradient_info:
        raise
    size = current_gradient_info[1]
    gradient_type_pxm = QPixmap(*size)
    gradient_type_pxm.fill(Qt.transparent)
    p = QPainter()
    p.begin(gradient_type_pxm)
    p.setRenderHint(QPainter.HighQualityAntialiasing, True)
    if _type == "top_left":
        gradient = QRadialGradient(QPoint(shadow_size, shadow_size), shadow_size)
        gradient.setColorAt(0, color1)
        gradient.setColorAt(1, color2)
    if _type == "top_right":
        gradient = QRadialGradient(QPoint(0, shadow_size), shadow_size)
        gradient.setColorAt(0, color1)
        gradient.setColorAt(1, color2)
    if _type == "bottom_right":
        gradient = QRadialGradient(QPoint(0, 0), shadow_size)
        gradient.setColorAt(0, color1)
        gradient.setColorAt(1, color2)
    if _type == "bottom_left":
        gradient = QRadialGradient(QPoint(shadow_size, 0), shadow_size)
        gradient.setColorAt(0, color1)
        gradient.setColorAt(1, color2)
    if _type == "top":
        gradient = QLinearGradient(0, 0, *size)
        gradient.setColorAt(1, color1)
        gradient.setColorAt(0, color2)
    if _type == "bottom":
        gradient = QLinearGradient(0, 0, *size)
        gradient.setColorAt(0, color1)
        gradient.setColorAt(1, color2)
    if _type == "left":
        gradient = QLinearGradient(0, 0, *size)
        gradient.setColorAt(1, color1)
        gradient.setColorAt(0, color2)
    if _type == "right":
        gradient = QLinearGradient(0, 0, *size)
        gradient.setColorAt(0, color1)
        gradient.setColorAt(1, color2)
    p.fillRect(QRect(0, 0, *size), gradient)
    p.end()
    del p
    return gradient_type_pxm

def draw_shadow(painter, rect, shadow_size, color1_hex, color2_hex):
    if not rect:
        return
    sr = rect
    # rectangle sides
    gradient_pxm = generate_gradient("top", shadow_size, color1_hex, color2_hex)
    top_left = sr.topLeft() + QPoint(1, -shadow_size)
    bottom_right = sr.topRight() + QPoint(-1, 0)
    target = QRectF(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, QRectF(gradient_pxm.rect()))

    gradient_pxm = generate_gradient("bottom", shadow_size, color1_hex, color2_hex)
    top_left = sr.bottomLeft() + QPoint(1, 0)
    bottom_right = sr.bottomRight() + QPoint(-1, -shadow_size)
    target = QRectF(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, QRectF(gradient_pxm.rect()))

    gradient_pxm = generate_gradient("left", shadow_size, color1_hex, color2_hex)
    top_left = sr.topLeft() + QPoint(-shadow_size, 1)
    bottom_right = sr.bottomLeft() + QPoint(0, -1)
    target = QRectF(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, QRectF(gradient_pxm.rect()))

    gradient_pxm = generate_gradient("right", shadow_size, color1_hex, color2_hex)
    top_left = sr.topRight() + QPoint(0, 1)
    bottom_right = sr.bottomRight() + QPoint(shadow_size, -1)
    target = QRectF(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, QRectF(gradient_pxm.rect()))

    # rectangle corners
    gradient_pxm = generate_gradient("top_left", shadow_size, color1_hex, color2_hex)
    top_left = sr.topLeft() + QPoint(-shadow_size, -shadow_size)
    bottom_right = sr.topLeft() + QPoint(0, 0)
    target = QRectF(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, QRectF(gradient_pxm.rect()))

    gradient_pxm = generate_gradient("top_right", shadow_size, color1_hex, color2_hex)
    top_left = sr.topRight() + QPoint(0, -shadow_size)
    bottom_right = sr.topRight() + QPoint(shadow_size, 0)
    target = QRectF(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, QRectF(gradient_pxm.rect()))

    gradient_pxm = generate_gradient("bottom_right", shadow_size, color1_hex, color2_hex)
    top_left = sr.bottomRight() + QPoint(0, 0)
    bottom_right = sr.bottomRight() + QPoint(shadow_size, shadow_size)
    target = QRectF(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, QRectF(gradient_pxm.rect()))

    gradient_pxm = generate_gradient("bottom_left", shadow_size, color1_hex, color2_hex)
    top_left = sr.bottomLeft() + QPoint(-shadow_size, 0)
    bottom_right = sr.bottomLeft() + QPoint(0, -shadow_size)
    target = QRectF(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, QRectF(gradient_pxm.rect()))

def draw_cyberpunk(painter, image_rect):
    # draw lines
    painter.setPen(QPen(QColor(255, 255 ,255 ,25), 2))
    offset = image_rect.topLeft()
    w = image_rect.width()
    h = image_rect.height()
    # vertical
    painter.drawLine(QPointF(w/3, 0)+offset, QPointF(w/3, h)+offset)
    painter.drawLine(QPointF(w/3*2, 0)+offset, QPointF(w/3*2, h)+offset)
    # horizontal
    painter.drawLine(QPointF(0, h/3)+offset, QPointF(w, h/3)+offset)
    painter.drawLine(QPointF(0, h/3*2)+offset, QPointF(w, h/3*2)+offset)


def constraint45Degree(pivot, point):
    sqrt_2 = math.sqrt(2)
    sqrt_2 *= 0.5 # обязательно, иначе диагональные направления не будут срабатывать
    directions = [
        QPointF(sqrt_2, -sqrt_2), # diagonal
        QPointF(sqrt_2, sqrt_2), # diagonal
        QPointF(-sqrt_2, -sqrt_2), # diagonal
        QPointF(-sqrt_2, sqrt_2), # diagonal
        QPointF(0, -1), # north
        QPointF(1, 0),  # east
        QPointF(0, 1),  # south
        QPointF(-1, 0), # west
    ]
    current_dir = None
    value = -1000000.0
    for dirn in directions:
        A = pivot
        B = pivot + dirn
        P = point
        AB = B - A
        AP = P - A
        raw_value = dot(AP, AB)/dot(AB, AB)
        if value < raw_value:
            value = raw_value
            current_dir = dirn
    point = pivot + current_dir*value
    return point

def fit_rect_into_rect(source_rect, input_rect, float_mode=False):
    # копируем прямоугольники, чтобы не изменять исходники
    if float_mode:
        main_rect = QRectF(input_rect)
        size_rect = QRectF(source_rect)
    else:
        main_rect = QRect(input_rect)
        size_rect = QRect(source_rect)
    w = size_rect.width()
    h = size_rect.height()
    nw = size_rect.width()
    nh = size_rect.height()
    if size_rect.width() == 0 or size_rect.height() == 0:
        return source_rect
    if size_rect.width() > main_rect.width() or size_rect.height() > main_rect.height():
        # если контент не влазит на экран
        image_scale1 = main_rect.width()/size_rect.width()
        image_scale2 = main_rect.height()/size_rect.height()
        new_width1 = w*image_scale1
        new_height1 = h*image_scale1
        new_width2 = w*image_scale2
        new_height2 = h*image_scale2
        nw = min(new_width1, new_width2)
        nh = min(new_height1, new_height2)
    elif size_rect.width() < main_rect.width() or size_rect.height() < main_rect.height():
        # если контент меньше экрана
        image_scale1 = main_rect.width()/size_rect.width()
        image_scale2 = main_rect.height()/size_rect.height()
        new_width1 = w*image_scale1
        new_height1 = h*image_scale1
        new_width2 = w*image_scale2
        new_height2 = h*image_scale2
        nw = min(new_width1, new_width2)
        nh = min(new_height1, new_height2)
    center = main_rect.center()
    new_width = int(nw)
    new_height = int(nh)
    result = QRectF(QPointF(center) - QPointF(new_width/2-1, new_height/2-1), QSizeF(new_width, new_height))
    if float_mode:
        return result
    else:
        return result.toRect()

def fit(t, input_a, input_b, output_a, output_b):
    t = max(input_a, min(input_b, t))
    factor = (t-input_a)/(input_b-input_a)
    return output_a + factor*(output_b-output_a)

def fit01(t, output_a, output_b):
    return fit(t, 0.0, 1.0, output_a, output_b)

def interpolate_values(start_value, end_value, factor):
    if isinstance(start_value, float):
        value = fit(factor, 0.0, 1.0, start_value, end_value)
    elif isinstance(start_value, QPoint):
        value_x = fit(factor, 0.0, 1.0, start_value.x(), end_value.x())
        value_y = fit(factor, 0.0, 1.0, start_value.y(), end_value.y())
        value = QPoint(int(value_x), int(value_y))
    elif isinstance(start_value, QPointF):
        value_x = fit(factor, 0.0, 1.0, start_value.x(), end_value.x())
        value_y = fit(factor, 0.0, 1.0, start_value.y(), end_value.y())
        value = QPointF(float(value_x), float(value_y))
    elif isinstance(start_value, QRect):
        value_x = fit(factor, 0.0, 1.0, start_value.left(), end_value.left())
        value_y = fit(factor, 0.0, 1.0, start_value.top(), end_value.top())
        value_w = fit(factor, 0.0, 1.0, start_value.width(), end_value.width())
        value_h = fit(factor, 0.0, 1.0, start_value.height(), end_value.height())
        value = QRect(int(value_x), int(value_y), int(value_w), int(value_h))
    elif isinstance(start_value, QColor):
        value_r = fit(factor, 0.0, 1.0, start_value.red(), end_value.red())
        value_g = fit(factor, 0.0, 1.0, start_value.green(), end_value.green())
        value_b = fit(factor, 0.0, 1.0, start_value.blue(), end_value.blue())
        value = QColor(int(value_r), int(value_g), int(value_b))
    return value

def draw_thirds(self, painter, image_rect):
    # draw lines
    painter.setPen(QPen(QColor(255, 255 ,255 ,25), 2))
    offset = image_rect.topLeft()
    w = image_rect.width()
    h = image_rect.height()
    # vertical
    painter.drawLine(QPoint(w//3, 0)+offset, QPoint(w//3, h)+offset)
    painter.drawLine(QPoint(w//3*2, 0)+offset, QPoint(w//3*2, h)+offset)
    # horizontal
    painter.drawLine(QPoint(0, h//3)+offset, QPoint(w, h//3)+offset)
    painter.drawLine(QPoint(0, h//3*2)+offset, QPoint(w, h//3*2)+offset)


def load_image_respect_orientation(filepath):
    imgReader = QImageReader(filepath)
    imgReader.setAutoTransform(True)
    img = imgReader.read()
    return QPixmap().fromImage(img)

def is_webp_file_animated(filepath):
    result = False
    file_h = open(filepath, "rb")
    file_h.seek(12)
    if file_h.read(4) == b"VP8X":
        file_h.seek(20)
        byte = file_h.read(1)
        if (ord(byte)>>1) & 1:
            result = True
        else:
            result = False
    file_h.close()
    return result

def apply_blur_effect(src_pix, pix, blur_radius=5):
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

def capture_rotated_rect_from_pixmap(pixmap, capture_pos, capture_rotation,
                                                                capture_width, capture_height):

    # При плавном изменении угла от 0 до 360 заметно подёргивание картинки.
    # можно избавиться от этого, избавившись от отрисовки во вспомогательном middle_pixmap,
    # потому что размеры этого middle_pixmap выражены всегда целыми числами.
    # Но мне анимация здесь ни к чему, поэтому оставлю как есть.
    # Избавится от вспомогательного middle_pixmap можно
    # если повернуть pixmap на угол относительно capture_pos

    orig_capture_height = capture_height
    orig_capture_width = capture_width
    # для полноценного копирования необходимо сфоромировать квадрат
    capture_width = capture_height = max(capture_width, capture_height)

    capture_size = QRectF(0, 0, capture_width, capture_height)
    capture_size.moveCenter(QPointF(0, 0))
    tr = QTransform()
    tr.translate(capture_pos.x(), capture_pos.y() )
    tr.rotate(capture_rotation)
    capture_polygon = tr.map(QPolygonF(capture_size))

    # для отладки в пейнтере виджета
    # painter.drawPolygon(capture_polygon)
    # painter.setBrush(Qt.NoBrush)

    cpbr = capture_polygon.boundingRect()
    # для отладки в пейнтере виджета
    # painter.drawRect(cpbr)

    cpbr_size = cpbr.size()
    middle_pixmap = QPixmap(
        math.ceil(cpbr_size.width()),
        math.ceil(cpbr_size.height()),
    )
    middle_pixmap.fill(Qt.transparent)

    mp = QPainter()
    mp.begin(middle_pixmap)
    mp.setRenderHint(QPainter.HighQualityAntialiasing, True)
    mp.setRenderHint(QPainter.Antialiasing, True)
    mp.setRenderHint(QPainter.SmoothPixmapTransform, True)
    cpbr_source = QRectF(cpbr)
    cpbr_source.moveCenter(capture_pos)
    cpbr_dest = QRectF(cpbr)
    cpbr_dest.moveTopLeft(QPointF(
                -cpbr.width()/2,
                -cpbr.height()/2
    ))
    draw_transform = QTransform()
    draw_transform.translate(cpbr.width()/2, cpbr.height()/2)
    draw_transform.rotate(-capture_rotation)
    mp.setTransform(draw_transform)
    mp.drawPixmap(cpbr_dest, pixmap, cpbr_source)
    mp.end()

    # для отладки в пейнтере виджета
    # painter.drawPixmap(QPointF(300, 300), middle_pixmap)
    # output_rect = QRectF(QPointF(300, 300), cpbr.size())
    # painter.drawRect(output_rect)

    # для отладки в пейнтере виджета
    # output_small_rect = QRectF(capture_size)
    # ppp = QPointF(300, 300) + QPointF(middle_pixmap.width()/2, middle_pixmap.height()/2)
    # output_small_rect.moveCenter(ppp)
    # для отладки в пейнтере виджета
    # painter.drawRect(output_small_rect)

    source_rect = QRectF(capture_size)
    source_rect.moveCenter(QPointF(middle_pixmap.width()/2, middle_pixmap.height()/2))
    dest_rect = QRectF(QPointF(500, 500), capture_size.size())

    # для отладки в пейнтере виджета
    # painter.drawPixmap(dest_rect, middle_pixmap, source_rect)

    output_pixmap = QPixmap(int(orig_capture_width), int(orig_capture_height))
    output_pixmap.fill(Qt.transparent)
    op = QPainter()
    op.begin(output_pixmap)
    dest_rect = QRectF(QPointF(0, 0), capture_size.size())
    dest_rect.moveCenter(QPointF(orig_capture_width/2, orig_capture_height/2))
    op.drawPixmap(dest_rect, middle_pixmap, source_rect)
    op.end()

    return output_pixmap

def copy_image_file_to_clipboard(filepath):
    # засовывает содержимое картинки в буфер,
    # чтобы можно было вставить в браузере или телеге
    if os.path.exists(filepath):
        app = QApplication.instance()
        data = QMimeData()
        url = QUrl.fromLocalFile(filepath)
        data.setUrls([url])
        app.clipboard().setMimeData(data)

def squarize_rect(rect):
    min_length = min(rect.width(), rect.height())
    _output_rect = QRectF(0, 0, min_length, min_length)
    _output_rect.moveCenter(rect.center())
    return _output_rect


def calculate_tangent_points(c1, r1, c2, r2):
    center_position_values = [c1, c2]
    radius_values = [r1, r2]

    radius_max = max(radius_values)
    radius_min = min(radius_values)
    radius_diff = radius_max - radius_min

    p1 = center_position_values[0]
    p2 = center_position_values[1]
    distance = math.hypot(p1.x()-p2.x(), p1.y() - p2.y())
    sinus_alpha = radius_diff/abs(distance)

    position_angle = math.atan2(p1.x()-p2.x(), p1.y() - p2.y())

    if radius_values[0] > radius_values[1]:
        factor = 1.0
    else:
        factor = -1.0

    def get_tangent_line_points(radians_angle):
        points_on_circles = []
        for n, (center_pos, radius) in enumerate(zip(center_position_values, radius_values)):
            radius_length = radius
            x = math.cos(radians_angle)*radius_length
            y = math.sin(radians_angle)*radius_length
            radius_vector = QPointF(x, y)
            point_on_circle = center_pos + radius_vector
            points_on_circles.append(point_on_circle)
        return points_on_circles

    tangent_lines = []

    try:
        radians_angle = math.asin(sinus_alpha)
    except:
        radians_angle = 0
    radians_angle += - position_angle - math.pi/2 - math.pi/2*factor

    tangent_lines.append(get_tangent_line_points(radians_angle))

    try:
        # !!! отличается знаком минус
        radians_angle = - math.asin(sinus_alpha)
    except:
        radians_angle = 0
        # !!! отличается знаком плюс
    radians_angle += - position_angle + math.pi/2 - math.pi/2*factor

    tangent_lines.append(get_tangent_line_points(radians_angle))

    return tangent_lines
