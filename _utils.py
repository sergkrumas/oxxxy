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

import psutil
from PIL import Image, ImageGrab, PngImagePlugin

from PyQt5.QtWidgets import (QWidget, QMessageBox, QDesktopWidget, QApplication)
from PyQt5.QtCore import (QRectF, QPoint, pyqtSignal, QSizeF, Qt, QPointF, QSize, QRect)
from PyQt5.QtGui import (QPixmap, QBrush, QRegion, QImage, QRadialGradient, QColor,
                    QGuiApplication, QPen, QPainterPath, QPolygon, QLinearGradient, QPainter)


win32process = None
if os.name == 'nt': # only for win32
    try:
        win32process = __import__("win32process")
    except ModuleNotFoundError:
        pass

__all__ = (
    'ch_left_index',
    'ch_orientation',

    'convex_hull',

    'check_scancode_for',

    'SettingsJson',

    'get_meta_info',
    'build_valid_rect',
    'dot',
    'get_nearest_point_on_rect',
    'get_creation_date',
    'find_browser_exe_file',
    'open_link_in_browser',
    'open_in_google_chrome',
    'save_meta_info',

    # 'make_screenshot_ImageGrab',
    'make_screenshot_pyqt',

    'CustomSlider',
    'webRGBA',
    'generate_gradient',
    'draw_shadow',
    'draw_cyberpunk',
    'elements45DegreeConstraint',

    # 'TransformWidgetPoint',
    'TransformWidget'
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
            # if points[i].y > points[minn].y:
            # это не работает для моего случая, поэтому изменено на нижний вариант
            if points[i].y() < points[minn].y():
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
    while True:

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
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(SettingsJson, cls).__new__(cls)
        return cls.instance

    def set_mode(self, debug_mode):
        self.debug_mode = debug_mode
        return self

    def get_filepath(self):
        if self.dubug_mode:
            root = os.path.dirname(__file__)
        else:
            root = os.path.expanduser("~")
        return os.path.join(root, "oxxxy_settings.json")

    def __init__(self):
        super().__init__()
        self.dubug_mode = False
        self.data = {}

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

    def get_data(self, key):
        self.read_data()
        return self.data.get(key, {})

def get_meta_info():
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

def build_valid_rect(p1, p2):
    MAX = sys.maxsize
    left = MAX
    right = -MAX
    top = MAX
    bottom = -MAX
    for p in [p1, p2]:
        left = min(p.x(), left)
        right = max(p.x(), right)
        top = min(p.y(), top)
        bottom = max(p.y(), bottom)
    return QRect(QPoint(int(left), int(top)), QPoint(int(right), int(bottom)))

def dot(p1, p2):
    return p1.x()*p2.x() + p1.y()*p2.y()

def get_nearest_point_on_rect(r, cursor):
    def length(a, b):
        delta = a - b
        return math.sqrt(math.pow(delta.x(), 2)+math.pow(delta.y(), 2))
    def create_points(a, b):
        a = QPointF(a)
        b = QPointF(b)
        ps = []
        count = int(length(a, b)/10)
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
        delta_length = length(cursor, p)
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

def save_meta_info(metadata, filepath_string):
    m0 = metadata[0]
    m1 = metadata[1]
    metastring = f"Screenshot metadata: {m0} {m1}"
    info = PngImagePlugin.PngInfo()
    info.add_text("text", metastring)
    im = Image.open(filepath_string)
    im.save(filepath_string, "PNG", pnginfo=info)

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
    # pixmap = QPixmap(all_monitors_zone.size())

    pixmap = QImage(
        all_monitors_zone.width(),
        all_monitors_zone.height(),
        QImage.Format_RGB32
    )
    pixmap.fill(Qt.black)

    painter = QPainter()
    painter.begin(pixmap)
    screens = QGuiApplication.screens()
    for n, screen in enumerate(screens):
        p = screen.grabWindow(0)
        source_rect = QRect(QPoint(0, 0), screen.geometry().size())
        painter.drawPixmap(screen.geometry(), p, source_rect)
    painter.end()
    return pixmap
    # return pixmap.toImage()

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
    target = QRect(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, gradient_pxm.rect())

    gradient_pxm = generate_gradient("bottom", shadow_size, color1_hex, color2_hex)
    top_left = sr.bottomLeft() + QPoint(1, 0)
    bottom_right = sr.bottomRight() + QPoint(-1, -shadow_size)
    target = QRect(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, gradient_pxm.rect())

    gradient_pxm = generate_gradient("left", shadow_size, color1_hex, color2_hex)
    top_left = sr.topLeft() + QPoint(-shadow_size, 1)
    bottom_right = sr.bottomLeft() + QPoint(0, -1)
    target = QRect(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, gradient_pxm.rect())

    gradient_pxm = generate_gradient("right", shadow_size, color1_hex, color2_hex)
    top_left = sr.topRight() + QPoint(0, 1)
    bottom_right = sr.bottomRight() + QPoint(shadow_size, -1)
    target = QRect(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, gradient_pxm.rect())

    # rectangle corners
    gradient_pxm = generate_gradient("top_left", shadow_size, color1_hex, color2_hex)
    top_left = sr.topLeft() + QPoint(-shadow_size, -shadow_size)
    bottom_right = sr.topLeft() + QPoint(0, 0)
    target = QRect(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, gradient_pxm.rect())

    gradient_pxm = generate_gradient("top_right", shadow_size, color1_hex, color2_hex)
    top_left = sr.topRight() + QPoint(0, -shadow_size)
    bottom_right = sr.topRight() + QPoint(shadow_size, 0)
    target = QRect(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, gradient_pxm.rect())

    gradient_pxm = generate_gradient("bottom_right", shadow_size, color1_hex, color2_hex)
    top_left = sr.bottomRight() + QPoint(0, 0)
    bottom_right = sr.bottomRight() + QPoint(shadow_size, shadow_size)
    target = QRect(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, gradient_pxm.rect())

    gradient_pxm = generate_gradient("bottom_left", shadow_size, color1_hex, color2_hex)
    top_left = sr.bottomLeft() + QPoint(-shadow_size, 0)
    bottom_right = sr.bottomLeft() + QPoint(0, -shadow_size)
    target = QRect(top_left, bottom_right)
    painter.drawPixmap(target, gradient_pxm, gradient_pxm.rect())

def draw_cyberpunk(painter, image_rect):
    # draw lines
    painter.setPen(QPen(QColor(255, 255 ,255 ,25), 2))
    offset = image_rect.topLeft()
    w = image_rect.width()
    h = image_rect.height()
    # vertical
    painter.drawLine(QPoint(int(w/3), 0)+offset, QPoint(int(w/3), h)+offset)
    painter.drawLine(QPoint(int(w/3*2), 0)+offset, QPoint(int(w/3*2), h)+offset)
    # horizontal
    painter.drawLine(QPoint(0, int(h/3))+offset, QPoint(w, int(h/3))+offset)
    painter.drawLine(QPoint(0, int(h/3*2))+offset, QPoint(w, int(h/3*2))+offset)


def elements45DegreeConstraint(pivot, point):
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
            if QApplication.queryKeyboardModifiers() & Qt.ShiftModifier:
                pp = self.get_pivot_point().point
                event_pos = elements45DegreeConstraint(pp, event_pos).toPoint()
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
