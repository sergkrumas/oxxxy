

from PyQt5.QtWidgets import (QApplication,)
from PyQt5.QtCore import (QPointF, QEvent, Qt)
from PyQt5.QtGui import (QPainterPath, QColor, QKeyEvent, QMouseEvent, QBrush, QPixmap,
    QPaintEvent, QPainter, QWindow, QPolygon, QImage, QTransform, QPen, QLinearGradient,
    QIcon, QFont, QCursor, QPolygonF, QVector2D, QFontDatabase)


from elements import ToolID

import time
import random

class EditorAutotestMixin():

    def animated_tool_drawing(self, tool_id, a, b, randomize=True):
        if self.tools_window.current_tool != tool_id:
            self.tools_window.set_current_tool(tool_id)

        points = []
        count = 10
        delta = b - a
        for n in range(count+1):
            ratio = n/count
            pos = a + delta*ratio
            points.append(self.elementsMapToViewport(pos))

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
