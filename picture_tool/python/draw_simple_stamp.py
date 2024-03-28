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

from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import sys
import os
import random
import string
import time
import ctypes
import subprocess
import datetime

def menu_items():
    items = (
        "today_date",
    )
    return items

def draw_handler(self, painter, inside_text, step=0):
    # color = QColor(200, 0, 0)
    color = QColor(0, 0, 200)
    # color = QColor(255, 160, 0)

    painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)

    font = painter.font()
    font.setPixelSize(30)
    font.setWeight(1900)
    font.setFamily("Consolas")
    painter.setFont(font)
    now = datetime.datetime.now()
    year = str(now.year)
    month = now.month
    month = {
        1: "Января",
        2: "Февраля",
        3: "Марта",
        4: "Апреля",
        5: "Мая",
        6: "Июня",
        7: "Июля",
        8: "Августа",
        9: "Сентября",
        10: "Октября",
        11: "Ноября",
        12: "Декабря",
    }[month]
    day = str(now.day)

    c = self.rect().center()
    painter.setPen(QPen(color))

    t = "{} {}\n{}".format(day, month , year)
    # painter.drawText(self.rect().adjusted(5, 5, -5, -5), Qt.AlignBottom | Qt.AlignHCenter, t)
    painter.drawText(self.rect().adjusted(5, 5, -5, -5), Qt.AlignCenter, t)

    x = int(self.rect().height()/4)
    rect = self.rect().adjusted(0, x, 0, -x)
    pen = painter.pen()
    pen.setWidth(5)
    pen.setCapStyle(Qt.FlatCap)
    pen.setJoinStyle(Qt.MiterJoin)
    painter.setPen(pen)
    painter.drawRect(rect.adjusted(5, 5, -5, -5))

    pen = painter.pen()
    pen.setWidth(1)
    painter.setPen(pen)
    painter.drawRect(rect.adjusted(10, 10, -10, -10))

    filepath = os.path.normpath(os.path.join(os.path.dirname(__file__), "mask2.png"))
    image = QImage(filepath)
    painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)
    painter.drawImage(self.rect(), image)

class MyWidget(QWidget):

    def __init__(self):
        super().__init__()
        self.timer = QTimer()
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.window_handler)
        self.timer.start()
        self.dir = 1
        self.step = 0
        texts = menu_items()
        self.chosen_text = random.choice(texts)

    def window_handler(self):
        if self.step > 20:
            self.dir = -1
        elif self.step < -20:
            self.dir = 1
        self.step += self.dir
        self.update()

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        draw_handler(self, painter, self.chosen_text, step=self.step)
        painter.end()

if __name__ == "__main__":

    app = QApplication(sys.argv)

    w = MyWidget()
    w.show()

    app.exec_()
    sys.exit()
