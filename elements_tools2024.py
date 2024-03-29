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

from _utils import (build_valid_rectF,)

from PyQt5.QtCore import (Qt, QPointF)
from PyQt5.QtGui import (QPen, QColor)

class Elements2024Mixin():

    def elementsDrawArrowsTreeNode(self, painter, element, final):
        if not final:
            painter.setTransform(element.get_transform_obj(canvas=self))

            capture_rect = build_valid_rectF(element.local_start_point, element.local_end_point)
            painter.setBrush(Qt.NoBrush)
            color = QColor(Qt.magenta)
            # color.setAlpha(20)
            painter.setPen(QPen(color, 1))
            painter.drawRect(capture_rect)

            a = QPointF(0, -100)
            b = QPointF(0, 100)
            a1 = QPointF(-20, 35)
            a2 = QPointF(20, 35)
            painter.drawLine(a, b)
            painter.drawLine(a, a+a1)
            painter.drawLine(a, a+a2)

            painter.resetTransform()

# для запуска программы прямо из этого файла при разработке и отладке
if __name__ == '__main__':
    import subprocess
    subprocess.Popen([sys.executable, "-u", "oxxxy.py"])
    sys.exit()
