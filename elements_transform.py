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

from enum import Enum
import math
import datetime
import sys
import os
import itertools
import json
import functools



from PyQt5.QtWidgets import (QSystemTrayIcon, QWidget, QMessageBox, QMenu, QGraphicsPixmapItem,
    QGraphicsScene, QFileDialog, QHBoxLayout, QCheckBox, QVBoxLayout, QTextEdit, QGridLayout,
    QPushButton, QGraphicsBlurEffect, QLabel, QApplication, QScrollArea, QDesktopWidget)
from PyQt5.QtCore import (QUrl, QMimeData, pyqtSignal, QPoint, QPointF, pyqtSlot, QRect, QEvent,
    QTimer, Qt, QSize, QSizeF, QRectF, QThread, QAbstractNativeEventFilter, QAbstractEventDispatcher,
    QFile, QDataStream, QIODevice)
from PyQt5.QtGui import (QPainterPath, QColor, QKeyEvent, QMouseEvent, QBrush, QPixmap,
    QPaintEvent, QPainter, QWindow, QPolygon, QImage, QTransform, QPen, QLinearGradient,
    QIcon, QFont, QCursor, QPolygonF, QVector2D)

from _utils import (convex_hull, check_scancode_for, SettingsJson, generate_metainfo,
     build_valid_rect, build_valid_rectF, dot, get_nearest_point_on_rect, get_creation_date,
     find_browser_exe_file, open_link_in_browser, open_in_google_chrome, save_meta_info,
     make_screenshot_pyqt, webRGBA, generate_gradient, draw_shadow, draw_cyberpunk,
     get_bounding_points, load_svg, is_webp_file_animated)


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

        self.prevent_item_deselection = False

        self.canvas_debug_transform_widget = False

        self.scale_rastr_source = None
        self.rotate_rastr_source = None
        self.translate_rastr_source = None
        self.load_svg_cursors()

        self.cyclic_select_activated = False

    def load_svg_cursors(self):
        folder_path = os.path.dirname(__file__)
        filepath_scale_svg = os.path.join(folder_path, "cursors", "scale.svg")
        filepath_rotate_svg = os.path.join(folder_path, "cursors", "rotate.svg")
        filepath_translate_svg = os.path.join(folder_path, "cursors", "translate.svg")

        scale_rastr_source = QPixmap(filepath_scale_svg)
        rotate_rastr_source = QPixmap(filepath_rotate_svg)
        translate_rastr_source = QPixmap(filepath_translate_svg)

        if not scale_rastr_source.isNull():
            self.scale_rastr_source = scale_rastr_source
        if not rotate_rastr_source.isNull():
            self.rotate_rastr_source = rotate_rastr_source
        if not translate_rastr_source.isNull():
            self.translate_rastr_source = translate_rastr_source

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


    def find_min_area_element(self, elements, pos):
        found_elements = self.find_all_elements_under_this_pos(elements, pos)
        found_elements = list(sorted(found_elements, key=lambda x: x.calc_area))
        if found_elements:
            return found_elements[0]
        return None

    def find_all_elements_under_this_pos(self, elements, pos):
        undermouse_elements = []
        for element in elements:
            if element.type in [self.ToolID.removing]:
                continue
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

    def is_over_translation_activation_area(self, position):
        for element in self.selected_items:
            sa = element.get_selection_area(canvas=self)
            if sa.containsPoint(position, Qt.WindingFill):
                return True
        return False

    def widget_get_cursor_angle(self):
        points_count = self.selection_bounding_box.size()
        index = self.widget_active_point_index
        pivot_point_index = (index+2) % points_count
        prev_point_index = (pivot_point_index-1) % points_count
        next_point_index = (pivot_point_index+1) % points_count
        prev_point = self.selection_bounding_box[prev_point_index]
        next_point = self.selection_bounding_box[next_point_index]
        self.scaling_pivot_corner_point = QPointF(self.selection_bounding_box[pivot_point_index])

        x_axis = QVector2D(next_point - self.scaling_pivot_corner_point).normalized().toPointF()
        y_axis = QVector2D(prev_point - self.scaling_pivot_corner_point).normalized().toPointF()

        __vector  = x_axis + y_axis
        return math.degrees(math.atan2(__vector.y(), __vector.x()))

    def get_widget_cursor(self, source_pixmap, angle):
        pixmap = QPixmap(source_pixmap.size())
        pixmap.fill(Qt.transparent)
        painter = QPainter()
        painter.begin(pixmap)
        transform = QTransform()
        transform1 = QTransform()
        transform2 = QTransform()
        transform3 = QTransform()
        rect = QRectF(source_pixmap.rect())
        center = rect.center()
        transform1.translate(-center.x(), -center.y())
        transform2.rotate(angle)
        transform3.translate(center.x(), center.y())
        transform = transform1 * transform2 * transform3
        painter.setTransform(transform)
        painter.drawPixmap(rect, source_pixmap, rect)
        painter.end()
        pixmap = pixmap.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QCursor(pixmap)

    @functools.cache
    def get_widget_translation_cursor(self):
        pixmap = self.translate_rastr_source.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QCursor(pixmap)

    def define_transform_tool_cursor(self):
        if self.scaling_ongoing:
            if self.scale_rastr_source is not None:
                cursor = self.get_widget_cursor(self.scale_rastr_source, self.widget_get_cursor_angle())
                return cursor
            else:
                return Qt.PointingHandCursor
        elif self.rotation_ongoing:
            if self.rotate_rastr_source is not None:
                cursor = self.get_widget_cursor(self.rotate_rastr_source, self.widget_get_cursor_angle())
                return cursor
            else:
                return Qt.OpenHandCursor
        elif self.selection_bounding_box is not None:
            if self.is_over_scaling_activation_area(self.mapped_cursor_pos()):
                cursor = self.get_widget_cursor(self.scale_rastr_source, self.widget_get_cursor_angle())
                return cursor

            elif self.is_over_rotation_activation_area(self.mapped_cursor_pos()):
                cursor = self.get_widget_cursor(self.rotate_rastr_source, self.widget_get_cursor_angle())
                return cursor
            elif self.is_over_translation_activation_area(self.mapped_cursor_pos()):
                cursor = self.get_widget_translation_cursor()
                return cursor
            else:
                return Qt.ArrowCursor
        else:
            return Qt.ArrowCursor

    def any_element_area_under_mouse(self, add_selection):
        self.prevent_item_deselection = False
        self.cyclic_select_activated = QApplication.queryKeyboardModifiers() & Qt.ControlModifier
        if self.cyclic_select_activated:
            return False

        elements = self.elementsFilterElementsForSelection()
        # reversed для того, чтобы пометки на переднем плане чекались первыми
        for element in reversed(elements):
            if element.type in [self.ToolID.removing]:
                continue
            element_selection_area = element.get_selection_area(canvas=self)
            is_under_mouse = element_selection_area.containsPoint(self.mapped_cursor_pos(), Qt.WindingFill)
            if is_under_mouse and element._selected:
                self.active_element = element
                return True
            if is_under_mouse and not element._selected:
                if not add_selection:
                    for el in elements:
                        el._selected = False
                element._selected = True
                self.active_element = element
                self.prevent_item_deselection = True
                # self.init_selection_bounding_box_widget() # может пригодится для отладки
                return True
        return False

    def canvas_selection_callback(self, add_to_selection):
        elements = self.elementsFilterElementsForSelection()
        if self.selection_rect is not None:
            # выделение через рамку выделения
            selection_rect_area = QPolygonF(self.selection_rect)
            for element in elements:
                if element.type in [self.ToolID.removing]:
                    continue
                element_selection_area = element.get_selection_area(canvas=self)
                if element_selection_area.intersects(selection_rect_area):
                    element._selected = True
                else:
                    if add_to_selection and element._selected:
                        pass
                    else:
                        element._selected = False
        else:
            # выделение кликом без рамки выделения
            if self.cyclic_select_activated:
                self.cyclic_select()
                self.cyclic_select_activated = False
            else:
                min_area_element = self.find_min_area_element(elements, self.mapped_cursor_pos())
                # reversed для того, чтобы пометки на переднем плане чекались первыми
                for element in reversed(elements):
                    if element.type in [self.ToolID.removing]:
                        continue
                    item_selection_area = element.get_selection_area(canvas=self)
                    is_under_mouse = item_selection_area.containsPoint(self.mapped_cursor_pos(), Qt.WindingFill)
                    if add_to_selection and element._selected:
                        # subtract element from selection!
                        if is_under_mouse and not self.prevent_item_deselection:
                            element._selected = False
                            self.active_element = None
                    else:
                        if min_area_element is not element:
                            element._selected = False
                            self.active_element = None
                        else:
                            element._selected = is_under_mouse
                            if is_under_mouse:
                                self.active_element = element


        self.init_selection_bounding_box_widget()
        self.elementsUpdatePanelUI()

    def cyclic_select(self):
        elements = self.elementsFilterElementsForSelection()
        undermouse_elements = []
        for element in elements:
            sa = element.get_selection_area(canvas=self)
            is_cursor_over_element = sa.containsPoint(self.mapped_cursor_pos(), Qt.WindingFill)
            if is_cursor_over_element:
                undermouse_elements.append(element)

        # reversed для того, чтобы пометки на переднем плане чекались первыми

        under_mouse_selected = [uel for uel in undermouse_elements if uel._selected]
        any_selected = len(under_mouse_selected) > 0
        if any_selected:

            current = under_mouse_selected[0]
            # циклический выбор перекрывадющих друг друга элементов в позиции курсора мыши
            els = itertools.cycle(undermouse_elements)
            if len(undermouse_elements) > 1:
                while next(els) != current:
                    pass
                next_element = next(els)
                next_element._selected = True
                current._selected = False

        elif undermouse_elements:
            undermouse_elements[0]._selected = True


    def init_selection_bounding_box_widget(self):
        self.selected_items = []
        for element in self.elementsHistoryFilter():
            if element._selected and element.type not in [self.ToolID.removing]:
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








    def canvas_START_selected_elements_ROTATION(self, event_pos, viewport_zoom_changed=False):
        self.rotation_ongoing = True
        if viewport_zoom_changed:
            for element in self.selected_items:
                pass
                # лучше закоментить этот код, так адекватнее и правильнее, как мне кажется
                # if element.__element_rotation is not None:
                #     element.element_rotation = element.__element_rotation
                # if bi.type != BoardItem.types.ITEM_FRAME:
                    # if bi.__item_position is not None:
                    #     bi.item_position = bi.__item_position
            self.update_selection_bouding_box()

        self.__selection_bounding_box = QPolygonF(self.selection_bounding_box)
        pivot = self.selection_bounding_box.boundingRect().center()
        radius_vector = QPointF(event_pos) - pivot
        self.rotation_start_angle_rad = math.atan2(radius_vector.y(), radius_vector.x())
        for element in self.selected_items:
            element.__element_rotation = element.element_rotation
            element.__element_position = QPointF(element.element_position)

            if not viewport_zoom_changed:
                element.__element_rotation_init = element.element_rotation
                element.__element_position_init = QPointF(element.element_position)

    def step_rotation(self, rotation_value):
        interval = 45.0
        # формулу подбирал в графическом калькуляторе desmos.com/calculator
        # value = math.floor((rotation_value-interval/2.0)/interval)*interval+interval
        # ниже упрощённый вариант
        value = (math.floor(rotation_value/interval-0.5)+1.0)*interval
        return value

    def canvas_DO_selected_elements_ROTATION(self, event_pos):
        self.start_translation_pos = None

        multi_element_mode = len(self.selected_items) > 1
        ctrl_mod = QApplication.queryKeyboardModifiers() & Qt.ControlModifier
        pivot = self.selection_bounding_box.boundingRect().center()
        radius_vector = QPointF(event_pos) - pivot
        self.rotation_end_angle_rad = math.atan2(radius_vector.y(), radius_vector.x())
        self.rotation_delta = self.rotation_end_angle_rad - self.rotation_start_angle_rad
        rotation_delta_degrees = math.degrees(self.rotation_delta)
        if multi_element_mode and ctrl_mod:
            rotation_delta_degrees = self.step_rotation(rotation_delta_degrees)
        rotation = QTransform()
        if ctrl_mod:
            rotation.rotate(self.step_rotation(rotation_delta_degrees))
        else:
            rotation.rotate(rotation_delta_degrees)
        for element in self.selected_items:
            # rotation component
            # if element.type == BoardItem.types.ITEM_FRAME:
            #     continue
            element.element_rotation = element.__element_rotation + rotation_delta_degrees
            if not multi_element_mode and ctrl_mod:
                element.element_rotation = self.step_rotation(element.element_rotation)
            # position component
            pos = element.calculate_absolute_position(canvas=self, rel_pos=element.__element_position)
            pos_radius_vector = pos - pivot
            pos_radius_vector = rotation.map(pos_radius_vector)
            new_absolute_position = pivot + pos_radius_vector
            rel_pos_global_scaled = new_absolute_position - self.canvas_origin
            new_item_position = QPointF(rel_pos_global_scaled.x()/self.canvas_scale_x, rel_pos_global_scaled.y()/self.canvas_scale_y)
            element.element_position = new_item_position
        # bounding box transformation
        translate_to_coord_origin = QTransform()
        translate_back_to_place = QTransform()
        offset = - self.__selection_bounding_box.boundingRect().center()
        translate_to_coord_origin.translate(offset.x(), offset.y())
        offset = - offset
        translate_back_to_place.translate(offset.x(), offset.y())
        transform = translate_to_coord_origin * rotation * translate_back_to_place
        self.selection_bounding_box = transform.map(self.__selection_bounding_box)

    def canvas_FINISH_selected_elements_ROTATION(self, event, cancel=False):
        self.rotation_ongoing = False
        if cancel:
            for element in self.selected_items:
                element.element_rotation = element.__element_rotation_init
                element.element_position = QPointF(element.__element_position_init)
        else:
            self.init_selection_bounding_box_widget()

    def canvas_CANCEL_selected_elements_ROTATION(self):
        if self.rotation_ongoing:
            self.canvas_FINISH_selected_elements_ROTATION(None, cancel=True)
            self.update_selection_bouding_box()
            self.transform_cancelled = True
            self.update()
            print('cancel rotation')






    def canvas_START_selected_elements_SCALING(self, event, viewport_zoom_changed=False):
        self.scaling_ongoing = True

        if viewport_zoom_changed:
            for element in self.selected_items:
                if element.__element_scale_x is not None:
                    element.element_scale_x = element.__element_scale_x
                if element.__element_scale_y is not None:
                    element.element_scale_y = element.__element_scale_y
                if element.__element_position is not None:
                    element.element_position = element.__element_position

            self.update_selection_bouding_box()

        self.__selection_bounding_box = QPolygonF(self.selection_bounding_box)

        bbw = self.selection_bounding_box.boundingRect().width()
        bbh = self.selection_bounding_box.boundingRect().height()
        self.selection_bounding_box_aspect_ratio = bbw/bbh
        self.selection_bounding_box_center = self.selection_bounding_box.boundingRect().center()

        points_count = self.selection_bounding_box.size()

        # заранее высчитываем пивот и оси для модификатора Alt;
        # для удобства вычислений оси заимствуем у нулевой точки и укорачиваем их в два раза
        index = 0
        pivot_point_index = (index+2) % points_count
        prev_point_index = (pivot_point_index-1) % points_count
        next_point_index = (pivot_point_index+1) % points_count
        prev_point = self.selection_bounding_box[prev_point_index]
        next_point = self.selection_bounding_box[next_point_index]
        spp = QPointF(self.selection_bounding_box[pivot_point_index])

        self.scaling_pivot_center_point = self.selection_bounding_box_center

        __x_axis = QVector2D(next_point - spp).toPointF()
        __y_axis = QVector2D(prev_point - spp).toPointF()

        self.scaling_from_center_x_axis = __x_axis/2.0
        self.scaling_from_center_y_axis = __y_axis/2.0

        # высчитываем пивот и оси для обычного скейла относительно угла
        index = self.scaling_active_point_index
        pivot_point_index = (index+2) % points_count
        prev_point_index = (pivot_point_index-1) % points_count
        next_point_index = (pivot_point_index+1) % points_count
        prev_point = self.selection_bounding_box[prev_point_index]
        next_point = self.selection_bounding_box[next_point_index]
        self.scaling_pivot_corner_point = QPointF(self.selection_bounding_box[pivot_point_index])

        x_axis = QVector2D(next_point - self.scaling_pivot_corner_point).toPointF()
        y_axis = QVector2D(prev_point - self.scaling_pivot_corner_point).toPointF()

        if self.scaling_active_point_index % 2 == 1:
            x_axis, y_axis = y_axis, x_axis

        self.scaling_x_axis = x_axis
        self.scaling_y_axis = y_axis

        for element in self.selected_items:
            element.__element_scale_x = element.element_scale_x
            element.__element_scale_y = element.element_scale_y
            element.__element_position = QPointF(element.element_position)
            if not viewport_zoom_changed:
                element.__element_scale_x_init = element.element_scale_x
                element.__element_scale_y_init = element.element_scale_y
                element.__element_position_init = QPointF(element.element_position)
            position_vec = element.calculate_absolute_position(canvas=self) - self.scaling_pivot_corner_point
            element.normalized_pos_x, element.normalized_pos_y = self.calculate_vector_projection_factors(x_axis, y_axis, position_vec)

    def calculate_vector_projection_factors(self, x_axis, y_axis, vector):
        x_axis = QVector2D(x_axis)
        y_axis = QVector2D(y_axis)
        x_axis_normalized = x_axis.normalized().toPointF()
        y_axis_normalized = y_axis.normalized().toPointF()
        x_axis_length = x_axis.length()
        y_axis_length = y_axis.length()
        x_factor = QPointF.dotProduct(x_axis_normalized, vector)/x_axis_length
        y_factor = QPointF.dotProduct(y_axis_normalized, vector)/y_axis_length
        return x_factor, y_factor

    def canvas_DO_selected_elements_SCALING(self, event_pos):
        self.start_translation_pos = None

        multi_element_mode = len(self.selected_items) > 1
        alt_mod = QApplication.queryKeyboardModifiers() & Qt.AltModifier
        shift_mod = QApplication.queryKeyboardModifiers() & Qt.ShiftModifier
        center_is_pivot = alt_mod
        proportional_scaling = multi_element_mode or shift_mod

        # отключаем модификатор alt для группы выделенных айтемов
        center_is_pivot = center_is_pivot and not multi_element_mode

        if center_is_pivot:
            pivot = self.scaling_pivot_center_point
            scaling_x_axis = self.scaling_from_center_x_axis
            scaling_y_axis = self.scaling_from_center_y_axis
        else:
            pivot = self.scaling_pivot_corner_point
            scaling_x_axis = self.scaling_x_axis
            scaling_y_axis = self.scaling_y_axis

        # updating for draw functions
        self.scaling_pivot_point = pivot
        self.scaling_pivot_point_x_axis = scaling_x_axis
        self.scaling_pivot_point_y_axis = scaling_y_axis

        for element in self.selected_items:
            __scaling_vector =  QVector2D(QPointF(event_pos) - pivot) # не вытаскивать вычисления вектора из цикла!
            # принудительно задаётся минимальный скейл, значение в экранных координатах
            # MIN_LENGTH = 100.0
            # if __scaling_vector.length() < MIN_LENGTH:
            #     __scaling_vector = __scaling_vector.normalized()*MIN_LENGTH
            self.scaling_vector = scaling_vector = __scaling_vector.toPointF()

            if proportional_scaling:
                x_axis = QVector2D(scaling_x_axis).normalized()
                y_axis = QVector2D(scaling_y_axis).normalized()
                x_sign = math.copysign(1.0, QVector2D.dotProduct(x_axis, QVector2D(self.scaling_vector).normalized()))
                y_sign = math.copysign(1.0, QVector2D.dotProduct(y_axis, QVector2D(self.scaling_vector).normalized()))
                if multi_element_mode:
                    aspect_ratio = self.selection_bounding_box_aspect_ratio
                else:
                    aspect_ratio = element.aspect_ratio()
                psv = x_sign*aspect_ratio*x_axis.toPointF() + y_sign*y_axis.toPointF()
                self.proportional_scaling_vector = QVector2D(psv).normalized().toPointF()
                factor = QPointF.dotProduct(self.proportional_scaling_vector, self.scaling_vector)
                self.proportional_scaling_vector *= factor

                self.scaling_vector = scaling_vector = self.proportional_scaling_vector

            if center_is_pivot:
                scaling_x_axis = - scaling_x_axis
                scaling_y_axis = - scaling_y_axis

            # scaling component
            x_factor, y_factor = self.calculate_vector_projection_factors(scaling_x_axis, scaling_y_axis, scaling_vector)

            element.element_scale_x = element.__element_scale_x * x_factor
            element.element_scale_y = element.__element_scale_y * y_factor
            if proportional_scaling and not multi_element_mode and not center_is_pivot:
                element.element_scale_x = math.copysign(1.0, element.element_scale_x)*abs(element.element_scale_y)

            # position component
            if center_is_pivot:
                element.element_position = element.__element_position
            else:
                pos = element.calculate_absolute_position(canvas=self, rel_pos=element.__element_position)
                scaling = QTransform()
                # эти нормализованные координаты актуальны для пропорционального и не для пропорционального редактирования
                scaling.scale(element.normalized_pos_x, element.normalized_pos_y)
                mapped_scaling_vector = scaling.map(scaling_vector)
                new_absolute_position = pivot + mapped_scaling_vector
                rel_pos_global_scaled = new_absolute_position - self.canvas_origin
                new_element_position = QPointF(rel_pos_global_scaled.x()/self.canvas_scale_x, rel_pos_global_scaled.y()/self.canvas_scale_y)
                element.element_position = new_element_position

        # bounding box update
        self.update_selection_bouding_box()

    def canvas_FINISH_selected_elements_SCALING(self, event, cancel=False):
        self.scaling_ongoing = False
        self.scaling_vector = None
        self.proportional_scaling_vector = None
        self.scaling_pivot_point = None
        if cancel:
            for elements in self.selected_items:
                elements.element_scale_x = elements.__element_scale_x_init
                elements.element_scale_y = elements.__element_scale_y_init
                elements.element_position = QPointF(elements.__element_position_init)
        else:
            self.init_selection_bounding_box_widget()

    def canvas_CANCEL_selected_elements_SCALING(self):
        if self.scaling_ongoing:
            self.canvas_FINISH_selected_elements_SCALING(None, cancel=True)
            self.update_selection_bouding_box()
            self.transform_cancelled = True
            self.update()
            print('cancel scaling')


    def elementsDrawSelectionMouseRect(self, painter):
        if self.selection_rect is not None:
            c = self.selection_color
            painter.setPen(QPen(c))
            c.setAlphaF(0.5)
            brush = QBrush(c)
            painter.setBrush(brush)
            painter.drawRect(self.selection_rect)

    def elementsDrawSelectedElementsDottedOutlines(self, painter):
        painter.save()
        painter.setBrush(Qt.NoBrush)
        pen = QPen(Qt.white, 1, Qt.DashLine)
        painter.setPen(pen)
        painter.setCompositionMode(QPainter.RasterOp_NotDestination) #RasterOp_SourceXorDestination
        for element in self.selected_items:
            sa = element.get_selection_area(self)
            painter.drawPolygon(sa)
        painter.restore()

    def elementsDrawSelectionTransformBox(self, painter):
        self.rotation_activation_areas = []
        if self.selection_bounding_box is not None:

            painter.setOpacity(self.canvas_selection_transform_box_opacity)
            pen = QPen(self.selection_color, 4)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPolygon(self.selection_bounding_box)

            default_pen = painter.pen()

            # roration activation areas
            painter.setPen(QPen(Qt.red))
            for index, point in enumerate(self.selection_bounding_box):
                points_count = self.selection_bounding_box.size()
                prev_point_index = (index-1) % points_count
                next_point_index = (index+1) % points_count
                prev_point = self.selection_bounding_box[prev_point_index]
                next_point = self.selection_bounding_box[next_point_index]

                a = QVector2D(point - prev_point).normalized().toPointF()
                b = QVector2D(point - next_point).normalized().toPointF()
                a *= self.STNG_transform_widget_activation_area_size*2
                b *= self.STNG_transform_widget_activation_area_size*2
                points = [
                    point,
                    point + a,
                    point + a + b,
                    point + b,
                ]
                raa = QPolygonF(points)
                if self.canvas_debug_transform_widget:
                    painter.drawPolygon(raa)

                self.rotation_activation_areas.append((index, raa))

            # scale activation areas
            default_pen.setWidthF(self.STNG_transform_widget_activation_area_size)
            default_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(default_pen)

            for index, point in enumerate(self.selection_bounding_box):
                painter.drawPoint(point)

            if self.canvas_debug_transform_widget and self.scaling_ongoing and self.scaling_pivot_point is not None:
                pivot = self.scaling_pivot_point
                x_axis = self.scaling_pivot_point_x_axis
                y_axis = self.scaling_pivot_point_y_axis

                painter.setPen(QPen(Qt.red, 4))
                painter.drawLine(pivot, pivot+x_axis)
                painter.setPen(QPen(Qt.green, 4))
                painter.drawLine(pivot, pivot+y_axis)
                if self.scaling_vector is not None:
                    painter.setPen(QPen(Qt.yellow, 4))
                    painter.drawLine(pivot, pivot + self.scaling_vector)

                if self.proportional_scaling_vector is not None:
                    painter.setPen(QPen(Qt.darkGray, 4))
                    painter.drawLine(pivot, pivot + self.proportional_scaling_vector)

            painter.setOpacity(1.0)





# для запуска программы прямо из этого файла при разработке и отладке
if __name__ == '__main__':
    import subprocess
    subprocess.Popen([sys.executable, "-u", "oxxxy.py"])
    sys.exit()
