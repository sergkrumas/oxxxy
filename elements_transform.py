
from enum import Enum
import math
import datetime
import sys
import os
import itertools
import json


from PyQt5.QtWidgets import (QSystemTrayIcon, QWidget, QMessageBox, QMenu, QGraphicsPixmapItem,
    QGraphicsScene, QFileDialog, QHBoxLayout, QCheckBox, QVBoxLayout, QTextEdit, QGridLayout,
    QPushButton, QGraphicsBlurEffect, QLabel, QApplication, QScrollArea, QDesktopWidget)
from PyQt5.QtCore import (QUrl, QMimeData, pyqtSignal, QPoint, QPointF, pyqtSlot, QRect, QEvent,
    QTimer, Qt, QSize, QSizeF, QRectF, QThread, QAbstractNativeEventFilter, QAbstractEventDispatcher,
    QFile, QDataStream, QIODevice)
from PyQt5.QtGui import (QPainterPath, QColor, QKeyEvent, QMouseEvent, QBrush, QPixmap,
    QPaintEvent, QPainter, QWindow, QPolygon, QImage, QTransform, QPen, QLinearGradient,
    QIcon, QFont, QCursor, QPolygonF, QVector2D)

from _utils import (convex_hull, check_scancode_for, SettingsJson,
     generate_metainfo, build_valid_rect, build_valid_rectF, dot, get_nearest_point_on_rect, get_creation_date,
     find_browser_exe_file, open_link_in_browser, open_in_google_chrome, save_meta_info,
     make_screenshot_pyqt, webRGBA, generate_gradient, draw_shadow, draw_cyberpunk,
     elements45DegreeConstraint, get_bounding_points, load_svg, is_webp_file_animated)


