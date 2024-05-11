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

import math
import datetime
import sys
import os
import json
import time
import cbor2

from PyQt5.QtWidgets import (QMenu, QFileDialog, QApplication)
from PyQt5.QtCore import (QPoint, QPointF, QRect, Qt, QSize, QSizeF, QRectF, QFile, QDataStream,
                                                                            QIODevice, QMarginsF)
from PyQt5.QtGui import (QPainterPath, QColor, QBrush, QPixmap, QPainter, QImage, QTransform,
                                QPen, QFont, QCursor, QPolygonF, QVector2D, QPainterPathStroker)

from _utils import (convex_hull, calculate_tangent_points, build_valid_rect, build_valid_rectF,
    get_nearest_point_on_rect, capture_rotated_rect_from_pixmap, squarize_rect, fit_rect_into_rect,
    constraint45Degree, get_bounding_pointsF, load_svg, is_webp_file_animated,
                                                            apply_blur_effect, get_rect_corners)

from elements_transform import ElementsTransformMixin
from elements_textedit import ElementsTextEditElementMixin
from elements_tools2024 import Elements2024ToolsMixin, Element2024Mixin

ZOOM_IN_REGION_DAFAULT_SCALE = 1.5

class ToolID():
    none = "none"

    transform = "transform"
    oval = "oval"
    rect = "rect"
    line = "line"
    pen = "pen"
    marker = "marker"
    arrow = "arrow"
    text = "text"
    numbering =  "numbering"
    blurring = "blurring"
    darkening = "darkening"
    picture = "picture"
    background_picture = 'background'
    zoom_in_region = "zoom_in_region"
    copypaste = "copypaste"
    arrowstree = "arrowstree"

    multiframing = "multiframing"
    removing = "removing"

    DONE = "done"
    FORWARDS = "forwards"
    BACKWARDS = "backwards"
    DRAG = "drag"
    TEMPORARY_TYPE_NOT_DEFINED = "TEMPORARY_TYPE_NOT_DEFINED"

class SelectionFilter():
    all = "all"
    content_only = "content_only"
    background_only = "background_only"

class CreateBackgroundOption():
    Initial = 1
    Reshoot = 2
    ContentToBackground = 3

class Element(Element2024Mixin):

    def __init__(self, oxxxy_element_type, elements_list, skip=False):
        self.oxxxy_type = oxxxy_element_type
        if not skip:
            elements_list.append(self)

            n = 0
            for el in elements_list:
                if el.oxxxy_type == ToolID.numbering:
                    n += 1
            self.number = n

            if hasattr(Element, "_counter"):
                Element._counter += 1
            else:
                Element._counter = 0
            self.unique_index = Element._counter

            self.pass2_unique_index = self.unique_index

        self.group_id = None
        self.source_indexes = []
        self.pass_through_filter_only_if_allowed = False
        self.allowed_indexes = []

        self.finished = False
        self.preview = False

        self.backup_pixmap = None
        self.frame_info = None
        self.background_image = False

        self.opacity = 1.0
        self.color = QColor(0, 0, 0)
        self.size = 1.0
        self.color_slider_value = 0.1
        self.color_slider_palette_index = 0
        self.toolbool = False
        self.plain_text = ''
        self.oxxxy_subtype = ''

        self.text_doc = None
        self.draw_transform = None
        self.proxy_pixmap = None

        self.selection_path = None

        # element attributes for canvas
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.position = QPointF()
        self.rotation = 0
        self.prerotation = 0
        self.width = None
        self.height = None
        # эти атрибуты с двойным нижним подчёркиванием в начале
        # на деле будут иметь префикс _Element__
        self.__scale_x = None
        self.__scale_y = None
        self.__position = None
        self.__rotation = None

        self.__scale_x_init = None
        self.__scale_y_init = None
        self.__position_init = None

        self._selected = False
        self._touched = False

        self._modification_stamp = 0.0

    def __repr__(self):
        return f'{self.unique_index} {self.oxxxy_type}'

    def get_parameters_info(self):
        info_text = ""
        if self.source_indexes:
            info_text += f"[{self.unique_index}] {self.oxxxy_type} from [{self.source_indexes}]"
        else:
            info_text += f"[{self.unique_index}] {self.oxxxy_type}"
        if hasattr(self, 'toolbool'):
            info_text += f" (tb: {self.toolbool})"
        if hasattr(self, 'opacity'):
            info_text += f' (opacity: {self.opacity})'
        if self.group_id is not None:
            info_text += f' (group_id: {self.group_id})'
        return info_text

    def calc_local_data_default(self):
        self.position = (self.start_point + self.end_point)/2.0
        self.local_start_point = self.start_point - self.position
        self.local_end_point = self.end_point - self.position
        diff = self.local_start_point - self.local_end_point
        self.width = abs(diff.x())
        self.height = abs(diff.y())

    def recalc_local_data_for_straight_objects(self):
        rot = QTransform()

        # default_45_degrees будет иметь значение не 45 градусов,
        # а -45, потому что здесь ось Y направлена вниз
        # -1, 1 обозначет вектор, направленный снизу слева вверх вправо
        # default_45_degrees = math.degrees(math.atan2(-1, 1))
        diff = self.local_end_point - self.local_start_point
        object_orientation_degrees = math.degrees(math.atan2(diff.y(), diff.x()))
        # diff_angle = default_45_degrees - object_orientation_degrees

        # актуальная поправочка, чтобы код действительно работал для всех направлений и углов
        diff_angle = object_orientation_degrees + 45

        rot.rotate(-diff_angle)
        self.prerotation = diff_angle

        self.local_start_point = rot.map(self.local_start_point)
        self.local_end_point = rot.map(self.local_end_point)

        self.rotation = diff_angle

        diff = self.local_start_point - self.local_end_point
        self.width = abs(diff.x())
        self.height = abs(diff.y())

    def calc_local_data_finish(self, first_element):
        self.width = first_element.width
        self.height = first_element.height
        # с предувеличением
        if self.oxxxy_type in [ToolID.zoom_in_region]:
            self.scale_y = ZOOM_IN_REGION_DAFAULT_SCALE
            self.scale_x = ZOOM_IN_REGION_DAFAULT_SCALE
        else:
            self.scale_y = 1.0
            self.scale_x = 1.0

    def calc_local_data_path(self):
        bb = self.path.boundingRect()
        self.position = bb.center()
        self.width = bb.width()
        self.height = bb.height()

    def calc_local_data_picture(self):
        self.width = self.pixmap.width()
        self.height = self.pixmap.height()

    def calc_local_data(self):
        if self.oxxxy_type in [ToolID.line]:
            self.calc_local_data_default()
        elif self.oxxxy_type in [ToolID.pen, ToolID.marker]:
            if self.straight:
                self.calc_local_data_default()
            else:
                self.calc_local_data_path()
        elif self.oxxxy_type in [ToolID.arrow]:
            self.calc_local_data_default()
        elif self.oxxxy_type in [ToolID.oval, ToolID.rect, ToolID.numbering]:
            self.calc_local_data_default()
        elif self.oxxxy_type in [ToolID.blurring, ToolID.darkening, ToolID.multiframing]:
            self.calc_local_data_default()
        elif self.oxxxy_type in [ToolID.picture]:
            self.calc_local_data_picture()
        elif self.oxxxy_type in [ToolID.zoom_in_region, ToolID.copypaste]:
            self.calc_local_data_default()
        elif self.oxxxy_type in [ToolID.text]:
            self.calc_local_data_default()
        elif self.oxxxy_type in [ToolID.arrowstree]:
            self.calc_local_data_arrowstree()
        else:
            raise Exception('calc_local_data', self.oxxxy_type)

    @property
    def calc_area(self):
        r = self.get_size_rect(scaled=True)
        return abs(r.width() * r.height())

    def calculate_absolute_position(self, canvas=None, rel_pos=None):
        _scale_x = canvas.canvas_scale_x
        _scale_y = canvas.canvas_scale_y
        if rel_pos is None:
            rel_pos = self.position
        return QPointF(canvas.canvas_origin) + QPointF(rel_pos.x()*_scale_x, rel_pos.y()*_scale_y)

    def aspect_ratio(self):
        rect = self.get_size_rect(scaled=False)
        return rect.width()/rect.height()

    def get_size_rect(self, scaled=False):
        if scaled:
            scale_x = self.scale_x
            scale_y = self.scale_y
        else:
            scale_x = 1.0
            scale_y = 1.0
        return QRectF(0, 0, self.width*scale_x, self.height*scale_y)

    def get_canvas_space_selection_area(self):
        return self.get_selection_area(canvas=None,
                                    # здесь обязательно надо центрировать объект в начало координат,
                                    # иначе повороты и масштабы неправильно сработают
                                    place_center_at_origin=True,
                                    apply_global_scale=False,
                                    apply_translation=True
        )

    def get_canvas_space_selection_rect_with_no_rotation(self):
        er = self.get_size_rect(scaled=True)
        er.moveCenter(self.position)
        return er

    def get_selection_area(self, canvas=None, place_center_at_origin=True, apply_global_scale=True, apply_translation=True):
        size_rect = self.get_size_rect()
        if place_center_at_origin:
            size_rect.moveCenter(QPointF(0, 0))
        points = [
            size_rect.topLeft(),
            size_rect.topRight(),
            size_rect.bottomRight(),
            size_rect.bottomLeft(),
        ]
        polygon = QPolygonF(points)
        transform = self.get_transform_obj(canvas=canvas, apply_global_scale=apply_global_scale, apply_translation=apply_translation)
        return transform.map(polygon)

    def is_selection_contains_pos(self, pos, canvas=None):
        if self.selection_path:
            return self.get_selection_path(canvas=canvas).contains(pos)
        else:
            return self.get_selection_area(canvas=canvas).containsPoint(pos, Qt.WindingFill)

    def get_selection_path(self, canvas=None):
        transform = self.get_transform_obj(canvas=canvas,
            apply_global_scale=True,
            apply_translation=True
        )
        return transform.map(self.selection_path)

    def construct_selection_path(self, canvas):
        stroker = QPainterPathStroker()
        amount = 10
        pen, _, _ = canvas.elementsGetPenFromElement(self)
        stroker.setWidth(max(pen.width(), 10))
        stroker.setJoinStyle(Qt.RoundJoin)
        path = None
        def from_path():
            return self.path
        def from_local_data():
            path = QPainterPath()
            path.moveTo(self.local_start_point)
            path.lineTo(self.local_end_point)
            return path
        if self.oxxxy_type in [ToolID.pen, ToolID.marker]:
            if self.straight:
                path = from_local_data()
            else:
                path = from_path()
        elif self.oxxxy_type in [ToolID.line]:
            path = from_local_data()
        elif self.oxxxy_type in [ToolID.arrow]:
            _, _, size = canvas.elementsGetPenFromElement(self)
            self.selection_path = canvas.elementsGetArrowPath(self.local_start_point, self.local_end_point, size, True)
        if path:
            selection_path = stroker.createStroke(path).simplified()
            path_center = selection_path.boundingRect().center()
            self.selection_path = selection_path.translated(-path_center)

    def get_transform_obj(self, canvas=None, apply_local_scale=True, apply_translation=True, apply_global_scale=True):
        local_scaling = QTransform()
        rotation = QTransform()
        global_scaling = QTransform()
        translation = QTransform()
        if apply_local_scale:
            local_scaling.scale(self.scale_x, self.scale_y)
        rotation.rotate(self.rotation)
        if apply_translation:
            if apply_global_scale:
                pos = self.calculate_absolute_position(canvas=canvas)
                translation.translate(pos.x(), pos.y())
            else:
                translation.translate(self.position.x(), self.position.y())
        if apply_global_scale:
            global_scaling.scale(canvas.canvas_scale_x, canvas.canvas_scale_y)
        transform = local_scaling * rotation * global_scaling * translation
        return transform

    def enable_distortion_fixer(self):
        if hasattr(self, 'local_end_point') and not self.oxxxy_type == ToolID.text:
            self._saved_data = (
                QPointF(self.local_end_point),
                QPointF(self.local_start_point),
                self.width,
                self.height,
                self.scale_x,
                self.scale_y
            )

            self.local_end_point.setX(self.local_end_point.x() * self.scale_x)
            self.local_end_point.setY(self.local_end_point.y() * self.scale_y)

            self.local_start_point.setX(self.local_start_point.x() * self.scale_x)
            self.local_start_point.setY(self.local_start_point.y() * self.scale_y)

            self.width *= self.scale_x
            self.height *= self.scale_y
            self.scale_x = self.scale_y = 1.0

    def disable_distortion_fixer(self):
        if hasattr(self, '_saved_data') and not self.oxxxy_type == ToolID.text:
            self.local_end_point, \
            self.local_start_point, \
            self.width, \
            self.height, \
            self.scale_x, \
            self.scale_y = self._saved_data

class ElementsModificationSlot():

    def __init__(self, content_type):
        super().__init__()
        self.elements = list()
        self.content_type = content_type