class ElementsTransformMixin():

    def elementsInitTransform(self):

        self.selection_color = QColor(18, 118, 127)
        #
        self.start_translation_pos = None
        self.translation_ongoing = False
        self.rotation_activation_areas = []
        self.rotation_ongoing = False
        self.scaling_ongoing = False
        self.scaling_vector = None
        self.proportional_scaling_vector = None
        self.scaling_pivot_point = None
        #
        self.selection_rect = None
        self.selection_start_point = None
        self.selection_ongoing = False
        self.selected_items = []
        self.selection_bounding_box = None

        self.transform_cancelled = False


        self.canvas_selection_transform_box_opacity = 1.0
        self.STNG_transform_widget_activation_area_size = 16.0

        self.canvas_debug_transform_widget = False



    def update_selection_bouding_box(self):
        self.selection_bounding_box = None
        if len(self.selected_items) == 1:
            self.selection_bounding_box = self.selected_items[0].get_selection_area(canvas=self)
        elif len(self.selected_items) > 1:
            bounding_box = QRectF()
            for element in self.selected_items:
                bounding_box = bounding_box.united(element.get_selection_area(canvas=self).boundingRect())
            self.selection_bounding_box = QPolygonF([
                bounding_box.topLeft(),
                bounding_box.topRight(),
                bounding_box.bottomRight(),
                bounding_box.bottomLeft(),
            ])

    def any_element_area_under_mouse(self, add_selection):
        self.prevent_item_deselection = False
        elements = self.elementsHistoryFilter()

        min_item = self.find_min_area_element(elements, self.mapped_cursor_pos())
        # reversed для того, чтобы картинки на переднем плане чекались первыми
        for element in reversed(elements):
            element_selection_area = element.get_selection_area(canvas=self)
            is_under_mouse = element_selection_area.containsPoint(self.mapped_cursor_pos(), Qt.WindingFill)

            if is_under_mouse and not element._selected:
                if not add_selection:
                    for bi in elements:
                        bi._selected = False

                element._selected = True
                # вытаскиваем айтем на передний план при отрисовке
                # закоменчено, потому что это может навредить истории действий
                # elements.remove(element)
                # elements.append(element)
                self.prevent_item_deselection = True
                return True
            if is_under_mouse and element._selected:
                return True
        return False

    def find_min_area_element(self, elements, pos):
        found_elements = self.find_all_elements_under_this_pos(elements, pos)
        found_elements = list(sorted(found_elements, key=lambda x: x.calc_area))
        if found_elements:
            return found_elements[0]
        return None

    def find_all_elements_under_this_pos(self, elements, pos):
        undermouse_elements = []
        for element in elements:
            element_selection_area = element.get_selection_area(canvas=self)
            is_under_mouse = element_selection_area.containsPoint(pos, Qt.WindingFill)
            if is_under_mouse:
                undermouse_elements.append(element)
        return undermouse_elements



    def is_over_rotation_activation_area(self, position):
        for index, raa in self.rotation_activation_areas:
            if raa.containsPoint(position, Qt.WindingFill):
                self.widget_active_point_index = index
                return True
        self.widget_active_point_index = None
        return False

    def is_over_scaling_activation_area(self, position):
        if self.selection_bounding_box is not None:
            enumerated = list(enumerate(self.selection_bounding_box))
            enumerated.insert(0, enumerated.pop(2))
            for index, point in enumerated:
                diff = point - QPointF(position)
                if QVector2D(diff).length() < self.STNG_transform_widget_activation_area_size:
                    self.scaling_active_point_index = index
                    self.widget_active_point_index = index
                    return True
        self.scaling_active_point_index = None
        self.widget_active_point_index = None
        return False




    def canvas_selection_callback(self, add_to_selection):
        if self.selection_rect is not None:
            selection_rect_area = QPolygonF(self.selection_rect)
            for element in self.elementsHistoryFilter():
                element_selection_area = element.get_selection_area(canvas=self)
                if element_selection_area.intersects(selection_rect_area):
                    element._selected = True
                else:
                    if add_to_selection and element._selected:
                        pass
                    else:
                        element._selected = False
        else:
            min_item = self.find_min_area_element(self.elementsHistoryFilter(), self.mapped_cursor_pos())
            # reversed для того, чтобы картинки на переднем плане чекались первыми
            for element in reversed(self.elementsHistoryFilter()):
                item_selection_area = element.get_selection_area(canvas=self)
                is_under_mouse = item_selection_area.containsPoint(self.mapped_cursor_pos(), Qt.WindingFill)
                if add_to_selection and element._selected:
                    # subtract item from selection!
                    if is_under_mouse and not self.prevent_item_deselection:
                        element._selected = False
                else:
                    if min_item is not element:
                        element._selected = False
                    else:
                        element._selected = is_under_mouse
        self.init_selection_bounding_box_widget(current_folder)

    def init_selection_bounding_box_widget(self):
        self.selected_items = []
        for element in self.elementsHistoryFilter():
            if element._selected:
                self.selected_items.append(element)
        self.update_selection_bouding_box()

    def canvas_START_selected_elements_TRANSLATION(self, event_pos, viewport_zoom_changed=False):
        self.start_translation_pos = self.elementsMapFromViewportToCanvas(event_pos)
        if viewport_zoom_changed:
            for element in self.elementsHistoryFilter():
                element.element_position = element.__element_position

        for element in self.elementsHistoryFilter():
            element.__element_position = QPointF(element.element_position)
            if not viewport_zoom_changed:
                element.__element_position_init = QPointF(element.element_position)
            element._children_items = []
            # if element.type == BoardItem.types.ITEM_FRAME:
            #     this_frame_area = element.calc_area
            #     item_frame_area = element.get_selection_area(canvas=self)
                # for el in self.elementsHistoryFilter():
                #     el_area = el.get_selection_area(canvas=self)
                #     center_point = el_area.boundingRect().center()
                #     if item_frame_area.containsPoint(QPointF(center_point), Qt.WindingFill):
                #         if el.type != BoardItem.types.ITEM_FRAME or (el.type == BoardItem.types.ITEM_FRAME and el.calc_area < this_frame_area):
                #             board_item._children_items.append(el)

    def canvas_DO_selected_elements_TRANSLATION(self, event_pos):
        if self.start_translation_pos:
            self.translation_ongoing = True
            delta = QPointF(self.elementsMapFromViewportToCanvas(event_pos)) - self.start_translation_pos
            for element in self.elementsHistoryFilter():
                if element._selected:
                    element.element_position = element.__element_position + delta
                    # if element.type == BoardItem.types.ITEM_FRAME:
                    #     for ch_bi in element._children_items:
                    #         ch_bi.element_position = ch_bi.__element_position + delta
            self.init_selection_bounding_box_widget()
        else:
            self.translation_ongoing = False

    def canvas_FINISH_selected_elements_TRANSLATION(self, event, cancel=False):
        self.start_translation_pos = None
        for element in self.elementsHistoryFilter():
            if cancel:
                element.element_position = QPointF(element.__element_position_init)
            else:
                element.__element_position = None
            element._children_items = []
        self.translation_ongoing = False

    def canvas_CANCEL_selected_elements_TRANSLATION(self):
        if self.translation_ongoing:
            self.canvas_FINISH_selected_elements_TRANSLATION(None, cancel=True)
            self.update_selection_bouding_box()
            self.transform_cancelled = True
            print('cancel translation')






# для запуска программы прямо из этого файла при разработке и отладке
if __name__ == '__main__':
    import subprocess
    subprocess.Popen([sys.executable, "-u", "oxxxy.py"])
    sys.exit()