class ElementsMixin(ElementsTransformMixin, ElementsTextEditElementMixin, Elements2024ToolsMixin):

    ToolID = ToolID #для поддержки миксина

    CreateBackgroundOption = CreateBackgroundOption

    def elementsInit(self):
        self.current_tool = ToolID.none
        self.drag_capture_zone = False
        self.ocp = self.mapFromGlobal(QCursor().pos())
        self.current_capture_zone_center = QPoint(0, 0)

        # хоть эти три атрибута и начинаются со слова "canvas",
        # но здесь они на самом деле значат "viewport",
        # потому что управляют лишь отображением холста на экране
        war = self.working_area_rect
        if war is not None:
            self.canvas_origin = QPointF(-war.left(), -war.top())
        else:
            self.canvas_origin = QPointF(0, 0)
        self.canvas_scale_x = 1.0
        self.canvas_scale_y = 1.0

        self.NUMBERING_ELEMENT_WIDTH = 25
        self.elements = []
        self._te = Element(ToolID.zoom_in_region, [], skip=True)
        self._tei = Element(ToolID.picture, None, skip=True)
        self._ted = Element(ToolID.line, None, skip=True)
        self.modification_slots = []
        self.elements_modification_index = 0
        self.SelectionFilter = SelectionFilter
        self.selection_filter = self.SelectionFilter.content_only
        self._active_element = None #active element is the last selected element
        # для выделения элементов и виджета трансформации элементов
        self.elementsInitTransform()
        self.elementsSetSelected(None)

        self.elementsTextElementInitModule()

        self.modification_stamp = None

        self.capture_region_widget_enabled = True
        self.show_background = True
        self.dark_pictures = True

        self.init2024Tools()

    def elementsStartModificationProcess(self, _type):
        """
            Acquires modification stamp for ongoing elements modification
        """
        if self.modification_stamp is None:
            self.modification_stamp = time.time()
            self.modification_slot = self.elementsCreateNewSlot(_type)
        # хуйня, срабатывает при зажатых клавишах-стрелка
        # else:
        #     raise Exception('Attempting to acquire new stamp, but the current is not deacquired!')

    def elementsStopModificationProcess(self):
        """
            Deacquires modification stamp after finished elements modification
        """
        if self.modification_stamp is not None:
            self.modification_stamp = None
            if len(self.modification_slot.elements) == 0:
                if self.modification_slot in self.modification_slots:
                    self.modification_slots.remove(self.modification_slot)
                    self.elements_modification_index -= 1
                    self.modification_slots = self.elementsModificationSlotsFilter()
                    self.elements = self.elementsFilter()
            self.modification_slot = None

    def elementsCheckAcquiredModificationStamp(self):
        if self.modification_stamp is None:
            raise Exception('Unsupported modification!')

    def elementsFindBackgroundSlot(self):
        for slot in self.elementsModificationSlotsFilter():
            if slot.content_type == ToolID.background_picture:
                return slot
        return None

    @property
    def active_element(self):
        return self._active_element

    @active_element.setter
    def active_element(self, el):
        self.elementsTextElementDeactivateEditMode()
        self._active_element = el

    def elementsCreateBackgroundPictures(self, option, offset=None):
        if offset is None:
            offset = QPointF(0, 0)

        if option == self.CreateBackgroundOption.Initial:

            background_pixmap = QPixmap.fromImage(self.source_pixels)
            bckg_element = self.elementsCreateNew(ToolID.picture, content_type=ToolID.background_picture)
            bckg_element.pixmap = background_pixmap
            bckg_element.background_image = True
            bckg_element.calc_local_data()
            bckg_element.position = QPointF(background_pixmap.width()/2, background_pixmap.height()/2)

        elif option == self.CreateBackgroundOption.Reshoot:

            # записываем индексы всех видимых элементов фона
            ve_b_indexes = [el.unique_index for el in self.elementsFilter() if el.background_image]
            # создаём основу для нового фона
            background_slot = self.elementsFindBackgroundSlot()
            bckg_element = self.elementsCreateNew(ToolID.picture,
                create_new_slot=False,
                modification_slot=background_slot,
            )
            # оставляем запись в истории действий
            rmv_element = self.elementsCreateNew(ToolID.removing)
            rmv_element.source_indexes = ve_b_indexes
            rmv_element.allowed_indexes = [bckg_element.pass2_unique_index]
            bckg_element.pass_through_filter_only_if_allowed = True
            # заправляем данными
            new_background_pixmap = QPixmap.fromImage(self.source_pixels)
            bckg_element.pixmap = new_background_pixmap
            bckg_element.background_image = True
            bckg_element.calc_local_data()
            bckg_element.position = QPointF(new_background_pixmap.width()/2, new_background_pixmap.height()/2)

        elif option == self.CreateBackgroundOption.ContentToBackground:

            # записываем индексы всех видимых элементов, даже фоновых
            ve_indexes = [el.unique_index for el in self.elementsFilter()]
            # создаём основу для нового фона
            background_slot = self.elementsFindBackgroundSlot()
            bckg_element = self.elementsCreateNew(ToolID.picture,
                create_new_slot=False,
                modification_slot=background_slot,
            )
            # оставляем запись в истории действий
            rmv_element = self.elementsCreateNew(ToolID.removing)
            rmv_element.source_indexes = ve_indexes
            rmv_element.allowed_indexes = [bckg_element.pass2_unique_index]
            bckg_element.pass_through_filter_only_if_allowed = True
            # заправляем данными
            new_background_pixmap = QPixmap.fromImage(self.source_pixels)
            bckg_element.pixmap = new_background_pixmap
            bckg_element.background_image = True
            bckg_element.calc_local_data()
            bckg_element.position = QPointF(new_background_pixmap.width()/2, new_background_pixmap.height()/2) + offset

    def elementsArrangeInGrid(self):

        ROWS = self.Globals.ARRANGE_ROWS
        COLS = self.Globals.ARRANGE_COLS

        elements = self.elementsFilterElementsForSelection()
        for el in elements:
            el.scale_x = 1.0
            el.scale_y = 1.0

        # вызываем для выравнивания по высоте:
        # каждая картинка будет отмасштабирована до высоты картинки с наибольшей высотой
        self.elementsAutoCollagePicturesHor()

        # фильтрация по типу выделения
        elements = self.elementsFilterElementsForSelection()
        elements = list(sorted(elements, key=lambda x: x.unique_index))


        if ROWS != 0:
            COLS = int(math.ceil(len(elements) / ROWS))

        rows = []
        current_row = []
        for n, el in enumerate(elements):
            if (n % COLS == 0) and n != 0:

                rows.append(current_row)
                current_row = []
            current_row.append(el)

        rows.append(current_row)

        # calculating MAX_ROW_WIDTH
        MAX_ROW_WIDTH = 0
        for row in rows:
            row_width = 0
            for el in row:
                b_rect = el.get_selection_area(canvas=self, apply_global_scale=False).boundingRect()
                row_width += b_rect.width()
            MAX_ROW_WIDTH = max(row_width, MAX_ROW_WIDTH)

        # задание масштаба для каждого ряда
        for row in rows:
            row_width = 0
            for el in row:
                b_rect = el.get_selection_area(canvas=self, apply_global_scale=False).boundingRect()
                row_width += b_rect.width()
            row_scale_factor = MAX_ROW_WIDTH/row_width
            for el in row:
                el.scale_x *= row_scale_factor
                el.scale_y *= row_scale_factor

        # расположение
        offset = QPointF(0, 0)
        points = []
        for row in rows:
            for el in row:
                b_rect = el.get_selection_area(canvas=self, apply_global_scale=False).boundingRect()
                bi_width = b_rect.width()
                bi_height = b_rect.height()
                half_size = QPointF(bi_width/2, bi_height/2)
                el.position = offset + half_size

                offset += QPointF(bi_width, 0)

                points.append(el.position - half_size)
                points.append(el.position + half_size)

            offset.setX(0)
            offset.setY(offset.y() + bi_height)

        self.input_POINT2, self.input_POINT1 = get_bounding_pointsF(points)
        self.capture_region_rect = build_valid_rectF(self.input_POINT1, self.input_POINT2)


        self.init_selection_bounding_box_widget()
        self.update()

    def elementsSliceBackgroundsIntoPieces(self):

        ROWS = self.Globals.SLICE_ROWS
        COLS = self.Globals.SLICE_COLS

        content_rect = self.elementsDoRenderToBackground(for_slicing=True)
        content_offset = content_rect.topLeft()
        background_pixmap = QPixmap.fromImage(self.source_pixels)

        col_width = background_pixmap.width()/COLS
        row_height = background_pixmap.height()/ROWS

        # записываем индексы всех видимых элементов фона
        ve_b_indexes = [el.unique_index for el in self.elementsFilter() if el.background_image]

        background_slot = self.elementsFindBackgroundSlot()
        allowed_indexes = []

        for row in range(ROWS):
            for col in range(COLS):

                bckg_el = self.elementsCreateNew(ToolID.picture,
                    content_type=ToolID.background_picture,
                    create_new_slot=False,
                    modification_slot=background_slot,
                )

                bckg_el.pixmap = background_pixmap
                bckg_el.background_image = True
                bckg_el.calc_local_data()
                x1 = col_width*col
                y1 = row_height*row
                x2 = x1 + col_width
                y2 = y1 + row_height
                frame_rect = QRectF(QPointF(x1, y1), QPointF(x2, y2)).toRect()
                frame_info = (
                    x1/background_pixmap.width(),
                    y1/background_pixmap.height(),
                    x2/background_pixmap.width(),
                    y2/background_pixmap.height(),
                )

                self.elementsFramePicture(element=bckg_el,
                    frame_rect=frame_rect,
                    frame_info=frame_info,
                    pixmap=bckg_el.pixmap,
                )
                bckg_el.backup_pixmap = None # зануляем, чтобы сохрание в файл не растягивалось на 100 лет

                pos_x = x1 + col_width/2
                pos_y = y1 + row_height/2
                bckg_el.position = QPointF(pos_x, pos_y) + content_offset

                # история действий
                allowed_indexes.append(bckg_el.pass2_unique_index)
                bckg_el.pass_through_filter_only_if_allowed = True

        rmv_element = self.elementsCreateNew(ToolID.removing)
        # данные для истории действий
        rmv_element.source_indexes = ve_b_indexes
        rmv_element.allowed_indexes = allowed_indexes

        self.elementsSetSelected(None)

    def elementsUpdateUI(self):
        self.update()
        if self.tools_window:
            self.tools_window.update()
            for children in self.tools_window.children():
                children.update()

    def elementsStartSaveToMemoryMode(self):
        self.Globals.save_to_memory_mode = not self.Globals.save_to_memory_mode
        self.elementsUpdateUI()

    def elementsFinishSaveToMemoryMode(self):
        self.Globals.save_to_memory_mode = False
        self.request_images_editor_mode(self.Globals.images_in_memory)
        self.Globals.images_in_memory.clear()
        self.update_sys_tray_icon(None, reset=True)
        self.elementsUpdateUI()

    def mapped_cursor_pos(self):
        return self.mapFromGlobal(QCursor().pos())

    def elementsDoScaleCanvas(self, scroll_value, ctrl, shift, no_mod,
                pivot=None, factor_x=None, factor_y=None, precalculate=False, canvas_origin=None, canvas_scale_x=None, canvas_scale_y=None):

        if pivot is None:
            pivot = self.mapped_cursor_pos()

        scale_speed = 10.0
        if scroll_value > 0:
            factor = scale_speed/(scale_speed-1)
        else:
            factor = (scale_speed-1)/scale_speed

        if factor_x is None:
            factor_x = factor

        if factor_y is None:
            factor_y = factor

        if ctrl:
            factor_x = factor
            factor_y = 1.0
        elif shift:
            factor_x = 1.0
            factor_y = factor

        _canvas_origin = canvas_origin if canvas_origin is not None else self.canvas_origin
        _canvas_scale_x = canvas_scale_x if canvas_scale_x is not None else self.canvas_scale_x
        _canvas_scale_y = canvas_scale_y if canvas_scale_y is not None else self.canvas_scale_y

        _canvas_scale_x *= factor_x
        _canvas_scale_y *= factor_y

        _canvas_origin -= pivot
        _canvas_origin = QPointF(_canvas_origin.x()*factor_x, _canvas_origin.y()*factor_y)
        _canvas_origin += pivot

        if precalculate:
            return _canvas_scale_x, _canvas_scale_y, _canvas_origin

        self.canvas_origin  = _canvas_origin
        self.canvas_scale_x = _canvas_scale_x
        self.canvas_scale_y = _canvas_scale_y

        if self.selection_rect:
            self.canvas_selection_callback(QApplication.queryKeyboardModifiers() == Qt.ShiftModifier)
        self.update_selection_bouding_box()

        event_pos = self.mapped_cursor_pos()
        if self.scaling_ongoing:
            self.canvas_START_selected_elements_SCALING(None, viewport_zoom_changed=True)
            self.canvas_DO_selected_elements_SCALING(event_pos)

        if self.rotation_ongoing:
            self.canvas_START_selected_elements_ROTATION(event_pos, viewport_zoom_changed=True)
            self.canvas_DO_selected_elements_ROTATION(event_pos)

        self.update()

    def save_project(self):
        # задание папки для скриншота
        self.SettingsWindow.set_screenshot_folder_path()
        if not os.path.exists(self.Globals.SCREENSHOT_FOLDER_PATH):
            return

        formated_datetime = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        folder_path = os.path.join(self.Globals.SCREENSHOT_FOLDER_PATH,
                                                f"OxxxyProject_{formated_datetime}")
        os.mkdir(folder_path)
        if not os.path.exists(folder_path):
            return
        if self.Globals.ENABLE_CBOR2:
            file_format = 'cbor2'
        else:
            file_format = 'json'
        project_filepath = os.path.join(folder_path, f"project.{file_format}.oxxxyshot")


        # инициализация словаря
        data = dict()

        # СОХРАНЕНИЕ ДАННЫХ

        # сохранение переменных, задаваемых через контекстное меню
        data.update({'dark_pictures':                    self.dark_pictures                     })
        data.update({'close_editor_on_done':             self.Globals.close_editor_on_done      })


        # сохранение готовых изображений из памяти
        data.update({'save_to_memory_mode':              self.Globals.save_to_memory_mode       })
        if self.Globals.save_to_memory_mode:
            subfolder_path = os.path.join(folder_path, "in_memory")
            os.mkdir(subfolder_path)
            for n, image_in_memory in enumerate(self.Globals.images_in_memory):
                image_path = os.path.join(subfolder_path, f'{n}.png')
                image_in_memory.save(image_path)


        # сохранение картинки-фона
        image_path = os.path.join(folder_path, "background.png")
        self.source_pixels.save(image_path)


        # сохранение метаданных
        data.update({'metadata':                   self.metadata                                })


        # сохранение обтравки маской
        data.update({'masked':                     self.tools_window.chb_masked.isChecked()     })


        # сохранение обтравки маской в виде шестиугольника
        data.update({'hex_mask':                   self.hex_mask                                })


        # сохранение области захвата
        if self.capture_region_rect is not None:
            r = self.capture_region_rect
            data.update({'capture_region_rect': (r.left(), r.top(), r.width(), r.height())      })
        else:
            data.update({'capture_region_rect': (0, 0, 0, 0)                                    })

        # !!! не сохраняются input_POINT1 и input_POINT2, так как это будет избыточным
        #
        data.update({'is_rect_defined':            self.is_rect_defined                         })


        # сохранение текущего инструмента
        data.update({'current_tool':               self.current_tool                            })


        # сохранение индексов для истории действий
        data.update({'elements_modification_index':     self.elements_modification_index        })


        # сохранение сдвига холста
        data.update({'canvas_origin':   tuple((self.canvas_origin.x(), self.canvas_origin.y())) })
        # сохранение зума холста
        data.update({'canvas_scale':      tuple((self.canvas_scale_x, self.canvas_scale_y))     })

        slots_to_store = list()
        # сохранение слотов
        for slot in self.modification_slots:

            slot_base = list()
            slots_to_store.append(slot_base)

            slot_attributes = slot.__dict__.items()
            for slot_attr_name, slot_attr_value in slot_attributes:
                slot_attr_type = type(slot_attr_value).__name__

                if isinstance(slot_attr_value, (int, str)):
                    slot_attr_data = slot_attr_value
                elif isinstance(slot_attr_value, list) and slot_attr_name == 'elements':
                    continue
                else:
                    status = f"name: '{slot_attr_name}' type: '{slot_attr_type}' value: '{slot_attr_value}'"
                    raise Exception(f"Unable to handle attribute, {status}")

                slot_base.append((slot_attr_name, slot_attr_type, slot_attr_data))

            elements_to_store = list()
            # сохранение пометок в слоте
            for element in slot.elements:

                element_base = list()
                elements_to_store.append(element_base)

                attributes = element.__dict__.items()
                for attr_name, attr_value in attributes:

                    if attr_name.startswith("__"):
                        continue

                    attr_type = type(attr_value).__name__

                    if isinstance(attr_value, QPointF):
                        attr_data = (attr_value.x(), attr_value.y())

                    elif attr_name == '_saved_data' and isinstance(attr_value, tuple):
                        continue

                    elif isinstance(attr_value, (bool, int, float, str, tuple, list)):
                        attr_data = attr_value

                    elif isinstance(attr_value, QPainterPath):
                        filename = f"path_{attr_name}_{element.unique_index:04}.data"
                        filepath = os.path.join(folder_path, filename)
                        file_handler = QFile(filepath)
                        file_handler.open(QIODevice.WriteOnly)
                        stream = QDataStream(file_handler)
                        stream << attr_value
                        attr_data = filename

                    elif isinstance(attr_value, QPixmap):
                        filename = f"pixmap_{attr_name}_{element.unique_index:04}.png"
                        filepath = os.path.join(folder_path, filename)
                        attr_value.save(filepath)
                        attr_data = filename

                    elif isinstance(attr_value, QColor):
                        attr_data = attr_value.getRgbF()

                    elif attr_value is None or attr_name in ["text_doc"]:
                        attr_data = None

                    elif isinstance(attr_value, (ElementsModificationSlot, QTransform)):
                        continue

                    else:
                        status = f"name: '{attr_name}' type: '{attr_type}' value: '{attr_value}'"
                        raise Exception(f"Unable to handle attribute, {status}")

                    element_base.append((attr_name, attr_type, attr_data))

            slot_base.append(('elements', 'list', elements_to_store))

        data.update({'slots': slots_to_store})

        # ЗАПИСЬ В ФАЙЛ НА ДИСКЕ
        if self.Globals.ENABLE_CBOR2:
            data_to_write = cbor2.dumps(data)
            with open(project_filepath, "wb") as file:
                file.write(data_to_write)
        else:
            data_to_write = json.dumps(data, indent=True)
            with open(project_filepath, "w+", encoding="utf8") as file:
                file.write(data_to_write)

        # ВЫВОД СООБЩЕНИЯ О ЗАВЕРШЕНИИ
        text = f"Проект сохранён в \n{project_filepath}"
        self.show_notify_dialog(text)

    def show_notify_dialog(self, text):
        self.dialog = self.NotifyDialog(self, label_text=text)
        self.dialog.show_at_center()

    def dialog_open_project(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.ExistingFile)
        title = ""
        filter_data = "OXXXY Project File (*.oxxxyshot)"
        self.SettingsWindow.set_screenshot_folder_path()
        data = dialog.getOpenFileName(self, title, self.Globals.SCREENSHOT_FOLDER_PATH, filter_data)
        return data[0]

    # при написании и отладке этой функции использовался готовый проект, который загружался сразу
    def open_project(self):
        project_filepath = ""

        project_filepath = self.dialog_open_project()
        if project_filepath == "":
            return

        is_file_exists = os.path.exists(project_filepath)
        is_file_extension_ok = project_filepath.lower().endswith(".oxxxyshot")
        is_file = os.path.isfile(project_filepath)
        if not (is_file_exists and is_file_extension_ok and is_file):
            self.show_notify_dialog("Ошибка: либо файла не существует, либо расширение не то. Отмена!")
            return

        # чтение json
        cbor2_project = False
        json_project = False
        try:

            # пытаемся читать как cbor2
            read_data = ""
            with open(project_filepath, "rb") as file:
                read_data = file.read()

            data = cbor2.loads(read_data)
            cbor2_project = True

        except:

            try:

                # пытаемся читать как json
                read_data = ""
                with open(project_filepath, "r", encoding="utf8") as file:
                    read_data = file.read()
                data = json.loads(read_data)

                json_project = True

            except:
                self.show_notify_dialog("Ошибка при чтении файла. Отмена!")
                return

        # подготовка перед загрузкой данных
        self.elementsInit()
        folder_path = os.path.dirname(project_filepath)

        # ЗАГРУЗКА ДАННЫХ

        # загрузка переменных, задаваемых через контекстное меню
        self.dark_pictures = data.get('dark_pictures', True)
        self.Globals.close_editor_on_done = data.get('close_editor_on_done', True)


        # загрузка готовых изображений в память
        self.Globals.save_to_memory_mode = data.get('save_to_memory_mode', False)
        if self.Globals.save_to_memory_mode:
            subfolder_path = os.path.join(folder_path, "in_memory")
            if os.path.exists(subfolder_path):
                filenames = os.listdir(subfolder_path)
                filenames = list(sorted(filenames))
                for filename in filenames:
                    filepath = os.path.join(subfolder_path, filename)
                    if not filepath.lower().endswith(".png"):
                        continue
                    self.Globals.images_in_memory.append(QPixmap(filepath))


        # загрузка исходной немодифицированной картинки-фона
        image_path = os.path.join(folder_path, "background.png")
        self.source_pixels = QImage(image_path)



        # загрузка метаданных
        self.metadata = data.get('metadata', ("", ""))

        # покажет панель инструментов если она скрыта
        self.create_tools_window_if_needed()


        # загрузка состояния обтравки маской
        self.tools_window.chb_masked.setChecked(data.get("masked", False))


        # загрузка состояния обтравки маской в виде шестиугольника
        self.hex_mask = data.get('hex_mask', False)


        # загрузка области захвата
        rect_tuple = data.get('capture_region_rect', (0, 0, 0, 0))
        if rect_tuple == (0, 0, 0, 0):
            self.capture_region_rect = None
            self.input_POINT1 = None
            self.input_POINT2 = None
            self.is_rect_defined = False
        else:
            self.capture_region_rect = QRectF(*rect_tuple)
            self.input_POINT1 = self.capture_region_rect.topLeft()
            self.input_POINT2 = self.capture_region_rect.bottomRight()
            self.is_rect_defined = True


        # загрузка текущего инструмента
        self.tools_window.set_current_tool(data.get('current_tool', 'none'))


        # загрузка индексов для истории действий
        self.elements_modification_index = data.get('elements_modification_index', 0)


        # сохранение сдвига холста
        self.canvas_origin = QPointF(*data.get('canvas_origin', (0.0, 0.0)))
        # сохранение зума холста
        canvas_scale = data.get('canvas_scale')
        self.canvas_scale_x = canvas_scale[0]
        self.canvas_scale_y = canvas_scale[1]

        # загрузка слотов, элементов и их данных
        slots_from_store = data.get('slots', [])

        for slot_attributes in slots_from_store:

            elements_from_slot = slot_attributes[-1][2]

            ms = self.elementsCreateNewSlot('FROM_FILE')

            for slot_attr_name, slot_attr_type, slot_attr_data in slot_attributes[:-1]:

                if slot_attr_type in ['bool', 'int', 'float', 'str', 'tuple', 'list']:
                    slot_attr_value = slot_attr_data

                else:
                    status = f"name: '{slot_attr_name}' type: '{slot_attr_type}' value: '{slot_attr_data}'"
                    raise Exception(f"Unable to handle attribute, {status}")

                setattr(ms, slot_attr_name, slot_attr_value)

            for element_attributes in elements_from_slot:
                element = self.elementsCreateNew(ToolID.TEMPORARY_TYPE_NOT_DEFINED,
                    create_new_slot=False, modification_slot=ms)
                # print(elements_from_slot)
                for attr_name, attr_type, attr_data in element_attributes:

                    if attr_type in ['QPoint']:
                        attr_value = QPoint(*attr_data)

                    elif attr_type in ['QPointF']:
                        attr_value = QPointF(*attr_data)

                    elif attr_type in ['bool', 'int', 'float', 'str', 'tuple', 'list']:
                        attr_value = attr_data

                    elif attr_type in ['QPainterPath']:
                        filepath = os.path.join(folder_path, attr_data)
                        file_handler = QFile(filepath)
                        file_handler.open(QIODevice.ReadOnly)
                        stream = QDataStream(file_handler)
                        path = QPainterPath()
                        stream >> path
                        attr_value = path

                    elif attr_type in ['QPixmap']:
                        filepath = os.path.join(folder_path, attr_data)
                        attr_value = QPixmap(filepath)

                    elif attr_type in ['QColor']:
                        attr_value = QColor()
                        attr_value.setRgbF(*attr_data)

                    elif attr_type in ['NoneType'] or attr_name in ["text_doc"]:
                        attr_value = None

                    else:
                        status = f"name: '{attr_name}' type: '{attr_type}' value: '{attr_data}' element: {element}"
                        raise Exception(f"Unable to handle attribute, {status}")

                    setattr(element, attr_name, attr_value)

                if element.oxxxy_type == ToolID.text:
                    self.elementsImplantTextElement(element)

        #  приготовление UI
        self.tools_window.forwards_backwards_update()
        self.update_tools_window()
        self.update()

        project_format = ''
        if cbor2_project:
            project_format = 'cbor2'
        elif json_project:
            project_format = 'json'

        msg = f'Файл загружен, формат {project_format}'
        self.show_notify_dialog(msg)

    def elementsMapToCanvas(self, viewport_pos):
        delta = QPointF(viewport_pos - self.canvas_origin)
        canvas_pos = QPointF(delta.x()/self.canvas_scale_x, delta.y()/self.canvas_scale_y)
        return canvas_pos

    def elementsMapToViewport(self, canvas_pos):
        scaled_rel_pos = QPointF(canvas_pos.x()*self.canvas_scale_x, canvas_pos.y()*self.canvas_scale_y)
        viewport_pos = self.canvas_origin + scaled_rel_pos
        return viewport_pos

    def elementsMapToViewportRectF(self, rect):
        rect = QRectF(
            self.elementsMapToViewport(rect.topLeft()),
            self.elementsMapToViewport(rect.bottomRight())
        )
        return rect

    def elementsResetCapture(self):
        self.elementsSetSelected(None)

        self.input_POINT1 = None
        self.input_POINT2 = None
        self.capture_region_rect = None

        self.user_input_started = False
        self.is_rect_defined = False
        self.current_capture_zone_center = QPoint(0, 0)

        tw = self.tools_window
        if tw:
            # надо выставить обязательно
            # чтобы, например, инструмент Картинка не крашил приложение
            tw.set_current_tool(ToolID.none)
            tw.close()
            self.tools_window = None
        self.update()

    def elementsSetElementParameters(self, element):
        tw = self.tools_window
        if tw:
            element.color = tw.color_slider.get_color()
            element.color_slider_value = tw.color_slider.value
            element.color_slider_palette_index = tw.color_slider.palette_index
            element.size = tw.size_slider.value
            element.toolbool = tw.chb_toolbool.isChecked()
            element.margin_value = 5
            element.opacity = tw.opacity_slider.value
        elif element.oxxxy_type == ToolID.picture:
            element.size = 1.0
            element.color = QColor(Qt.red)
            element.color_slider_value = 0.01
            element.color_slider_palette_index = 0
            element.toolbool = False
        if element.oxxxy_type == ToolID.blurring:
            self.elementsSetBlurredPixmap(element)
        if element.oxxxy_type in [ToolID.copypaste, ToolID.zoom_in_region]:
            if hasattr(element, 'second') and not element.second:
                self.elementsSetCopiedPixmap(element)

    def elementsFramePicture(self, element=None, frame_rect=None, frame_info=None, pixmap=None, set_selected=True):
        if element is not None:
            ae = element
        else:
            ae = self.active_element
        if frame_rect:
            if ae.backup_pixmap is None:
                ae.backup_pixmap = ae.pixmap
            if pixmap is not None:
                ae.pixmap = pixmap.copy(frame_rect)
            else:
                ae.pixmap = ae.backup_pixmap.copy(frame_rect)
        else:
            # reset
            ae.pixmap = ae.backup_pixmap
            ae.backup_pixmap = None
        ae.frame_info = frame_info
        ae.calc_local_data()
        ae.scale_x = 1.0
        ae.scale_y = 1.0
        if set_selected:
            self.elementsSetSelected(ae)
        self.update()

    def elementsSetPixmapFromMagazin(self):
        if not self.Globals.dasPictureMagazin and \
                                        self.current_picture_id in [self.PictureInfo.TYPE_FROM_MAGAZIN]:
            self.current_picture_id = self.PictureInfo.TYPE_FROM_FILE
            self.current_picture_pixmap = None
            self.current_picture_angle = 0

        if self.Globals.dasPictureMagazin:
            pixmap = self.Globals.dasPictureMagazin.pop(0)

            capture_height = max(self.capture_region_rect.height(), 100)
            if pixmap.height() > capture_height:
                pixmap = pixmap.scaledToHeight(capture_height, Qt.SmoothTransformation)
            self.current_picture_id = self.PictureInfo.TYPE_FROM_MAGAZIN
            self.current_picture_pixmap = pixmap
            self.current_picture_angle = 0
            tw = self.tools_window
            tw.on_parameters_changed()
            self.activateWindow()

    def elementsFramePictures(self, data):
        pictures = []
        for pixmap, frame_rect in data:
            pictures.append(pixmap.copy(frame_rect))

        tw = self.tools_window
        if tw and tw.current_tool == ToolID.picture:
            self.Globals.dasPictureMagazin = pictures
            self.elementsSetPixmapFromMagazin()

        else:
            pos = self.capture_region_rect.topLeft()
            for picture in pictures:
                element = self.elementsCreateNew(ToolID.picture)
                element.pixmap = picture
                element.position = pos + QPointF(picture.width()/2, picture.height()/2)
                element.calc_local_data()
                pos += QPoint(element.pixmap.width(), 0)
                self.elementsActiveElementParamsToPanelSliders()

        self.update()

    def elementsFramedFinalToImageTool(self, pixmap, frame_rect):
        self.current_picture_id = self.PictureInfo.TYPE_STAMP
        self.current_picture_pixmap = pixmap.copy(frame_rect)
        self.current_picture_angle = 0

        tools_window = self.tools_window
        if tools_window:
            if tools_window.current_tool != ToolID.picture:
                tools_window.set_current_tool(ToolID.picture)
        tools_window.on_parameters_changed()
        self.update()
        tools_window.update()

    def elementsActivateTransformTool(self):
        if not self.elements:
            return
        try:
            candidat = self.active_element
            if candidat not in self.elementsFilter(): # element should be visible at the moment
                candidat = None
        except Exception:
            candidat = None
        if not candidat:
            return
        self.elementsSetSelected(candidat)
        tools_window = self.tools_window
        if tools_window:
            tools_window.set_current_tool(ToolID.transform)
        self.update()

    def elementsRemoveSelectedElements(self):
        if not self.elementsModificationSlotsFilter():
            return
        ve = self.elementsFilter()
        if self.selected_items:
            source_indexes = []
            for candidat in self.selected_items:
                if candidat.oxxxy_type == ToolID.removing:
                    continue
                # для удаления стрелки, которая наносилась вместе с текстом (если она ещё не удалена)
                if candidat.oxxxy_type in [ToolID.text]:
                    elements_pair = self.elementsRetrieveElementsFromGroup(ve, candidat.group_id)
                    if len(elements_pair) == 2:
                        for el in elements_pair:
                            if el is candidat:
                                continue
                            elif el not in self.selected_items:
                                el._selected = False
                                source_indexes.append(el.unique_index)
                # для пар взаимозависимых пометок
                if candidat.oxxxy_type in [ToolID.zoom_in_region, ToolID.copypaste]:
                    elements_pair = self.elementsRetrieveElementsFromUniformGroup(ve, candidat.group_id)
                    for el in elements_pair:
                        if el is candidat:
                            continue
                        elif el not in self.selected_items:
                            el._selected = False
                            source_indexes.append(el.unique_index)
                candidat._selected = False
                source_indexes.append(candidat.unique_index)
            if source_indexes:
                removing_element = self.elementsCreateNew(ToolID.removing)
                removing_element.source_indexes = source_indexes
            self.elementsSetSelected(None)
        self.update()

    def elementsGetLastElement(self):
        try:
            element = self.elementsFilter()[-1]
        except Exception:
            element = None
        return element

    def elementsGetLastElement1(self):
        try:
            element = self.elementsFilter()[-2]
        except Exception:
            element = None
        return element

    def elementsCopyElementData(self, element, source_element):
        attributes = source_element.__dict__.items()
        for attr_name, attr_value in attributes:
            if attr_name in ["unique_index", "ms"]:
                continue
            type_class = type(attr_value)
            # if type_class is type(None):
            #     print(attr_name)
            #     print(attributes)
            if attr_value is None:
                final_value = attr_value
            elif isinstance(attr_value, Element):
                continue
            else:
                final_value = type_class(attr_value)
            if attr_name == "text_doc" and attr_value is not None:
                element.text_doc = type_class(attr_value)
                element.text_doc.setPlainText(attr_value.toPlainText())
                self.elementsTextElementInit(element)
            else:
                setattr(element, attr_name, final_value)

    def elementsActiveElementParamsToPanelSliders(self):
        tw = self.tools_window
        if not tw:
            return
        if self.active_element is not None:
            el = self.active_element
            tw.color_slider.value = el.color_slider_value
            tw.color_slider.palette_index = el.color_slider_palette_index
            tw.size_slider.value = el.size
            tw.opacity_slider.value = el.opacity
            tw.chb_toolbool.blockSignals(True)
            tw.chb_toolbool.setChecked(el.toolbool)
            tw.chb_toolbool.blockSignals(False)
            tw.set_ui_on_toolchange(element_type=el.oxxxy_type)
            tw.update()
        else:
            tw.set_ui_on_toolchange(hide=True)
            tw.update()
        self.update()

    def elementsRemoveCurrentModificationSlot(self):
        self.elements_modification_index -= 1
        self.modification_slots = self.elementsModificationSlotsFilter()
        self.elements = self.elementsFilter()

    def elementsMakeSureTheresNoUnfinishedElement(self):
        return
        ms = self.elementsGetLastModSlot()
        if ms and ms.content_type in [ToolID.zoom_in_region, ToolID.copypaste] and len(ms.elements) == 1:
            self.elementsRemoveCurrentModificationSlot()

    def elementsOnTransformToolActivated(self):
        if self.active_element:
            self.elementsSetSelected(self.active_element)
        self.elementsActiveElementParamsToPanelSliders()
        self.update()
        self.activateWindow() # чтобы фокус не соскакивал на панель иструментов

    def elementsCreateNewSlot(self, content_type):
        ms = ElementsModificationSlot(content_type)
        self.modification_slots.append(ms)
        self.elements_modification_index += 1
        return ms

    def elementsAppendElementToMS(self, element, ms):
        ms.elements.append(element)
        # для редактора
        element.ms = ms

    def elementsGetLastModSlot(self):
        slots = self.elementsModificationSlotsFilter()
        if slots:
            return slots[-1]
        else:
            return None

    def elementsCreateNew(self, element_oxxxy_type, start_drawing=False,
                                        create_new_slot=True, content_type=None, modification_slot=None):
        # срезание отменённой (невидимой) части истории
        # перед созданием элемента
        if create_new_slot:
            if content_type is None:
                content_type = element_oxxxy_type
            self.modification_slots = self.elementsModificationSlotsFilter()
            ms = self.elementsCreateNewSlot(content_type)
        else:
            if modification_slot is None:
                ms = self.elementsGetLastModSlot()
            else:
                ms = modification_slot
        case1 = element_oxxxy_type == ToolID.removing
        case2 = element_oxxxy_type == ToolID.TEMPORARY_TYPE_NOT_DEFINED
        case3 = start_drawing
        is_removing = case1 or case2 or case3
        self.elements = self.elementsFilter(only_filter=is_removing)
        # создание элемента
        element = Element(element_oxxxy_type, self.elements)
        self.elementsAppendElementToMS(element, ms)
        # обновление индекса после создания элемента
        self.elements_modification_index = len(self.modification_slots)
        return element

    def _elementsSetSelectedPreReset(self):
        for __el in self.elements:
            __el._selected = False
        # пришлось закомментировать, чтобы активный элемент не пропадал
        # во время смены инструментов и при нанесении следующего элемента
        # self.active_element = None

    def elementsSetSelected(self, arg, update_panel=True, update_widget=True):
        els = None
        el = None
        if isinstance(arg, (list, tuple)):
            els = arg
        elif isinstance(arg, Element):
            el = arg

        # reset
        self._elementsSetSelectedPreReset()
        # setting
        if el:
            el._selected = True
            self.active_element = el
        if els:
            for __el in els:
                __el._selected = True
        # updating
        self.init_selection_bounding_box_widget(update_widget=update_widget)
        if update_panel:
            self.elementsActiveElementParamsToPanelSliders()
        self.update()

    def elementsSelectDeselectAll(self):
        any_selected = any(el._selected for el in self.elements)
        if any_selected:
            # delesect all
            for el in self.elements:
                el._selected = False
        else:
            # select all that allowed to select
            for el in self.elementsFilterElementsForSelection():
                el._selected = True
        self.init_selection_bounding_box_widget()
        self.elementsActiveElementParamsToPanelSliders()
        self.update()

    def elementsFilterElementsForSelection(self):
        if self.selection_filter == self.SelectionFilter.all:
            return self.elementsAllVisibleElements()

        elif self.selection_filter == self.SelectionFilter.content_only:
            return self.elementsAllVisibleElementsButBackground()

        elif self.selection_filter == self.SelectionFilter.background_only:
            return self.elementsAllBackgroundElements()

    def elementsSelectionFilterChangedCallback(self):
        self.elementsSetSelected(None)

    def elementsAllVisibleElementsButBackground(self):
        visible_elements = self.elementsAllVisibleElements()
        return [el for el in visible_elements if not el.background_image]

    def elementsAllBackgroundElements(self):
        visible_elements = self.elementsAllVisibleElements()
        return [el for el in visible_elements if el.background_image]

    def elementsAllVisibleElements(self):
        return self.elementsFilter()

    def elementsModificationSlotsFilter(self):
        # all visible slots
        return self.modification_slots[:self.elements_modification_index]

    def elementsFilter(self, only_filter=False):
        # фильтрация по индексу
        visible_elements = []
        for ms in self.elementsModificationSlotsFilter():
            visible_elements.extend(ms.elements)

        if only_filter:
            return visible_elements
        # не показываем удалённые элементы
        # или элементы, что были скопированы для внесения изменений в уже существующие
        remove_indexes = []
        for el in visible_elements:
            remove_indexes.extend(el.source_indexes)
        PASS1_elements = []
        for el in visible_elements:
            if el.unique_index not in remove_indexes:
                PASS1_elements.append(el)
        # ещё один тип фильтрации: элементы с этими индексами проходят фильтрацию
        # только если элемент, который содержит их индексы, прошёл первоначальную фильтрацию
        PASS2_elements = []
        allowed_indexes = []
        for el in PASS1_elements:
            allowed_indexes.extend(el.allowed_indexes)
        for el in PASS1_elements:
            if el.pass_through_filter_only_if_allowed:
                if el.pass2_unique_index in allowed_indexes:
                    PASS2_elements.append(el)
            else:
                PASS2_elements.append(el)
        return PASS2_elements

    def elementsGetElementsUnderMouse(self, cursor_pos):
        elements_under_mouse = []
        for el in self.elementsFilter():
            if el.oxxxy_type in [ToolID.removing,]:
                continue
            element_selection_area = el.get_selection_area(canvas=self)
            is_under_mouse = element_selection_area.containsPoint(cursor_pos, Qt.WindingFill)
            if is_under_mouse:
                elements_under_mouse.append(el)
        return elements_under_mouse

    def elementsMousePressEventDefault(self, element, event, reversed=False):
        event_pos = self.elementsMapToCanvas(QPointF(event.pos()))
        if element.oxxxy_type == ToolID.line and event.modifiers() & Qt.ControlModifier:
            last_element = self.elementsGetLastElement1()
            if last_element and last_element.oxxxy_type == ToolID.line:
                element.start_point = QPointF(last_element.end_point)
            else:
                element.start_point = event_pos
        else:
            if reversed:
                element.start_point = event_pos
                element.end_point = event_pos
            else:
                element.start_point = event_pos
        element.end_point = event_pos
        element.calc_local_data()

    def elementsIsSpecialCase(self, element):
        special_case = element is not None
        ms = self.elementsGetLastModSlot()
        special_case = special_case and ms and ms.content_type in [ToolID.zoom_in_region, ToolID.copypaste]
        # даём возможность создать другой слот
        special_case = special_case and ms and not len(ms.elements) == 2
        return special_case

    def elementsRetrieveElementsFromGroup(self, visible_elements, group_id):
        if group_id is None:
            return []
        else:
            return [el for el in visible_elements if el.group_id == group_id]

    def elementsRetrieveElementsFromUniformGroup(self, visible_elements, group_id):
        if group_id is not None:
            first_element = None
            second_element = None
            for el in visible_elements:
                if el.group_id == group_id:
                    if el.second:
                        second_element = el
                    else:
                        first_element = el
            return first_element, second_element
        else:
            return None, None

    def elementsAdvancedInputPressEvent(self, event, event_pos, element):
        els_count = element.ms.elements.__len__()
        if els_count == 1:
            self.elementsMousePressEventDefault(element, event)
            element.calc_local_data()
            element.second = False
            element.group_id = element.unique_index
        elif els_count == 2:
            element.position = event_pos
            first_element = element.ms.elements[0]
            element.group_id = first_element.group_id
            element.calc_local_data_finish(first_element)
            element.second = True
        else:
            raise Exception("unsupported branch!")

    def elementsAdvancedInputMoveEvent(self, event, event_pos, element, finish=False):
        els_count = element.ms.elements.__len__()
        if els_count == 1:
            element.end_point = event_pos
            element.calc_local_data()
            if finish:
                element.finished = True
                self.elementsSetCopiedPixmap(element)
        elif els_count == 2:
            element.position = event_pos
        else:
            raise Exception("unsupported branch!")

    def elementsMousePressEvent(self, event):
        tool = self.current_tool

        event_pos = self.elementsMapToCanvas(QPointF(event.pos()))

        self.prev_elements_modification_index = self.elements_modification_index
        isLeftButton = event.buttons() == Qt.LeftButton
        isAltOnly = event.modifiers() == Qt.AltModifier
        isCaptureZone = self.capture_region_rect is not None
        if self.current_tool == ToolID.none and isLeftButton and isCaptureZone and not isAltOnly:
            self.current_capture_zone_center = self.capture_region_rect.center()
            self.ocp = event.pos()
            self.drag_capture_zone = True
            return
        else:
            self.drag_capture_zone = False

        if self.current_tool == ToolID.none:
            return
        if self.current_tool == ToolID.picture and not self.current_picture_pixmap:
            self.tools_window.show_picture_menu()
            return

        # вызов elementsSetElementParameters сбрасывает значение переменной,
        # поэтому сохраняем значение здесь
        fixed_active_element = self.active_element

        # основная часть
        el = self.elementsGetLastElement()
        if self.current_tool == ToolID.transform:
            element = None
        elif self.elementsIsSpecialCase(el):
            # zoom_in_region and copypaste case, when it needs more additional clicks
            element = self.elementsCreateNew(self.current_tool, start_drawing=True, create_new_slot=False)
            self.elementsSetElementParameters(element)
        elif self.current_tool == ToolID.text:
            arrow_element = self.elementsCreateNew(ToolID.arrow, start_drawing=True)
            arrow_element._modified = False
            arrow_element.color = QColor(Qt.red)
            arrow_element.size = 0.5
            element = self.elementsCreateNew(self.current_tool, create_new_slot=False)
            self.elementsSetElementParameters(element)
            element.arrow = arrow_element
        else:
            # default case
            element = self.elementsCreateNew(self.current_tool, start_drawing=True)
            self.elementsSetElementParameters(element)

        if element and element.oxxxy_type == ToolID.arrowstree:
            if not event.modifiers() & Qt.ControlModifier:
                self.elementsCreateEdgeWithNearestNode(element)
            else:
                self.elementsMarkRoot(element)

        self.active_element = element
        # #######
        if tool == ToolID.arrow:
            self.elementsMousePressEventDefault(element, event)
        elif tool == ToolID.arrowstree:
            self.elementsMousePressEventDefault(element, event)
        elif tool in [ToolID.zoom_in_region, ToolID.copypaste]:
            self.elementsAdvancedInputPressEvent(event, event_pos, element)
        elif tool == ToolID.picture:
            element.pixmap = self.current_picture_pixmap
            element.rotation = self.current_picture_angle
            element.position = event_pos
            element.calc_local_data()
        elif tool in [ToolID.pen, ToolID.marker]:
            if event.modifiers() & Qt.ShiftModifier:
                element.straight = True
                self.elementsMousePressEventDefault(element, event)
            else:
                element.straight = False
                path = QPainterPath()
                path.moveTo(event_pos)
                element.path = path
                self.elementsMousePressEventDefault(element, event)
        elif tool == ToolID.line:
            self.elementsMousePressEventDefault(element, event)
        elif tool in [ToolID.oval, ToolID.rect, ToolID.numbering, ToolID.multiframing]:
            element.equilateral = bool(event.modifiers() & Qt.ShiftModifier)
            element.filled = bool(event.modifiers() & Qt.ControlModifier)
            self.elementsMousePressEventDefault(element, event)
        elif tool == ToolID.text:
            self.elementsMousePressEventDefault(element, event)
            self.elementsMousePressEventDefault(element.arrow, event, reversed=True)
            element.calc_local_data()
            element.arrow.calc_local_data()
        elif tool in [ToolID.blurring, ToolID.darkening]:
            self.elementsMousePressEventDefault(element, event)
            if tool == ToolID.blurring:
                element.finished = False
        elif tool == ToolID.transform:

            self.elementsTextElementDeactivateEditMode()

            if self.is_over_scaling_activation_area(event.pos()):
                self.elementsStartModificationProcess('mouse; scaling')
                self.canvas_START_selected_elements_SCALING(event)

            elif self.is_over_rotation_activation_area(event.pos()):
                self.elementsStartModificationProcess('mouse; rotation')
                self.canvas_START_selected_elements_ROTATION(event.pos())

            elif self.any_element_area_under_mouse(event.modifiers() & Qt.ShiftModifier):
                self.elementsStartModificationProcess('mouse; translation')
                self.canvas_START_selected_elements_TRANSLATION(event.pos())
                self.update_selection_bouding_box()

            else:
                self.selection_start_point = QPointF(event.pos())
                self.selection_rect = None
                self.selection_ongoing = True

        self.update()

    def equilateral_delta(self, delta):
        sign = math.copysign(1.0, delta.x())
        if delta.y() < 0:
            if delta.x() < 0:
                sign = 1.0
            else:
                sign = -1.0
        delta.setX(int(delta.y()*sign))
        return delta

    def elementsTextElementRotate(self, clockwise_rotation):
        element = None
        for el in self.elementsFilter():
            if el.oxxxy_type == ToolID.text:
                element = el
        if element:
            if clockwise_rotation:
                delta = 10
            else:
                delta = -10
            element.rotation += delta
        self.update()

    def elementsMoveElement(self, event):
        self.elementsStartModificationProcess('arrows')
        modifiers = QApplication.queryKeyboardModifiers()
        value = 1
        if modifiers & Qt.ShiftModifier:
            value = 10
        key = event.key()
        if key == Qt.Key_Up:
            delta = QPoint(0, -value)
        elif key == Qt.Key_Down:
            delta = QPoint(0, value)
        elif key == Qt.Key_Right:
            delta = QPoint(value, 0)
        elif key == Qt.Key_Left:
            delta = QPoint(-value, 0)
        new_elements = []
        for element in self.selected_items[:]:
            mod_el = self.elementsPrepareElementCopyForModifications(element)
            new_elements.append(mod_el)
            if hasattr(mod_el, 'position'):
                mod_el.position += delta
            else:
                raise Exception('Unsupported type:', mod_el.oxxxy_type)
        self.elementsSetSelected(new_elements)
        self.update()

    def elementsSetCursorShapeInsideCaptureZone(self):
        cursor_pos = self.mapFromGlobal(QCursor().pos())
        is_tool_transform = self.current_tool == ToolID.transform
        if is_tool_transform:
            return self.define_transform_tool_cursor()
        else:
            return self.get_custom_cross_cursor()

    def move_capture_rect(self, delta):
        self.capture_region_rect.moveCenter(self.current_capture_zone_center + delta)
        self.input_POINT1 = self.capture_region_rect.topLeft()
        self.input_POINT2 = self.capture_region_rect.bottomRight()

    def elementsMouseDoubleClick(self, event):
        for el in self.elementsFilter():
            el_selection_area = el.get_selection_area(canvas=self)
            is_under_mouse = el_selection_area.containsPoint(self.mapped_cursor_pos(), Qt.WindingFill)
            if is_under_mouse:
                el.oxxxy_type == ToolID.text:
                self.elementsTextElementActivateEditMode(el)
                break

    def elementsMouseMoveEvent(self, event):
        event_pos = self.elementsMapToCanvas(QPointF(event.pos()))

        tool = self.current_tool
        isLeftButton = event.buttons() == Qt.LeftButton
        isMiddleButton = event.buttons() == Qt.MiddleButton
        if self.drag_capture_zone and isLeftButton:
            delta = QPoint(event.pos() - self.ocp)
            delta = QPointF(delta.x()/self.canvas_scale_x, delta.y()/self.canvas_scale_y)
            self.move_capture_rect(delta.toPoint())

        if tool == ToolID.none:
            return
        # основная часть
        element = self.elementsGetLastElement()
        if element is None:
            return
        if tool == ToolID.arrow:
            element.end_point = event_pos
            if event.modifiers() & Qt.ShiftModifier:
                element.end_point = constraint45Degree(element.start_point, element.end_point)
            element.calc_local_data()
        elif tool == ToolID.arrowstree:
            element.end_point = event_pos
            element.calc_local_data()
            self.elementsArrowsTreeNodeOrientToEdgeNeighbor(element)
        elif tool in [ToolID.zoom_in_region, ToolID.copypaste]:
            self.elementsAdvancedInputMoveEvent(event, event_pos, element)
        elif tool == ToolID.picture:
            element.pixmap = self.current_picture_pixmap
            element.rotation = self.current_picture_angle
            element.position = event_pos
        elif tool in [ToolID.pen, ToolID.marker]:
            if element.straight:
                element.end_point = event_pos
            else:
                element.path.lineTo(event_pos)
                element.end_point = event_pos
            element.calc_local_data()
        elif tool == ToolID.line:
            element.end_point = event_pos
            if event.modifiers() & Qt.ShiftModifier:
                element.end_point = constraint45Degree(element.start_point, element.end_point)
            element.calc_local_data()
        elif tool in [ToolID.oval, ToolID.rect, ToolID.numbering, ToolID.multiframing]:
            element.filled = bool(event.modifiers() & Qt.ControlModifier)
            element.equilateral = bool(event.modifiers() & Qt.ShiftModifier)
            if element.equilateral:
                delta = element.start_point - event_pos
                delta = self.equilateral_delta(delta)
                element.end_point = element.start_point - delta
            else:
                element.end_point = event_pos
            element.calc_local_data()
        elif tool == ToolID.text:
            element.end_point = event_pos
            element.arrow.start_point = event_pos
            element.calc_local_data()
            element.arrow.calc_local_data()
        elif tool in [ToolID.blurring, ToolID.darkening]:
            element.equilateral = bool(event.modifiers() & Qt.ShiftModifier)
            if element.equilateral:
                delta = element.start_point - event_pos
                delta = self.equilateral_delta(delta)
                element.end_point = element.start_point - delta
            else:
                element.end_point = event_pos
            element.calc_local_data()
        elif tool == ToolID.transform:
            no_mod = event.modifiers() == Qt.NoModifier

            self.canvas_ALLOW_selected_elements_TRANSLATION(event.pos())

            if any((self.translation_ongoing, self.scaling_ongoing, self.rotation_ongoing)):
                new_elements = []
                for element in self.selected_items[:]:
                    mod_element = self.elementsPrepareElementCopyForModifications(element)
                    new_elements.append(mod_element)

                    if mod_element.oxxxy_type == ToolID.text:
                        self.elementsTextElementUpdateProxyPixmap(mod_element)

                self.elementsSetSelected(new_elements, update_panel=False, update_widget=False)

            if self.transform_cancelled:
                pass

            elif self.scaling_ongoing:
                self.canvas_DO_selected_elements_SCALING(event.pos())

            elif self.rotation_ongoing:
                self.canvas_DO_selected_elements_ROTATION(event.pos())

            elif self.translation_ongoing:
                self.canvas_DO_selected_elements_TRANSLATION(event.pos())
                self.update_selection_bouding_box()

            elif self.selection_ongoing is not None:
                self.selection_end_point = QPointF(event.pos())
                if self.selection_start_point:
                    self.selection_rect = build_valid_rectF(self.selection_start_point, self.selection_end_point)
                    self.canvas_selection_callback(event.modifiers() == Qt.ShiftModifier)

            self.elementsUpdateDependentElementsOnTransforms()

        self.update()

    def elementsMouseReleaseEvent(self, event):
        event_pos = self.elementsMapToCanvas(QPointF(event.pos()))


        tool = self.current_tool
        if self.drag_capture_zone:
            self.drag_capture_zone = False
            return
        element = self.elementsGetLastElement()
        if element is None:
            return
        if tool == ToolID.arrow:
            element.end_point = event_pos
            if event.modifiers() & Qt.ShiftModifier:
                element.end_point = constraint45Degree(element.start_point, element.end_point)
            element.calc_local_data()
            element.recalc_local_data_for_straight_objects()
            element.construct_selection_path(self)
        elif tool == ToolID.arrowstree:
            element.end_point = event_pos
            element.calc_local_data()
            self.elementsArrowsTreeNodeClearInputData(element)
        elif tool in [ToolID.zoom_in_region, ToolID.copypaste]:
            self.elementsAdvancedInputMoveEvent(event, event_pos, element, finish=True)
        elif tool == ToolID.picture:
            element.pixmap = self.current_picture_pixmap
            element.rotation = self.current_picture_angle
            element.position = event_pos
            self.elementsSetPixmapFromMagazin()
        elif tool in [ToolID.pen, ToolID.marker]:
            if element.straight:
                element.end_point = event_pos
            else:
                element.end_point = event_pos
                element.path.lineTo(event_pos)
            element.calc_local_data()
            if element.straight:
                element.recalc_local_data_for_straight_objects()
            element.construct_selection_path(self)
        elif tool == ToolID.line:
            element.end_point = event_pos
            if event.modifiers() & Qt.ShiftModifier:
                element.end_point = constraint45Degree(element.start_point, element.end_point)
            element.calc_local_data()
            element.recalc_local_data_for_straight_objects()
            element.construct_selection_path(self)
        # где-то здесь надо удалять элементы, если начальная и конечная точки совпадают
        elif tool in [ToolID.oval, ToolID.rect, ToolID.numbering, ToolID.multiframing]:
            if element.equilateral:
                delta = element.start_point - event_pos
                delta = self.equilateral_delta(delta)
                element.end_point = element.start_point - delta
            else:
                element.end_point = event_pos
            element.calc_local_data()
        elif tool == ToolID.text:
            element.start_point = event_pos
            element.end_point = event_pos + QPointF(200, 50)
            element.calc_local_data()
            element.arrow.calc_local_data()
            element.arrow.group_id = element.unique_index
            element.group_id = element.unique_index
            a = element.arrow
            arrow_included = True
            if QVector2D(a.end_point-a.start_point).length() < 100.0:
                self.elements.remove(a)
                element.ms.elements.remove(a)
                a.ms = None
                arrow_included = False
            ms = self.elementsGetLastModSlot()
            if arrow_included:
                ms.content_type = 'text with arrow'
            else:
                ms.content_type = 'text'
            element.arrow = None
            del element.arrow # чтобы не было проблем при сохранении файла
            self.elementsImplantTextElement(element)
            if arrow_included:
                self.elementsTextElementRecalculateGabarit(element)
                self.elementsFixArrowStartPositionIfNeeded(element)
        elif tool in [ToolID.blurring, ToolID.darkening]:
            element.equilateral = bool(event.modifiers() & Qt.ShiftModifier)
            if element.equilateral:
                delta = element.start_point - event_pos
                delta = self.equilateral_delta(delta)
                element.end_point = element.start_point - delta
            else:
                element.end_point = event_pos
            element.calc_local_data()
            if tool == ToolID.blurring:
                element.finished = True
                self.elementsSetBlurredPixmap(element)
        elif tool == ToolID.transform:

            ctrl = event.modifiers() & Qt.ControlModifier
            shift = event.modifiers() & Qt.ShiftModifier
            no_mod = event.modifiers() == Qt.NoModifier
            alt = event.modifiers() & Qt.AltModifier

            if self.transform_cancelled:
                self.transform_cancelled = False
                return

            if event.button() == Qt.LeftButton:
                self.start_translation_pos = None

                if any((self.translation_ongoing, self.scaling_ongoing, self.rotation_ongoing)):
                    if self.selected_items:
                        if any([el for el in self.selected_items if el.background_image]):
                            for el in self.elements:
                                if el.oxxxy_type == ToolID.blurring:
                                    el.finished = True
                                    self.elementsSetBlurredPixmap(el)
                                elif el.oxxxy_type == [ToolID.zoom_in_region, ToolID.copypaste]:
                                    if not el.second:
                                        self.elementsSetCopiedPixmap(el)

                        for el in self.selected_items:
                            if el.oxxxy_type in [ToolID.arrow, ToolID.text]:
                                self.elementsFixArrowStartPositionIfNeeded(el)
                                if el.oxxxy_type == ToolID.text:
                                    self.elementsTextElementUpdateProxyPixmap(el)

                if not alt and not self.translation_ongoing and not self.rotation_ongoing and not self.scaling_ongoing:
                    self.canvas_selection_callback(event.modifiers() == Qt.ShiftModifier)
                    # if self.selection_rect is not None:
                    self.selection_start_point = None
                    self.selection_end_point = None
                    self.selection_rect = None
                    self.selection_ongoing = False

                if self.rotation_ongoing:
                    self.canvas_FINISH_selected_elements_ROTATION(event)

                if self.scaling_ongoing:
                    self.canvas_FINISH_selected_elements_SCALING(event)

                if self.translation_ongoing:
                    self.canvas_FINISH_selected_elements_TRANSLATION(event)
                    self.selection_start_point = None
                    self.selection_end_point = None
                    self.selection_rect = None
                    self.selection_ongoing = False

                self.elementsUpdateDependentElementsOnTransforms()

        self.elementsStopModificationProcess()

        self.elementsAutoDeleteInvisibleElement(element)
        self.tools_window.forwards_backwards_update()
        self.update()

    def elementsUpdateDependentElementsOnTransforms(self):
        if self.selected_items:
            for se in self.selected_items:
                if se.oxxxy_type == ToolID.blurring:
                    se.finished = True
                    self.elementsSetBlurredPixmap(se)
                elif se.oxxxy_type in [ToolID.zoom_in_region, ToolID.copypaste]:
                    if not se.second:
                        self.elementsSetCopiedPixmap(se)
                elif se.oxxxy_type == ToolID.text:
                    se.end_point_modified = True

    def elementsAutoDeleteInvisibleElement(self, element):
        tool = self.current_tool
        if tool in [ToolID.line, ToolID.pen, ToolID.marker]:
            if element.end_point == element.start_point:
                self.elements.remove(element)
                if self.tools_window:
                    self.elements_modification_index = self.prev_elements_modification_index
                    # print('correcting after autodelete')

    def elementsSetCopiedPixmap(self, element):
        if element.second:
            return

        if False:
            er = element.get_size_rect(scaled=True)
            capture_pos = element.position
            capture_width = er.width()
            capture_height = er.height()
            capture_rotation = element.rotation
            pixmap = QPixmap.fromImage(self.source_pixels)
            element.pixmap = capture_rotated_rect_from_pixmap(pixmap,
                capture_pos,
                capture_rotation,
                capture_width,
                capture_height
            )
        else:
            capture_region_rect = element.get_canvas_space_selection_area().boundingRect()
            pixmap = self.elementsRenderFinal(
                capture_region_rect=capture_region_rect,
                draw_background_only=True,
                no_multiframing=True,
                clean=True
            )
            er = element.get_size_rect(scaled=True)
            capture_pos = element.position - capture_region_rect.topLeft()
            capture_width = er.width()
            capture_height = er.height()
            capture_rotation = element.rotation
            element.pixmap = capture_rotated_rect_from_pixmap(pixmap,
                capture_pos,
                capture_rotation,
                capture_width,
                capture_height
            )

    def elementsSetBlurredPixmap(self, element):
        if not element.finished:
            return

        if False:
            element_area = element.get_canvas_space_selection_area()
            eabr = element_area.boundingRect()
            canvas_source_rect = build_valid_rectF(QPointF(0, 0), eabr.bottomRight())

            # код для учёта затемнения в фоне
            cropped_source_pixels = QPixmap(canvas_source_rect.size().toSize())
            cropped_source_pixels.fill(Qt.transparent)
            pr = QPainter()
            pr.begin(cropped_source_pixels)
            target_rect = canvas_source_rect
            source_rect = canvas_source_rect
            pr.drawImage(target_rect, self.source_pixels, source_rect)
            self.elementsDrawDarkening(pr, prepare_pixmap=True)
            pr.end()
            del pr

            er = element.get_size_rect(scaled=True)
            capture_pos = element.position
            capture_width = er.width()
            capture_height = er.height()
            capture_rotation = element.rotation
            source_pixmap = cropped_source_pixels
            element.pixmap = capture_rotated_rect_from_pixmap(source_pixmap,
                capture_pos,
                capture_rotation,
                capture_width,
                capture_height
            )
        else:

            capture_region_rect = element.get_canvas_space_selection_area().boundingRect()
            source_pixmap = self.elementsRenderFinal(
                capture_region_rect=capture_region_rect,
                draw_background_only=True,
                no_multiframing=True,
                prepare_darkening=True,
                clean=True,
            )
            er = element.get_size_rect(scaled=True)
            capture_pos = element.position - capture_region_rect.topLeft()
            capture_width = er.width()
            capture_height = er.height()
            capture_rotation = element.rotation
            element.pixmap = capture_rotated_rect_from_pixmap(source_pixmap,
                capture_pos,
                capture_rotation,
                capture_width,
                capture_height
            )

        blured = QPixmap(er.size().toSize())
        blured.fill(Qt.transparent)
        if element.toolbool:
            pixel_size = int(element.size*60)+1
            orig_width = element.pixmap.width()
            orig_height = element.pixmap.height()
            element.pixmap = element.pixmap.scaled(
                orig_width//pixel_size,
                orig_height//pixel_size).scaled(orig_width, orig_height)
        else:
            blur_radius = 30*element.size #30 is maximum
            blured = apply_blur_effect(element.pixmap, blured, blur_radius=blur_radius)
            blured = apply_blur_effect(blured, blured, blur_radius=2)
            blured = apply_blur_effect(blured, blured, blur_radius=blur_radius)
            blured = apply_blur_effect(blured, blured, blur_radius=5)
            element.pixmap = blured

    def elementsFixArrowStartPositionIfNeeded(self, element):
        ve = self.elementsFilter()
        elements_in_group = self.elementsRetrieveElementsFromGroup(ve, element.group_id)
        if elements_in_group.__len__() > 1:
            arrow_element = None
            text_element = None
            if element.oxxxy_type == ToolID.text:
                elements_in_group.remove(element)
                arrow_element = elements_in_group[0]
                text_element = element
            elif element.oxxxy_type == ToolID.arrow:
                arrow_element = element
                elements_in_group.remove(element)
                text_element = elements_in_group[0]
            if arrow_element and text_element:
                # все вычисления проводим в canvas space
                text_rect = text_element.get_size_rect(scaled=True)
                text_rect.moveCenter(QPointF(0, 0))
                text_transform = QTransform()
                text_transform.rotate(text_element.rotation)
                p1 = text_transform.map(text_rect.bottomLeft())
                p2 = text_transform.map(text_rect.topLeft())
                p3 = text_transform.map(text_rect.topRight())
                p4 = text_transform.map(text_rect.bottomRight())

                p1 += text_element.position
                p2 += text_element.position
                p3 += text_element.position
                p4 += text_element.position

                modified_start_point = get_nearest_point_on_rect(p1, p2, p3, p4, arrow_element.end_point)
                arrow_element.start_point = modified_start_point
                arrow_element.calc_local_data()
                arrow_element.recalc_local_data_for_straight_objects()
                arrow_element.construct_selection_path(self)

    def elementsDrawDarkening(self, painter, prepare_pixmap=False):
        if self.capture_region_rect:
            darkening_value = 0.0
            darkening_zone = QPainterPath()
            darkening_zone.setFillRule(Qt.WindingFill)
            at_least_one_exists = False
            for element in self.elementsFilter():
                if element.oxxxy_type == ToolID.darkening:
                    at_least_one_exists = True
                    darkening_value = element.size
                    if prepare_pixmap:
                        element_area = element.get_canvas_space_selection_area()
                    else:
                        element_area = element.get_selection_area(canvas=self)
                    piece = QPainterPath()
                    piece.addPolygon(element_area)
                    darkening_zone = darkening_zone.united(piece)
            if at_least_one_exists:
                painter.setClipping(True)
                capture_rect = QRectF(self.capture_region_rect)
                capture_rect.setTopLeft(QPoint(0,0))
                painter.setClipRect(QRectF(capture_rect))
                painter.setOpacity(0.1+0.9*darkening_value)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(Qt.black))
                capture_dark = QPainterPath()
                capture_dark.addRect(QRectF(capture_rect))
                capture_dark.addPath(darkening_zone)
                painter.drawPath(capture_dark)
                painter.setOpacity(1.0)
                painter.setClipping(False)

    def elementsGetPenFromElement(self, element):
        color = element.color
        size = element.size
        if element.oxxxy_type in [ToolID.pen, ToolID.line]:
            PEN_SIZE = 25
        elif element.oxxxy_type == ToolID.marker:
            PEN_SIZE = 40
            color.setAlphaF(0.3)
        else:
            PEN_SIZE = 25
        pen = QPen(color, 1+PEN_SIZE*size)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen, color, size

    def elementsDrawMainElement(self, painter, element, final, ve):
        el_type = element.oxxxy_type
        pen, color, size = self.elementsGetPenFromElement(element)
        painter.setPen(pen)
        painter.setBrush(QBrush(color))
        element.enable_distortion_fixer()
        if el_type == ToolID.arrow:
            painter.setTransform(element.get_transform_obj(canvas=self))
            painter.setPen(Qt.NoPen)
            self.elementsDrawArrow(painter, element.local_start_point, element.local_end_point, size, True)
            painter.resetTransform()
        elif el_type in [ToolID.pen, ToolID.marker]:
            painter.setTransform(element.get_transform_obj(canvas=self))
            painter.setBrush(Qt.NoBrush)
            if element.preview:
                painter.drawPoint(QPointF(0, 0))
            else:
                if element.straight:
                    painter.drawLine(element.local_start_point, element.local_end_point)
                else:
                    p = element.path
                    # хоть это и некрасиво, но путь надо корректировать только тут,
                    # иначе будут баги с отрисовкой в процессе нанесения
                    path = p.translated(-p.boundingRect().center())
                    painter.drawPath(path)
            painter.resetTransform()
        elif el_type == ToolID.line:
            painter.setTransform(element.get_transform_obj(canvas=self))
            if element.preview:
                painter.drawPoint(QPointF(0, 0))
            else:
                sp = element.local_start_point
                ep = element.local_end_point
                painter.drawLine(sp, ep)
            painter.resetTransform()
        elif el_type in [ToolID.multiframing]:
            if not final:
                painter.save()
                painter.setPen(QPen(QColor(255, 0, 0), 1))
                painter.setBrush(Qt.NoBrush)
                rect = build_valid_rectF(element.local_start_point, element.local_end_point)
                painter.setTransform(element.get_transform_obj(canvas=self))
                cm = painter.compositionMode()
                painter.setCompositionMode(QPainter.RasterOp_NotDestination) #RasterOp_SourceXorDestination
                painter.drawRect(rect)
                painter.setCompositionMode(cm)
                painter.resetTransform()
                painter.restore()
        elif el_type in [ToolID.oval, ToolID.rect, ToolID.numbering]:
            painter.setTransform(element.get_transform_obj(canvas=self))
            cur_brush = painter.brush()
            if not element.filled:
                painter.setBrush(Qt.NoBrush)
            rect = build_valid_rect(element.local_start_point, element.local_end_point)
            if el_type == ToolID.oval:
                painter.drawEllipse(rect)
            else:
                painter.drawRect(rect)
            if el_type == ToolID.numbering:
                w = self.NUMBERING_ELEMENT_WIDTH
                end_point_rect = QRectF(element.local_end_point - QPointF(int(w/2), int(w/2)), QSizeF(w, w))
                painter.setBrush(cur_brush)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(end_point_rect)
                if color == Qt.white:
                    painter.setPen(QPen(Qt.black))
                else:
                    painter.setPen(QPen(Qt.white))
                font = painter.font()
                font.setFamily("Consolas")
                font.setWeight(1600)
                painter.setFont(font)
                painter.drawText(end_point_rect.adjusted(-20, -20, 20, 20), Qt.AlignCenter,
                                                                        str(element.number))
            painter.resetTransform()
        elif el_type == ToolID.text:
            self.elementsTextElementDrawOnCanvas(painter, element, final)
        elif el_type in [ToolID.blurring, ToolID.darkening]:
            painter.setTransform(element.get_transform_obj(canvas=self))
            rect = build_valid_rectF(element.local_start_point, element.local_end_point)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(Qt.NoPen)
            if el_type == ToolID.blurring:
                if not element.finished:
                    painter.setBrush(QBrush(QColor(150, 0, 0), Qt.DiagCrossPattern))
                else:
                    painter.drawPixmap(rect, element.pixmap, QRectF(element.pixmap.rect()))
            elif el_type == ToolID.darkening:
                pass
            painter.drawRect(rect)
            painter.resetTransform()
        elif el_type == ToolID.picture:
            if element.background_image and not self.show_background:
                pass
            else:
                current_opacity = painter.opacity()
                picture_opacity = current_opacity*element.opacity
                painter.setTransform(element.get_transform_obj(canvas=self))
                painter.setOpacity(min(1.0, picture_opacity))
                pixmap = element.pixmap
                r = element.get_size_rect()
                r.moveCenter(QPointF(0, 0))
                s = QRectF(QPointF(0,0), QSizeF(pixmap.size()))
                painter.drawPixmap(r, pixmap, s)
                painter.setOpacity(current_opacity)
                painter.resetTransform()
        elif el_type == ToolID.removing:
            if self.Globals.CRASH_SIMULATOR:
                1 / 0
        elif el_type == ToolID.arrowstree:
            self.elementsDrawArrowsTreeNode(painter, element, final)
        elif el_type in [ToolID.zoom_in_region, ToolID.copypaste]:

            painter.setBrush(Qt.NoBrush)

            f_element, s_element = self.elementsRetrieveElementsFromUniformGroup(ve, element.group_id)

            if s_element is None:
                output_pos = self.elementsMapToCanvas(QCursor().pos())
                apply_circle_mask = f_element.toolbool
                color = f_element.color
            else:
                output_pos = s_element.position
                apply_circle_mask = s_element.toolbool
                color = s_element.color

            if el_type == ToolID.zoom_in_region:
                painter.setPen(QPen(color, 1))
            if el_type == ToolID.copypaste:
                painter.setPen(QPen(Qt.red, 1, Qt.DashLine))


            # отрисовка первой пометки
            if not element.second:
                painter.setTransform(element.get_transform_obj(canvas=self))
                if el_type == ToolID.zoom_in_region or (el_type == ToolID.copypaste and not final):
                    capture_rect = build_valid_rectF(
                        f_element.local_start_point,
                        f_element.local_end_point
                    )
                    if apply_circle_mask and el_type == ToolID.zoom_in_region:
                        if not element.finished:
                            # отрисовка только при нанесении, потом отрисовка будет происходить через второй элемент
                            capture_rect = squarize_rect(capture_rect)
                            painter.drawEllipse(capture_rect)
                    else:
                        painter.drawRect(capture_rect)
                painter.resetTransform()

            # отрисовка второй пометки, которая ещё и отрисовываться как превью при нанесении
            special_case = (not element.second and f_element.finished and s_element is None)
            if special_case:
                # заменяем пока не нарисованный второй элемент на превью
                self._te.position = output_pos
                self._te.oxxxy_type = element.oxxxy_type
                self._te.calc_local_data_finish(f_element)
                s_element = self._te

            if element.second or special_case:
                painter.setTransform(s_element.get_transform_obj(canvas=self))
                output_rect = element.get_size_rect(scaled=False)
                if s_element is None:
                    pos = output_pos - f_element.position
                    if el_type in [ToolID.zoom_in_region]:
                        s = ZOOM_IN_REGION_DAFAULT_SCALE
                    else:
                        s = 1.0
                    output_rect = QRectF(0, 0, output_rect.width()*s, output_rect.height()*s)
                else:
                    pos = output_pos - s_element.position
                output_rect.moveCenter(pos)


                if apply_circle_mask and el_type not in [self.ToolID.copypaste]:
                    painter.setClipping(True)
                    path = QPainterPath()
                    r = squarize_rect(element.get_size_rect(scaled=False))
                    r.moveCenter(QPointF(0, 0))
                    path.addEllipse(r)
                    painter.setClipPath(path)
                    painter.drawPixmap(output_rect, f_element.pixmap, QRectF(f_element.pixmap.rect()))
                    painter.setClipping(False)
                else:
                    painter.drawPixmap(output_rect, f_element.pixmap, QRectF(f_element.pixmap.rect()))

                if el_type == ToolID.zoom_in_region:
                    if apply_circle_mask:
                        output_rect = squarize_rect(output_rect)
                        painter.drawEllipse(output_rect)
                    else:
                        painter.drawRect(output_rect)

                # выпуклая оболочка для прямоугольников или касательные к окружностям
                if el_type == ToolID.zoom_in_region:
                    convex_hull_points = []
                    tangent_lines_points = []
                    kwargs = {
                        "canvas":self,
                        "apply_local_scale":True,
                        "apply_translation":True,
                        "apply_global_scale":False
                    }
                    f_canvas_transform = f_element.get_transform_obj(**kwargs)

                    # ! рисуем относительно фрейма второго элемента
                    s_canvas_transform = s_element.get_transform_obj(**kwargs)
                    size_rect_local = s_element.get_size_rect(scaled=False)

                    def map_point(point_pos):
                        point_pos = f_canvas_transform.map(point_pos)
                        sc_inv, status = s_canvas_transform.inverted()
                        if not status:
                            # inverted matrix doesn't exist!
                            return None
                        point_pos = sc_inv.map(point_pos)
                        return point_pos

                    if apply_circle_mask:
                        c1 = map_point(QPointF(0, 0))
                        if c1 is not None:
                            c2 = QPointF(0, 0)
                            r = squarize_rect(f_element.get_size_rect(scaled=False))
                            radius_length = map_point(QPointF(r.width()/2,0))
                            r1 = QVector2D(c1 - radius_length).length()
                            r2 = min(size_rect_local.width(), size_rect_local.height())/2
                            tangent_lines_points = calculate_tangent_points(c1, r1, c2, r2)

                            # рисуем кружок первой пометки
                            # рисуем именно здесь, чтобы толщины линий были одинаковыми
                            f_rect = QRectF(0, 0, r1*2, r1*2)
                            f_rect.moveCenter(c1)
                            painter.drawEllipse(f_rect)

                    else:

                        size_rect = f_element.get_size_rect(scaled=False)
                        size_rect.moveCenter(QPointF(0, 0))
                        sr1_points = get_rect_corners(size_rect)
                        for p in sr1_points:
                            # from f_element local to canvas world
                            p = f_canvas_transform.map(p)
                            # from canvas world to s_element local
                            t = s_canvas_transform.inverted()
                            if not t[1]:
                                raise Exception('inverted matrix doesn\'t exist!')
                            s_canvas_transform_inverted = t[0]
                            p = s_canvas_transform_inverted.map(p)
                            convex_hull_points.append(p)

                        size_rect_local.moveCenter(QPointF(0, 0))
                        sr2_points = get_rect_corners(size_rect_local)
                        for p in sr2_points:
                            convex_hull_points.append(p)

                    if convex_hull_points:
                        coords = convex_hull(convex_hull_points)
                        if coords is not None and len(coords) > 1:
                            coords.append(coords[0])
                            for n, coord in enumerate(coords[:-1]):
                                painter.drawLine(coord, coords[n+1])

                    if tangent_lines_points:
                        for line in tangent_lines_points:
                            painter.drawLine(line[0], line[1])



                painter.resetTransform()

            painter.resetTransform()
        element.disable_distortion_fixer()


    def elementsDrawBackgroundGhost(self, painter, self_rect):
        if False:
            painter.fillRect(self_rect, QColor(0, 0, 0, 150))
        else:
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
            unmodificated_backgrounds = self.modification_slots[0].elements
            visible_backgorunds = self.elementsFilter()
            if False:
                elements = visible_backgorunds
            else:
                elements = unmodificated_backgrounds
            backgrounds = [el for el in elements if el.background_image]
            for bg in backgrounds:
                sa = bg.get_selection_area(canvas=self)
                painter.drawPolygon(sa)
            painter.restore()

    def elementsDrawMainBackgroundOnlyNotFinal(self, painter):
        self.elementsDrawMain(painter, final=False, draw_background_only=True)

    def elementsGenerateDateTimeStamp(self, picture_rect, text_rect, text, font, base=False):
        stamp = QPixmap(picture_rect.width(), picture_rect.height())
        stamp.fill(Qt.transparent)
        ps = QPainter()
        ps.begin(stamp)
        # coral   #FF7F50 rgb(255,127,80)
        # tomato  #FF6347 rgb(255,99,71)
        # orangered   #FF4500 rgb(255,69,0)
        # gold    #FFD700 rgb(255,215,0)
        # orange  #FFA500 rgb(255,165,0)
        # darkorange  #FF8C00 rgb(255,140,0)
        if base:
            color = QColor("#FFD700")
        else:
            color = QColor(Qt.red) # "#FF4500"
        ps.setPen(QPen(color))
        ps.setFont(font)
        _pos = stamp.rect().bottomRight() - QPoint(text_rect.height(), 0)
        ps.drawText(text_rect, Qt.AlignLeft, text)
        ps.end()
        return stamp

    def elementsDrawDateTime(self, painter, pos=None):
        tw = self.tools_window
        if tw and tw.chb_datetimestamp.isChecked():

            font = QFont(self.Globals.SEVEN_SEGMENT_FONT)
            font.setPixelSize(20)
            painter.save()
            painter.setFont(font)
            text = self.datetime_stamp

            text_rect_b = painter.boundingRect(QRect(), Qt.AlignLeft, text)
            picture_rect = text_rect_b.adjusted(0, 0, 20, 10)
            text_rect = painter.boundingRect(picture_rect, Qt.AlignHCenter | Qt.AlignVCenter, text)

            stamp1 = self.elementsGenerateDateTimeStamp(picture_rect, text_rect, text, font, base=True)
            stamp2 = self.elementsGenerateDateTimeStamp(picture_rect, text_rect, text, font)

            result = QPixmap(picture_rect.width(), picture_rect.height())
            result.fill(Qt.transparent)

            # здесь result и stamp поменяны местами, чтобы текст был резким
            result = apply_blur_effect(result, stamp1, blur_radius=20)

            # блюр
            result = apply_blur_effect(stamp2, result, blur_radius=5)
            result = apply_blur_effect(stamp2, result, blur_radius=8)

            if pos is None:
                pos = self.rect().bottomRight()


            stamp_place = QRect(result.rect())
            stamp_place.moveBottomLeft(stamp_place.topLeft())

            pos -= QPoint(5, 10) # offset
            t = QTransform()
            t.translate(pos.x(), pos.y())
            t.rotate(-90)
            painter.setTransform(t)
            painter.setOpacity(0.85)
            painter.setCompositionMode(QPainter.CompositionMode_HardLight)
            painter.drawPixmap(stamp_place, result, result.rect())
            painter.restore()

    def elementsDrawMain(self, painter, final=False, draw_background_only=False, prepare_darkening=False):
        if final or self.Globals.ANTIALIASING_AND_SMOOTH_PIXMAP_TRANSFORM:
            painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if not final:
            self.elementsTextElementResetColorsButtons()            
        painter.save()
        # draw elements
        if not prepare_darkening:
            if not self.dark_pictures:
                self.elementsDrawDarkening(painter)

        # штампы (изображения) рисуем первыми, чтобы пометки всегда были поверх них
        all_visible_elements = self.elementsFilter()
        pictures_first = []
        all_the_rest = []
        if draw_background_only:
            pictures_first = [el for el in all_visible_elements if el.background_image]
        else:
            for element in all_visible_elements:
                if element.oxxxy_type == ToolID.picture:
                    if not element.background_image or final:
                        pictures_first.append(element)
                else:
                    all_the_rest.append(element)

        all_the_rest = [e for e in all_the_rest if e.oxxxy_type != self.ToolID.arrowstree]

        for element in pictures_first:
            self.elementsDrawMainElement(painter, element, final, all_visible_elements)
        for element in all_the_rest:
            self.elementsDrawMainElement(painter, element, final, all_visible_elements)

        self.elementsDrawArrowTrees(painter, final)
        if not final:
            self.elementsDrawArrowTreesTech(painter)

        if not draw_background_only:
            self.elementsDrawSystemCursor(painter)

        if not final:
            # отрисовка виджетов
            self.elementsDrawSelectionMouseRect(painter)
            self.elementsDrawSelectionTransformBox(painter)
            self.elementsDrawSelectedElementsDottedOutlines(painter, all_visible_elements)

        if self.dark_pictures or prepare_darkening:
            self.elementsDrawDarkening(painter)

        if self.Globals.DEBUG and self.capture_region_rect and not final:
            painter.setPen(QPen(QColor(Qt.white)))
            text = f"{self.elements_modification_index} :: {self.current_tool}"
            painter.drawText(self.capture_region_rect, Qt.AlignCenter, text)

        painter.restore()

        painter.setRenderHint(QPainter.HighQualityAntialiasing, False)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)

    def elementsDrawSystemCursor(self, painter):
        if self.tools_window and self.tools_window.chb_draw_cursor.isChecked():
            screenshot_cursor_position = self.elementsMapToViewport(self.screenshot_cursor_position)
            painter.drawPixmap(screenshot_cursor_position, self.cursor_pixmap)

    def elementsGetDrawOffsetAndZoomTransform(self, offset):
        translation = QTransform()
        global_scaling = QTransform()
        translation.translate(offset.x(), offset.y())
        global_scaling.scale(self.canvas_scale_x, self.canvas_scale_y)
        transform = global_scaling * translation
        return transform

    def elementsDrawDebugInfo(self, painter, viewport_input_rect):
        if self.capture_region_rect:
            r = self.capture_region_rect
            pos_right = self.elementsMapToViewport(r.bottomRight())
            pos_left = self.elementsMapToViewport(r.bottomLeft())
        else:
            r = viewport_input_rect
            pos_right = r.bottomRight()
            pos_left = r.bottomLeft()
        visible_elements = self.elementsFilter()


        # левая сторона
        painter.save()
        info_rect = build_valid_rectF(pos_left, self.rect().topLeft())
        info_rect.setWidth(300)
        info_rect.moveBottomRight(pos_left)
        painter.fillRect(info_rect, QColor(0, 0, 0, 180))

        # для соблюдения зума вьюпорта задаём эти трансформации
        painter.setTransform(self.elementsGetDrawOffsetAndZoomTransform(pos_left))
        pos_left = QPointF(0, 0)


        font = painter.font()
        pixel_height = 25
        font.setPixelSize(20)
        max_width = 0

        pos_left += QPointF(-10, -10)
        for element in self.elements:
            element.debug_text = element.get_parameters_info()
            max_width = max(max_width, painter.boundingRect(QRect(), Qt.AlignLeft, element.debug_text).width())

        for n, element in enumerate(self.elements):
            font = painter.font()
            if element not in visible_elements:
                painter.setPen(QPen(QColor(255, 100, 100)))
                font.setStrikeOut(True)
            else:
                painter.setPen(QPen(Qt.white))
                font.setStrikeOut(False)
            painter.setFont(font)
            p = pos_left + QPointF(-max_width, -pixel_height*n)
            painter.drawText(p, element.debug_text)
        painter.restore()

        painter.resetTransform()
        info_rect = build_valid_rectF(pos_right, self.rect().topRight())
        info_rect.setWidth(800)
        painter.fillRect(info_rect, QColor(0, 0, 0, 180))

        painter.save()
        # для соблюдения зума вьюпорта задаём эти трансформации
        painter.setTransform(self.elementsGetDrawOffsetAndZoomTransform(pos_right))
        pos_right = QPointF(0, 0)
        info_rect = build_valid_rectF(pos_right, self.rect().topRight())
        info_rect.setWidth(800)
        info_rect.moveBottomLeft(QPointF(10, -10) + info_rect.bottomLeft())
        # правая сторона, под линией
        if self.active_element is not None:
            info = f'active element: ' + self.active_element.get_parameters_info()
        else:
            info = f'No active element: {self.active_element}'
        info += f"\nself.modification_stamp = {self.modification_stamp}"

        r = painter.boundingRect(QRect(), Qt.AlignLeft, info)
        right_underground = QRectF(r)
        right_underground.moveTopLeft(pos_right)
        painter.drawText(right_underground, info)

        # правая сторона, над линией
        vertical_offset = 0
        visible_slots = self.elementsModificationSlotsFilter()
        for index, ms in list(enumerate(self.modification_slots)):
            painter.save()
            painter.setPen(Qt.white)
            slot_info_text = f'[slot {index}] {ms.content_type}'
            if index == self.elements_modification_index-1:
                pointer = '➜'
            else:
                pointer = '   '
            slot_info_text = f'{pointer} {slot_info_text}'
            font = painter.font()
            pixel_height = 25
            if ms not in visible_slots:
                painter.setPen(QPen(QColor(255, 100, 100)))
                font.setStrikeOut(True)
            else:
                painter.setPen(QPen(Qt.white))
                font.setStrikeOut(False)
            font.setPixelSize(20)
            painter.setFont(font)
            vertical_offset += (len(ms.elements) + 1)
            pos_right = info_rect.bottomLeft() + QPointF(0, -vertical_offset*pixel_height)
            painter.drawText(pos_right, slot_info_text)
            for i, elem in enumerate(ms.elements):

                painter.setPen(Qt.white)
                if elem not in visible_elements:
                    painter.setPen(QPen(QColor(255, 100, 100)))
                    font.setStrikeOut(True)
                else:
                    painter.setPen(QPen(Qt.white))
                    font.setStrikeOut(False)
                painter.setFont(font)
                if self.selected_items and elem in self.selected_items:
                    painter.setPen(QPen(Qt.green))

                info_text = elem.get_parameters_info()

                y = -vertical_offset*pixel_height + pixel_height*(i+1)
                pos_right = info_rect.bottomLeft() + QPointF(100, y)
                color_rect_pos = info_rect.bottomLeft() + QPointF(20, y+3)
                size_pos = info_rect.bottomLeft() + QPointF(40, y)
                painter.save()
                painter.setPen(QPen(Qt.gray, 2))
                painter.drawText(size_pos, f'{elem.size:.03}')
                painter.restore()
                painter.drawText(pos_right, info_text)
                painter.save()
                painter.setPen(QPen(Qt.black, 2))
                painter.setBrush(elem.color)
                color_rect = QRectF(0, 0, 20, 20)
                color_rect.moveBottomLeft(color_rect_pos)
                painter.drawRect(color_rect)
                painter.restore()
            painter.restore()
        painter.restore()

    def elementsRenderFinal(self, capture_region_rect=None,
                draw_background_only=False, no_multiframing=False, prepare_darkening=False, clean=False,
                force_no_datetime_stamp=False):
        FINAL_PIXMAP = None
        if self.capture_region_rect:
            specials = [el for el in self.elementsFilter() if el.oxxxy_type == ToolID.multiframing]
            any_multiframing_element = any(specials)
            if any_multiframing_element and not no_multiframing and not clean:
                max_width = -1
                total_height = 0
                specials_rects = []
                source_pixmap = QPixmap.fromImage(self.source_pixels)
                for number, el in enumerate(specials):
                    br = el.get_canvas_space_selection_rect_with_no_rotation()
                    capture_pos = el.position
                    el.bounding_rect = br
                    capture_pos = el.position
                    capture_rotation = el.rotation
                    capture_width = br.width()
                    capture_height = br.height()
                    el.pixmap = capture_rotated_rect_from_pixmap(source_pixmap, capture_pos,
                        capture_rotation, capture_width, capture_height)
                for el in specials:
                    max_width = max(max_width, el.bounding_rect.width())
                for el in specials:
                    br = el.bounding_rect
                    el.height = max_width/br.width()*br.height()
                    total_height += el.height
                max_width = int(max_width)
                total_height = int(total_height)
                FINAL_PIXMAP = QPixmap(QSize(max_width, total_height))
                painter = QPainter()
                painter.begin(FINAL_PIXMAP)
                cur_pos = QPointF(0, 0)
                for el in specials:
                    dst_rect = QRectF(cur_pos, QSizeF(max_width, el.height))
                    painter.drawPixmap(dst_rect, el.pixmap, QRectF(el.pixmap.rect()))
                    cur_pos += QPointF(0, el.height)
                for el in specials:
                    del el.bounding_rect
                    del el.pixmap
                painter.end()
            else:
                if capture_region_rect is None:
                    capture_region_rect = self.capture_region_rect

                # draw elements
                FINAL_PIXMAP = QPixmap(capture_region_rect.size().toSize())
                FINAL_PIXMAP.fill(Qt.transparent)
                painter = QPainter()
                painter.begin(FINAL_PIXMAP)
                self._canvas_origin = QPointF(self.canvas_origin)
                self._canvas_scale_x = self.canvas_scale_x
                self._canvas_scale_y = self.canvas_scale_y
                self.canvas_origin = -capture_region_rect.topLeft()
                self.canvas_scale_x = 1.0
                self.canvas_scale_y = 1.0
                self.elementsDrawMain(painter, final=True,
                        draw_background_only=draw_background_only,
                        prepare_darkening=prepare_darkening,
                )
                self.canvas_origin = self._canvas_origin
                self.canvas_scale_x = self._canvas_scale_x
                self.canvas_scale_y = self._canvas_scale_y
                painter.end()

                # mask
                if not clean and self.tools_window and self.tools_window.chb_masked.isChecked():
                    FINAL_PIXMAP = self.circle_mask_image(FINAL_PIXMAP)

                if (not clean) and not force_no_datetime_stamp:
                    # datetime stamp
                    painter = QPainter()
                    painter.begin(FINAL_PIXMAP)
                    pos = QPoint(FINAL_PIXMAP.width(), FINAL_PIXMAP.height())
                    self.elementsDrawDateTime(painter, pos=pos)
                    painter.end()
        return FINAL_PIXMAP

    def elementsPrepareElementCopyForModifications(self, element):
        if self.modification_stamp is None:
            raise Exception('modifcation stamp is not acquired for this modification operation!')
        if element._modification_stamp != self.modification_stamp:
            new_element = self.elementsCreateNew(ToolID.TEMPORARY_TYPE_NOT_DEFINED,
                modification_slot=self.modification_slot,
                create_new_slot=False
            )
            self.elementsCopyElementData(new_element, element)
            new_element.source_indexes = [element.unique_index]
            new_element._modification_stamp = self.modification_stamp
            return new_element
        else:
            return element

    def elementsMakeElementCopy(self, element, mod_slot=None):
        el_copy = self.elementsCreateNew(ToolID.TEMPORARY_TYPE_NOT_DEFINED,
            modification_slot=mod_slot,
            create_new_slot=False
        )
        self.elementsCopyElementData(el_copy, element)
        return el_copy

    def elementsParametersChanged(self):
        tw = self.tools_window
        if tw:
            element = self.active_element
            case1 = element and element.oxxxy_type == tw.current_tool
            case2 = element and tw.current_tool == ToolID.transform
            if case1 or case2:
                el = self.elementsPrepareElementCopyForModifications(element)
                self.elementsSetSelected(el, update_panel=False)
                self.elementsSetElementParameters(el)
                el.construct_selection_path(self)
        self.update()
        self.activateWindow() # чтобы фокус не соскакивал на панель иструментов

    def elementsGetArrowPath(self, start_point, tip_point, size, sharp):
        dist_delta = start_point - tip_point
        radians_angle = math.atan2(dist_delta.y(), dist_delta.x())
        arrow_length = QVector2D(dist_delta).length()
        tip = QPointF(arrow_length, 0)
        offset_x = 40
        offset_y = 19
        t = (arrow_length+5)/50 #делаем масштаб кончика стрелки зависимым от длины
        t = min(1.5, t)
        t *= (0.5 + size)
        if sharp:
            p1 = QPointF(arrow_length-30, 5) - tip  #20, 4  #25, 6
            p1 = tip + p1*t
            p2 = QPointF(arrow_length-offset_x, offset_y) - tip
            p2 = tip + p2*t
            p12 = (p1 + p2)/2.0
            p3 = QPointF(arrow_length-offset_x, -offset_y) - tip
            p3 = tip + p3*t
            p4 = QPointF(arrow_length-30, -5) - tip #20, -4  #25, -6
            p4 = tip + p4*t
            p34 = (p3 + p4)/2.0
            path = QPainterPath()
            path.moveTo(QPointF(0, 1))
            m = 0.25
            inside = (p34 + (p12 - p34)/2.0)*m + (1-m)*(tip)
            path.lineTo(p1)
            path.lineTo(p12)
            path.cubicTo(
                inside,
                inside,
                tip
            )
            path.cubicTo(
                inside,
                inside,
                p34
            )
            path.lineTo(p4)
            path.lineTo(QPointF(0, -1))
            path.lineTo(QPointF(0, 1))
        else:
            rounded = True
            tip_factor=0.85
            t *= 0.15
            tip_point = QPointF(arrow_length, 0)
            start_point = QPointF(0,0)
            start_point_left = start_point + QPointF(0, -1)
            start_point_right = start_point + QPointF(0, 1)
            center = tip_point + QPointF(-80, 0)*t
            center_left = center + QPointF(0, -20)*t
            center_right = center + QPointF(0, 20)*t
            side_left = center_left + QPointF(-10, -40)*t
            side_right = center_right + QPointF(-10, 40)*t
            # building path
            path = QPainterPath()
            if rounded:
                path.moveTo(start_point_left)
                path.lineTo(center_left)
                path.lineTo(center_left*.5+side_left*.5)
                path.quadTo(
                    side_left,
                    side_left*tip_factor+tip_point*(1.0-tip_factor)
                )
                path.lineTo(
                    side_left*(1.0-tip_factor)+tip_point*tip_factor
                )
                path.quadTo(
                    tip_point,
                    side_right*(1.0-tip_factor)+tip_point*tip_factor
                )
                path.lineTo(
                    side_right*tip_factor+tip_point*(1.0-tip_factor)
                )
                path.quadTo(
                    side_right,
                    center_right*.5+side_right*.5
                )
                path.lineTo(center_right)
                path.lineTo(start_point_right)
                path.lineTo(start_point_left)
            else:
                path.moveTo(start_point_left)
                path.lineTo(center_left)
                path.lineTo(side_left)
                path.lineTo(tip_point)
                path.lineTo(side_right)
                path.lineTo(center_right)
                path.lineTo(start_point_right)
                path.lineTo(start_point_left)
        transform = QTransform()
        deg_angle = 180+180/3.14*radians_angle
        transform.rotate(deg_angle)
        path = path.translated(-path.boundingRect().center())
        path = transform.map(path)
        return path

    def elementsDrawArrow(self, painter, start_point, tip_point, size, sharp):
        path = self.elementsGetArrowPath(start_point, tip_point, size, sharp)
        painter.drawPath(path)

    def elementsEditHistoryForwards(self):
        self.elementsTextElementDeactivateEditMode()
        if self.elements_modification_index < len(self.modification_slots):
            self.elements_modification_index += 1
        self.elementsSetSelected(None)

    def elementsEditHistoryBackwards(self):
        self.elementsTextElementDeactivateEditMode()
        if self.elements_modification_index > 0:
            self.elements_modification_index -= 1
        self.elementsSetSelected(None)

    def elementsUpdateEditHistoryButtonsStatus(self):
        f = self.elements_modification_index < len(self.modification_slots)
        b = self.elements_modification_index > 0
        return f, b

    def elementsSetCaptureFromContent(self):
        points = []
        for element in self.elementsFilterElementsForSelection():
            if element.oxxxy_type in [ToolID.removing, ToolID.multiframing]:
                continue
            pen, _, _ = self.elementsGetPenFromElement(element)
            width = pen.width()
            br = element.get_canvas_space_selection_area().boundingRect()
            offset = width
            ms = QMarginsF(offset, offset, offset, offset)
            br = br.marginsAdded(ms)
            points.append(br.topLeft())
            points.append(br.bottomRight())

        if points:
            # обновление области захвата
            self.input_POINT2, self.input_POINT1 = get_bounding_pointsF(points)
            self.capture_region_rect = build_valid_rectF(self.input_POINT1, self.input_POINT2)

        self.update()

    def elementsDoRenderToBackground(self, for_slicing=False):
        subMenu = QMenu()
        subMenu.setStyleSheet(self.context_menu_stylesheet)
        action_extend = subMenu.addAction("Расширить картинку-фон, если контент будет превосходить её размеры")
        action_keep = subMenu.addAction("Оставить размеры картинки-фона как есть")
        action_crop = subMenu.addAction("Обрезать по рамке захвата")
        action_cancel = subMenu.addAction("Отмена")

        if for_slicing:
            action = action_extend
        else:
            pos = self.mapFromGlobal(QCursor().pos())
            action = subMenu.exec_(pos)

        if action == None or action == action_cancel:
            return
        elif action == action_keep:
            pass
        elif action == action_crop:
            pass
        elif action == action_extend:
            points = []

            elements = self.elementsFilter()

            if for_slicing:
                elements = [el for el in elements if el.background_image]

            for element in elements:
                sel_area = element.get_canvas_space_selection_area()
                br = sel_area.boundingRect()

                points.append(br.topLeft())
                points.append(br.bottomRight())

            if points:
                content_rect = build_valid_rectF(*get_bounding_pointsF(points))
            else:
                content_rect = QRectF()
            new_width = max(self.source_pixels.width(), content_rect.width())
            new_height = max(self.source_pixels.height(), content_rect.height())

        draw_background_only = for_slicing
        # рендер картинки
        if for_slicing:
            final_pix = self.elementsRenderFinal(capture_region_rect=content_rect, clean=True,
                                                                        draw_background_only=True)
            self.source_pixels = final_pix.toImage()
            return content_rect

        else:
            if action == action_crop:
                final_pix = self.elementsRenderFinal(clean=True)
            elif action == action_keep:
                hs = self.modification_slots[0]
                r = QRectF(QPointF(0, 0), QSizeF(hs.elements[0].pixmap.size()))
                final_pix = self.elementsRenderFinal(capture_region_rect=r, clean=True)
            elif action == action_extend:
                final_pix = self.elementsRenderFinal(
                        capture_region_rect=content_rect, clean=True)

        # заменяем картинку и пишем в историю с удалением содержимого
        self.source_pixels = final_pix.toImage()
        if action == action_extend:
            offset = content_rect.topLeft()
        else:
            offset = None
        self.elementsCreateBackgroundPictures(self.CreateBackgroundOption.ContentToBackground, offset=offset)

        # обновляем рамку, если по ней производилась обрезка
        if action == action_crop:
            w = self.capture_region_rect.width()
            h = self.capture_region_rect.height()
            self.input_POINT2, self.input_POINT1 = get_bounding_pointsF([QPointF(0, 0), QPointF(w, h)])
            self.capture_region_rect = build_valid_rectF(self.input_POINT1, self.input_POINT2)

        # cleaning
        self.elementsSetSelected(None)

        if self.tools_window:
            self.tools_window.forwards_backwards_update()

        self.update_tools_window()
        self.update()

    def elementsFitImagesToSize(self):
        subMenu = QMenu()
        subMenu.setStyleSheet(self.context_menu_stylesheet)
        to_width = subMenu.addAction("По ширине")
        to_height = subMenu.addAction("По высоте")

        action = subMenu.exec_(QCursor().pos())

        elements = self.elementsSortPicturesByXPosition(self.elementsPicturesFilter())

        if action == None:
            pass
        elif elements:

            m = Element.get_canvas_space_selection_area
            br_getter = lambda el: m(el).boundingRect()

            if action == to_height:
                if self.active_element:
                    fit_height = br_getter(self.active_element).height()
                else:
                    fit_height = max(br_getter(el).height() for el in elements)
            else:
                fit_height = None

            if action == to_width:
                if self.active_element:
                    fit_width = br_getter(self.active_element).width()
                else:
                    fit_width = max(br_getter(el).width() for el in elements)
            else:
                fit_width = None

            self.elementsArrangePictures(elements, fit_width, fit_height)

        self.update()

    def elementsArrangePictures(self, elements, target_width, target_height):
        points = []
        pos = QPointF(0, 0)
        for source_element in elements:

            self.elementsStartModificationProcess('arranging')
            element = self.elementsPrepareElementCopyForModifications(source_element)
            self.elementsStopModificationProcess()

            start_br = element.get_canvas_space_selection_area().boundingRect()

            if target_height is not None:
                scale = target_height / start_br.height()

            if target_width is not None:
                scale = target_width / start_br.width()

            element.scale_x = scale
            element.scale_y = scale

            br = element.get_canvas_space_selection_area().boundingRect()

            element.position = QPointF(pos) + QPointF(br.width()/2, br.height()/2)
            if target_height is not None:
                pos += QPointF(br.width(), 0)

            if target_width is not None:
                pos += QPointF(0, br.height())

            br = element.get_canvas_space_selection_area().boundingRect()

            points.append(br.topLeft())
            points.append(br.bottomRight())

        # обновление области захвата
        self.input_POINT2, self.input_POINT1 = get_bounding_pointsF(points)
        self.capture_region_rect = build_valid_rectF(self.input_POINT1, self.input_POINT2)
        # print('capture region', self.capture_region_rect)

        self.elementsSetSelected(None)
        tw = self.tools_window
        if tw:
            tw.forwards_backwards_update()
        self.update_tools_window()

    def elementsPicturesFilter(self):
        elements = []
        for element in self.elementsFilterElementsForSelection():
            if element.oxxxy_type == ToolID.picture:
                elements.append(element)
        return elements

    def elementsSortPicturesByXPosition(self, elements):
        m = Element.get_canvas_space_selection_rect_with_no_rotation
        cmp_func = lambda e: m(e).center().x()
        return list(sorted(elements, key=cmp_func))

    def elementsAutoCollagePicturesHor(self):
        self.elementsAutoCollagePictures(param='hor')

    def elementsAutoCollagePictures(self, param=None):
        subMenu = QMenu()
        subMenu.setStyleSheet(self.context_menu_stylesheet)
        horizontal = subMenu.addAction("По горизонтали")
        vertical = subMenu.addAction("По вертикали")
        if param is None:
            action = subMenu.exec_(QCursor().pos())
        elif param == 'hor':
            action = horizontal
        elif param == 'ver':
            action = vertical

        elements = self.elementsSortPicturesByXPosition(self.elementsPicturesFilter())

        if action == None:
            pass
        elif elements:

            m = Element.get_canvas_space_selection_area
            br_getter = lambda el: m(el).boundingRect()

            if action == horizontal:
                max_height = max(br_getter(el).height() for el in elements)
            else:
                max_height = None

            if action == vertical:
                max_width = max(br_getter(el).width() for el in elements)
            else:
                max_width = None

            self.elementsArrangePictures(elements, max_width, max_height)

        self.update()

    def elementsPasteSelectedItems(self):
        canvas_selection_center = self.elementsMapToCanvas(self.selection_bounding_box.boundingRect().center())
        canvas_cursor_pos = self.elementsMapToCanvas(self.mapped_cursor_pos())
        if self.selected_items:
            copies = []
            ms = self.elementsCreateNewSlot('Ctrl+C, Ctrl+V')
            for element in self.selected_items:
                element._selected = False
                element_copy = self.elementsMakeElementCopy(element, mod_slot=ms)
                copies.append(element_copy)
                delta = element_copy.position - canvas_selection_center
                element_copy.position = canvas_cursor_pos + delta
                element_copy._selected = True
            self.elementsSetSelected(None)
            self.elementsSetSelected(copies)

    def elementsGetImageFromBuffer(self):
        app = QApplication.instance()
        cb = app.clipboard()
        mdata = cb.mimeData()
        pixmap = None

        is_gif_file = lambda fp: fp.lower().endswith(".gif")
        is_webp_file = lambda fp: fp.lower().endswith(".webp")

        if mdata and mdata.hasText():
            path = mdata.text()
            qt_supported_exts = (
                ".jpg", ".jpeg", ".jfif",
                ".bmp",
                ".gif",
                ".png",
                ".tif", ".tiff",
                ".webp",
            )
            svg_exts = (
                ".svg",
                ".svgz"
            )
            PREFIX = "file:///"
            if path.startswith(PREFIX):
                filepath = path[len(PREFIX):]
                _gif_file = is_gif_file(filepath)
                _webp_animated_file = is_webp_file(filepath) and is_webp_file_animated(filepath)
                if _gif_file or _webp_animated_file:
                    return filepath
                # supported exts
                elif path.lower().endswith(qt_supported_exts):
                    pixmap = QPixmap(filepath)
                # svg-files
                elif path.lower().endswith(svg_exts):
                    contextMenu = QMenu()
                    contextMenu.setStyleSheet(self.context_menu_stylesheet)
                    factors = [1, 5, 10, 20, 30, 40, 50, 80, 100]
                    actions = []
                    for factor in factors:
                        action = contextMenu.addAction(f"x{factor}")
                        actions.append((action, factor))
                    cur_action = contextMenu.exec_(QCursor().pos())
                    if cur_action is not None:
                        for (action, factor) in actions:
                            if cur_action == action:
                                pixmap = load_svg(filepath, scale_factor=factor)
        elif mdata and mdata.hasImage():
            pixmap = QPixmap().fromImage(mdata.imageData())
        return pixmap

    def elementsUpdateDependentElementsAfterReshot(self):
        # updating dependent elements
        for element in self.elements:
            if element.oxxxy_type in [ToolID.blurring]:
                self.elementsSetBlurredPixmap(element)
            if element.oxxxy_type in [ToolID.copypaste, ToolID.zoom_in_region]:
                if not element.second:
                    self.elementsSetCopiedPixmap(element)

    def elementsPasteImageToImageToolOrImageElement(self, pixmap):
        if pixmap and not pixmap.isNull():
            if self.tools_window.current_tool == ToolID.picture:
                capture_height = max(self.capture_region_rect.height(), 100)
                if pixmap.height() > capture_height:
                    pixmap = pixmap.scaledToHeight(int(capture_height), Qt.SmoothTransformation)
                self.current_picture_id = self.PictureInfo.TYPE_FROM_FILE
                self.current_picture_pixmap = pixmap
                self.current_picture_angle = 0
                tools_window = self.tools_window
                tools_window.on_parameters_changed()
                self.activateWindow()
            else:
                self.elementsSetSelected(None)
                element = self.elementsCreateNew(ToolID.picture)
                element.pixmap = pixmap
                pos = self.capture_region_rect.topLeft()
                element.position = pos + QPointF(pixmap.width()/2, pixmap.height()/2)
                element.calc_local_data()
                self.elementsSetSelected(element)
                self.elementsActiveElementParamsToPanelSliders()
        else:
            print("image is broken")

    def elementsPasteImageFromBuffer(self, event):
        mods = event.modifiers()
        ctrl = mods & Qt.ControlModifier
        if not (ctrl and self.tools_window):
            return
        data = self.elementsGetImageFromBuffer()
        if isinstance(data, QPixmap):
            pixmap = data
            self.elementsPasteImageToImageToolOrImageElement(pixmap)
        elif data is not None:
            filepath = data
            self.show_view_window_for_animated(filepath)
        else:
            print("Nothing to paste")

    def elementsResetPanZoom(self, reset_pan=True, reset_zoom=True):
        if reset_pan:
            self.canvas_origin = QPointF(0, 0)
        if reset_zoom:
            self.canvas_scale_x = 1.0
            self.canvas_scale_y = 1.0
        self.update_selection_bouding_box()
        self.update()
        if self.tools_window:
            self.autopos_tools_window()
            self.tools_window.update()

    def elementsFitContentOnScreen(self, element=None, use_selection=False, use_capture_region=False):
        canvas_scale_x = self.canvas_scale_x
        canvas_scale_y = self.canvas_scale_y

        if use_selection:
            content_pos = self.selection_bounding_box.boundingRect().center() - self.canvas_origin
        elif use_capture_region:
            mapped_capture = self.elementsMapToViewportRectF(self.capture_region_rect)
            mapped_capture_center = mapped_capture.center()
            content_pos = mapped_capture_center - self.canvas_origin
        else:
            content_pos = QPointF(element.position.x()*canvas_scale_x, element.position.y()*canvas_scale_y)
        viewport_center_pos, working_area_rect = self.get_center_position_and_screen_rect()

        self.canvas_origin = - content_pos + viewport_center_pos

        if use_selection:
            content_rect = self.selection_bounding_box.boundingRect().toRect()
        elif use_capture_region:
            content_rect = mapped_capture
        else:
            content_rect = element.get_selection_area(canvas=self, place_center_at_origin=False).boundingRect().toRect()

        fitted_rect = fit_rect_into_rect(content_rect, working_area_rect, float_mode=True)
        self.elementsDoScaleCanvas(0, False, False, False,
            pivot=viewport_center_pos,
            factor_x=fitted_rect.width()/content_rect.width(),
            factor_y=fitted_rect.height()/content_rect.height(),
        )

        self.update_selection_bouding_box()
        self.update()
        if self.tools_window:
            self.autopos_tools_window()
            self.tools_window.update()

    def elementsFitSelectedItemsOnScreen(self):
        if self.selected_items:
            self.elementsFitContentOnScreen(use_selection=True)

    def elementsFitCaptureZoneOnScreen(self):
        if self.capture_region_rect:
            self.elementsFitContentOnScreen(use_capture_region=True)




# для запуска программы прямо из этого файла при разработке и отладке
if __name__ == '__main__':
    import subprocess
    subprocess.Popen([sys.executable, "-u", "oxxxy.py"])
    sys.exit()
