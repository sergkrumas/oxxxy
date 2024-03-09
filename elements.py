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

from PyQt5.QtWidgets import (QSystemTrayIcon, QWidget, QMessageBox, QMenu, QGraphicsPixmapItem,
    QGraphicsScene, QFileDialog, QHBoxLayout, QCheckBox, QVBoxLayout, QTextEdit, QGridLayout,
    QPushButton, QGraphicsBlurEffect, QLabel, QApplication, QScrollArea, QDesktopWidget)
from PyQt5.QtCore import (QUrl, QMimeData, pyqtSignal, QPoint, QPointF, pyqtSlot, QRect, QEvent,
    QTimer, Qt, QSize, QSizeF, QRectF, QThread, QAbstractNativeEventFilter,
    QAbstractEventDispatcher, QFile, QDataStream, QIODevice, QMarginsF)
from PyQt5.QtGui import (QPainterPath, QColor, QKeyEvent, QMouseEvent, QBrush, QPixmap,
    QPaintEvent, QPainter, QWindow, QPolygon, QImage, QTransform, QPen, QLinearGradient,
    QIcon, QFont, QCursor, QPolygonF, QVector2D)

from _utils import (convex_hull, check_scancode_for, SettingsJson,
     generate_metainfo, build_valid_rect, build_valid_rectF, dot, get_nearest_point_on_rect,
     get_creation_date, capture_rotated_rect_from_pixmap, fit_rect_into_rect,
     find_browser_exe_file, open_link_in_browser, open_in_google_chrome, save_meta_info,
     make_screenshot_pyqt, webRGBA, generate_gradient, draw_shadow, draw_cyberpunk,
     constraint45Degree, get_bounding_points, load_svg, is_webp_file_animated, apply_blur_effect)

from elements_transform import ElementsTransformMixin


ZOOM_IN_REGION_DAFULT_SCALE = 1.5

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

class Element():

    def __init__(self, element_type, elements_list):
        self.type = element_type
        elements_list.append(self)

        n = 0
        for el in elements_list:
            if el.type == ToolID.numbering:
                n += 1
        self.number = n

        if hasattr(Element, "_counter"):
            Element._counter += 1
        else:
            Element._counter = 0
        self.unique_index = Element._counter

        self.fresh = True
        self.finished = False

        self.backup_pixmap = None
        self.frame_info = None
        self.background_image = False

        self.opacity = 1.0

        self.textbox = None

        # element attributes for canvas
        self.element_scale_x = 1.0
        self.element_scale_y = 1.0
        self.element_position = QPointF()
        self.element_rotation = 0
        self.element_width = None
        self.element_height = None

        self.__element_scale_x = None
        self.__element_scale_y = None
        self.__element_position = None
        self.__element_rotation = None

        self.__element_scale_x_init = None
        self.__element_scale_y_init = None
        self.__element_position_init = None

        self._selected = False
        self._touched = False

    def __repr__(self):
        return f'{self.unique_index} {self.type}'

    def calc_local_data_default(self):
        self.element_position = (self.start_point + self.end_point)/2.0
        self.local_start_point = self.start_point - self.element_position
        self.local_end_point = self.end_point - self.element_position
        diff = self.start_point - self.end_point
        self.element_width = abs(diff.x())
        self.element_height = abs(diff.y())

    def calc_local_data_finish(self, first_element):
        self.element_width = first_element.element_width
        self.element_height = first_element.element_height
        # с предувеличением
        if self.type in [ToolID.zoom_in_region]:
            self.element_scale_y = ZOOM_IN_REGION_DAFULT_SCALE
            self.element_scale_x = ZOOM_IN_REGION_DAFULT_SCALE

    def calc_local_data_path(self):
        bb = self.path.boundingRect()
        self.element_position = bb.center()
        self.element_width = bb.width()
        self.element_height = bb.height()

    def calc_local_data_picture(self):
        self.element_width = self.pixmap.width()
        self.element_height = self.pixmap.height()

    def calc_local_data(self):
        if self.type in [ToolID.line]:
            self.calc_local_data_default()
        elif self.type in [ToolID.pen, ToolID.marker]:
            if self.straight:
                self.calc_local_data_default()
            else:
                self.calc_local_data_path()
        elif self.type in [ToolID.arrow]:
            self.calc_local_data_default()
        elif self.type in [ToolID.oval, ToolID.rect, ToolID.numbering]:
            self.calc_local_data_default()
        elif self.type in [ToolID.blurring, ToolID.darkening, ToolID.multiframing]:
            self.calc_local_data_default()
        elif self.type in [ToolID.picture]:
            self.calc_local_data_picture()
        elif self.type in [ToolID.zoom_in_region, ToolID.copypaste]:
            self.calc_local_data_default()
        elif self.type in [ToolID.text]:
            self.calc_local_data_default()
        else:
            raise Exception('calc_local_data', self.type)

    @property
    def calc_area(self):
        r = self.get_size_rect(scaled=True)
        return abs(r.width() * r.height())

    def calculate_absolute_position(self, canvas=None, rel_pos=None):
        _scale_x = canvas.canvas_scale_x
        _scale_y = canvas.canvas_scale_y
        if rel_pos is None:
            rel_pos = self.element_position
        return QPointF(canvas.canvas_origin) + QPointF(rel_pos.x()*_scale_x, rel_pos.y()*_scale_y)

    def aspect_ratio(self):
        rect = self.get_size_rect(scaled=False)
        return rect.width()/rect.height()

    def get_size_rect(self, scaled=False):
        if scaled:
            scale_x = self.element_scale_x
            scale_y = self.element_scale_y
        else:
            scale_x = 1.0
            scale_y = 1.0
        return QRectF(0, 0, self.element_width*scale_x, self.element_height*scale_y)

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
        er.moveCenter(self.element_position)
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

    def get_transform_obj(self, canvas=None, apply_local_scale=True, apply_translation=True, apply_global_scale=True):
        local_scaling = QTransform()
        rotation = QTransform()
        global_scaling = QTransform()
        translation = QTransform()
        if apply_local_scale:
            local_scaling.scale(self.element_scale_x, self.element_scale_y)
        rotation.rotate(self.element_rotation)
        if apply_translation:
            if apply_global_scale:
                pos = self.calculate_absolute_position(canvas=canvas)
                translation.translate(pos.x(), pos.y())
            else:
                translation.translate(self.element_position.x(), self.element_position.y())
        if apply_global_scale:
            global_scaling.scale(canvas.canvas_scale_x, canvas.canvas_scale_y)
        transform = local_scaling * rotation * global_scaling * translation
        return transform

class ElementsHistorySlot():

    __slots__ = ['elements', 'content_type', 'unique_index']

    def __init__(self, content_type):
        super().__init__()
        self.elements = list()
        self.content_type = content_type
        if hasattr(ElementsHistorySlot, "_counter"):
            ElementsHistorySlot._counter += 1
        else:
            ElementsHistorySlot._counter = 0
        self.unique_index = ElementsHistorySlot._counter

class ElementsMixin(ElementsTransformMixin):

    ToolID = ToolID #для поддержки миксина

    def elementsInit(self):
        self.current_tool = ToolID.none
        self.drag_capture_zone = False
        self.ocp = self.mapFromGlobal(QCursor().pos())
        self.current_capture_zone_center = QPoint(0, 0)

        # хоть эти три атрибута и начинаются со слова "canvas",
        # но здесь они на самом деле значат "viewport",
        # потому что управляют лишь отображением холста на экране
        self.canvas_origin = QPointF(0, 0)
        self.canvas_scale_x = 1.0
        self.canvas_scale_y = 1.0

        self.NUMBERING_ELEMENT_WIDTH = 25
        self.elements = []
        self.__te = Element(ToolID.zoom_in_region, [])
        self.history_slots = []
        self.elements_history_index = 0
        self.SelectionFilter = SelectionFilter
        self.selection_filter = self.SelectionFilter.content_only
        self.active_element = None #active element is the last selected element
        # для выделения элементов и виджета трансформации элементов
        self.elementsInitTransform()
        self.elementsSetSelected(None)

        self.elements_final_output = None

        self.capture_region_widget_enabled = True
        self.show_background = True
        self.dark_pictures = True

    def elementsFindBackgroundSlot(self):
        for slot in self.elementsHistoryFilterSlots():
            if slot.content_type == ToolID.background_picture:
                return slot
        return None

    def elementsCreateBackgroundPictures(self, update=False):
        background_pixmap = QPixmap.fromImage(self.source_pixels)
        background_history_slot = self.elementsFindBackgroundSlot()
        if update and background_history_slot is not None:
            unique_index = None
            els = background_history_slot.elements
            if els and els[-1]:
                unique_index =  els[-1].unique_index

            element = self.elementsCreateNew(ToolID.picture,
                content_type=ToolID.background_picture,
                create_new_slot=False,
                history_slot=background_history_slot,
            )
            if unique_index is not None:
                # задавая source_index мы удаляем из фильтра прошлое изображение,
                # но оно остаётся в слоте
                element.source_index = unique_index
        else:
            element = self.elementsCreateNew(ToolID.picture, content_type=ToolID.background_picture)
        element.pixmap = background_pixmap
        element.background_image = True
        element.calc_local_data()
        element.element_position = QPointF(background_pixmap.width()/2, background_pixmap.height()/2)

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
        project_filepath = os.path.join(folder_path, "project.oxxxyshot")


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
        data.update({'elements_history_index':     self.elements_history_index                  })


        # сохранение сдвига холста
        data.update({'canvas_origin':   tuple((self.canvas_origin.x(), self.canvas_origin.y())) })
        # сохранение зума холста
        data.update({'canvas_scale':      tuple((self.canvas_scale_x, self.canvas_scale_y))     })

        elements_to_store = list()
        # сохранение элементов
        for n, element in enumerate(self.elements):

            element_base = list()
            elements_to_store.append(element_base)

            attributes = element.__dict__.items()
            for attr_name, attr_value in attributes:

                attr_type = type(attr_value).__name__

                if isinstance(attr_value, QPoint):
                    attr_data = (attr_value.x(), attr_value.y())

                elif isinstance(attr_value, (bool, int, float, str, tuple, list)):
                    attr_data = attr_value

                elif isinstance(attr_value, QPainterPath):
                    filename = f"path_{attr_name}_{n:04}.data"
                    filepath = os.path.join(folder_path, filename)
                    file_handler = QFile(filepath)
                    file_handler.open(QIODevice.WriteOnly)
                    stream = QDataStream(file_handler)
                    stream << attr_value
                    attr_data = filename

                elif isinstance(attr_value, QPixmap):
                    filename = f"pixmap_{attr_name}_{n:04}.png"
                    filepath = os.path.join(folder_path, filename)
                    attr_value.save(filepath)
                    attr_data = filename

                elif isinstance(attr_value, QColor):
                    attr_data = attr_value.getRgbF()

                elif attr_value is None or attr_name in ["textbox"]:
                    attr_data = None

                else:
                    status = f"name: '{attr_name}' type: '{attr_type}' value: '{attr_value}'"
                    raise Exception(f"Unable to handle attribute, {status}")

                element_base.append((attr_name, attr_type, attr_data))

        data.update({'elements': elements_to_store})

        # ЗАПИСЬ В ФАЙЛ НА ДИСКЕ
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

        is_file_exists = os.path.exists(project_filepath)
        is_file_extension_ok = project_filepath.lower().endswith(".oxxxyshot")
        is_file = os.path.isfile(project_filepath)
        if not (is_file_exists and is_file_extension_ok and is_file):
            self.show_notify_dialog("Ошибка: либо файла не существует, либо расширение не то. Отмена!")
            return

        # чтение json
        read_data = ""
        with open(project_filepath, "r", encoding="utf8") as file:
            read_data = file.read()

        try:
            data = json.loads(read_data)
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


        # загрузка картинки-фона
        image_path = os.path.join(folder_path, "background.png")
        self.source_pixels = QImage(image_path)



        # загрузка метаданных
        self.metadata = data.get('metadata', ("", ""))


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
        self.elements_history_index = data.get('elements_history_index', 0)


        # сохранение сдвига холста
        self.canvas_origin = QPointF(*data.get('canvas_origin', (0.0, 0.0)))
        # сохранение зума холста
        self.canvas_scale_x = data.get('canvas_scale_x')
        self.canvas_scale_y = data.get('canvas_scale_y')

        # загрузка элементов и их данных
        elements_from_store = data.get('elements', [])
        for element_attributes in elements_from_store:
            element = self.elementsCreateNew(ToolID.TEMPORARY_TYPE_NOT_DEFINED)

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

                elif attr_type in ['NoneType'] or attr_name in ["textbox"]:
                    attr_value = None

                else:
                    status = f"name: '{attr_name}' type: '{attr_type}' value: '{attr_data}'"
                    raise Exception(f"Unable to handle attribute, {status}")

                setattr(element, attr_name, attr_value)

        #  приготовление UI
        self.tools_window.forwards_backwards_update()
        self.update_tools_window()
        self.update()

        self.show_notify_dialog("Файл загружен")

    def elementsMapFromViewportToCanvas(self, viewport_pos):
        delta = QPointF(viewport_pos - self.canvas_origin)
        canvas_pos = QPointF(delta.x()/self.canvas_scale_x, delta.y()/self.canvas_scale_y)
        return canvas_pos

    def elementsMapFromCanvasToViewport(self, canvas_pos):
        scaled_rel_pos = QPointF(canvas_pos.x()*self.canvas_scale_x, canvas_pos.y()*self.canvas_scale_y)
        viewport_pos = self.canvas_origin + scaled_rel_pos
        return viewport_pos

    def elementsMapFromCanvasToViewportRectF(self, rect):
        rect = QRectF(
            self.elementsMapFromCanvasToViewport(rect.topLeft()),
            self.elementsMapFromCanvasToViewport(rect.bottomRight())
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
        elif element.type == ToolID.picture:
            element.size = 1.0
            element.color = QColor(Qt.red)
            element.color_slider_value = 0.01
            element.color_slider_palette_index = 0
            element.toolbool = False
            element.margin_value = 5
        if element.type == ToolID.text:
            self.elementsChangeTextbox(element)
        if element.type == ToolID.blurring:
            self.elementsSetBlurredPixmap(element)
        if element.type in [ToolID.copypaste, ToolID.zoom_in_region]:
            if hasattr(element, 'second') and not element.second:
                self.elementsSetCopiedPixmap(element)

    def elementsFramePicture(self, frame_rect=None, frame_info=None, pixmap=None):
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
        ae.element_scale_y = 1.0
        ae.element_scale_y = 1.0
        self.elementsSetSelected(ae)

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
                element.element_position = pos + QPointF(picture.width()/2, picture.height()/2)
                element.calc_local_data()
                pos += QPoint(element.pixmap.width(), 0)
                self.elementsUpdatePanelUI()

        self.update()

    def elementsFramedFinalToImageTool(self, pixmap, frame_rect):
        self.current_picture_id = PictureInfo.TYPE_STAMP
        self.current_picture_pixmap = pixmap.copy(frame_rect)
        self.current_picture_angle = 0

        tools_window = self.tools_window
        if tools_window:
            if tools_window.current_tool != ToolID.picture:
                tools_window.set_current_tool(ToolID.picture)
        tools_window.on_parameters_changed()
        self.update()
        tools_window.update()

    def get_final_picture(self):
        self.elementsUpdateFinalPicture()
        return self.elements_final_output

    def elementsActivateTransformTool(self):
        if not self.elements:
            return
        try:
            candidat = self.active_element or self.elementsHistoryFilter()[-1]
            if candidat not in self.elementsHistoryFilter(): # element should be visible at the moment
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

    def elementsRemoveElement(self):
        if not self.elementsHistoryFilterSlots():
            return
        create_new_slot = True
        if self.selected_items:
            for candidat in self.selected_items:
                if candidat.type == ToolID.removing:
                    continue
                candidat.selected = False
                element = self.elementsCreateNew(ToolID.removing, create_new_slot=create_new_slot)
                create_new_slot = False # first candidat creates new history slot for all candidates
                element.source_index = candidat.unique_index
            self.elementsSetSelected(None)
        self.update()

    def elementsGetLastElement(self):
        try:
            element = self.elementsHistoryFilter()[-1]
        except Exception:
            element = None
        return element

    def elementsGetLastElement1(self):
        try:
            element = self.elementsHistoryFilter()[-2]
        except Exception:
            element = None
        return element

    def elementsCopyElementData(self, element, source_element):
        attributes = source_element.__dict__.items()
        copy_textbox = None
        copy_textbox_value = None
        for attr_name, attr_value in attributes:
            if attr_name in ["unique_index", "hs", "hs_index"]:
                continue
            type_class = type(attr_value)
            # if type_class is type(None):
            #     print(attr_name)
            #     print(attributes)
            if attr_value is None:
                final_value = attr_value
            else:
                final_value = type_class(attr_value)
            if attr_name == "textbox" and attr_value is not None:
                copy_textbox = type_class(attr_value)
                copy_textbox_value = attr_value.toPlainText()
            else:
                setattr(element, attr_name, final_value)
        if copy_textbox:
            self.elementsTextBoxInit(copy_textbox, self, element)
            copy_textbox.setText(copy_textbox_value)
            setattr(element, "textbox", copy_textbox)

    def elementsUpdatePanelUI(self):
        if not self.selected_items:
            return
        self.elementsDeactivateTextElements()
        if len(self.selected_items) > 1:
            self.tools_window.set_ui_on_toolchange(hide=True)
            self.tools_window.update()
        else:
            element = self.selected_items[0]
            self.tools_window.color_slider.value = element.color_slider_value
            self.tools_window.color_slider.palette_index = element.color_slider_palette_index
            self.tools_window.size_slider.value = element.size
            self.tools_window.opacity_slider.value = element.opacity
            self.tools_window.chb_toolbool.setChecked(element.toolbool)
            if element.type == ToolID.text:
                self.elementsActivateTextElement(element)
            self.tools_window.set_ui_on_toolchange(element_type=element.type)
            self.tools_window.update()
        self.update()

    def elementsMakeSureTheresNoUnfinishedElement(self):
        hs = self.elementsGetLastHS()
        if hs and hs.content_type in [ToolID.zoom_in_region, ToolID.copypaste] and len(hs.elements) == 1:
            self.elements_history_index -= 1
            self.history_slots = self.elementsHistoryFilterSlots()
            self.elements = self.elementsHistoryFilter()

    def elementsOnTransformToolActivated(self):
        elements = self.elementsFilterElementsForSelection()
        if elements:
            self.elementsSetSelected(elements[-1])
        self.elementsUpdatePanelUI()
        self.update()
        self.activateWindow() # чтобы фокус не соскакивал на панель иструментов

    def elementsActivateTextElement(self, element):
        if element.textbox is None:
            # после загрузки open_project
            parent = self
            self.elementsCreateTextbox(parent, element)
        else:
            element.textbox.setParent(self)
            element.textbox.show()
            element.textbox.setFocus()

    def elementsDeactivateTextElements(self):
        for element in self.elementsHistoryFilter():
            if element.type == ToolID.text and element.textbox and element.textbox.parent():
                self.elementsOnTextChanged(element)
                element.textbox.hide()
                element.textbox.setParent(None)

    def elementsCreateNewSlot(self, content_type):
        hs = ElementsHistorySlot(content_type)
        self.history_slots.append(hs)
        self.elements_history_index += 1
        return hs

    def elementsAppendElementToHS(self, element, hs):
        hs.elements.append(element)
        # для редактора
        element.hs = hs
        # для сохранения в файл
        element.hs_index = hs.unique_index

    def elementsGetLastHS(self):
        slots = self.elementsHistoryFilterSlots()
        if slots:
            return slots[-1]
        else:
            return None

    def elementsCreateNew(self, element_type, start_drawing=False,
                                        create_new_slot=True, content_type=None, history_slot=None):
        self.elementsDeactivateTextElements()
        # срезание отменённой (невидимой) части истории
        # перед созданием элемента
        if create_new_slot:
            if content_type is None:
                content_type = element_type
            self.history_slots = self.elementsHistoryFilterSlots()
            hs = self.elementsCreateNewSlot(content_type)
        else:
            if history_slot is None:
                hs = self.elementsGetLastHS()
            else:
                hs = history_slot
        case1 = element_type == ToolID.removing
        case2 = element_type == ToolID.TEMPORARY_TYPE_NOT_DEFINED
        case3 = start_drawing
        is_removing = case1 or case2 or case3
        self.elements = self.elementsHistoryFilter(only_filter=is_removing)
        # создание элемента
        element = Element(element_type, self.elements)
        self.elementsAppendElementToHS(element, hs)
        self.elementsSetElementParameters(element)
        # обновление индекса после создания элемента
        self.elements_history_index = len(self.history_slots)
        return element

    def elementsSetSelected(self, element):
        if element is None:
            self.active_element = None
            for element in self.elementsHistoryFilter():
                element._selected = False
        else:
            element._selected = True
            self.active_element = element
        self.init_selection_bounding_box_widget()
        self.elementsUpdatePanelUI()
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
        self.elementsUpdatePanelUI()
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
        return self.elementsHistoryFilter()

    def elementsHistoryFilterSlots(self):
        # all visible slots
        return self.history_slots[:self.elements_history_index]

    def elementsHistoryFilter(self, only_filter=False):
        # фильтрация по индексу
        visible_elements = []
        for hs in self.elementsHistoryFilterSlots():
            visible_elements.extend(hs.elements)

        if only_filter:
            return visible_elements
        # не показываем удалённые элементы
        # или элементы, что были скопированы для внесения изменений в уже существующие
        remove_indexes = []
        for el in visible_elements:
            if hasattr(el, "source_index"):
                remove_indexes.append(el.source_index)
        non_deleted_elements = []
        for index, el in enumerate(visible_elements):
            # if index not in remove_indexes:
            if el.unique_index not in remove_indexes:
                non_deleted_elements.append(el)
        return non_deleted_elements

    def elementsGetElementsUnderMouse(self, cursor_pos):
        elements_under_mouse = []
        for el in self.elementsHistoryFilter():
            if el.type in [ToolID.removing,]:
                continue
            element_selection_area = el.get_selection_area(canvas=self)
            is_under_mouse = element_selection_area.containsPoint(cursor_pos, Qt.WindingFill)
            if is_under_mouse:
                elements_under_mouse.append(el)
        return elements_under_mouse

    def elementsMousePressEventDefault(self, element, event):
        event_pos = self.elementsMapFromViewportToCanvas(QPointF(event.pos()))
        if element.type == ToolID.line and event.modifiers() & Qt.ControlModifier:
            last_element = self.elementsGetLastElement1()
            if last_element and last_element.type == ToolID.line:
                element.start_point = QPointF(last_element.end_point)
            else:
                element.start_point = event_pos
        else:
            element.start_point = event_pos
        element.end_point = event_pos
        element.calc_local_data()

    def elementsIsSpecialCase(self, element):
        special_case = element is not None
        hs = self.elementsGetLastHS()
        special_case = special_case and hs and hs.content_type in [ToolID.zoom_in_region, ToolID.copypaste]
        # даём возможность создать другой слот
        special_case = special_case and hs and not len(hs.elements) == 2
        return special_case

    def elementsFreshAttributeHandler(self, el):
        if el:
            if hasattr(el, 'finished'):
                if el.finished:
                    el.fresh = False
            else:
                el.fresh = False

    def elementsAdvancedInputPressEvent(self, event, event_pos, element):
        els_count = len(element.hs.elements)
        if els_count == 1:
            self.elementsMousePressEventDefault(element, event)
            element.calc_local_data()
            element.second = False
        elif els_count == 2:
            element.element_position = event_pos
            first_element = element.hs.elements[0]
            element.calc_local_data_finish(first_element)
            element.second = True
        else:
            raise Exception("unsupported branch!")

    def elementsAdvancedInputMoveEvent(self, event, event_pos, element, finish=False):
        els_count = len(element.hs.elements)
        if els_count == 1:
            element.end_point = event_pos
            element.calc_local_data()
            if finish:
                element.finished = True
                self.elementsSetCopiedPixmap(element)
        elif els_count == 2:
            element.element_position = event_pos
        else:
            raise Exception("unsupported branch!")

    def elementsMousePressEvent(self, event):
        tool = self.current_tool

        self.active_element = None

        event_pos = self.elementsMapFromViewportToCanvas(QPointF(event.pos()))

        self.prev_elements_history_index = self.elements_history_index
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
        # основная часть
        el = self.elementsGetLastElement()
        self.elementsFreshAttributeHandler(el)
        if self.current_tool == ToolID.transform:
            element = None
        elif self.elementsIsSpecialCase(el):
            # zoom_in_region and copypaste case, when it needs more additional clicks
            element = self.elementsCreateNew(self.current_tool, start_drawing=True, create_new_slot=False)
        else:
            # default case
            element = self.elementsCreateNew(self.current_tool, start_drawing=True)
        # #######
        if tool == ToolID.arrow:
            self.elementsMousePressEventDefault(element, event)
        elif tool in [ToolID.zoom_in_region, ToolID.copypaste]:
            self.elementsAdvancedInputPressEvent(event, event_pos, element)
        elif tool == ToolID.picture:
            element.pixmap = self.current_picture_pixmap
            element.element_rotation = self.current_picture_angle
            element.element_position = event_pos
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
            element.pixmap = None
            element.modify_end_point = False
        elif tool in [ToolID.blurring, ToolID.darkening]:
            self.elementsMousePressEventDefault(element, event)
            if tool == ToolID.blurring:
                element.finished = False
        elif tool == ToolID.transform:

            if self.is_over_scaling_activation_area(event.pos()):
                self.canvas_START_selected_elements_SCALING(event)

            elif self.is_over_rotation_activation_area(event.pos()):
                self.canvas_START_selected_elements_ROTATION(event.pos())

            elif self.any_element_area_under_mouse(event.modifiers() & Qt.ShiftModifier):
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
        for el in self.elementsHistoryFilter():
            if el.type == ToolID.text:
                element = el
        if element:
            if clockwise_rotation:
                delta = 10
            else:
                delta = -10
            element.rotation += delta
        self.update()

    def elementsMoveElement(self, event):
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
        for element in self.selected_items:
            element = self.elementsPrepareForModificationsIfNeeded(element)
            if hasattr(element, 'element_position'):
                element.element_position += delta
            else:
                raise Exception('Unsupported type:', element.type)
            self.elementsSetSelected(element)
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

    def elementsMouseMoveEvent(self, event):
        event_pos = self.elementsMapFromViewportToCanvas(QPointF(event.pos()))

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
        elif tool in [ToolID.zoom_in_region, ToolID.copypaste]:
            self.elementsAdvancedInputMoveEvent(event, event_pos, element)
        elif tool == ToolID.picture:
            element.pixmap = self.current_picture_pixmap
            element.element_rotation = self.current_picture_angle
            element.element_position = event_pos
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
            element.modify_end_point = False
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
                pass
        elif tool == ToolID.transform:
            no_mod = event.modifiers() == Qt.NoModifier

            if self.transform_cancelled:
                pass

            elif self.scaling_ongoing:
                self.canvas_DO_selected_elements_SCALING(event.pos())

            elif self.rotation_ongoing:
                self.canvas_DO_selected_elements_ROTATION(event.pos())

            elif no_mod and not self.selection_ongoing:
                self.canvas_DO_selected_elements_TRANSLATION(event.pos())
                self.update_selection_bouding_box()

            elif self.selection_ongoing is not None and not self.translation_ongoing:
                self.selection_end_point = QPointF(event.pos())
                if self.selection_start_point:
                    self.selection_rect = build_valid_rectF(self.selection_start_point, self.selection_end_point)
                    self.canvas_selection_callback(event.modifiers() == Qt.ShiftModifier)

            for element in self.selected_items:
                element = self.elementsPrepareForModificationsIfNeeded(element)

        self.update()

    def elementsMouseReleaseEvent(self, event):
        event_pos = self.elementsMapFromViewportToCanvas(QPointF(event.pos()))

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
        elif tool in [ToolID.zoom_in_region, ToolID.copypaste]:
            self.elementsAdvancedInputMoveEvent(event, event_pos, element, finish=True)
        elif tool == ToolID.picture:
            element.pixmap = self.current_picture_pixmap
            element.element_rotation = self.current_picture_angle
            element.element_position = event_pos
            self.elementsSetPixmapFromMagazin()
        elif tool in [ToolID.pen, ToolID.marker]:
            if element.straight:
                element.end_point = event_pos
            else:
                element.end_point = event_pos
                element.path.lineTo(event_pos)
            element.calc_local_data()
        elif tool == ToolID.line:
            element.end_point = event_pos
            if event.modifiers() & Qt.ShiftModifier:
                element.end_point = constraint45Degree(element.start_point, element.end_point)
            element.calc_local_data()
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
            element.end_point = event_pos
            element.modify_end_point = False
            self.elementsCreateTextbox(self, element)
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

                if self.selected_items:
                    for element in self.selected_items:
                        if element.type == ToolID.blurring:
                            element.finished = True
                            self.elementsSetBlurredPixmap(element)
                        elif element.type in [ToolID.zoom_in_region, ToolID.copypaste]:
                            if not element.second:
                                self.elementsSetCopiedPixmap(element)
                        elif element.type == ToolID.text:
                            element.modify_end_point = True

        if tool != ToolID.transform:
            self.elementsSetSelected(None)

        self.elementsAutoDeleteInvisibleElement(element)
        self.tools_window.forwards_backwards_update()
        self.update()

    def elementsAutoDeleteInvisibleElement(self, element):
        tool = self.current_tool
        if tool in [ToolID.line, ToolID.pen, ToolID.marker]:
            if element.end_point == element.start_point:
                self.elements.remove(element)
                if self.tools_window:
                    self.elements_history_index = self.prev_elements_history_index
                    # print('correcting after autodelete')

    def elementsSetCopiedPixmap(self, element):
        if element.second:
            return
        er = element.get_size_rect(scaled=True)
        er.moveCenter(element.element_position)
        capture_pos = element.element_position
        capture_width = er.width()
        capture_height = er.height()
        capture_rotation = element.element_rotation
        pixmap = QPixmap.fromImage(self.source_pixels)
        element.pixmap = capture_rotated_rect_from_pixmap(pixmap,
            capture_pos,
            capture_rotation,
            capture_width,
            capture_height
        )

    def elementsSetBlurredPixmap(self, element):
        if not element.finished:
            return

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
        er.moveCenter(element.element_position)
        capture_pos = element.element_position
        capture_width = er.width()
        capture_height = er.height()
        capture_rotation = element.element_rotation
        # source_pixmap = QPixmap.fromImage(self.source_pixels)
        source_pixmap = cropped_source_pixels
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

    def elementsChangeTextbox(self, elem):
        if elem.toolbool:
            background_color = "rgb(200, 200, 200)"
        else:
            background_color = "transparent"
        style = """QTextEdit {
            border: none;
            font-size: %dpx;
            background-color: %s;
            padding: %dpx;
            border-radius: 5px;
            color: %s;
        }
        QTextEdit QMenu::item {
            color: rgb(100, 100, 100);
        }
        QTextEdit QMenu::item:selected{
            color: rgb(0, 0, 0);
        }
        """ % (
                self.elementsGetFontPixelSize(elem),
                background_color,
                elem.margin_value,
                elem.color.name()
        )
        if elem.textbox:
            elem.textbox.setStyleSheet(style)
            self.elementsOnTextChanged(elem)

    def elementsGetFontPixelSize(self, elem):
        return 20+10*elem.size

    def elementsOnTextChanged(self, elem):
        tb = elem.textbox
        textbox_text = tb.toPlainText()
        if textbox_text: # проверяем есть ли текст,
                         # это нужно чтобы при иниализации не стёрлось ничего
            elem.text = textbox_text
        size = tb.document().size().toSize()
        # correcting height
        new_height = size.height()+elem.margin_value*2
        tb.setFixedHeight(int(new_height))
        # correcting width
        max_width_limit = int(max(20, self.capture_region_rect.right() - elem.end_point.x()))
        H, W = 100, max_width_limit+10
        pixmap = QPixmap(H, W)
        r = QRect(0, 0, H, W)
        p = QPainter()
        p.begin(pixmap)
        font = tb.currentFont()
        font_pixel_size = self.elementsGetFontPixelSize(elem)
        font.setPixelSize(int(font_pixel_size))
        p.setFont(font)
        brect = p.drawText(r.x(), r.y(), r.width(), r.height(), Qt.AlignCenter, tb.toPlainText())
        p.end()
        del p
        del pixmap
        new_width = min(max_width_limit, brect.width()+elem.margin_value*2+font_pixel_size*1.5)
        tb.setFixedWidth(int(new_width))
        ___p = elem.end_point-QPointF(0, new_height)
        tb.move(___p.toPoint())
        # making screenshot
        r = tb.rect()
        cw = tb.cursorWidth()
        tb.setCursorWidth(0)
        elem.pixmap = tb.grab(r)
        tb.setCursorWidth(cw)
        if tb.parent():
            tb.parent().update()

    def elementsCreateTextbox(self, parent, elem):
        textbox = QTextEdit()
        if hasattr(elem, "text"):
            textbox.setText(elem.text)
        self.elementsTextBoxInit(textbox, parent, elem)

    def elementsTextBoxInit(self, textbox, parent, elem):
        textbox.setParent(parent)
        elem.textbox = textbox
        textbox.move(elem.end_point.toPoint())
        self.elementsChangeTextbox(elem)
        textbox.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        textbox.show()
        self.elementsOnTextChanged(elem) #call to adjust for empty string
        textbox.textChanged.connect(lambda x=elem: self.elementsOnTextChanged(x))
        textbox.setFocus()

    def elementsDrawDarkening(self, painter, prepare_pixmap=False):
        if self.capture_region_rect:
            darkening_value = 0.0
            darkening_zone = QPainterPath()
            darkening_zone.setFillRule(Qt.WindingFill)
            at_least_one_exists = False
            for element in self.elementsHistoryFilter():
                if element.type == ToolID.darkening:
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
        if element.type in [ToolID.pen, ToolID.line]:
            PEN_SIZE = 25
        elif element.type == ToolID.marker:
            PEN_SIZE = 40
            color.setAlphaF(0.3)
        else:
            PEN_SIZE = 25
        pen = QPen(color, 1+PEN_SIZE*size)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen, color, size

    def elementsDrawMainElement(self, painter, element, final):
        el_type = element.type
        pen, color, size = self.elementsGetPenFromElement(element)
        painter.setPen(pen)
        painter.setBrush(QBrush(color))
        if el_type == ToolID.arrow:
            painter.setTransform(element.get_transform_obj(canvas=self))
            painter.setPen(Qt.NoPen)
            self.elementsDrawArrow(painter, element.local_start_point, element.local_end_point, size, True)
            painter.setPen(QPen(Qt.green, 5))
            painter.resetTransform()
        elif el_type in [ToolID.pen, ToolID.marker]:
            painter.setTransform(element.get_transform_obj(canvas=self))
            painter.setBrush(Qt.NoBrush)
            if element.straight:
                painter.drawLine(element.local_start_point, element.local_end_point)
            else:
                p = element.path
                path = p.translated(-p.boundingRect().center())
                painter.drawPath(path)
            painter.resetTransform()
        elif el_type == ToolID.line:
            painter.setTransform(element.get_transform_obj(canvas=self))
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
            if element.pixmap:
                pixmap = QPixmap(element.pixmap.size())
                pixmap.fill(Qt.transparent)
                p = QPainter()
                p.begin(pixmap)
                p.setClipping(True)
                path = QPainterPath()
                pos = element.end_point - QPoint(0, element.pixmap.height())
                # text_rect = QRectF(pos, element.pixmap.size())
                text_rect = QRectF(QPointF(0, 0), QSizeF(element.pixmap.size()))
                path.addRoundedRect(QRectF(text_rect), element.margin_value,
                        element.margin_value)
                p.setClipPath(path)
                p.drawPixmap(QPoint(0, 0), element.pixmap)
                p.setClipping(False)
                p.end()

            painter.setPen(Qt.NoPen)
            if element.start_point != element.end_point:
                if element.modify_end_point:
                    modified_end_point = get_nearest_point_on_rect(
                        QRect(pos, QSize(element.pixmap.width(), element.pixmap.height())),
                        element.start_point
                    )
                else:
                    modified_end_point = element.end_point
                self.elementsDrawArrow(painter, modified_end_point, element.start_point,
                                                                                size, False)
            if element.pixmap:
                image_rect = QRectF(pos, QSizeF(pixmap.size()))
                painter.translate(image_rect.center())
                image_rect = QRectF(-image_rect.width()/2, -image_rect.height()/2,
                        image_rect.width(), image_rect.height()).toRect()
                painter.rotate(element.element_rotation)
                editing = not final and (element is self.active_element or \
                                    (element.textbox is not None and element.textbox.isVisible()))
                if editing:
                    painter.setOpacity(0.5)
                painter.drawPixmap(image_rect, pixmap)
                if editing:
                    painter.setOpacity(1.0)
                painter.resetTransform()

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
                # painter.setBrush(QBrush(QColor(150, 150, 0), Qt.BDiagPattern))
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
        elif el_type in [ToolID.zoom_in_region, ToolID.copypaste]:

            painter.setBrush(Qt.NoBrush)

            slot_elements = element.hs.elements
            f_element = slot_elements[0]

            if len(slot_elements) > 1:
                s_element = slot_elements[1]
            else:
                s_element = None

            if f_element.finished:
                if s_element is None:
                    output_pos = self.elementsMapFromViewportToCanvas(QCursor().pos())
                    toolbool = f_element.toolbool
                    color = f_element.color
                else:
                    output_pos = s_element.element_position
                    toolbool = s_element.toolbool
                    color = s_element.color

            if el_type == ToolID.zoom_in_region:
                painter.setPen(QPen(color, 1))
            if el_type == ToolID.copypaste:
                painter.setPen(QPen(Qt.red, 1, Qt.DashLine))

            painter.setTransform(element.get_transform_obj(canvas=self))

            # отрисовка первой пометки
            if not element.second:
                if el_type == ToolID.zoom_in_region or (el_type == ToolID.copypaste and not final):
                    capture_rect = build_valid_rectF(
                        f_element.local_start_point,
                        f_element.local_end_point
                    )
                    painter.drawRect(capture_rect)

            # отрисовка второй пометки
            # special_case - когда вторая пометка ещё не введена,
            # надо рисовать её образ центированный по кусроску мыши
            special_case = (not element.second and f_element.finished and s_element is None)
            if element.second or special_case:

                output_rect = element.get_size_rect(scaled=False)
                if s_element is None:
                    pos = output_pos - f_element.element_position
                    if el_type in [ToolID.zoom_in_region]:
                        s = ZOOM_IN_REGION_DAFULT_SCALE
                        output_rect = QRectF(0, 0, output_rect.width()*s, output_rect.height()*s)
                else:
                    pos = output_pos - s_element.element_position
                output_rect.moveCenter(pos)


                painter.drawPixmap(output_rect, f_element.pixmap, QRectF(f_element.pixmap.rect()))

                if el_type == ToolID.zoom_in_region:

                    painter.drawRect(output_rect)

                if toolbool and el_type == ToolID.zoom_in_region:
                    all_points = []

                    font = painter.font()
                    font.setPixelSize(35)
                    painter.setFont(font)

                    kwargs = {
                        "canvas":self,
                        "apply_local_scale":True,
                        "apply_translation":True,
                        "apply_global_scale":False
                    }
                    f_canvas_transform = f_element.get_transform_obj(**kwargs)
                    if s_element is not None:
                        s_canvas_transform = s_element.get_transform_obj(**kwargs)
                        size_rect_local = s_element.get_size_rect(scaled=False)

                        size_rect = f_element.get_size_rect(scaled=False)
                        size_rect.moveCenter(QPointF(0, 0))
                        sr1_points = self.elementsGetRectCorners(size_rect)
                        for p in sr1_points:
                            # from f_element local to canvas world
                            p = f_canvas_transform.map(p)
                            # from canvas world to s_element local
                            t = s_canvas_transform.inverted()
                            if not t[1]:
                                raise Exception('inverted matrix doesn\'t exist!')
                            s_canvas_transform_inverted = t[0]
                            p = s_canvas_transform_inverted.map(p)
                            all_points.append(p)


                        size_rect_local.moveCenter(QPointF(0, 0))
                        sr2_points = self.elementsGetRectCorners(size_rect_local)
                        for p in sr2_points:
                            all_points.append(p)

                    else:

                        self.__te.element_position = output_pos
                        self.__te.calc_local_data_finish(f_element)

                        s_canvas_transform = self.__te.get_transform_obj(**kwargs)
                        size_rect_non_local = self.__te.get_size_rect(scaled=False)

                        # так как образ отрисовывается во фрейме первого элемента,
                        # то мапить придётся уже sr2, а не sr1
                        size_rect = f_element.get_size_rect(scaled=False)
                        size_rect.moveCenter(QPointF(0, 0))
                        sr1_points = self.elementsGetRectCorners(size_rect)
                        for p in sr1_points:
                            all_points.append(p)

                        size_rect_non_local.moveCenter(QPointF(0, 0))
                        sr2_points = self.elementsGetRectCorners(size_rect_non_local)
                        for p in sr2_points:
                            p = s_canvas_transform.map(p)
                            t = f_canvas_transform.inverted()
                            if not t[1]:
                                raise Exception('inverted matrix doesn\'t exist!')
                            f_canvas_transform_inverted = t[0]
                            p = f_canvas_transform_inverted.map(p)
                            all_points.append(p)


                    coords = convex_hull(all_points)
                    if coords is not None and len(coords) > 1:
                        coords.append(coords[0])
                        for n, coord in enumerate(coords[:-1]):
                            painter.drawLine(coord, coords[n+1])


            painter.resetTransform()

    def elementsGetRectCorners(self, rect):
        return [
            rect.topLeft(),
            rect.topRight(),
            rect.bottomRight(),
            rect.bottomLeft()
        ]

    def elementsDrawMain(self, painter, final=False, draw_background_only=False):
        painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        old_brush = painter.brush()
        old_pen = painter.pen()
        # draw elements
        if not self.dark_pictures:
            self.elementsDrawDarkening(painter)

        # штампы (изображения) рисуем первыми, чтобы пометки всегда были поверх них
        all_visible_elements = self.elementsHistoryFilter()
        pictures_first = []
        all_the_rest = []
        if draw_background_only:
            pictures_first = [el for el in all_visible_elements if el.background_image]
        else:
            for element in all_visible_elements:
                if element.type == ToolID.picture:
                    if not element.background_image or final:
                        pictures_first.append(element)
                else:
                    all_the_rest.append(element)
        for element in pictures_first:
            self.elementsDrawMainElement(painter, element, final)
        for element in all_the_rest:
            self.elementsDrawMainElement(painter, element, final)

        if not draw_background_only:
            self.elementsDrawSystemCursor(painter)

        if not final:
            # отрисовка виджетов
            self.elementsDrawSelectionMouseRect(painter)
            self.elementsDrawSelectionTransformBox(painter)
            self.elementsDrawSelectedElementsDottedOutlines(painter)

        if self.Globals.DEBUG and self.capture_region_rect and not final:
            painter.setPen(QPen(QColor(Qt.white)))
            text = f"{self.elements_history_index} :: {self.current_tool}"
            painter.drawText(self.capture_region_rect, Qt.AlignCenter, text)
        if self.dark_pictures:
            self.elementsDrawDarkening(painter)
        painter.setBrush(old_brush)
        painter.setPen(old_pen)

        painter.setRenderHint(QPainter.HighQualityAntialiasing, False)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)

    def elementsDrawSystemCursor(self, painter):
        if self.tools_window and self.tools_window.chb_draw_cursor.isChecked():
            screenshot_cursor_position = self.elementsMapFromCanvasToViewport(self.screenshot_cursor_position)
            painter.drawPixmap(screenshot_cursor_position, self.cursor_pixmap)

    def elementsDrawDebugInfo(self, painter, viewport_input_rect):
        pos_right = self.elementsMapFromCanvasToViewport(viewport_input_rect.bottomRight())
        pos_left = self.elementsMapFromCanvasToViewport(viewport_input_rect.bottomLeft())
        visible_elements = self.elementsHistoryFilter()

        def build_info_text(elem):
            info_text = ""
            if hasattr(elem, "source_index"):
                info_text += f"[{elem.unique_index}] {elem.type} from [{elem.source_index}]"
            else:
                info_text += f"[{elem.unique_index}] {elem.type}"
            if hasattr(elem, 'toolbool'):
                info_text += f" {elem.toolbool}"
            return info_text

        # левая сторона
        painter.save()
        info_rect = build_valid_rectF(pos_left, self.rect().topLeft())
        info_rect.setWidth(300)
        info_rect.moveBottomRight(pos_left)
        painter.fillRect(info_rect, QColor(0, 0, 0, 180))
        font = painter.font()
        pixel_height = 25
        font.setPixelSize(20)
        max_width = 0

        pos_left += QPointF(-10, -10)
        for element in self.elements:
            element.debug_text = build_info_text(element)
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


        # правая сторона
        info_rect = build_valid_rectF(pos_right, self.rect().topRight())
        info_rect.setWidth(800)
        painter.fillRect(info_rect, QColor(0, 0, 0, 180))
        info_rect.moveBottomLeft(QPointF(10, -10) + info_rect.bottomLeft())
        vertical_offset = 0
        for index, hs in list(enumerate(self.history_slots)):
            painter.save()
            painter.setPen(Qt.white)
            slot_info_text = f'[slot {index}] {hs.content_type}'
            font = painter.font()
            pixel_height = 25
            font.setPixelSize(20)
            painter.setFont(font)
            vertical_offset += (len(hs.elements) + 1)
            pos_right = info_rect.bottomLeft() + QPointF(0, -vertical_offset*pixel_height)
            painter.drawText(pos_right, slot_info_text)
            for i, elem in enumerate(hs.elements):

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

                info_text = build_info_text(elem)

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

    def elementsUpdateFinalPicture(self, capture_region_rect=None):
        if self.capture_region_rect:
            specials = [el for el in self.elementsHistoryFilter() if el.type == ToolID.multiframing]
            any_multiframing_element = any(specials)
            if any_multiframing_element:
                max_width = -1
                total_height = 0
                specials_rects = []
                source_pixmap = QPixmap.fromImage(self.source_pixels)
                for number, el in enumerate(specials):
                    br = el.get_canvas_space_selection_rect_with_no_rotation()
                    capture_pos = el.element_position
                    el.bounding_rect = br
                    capture_pos = el.element_position
                    capture_rotation = el.element_rotation
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
                self.elements_final_output = QPixmap(QSize(max_width, total_height))
                painter = QPainter()
                painter.begin(self.elements_final_output)
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

                self.elements_final_output = QPixmap(capture_region_rect.size().toSize())
                self.elements_final_output.fill(Qt.transparent)
                painter = QPainter()
                painter.begin(self.elements_final_output)
                self._canvas_origin = QPointF(self.canvas_origin)
                self._canvas_scale_x = self.canvas_scale_x
                self._canvas_scale_y = self.canvas_scale_y
                self.canvas_origin = -capture_region_rect.topLeft()
                self.canvas_scale_x = 1.0
                self.canvas_scale_y = 1.0
                self.elementsDrawMain(painter, final=True)
                self.canvas_origin = self._canvas_origin
                self.canvas_scale_x = self._canvas_scale_x
                self.canvas_scale_y = self._canvas_scale_y
                painter.end()

                if self.tools_window and self.tools_window.chb_masked.isChecked():
                    self.elements_final_output = self.circle_mask_image(self.elements_final_output)

    def elementsPrepareForModificationsIfNeeded(self, element, force_new=False):
        if element == self.elementsGetLastElement() and not force_new:
            # если элемент последний в списке элементов,
            # то его предыдущее состояние не сохраняется
            return element
        elif element.hs.content_type in (ToolID.zoom_in_region, ToolID.copypaste):
            return element
        else:
            new_element = self.elementsCreateNew(ToolID.TEMPORARY_TYPE_NOT_DEFINED)
            self.elementsCopyElementData(new_element, element)
            new_element.source_index = element.unique_index
            self.elementsSetSelected(new_element)
            return new_element

    def elementsParametersChanged(self):
        tw = self.tools_window
        if tw:
            element = self.active_element or self.elementsGetLastElement()
            case1 = element and element.type == self.tools_window.current_tool and element.fresh
            case2 = element and tw.current_tool == ToolID.transform
            if case1 or case2:
                element = self.elementsPrepareForModificationsIfNeeded(element)
                self.elementsSetElementParameters(element)
        self.update()
        self.activateWindow() # чтобы фокус не соскакивал на панель иструментов

    def elementsDrawArrow(self, painter, start_point, tip_point, size, sharp):
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
        painter.drawPath(path)

    def elementsHistoryForwards(self):
        self.elementsDeactivateTextElements()
        if self.elements_history_index < len(self.history_slots):
            self.elements_history_index += 1
        self.elementsSetSelected(None)

    def elementsHistoryBackwards(self):
        self.elementsDeactivateTextElements()
        if self.elements_history_index > 0:
            self.elements_history_index -= 1
        self.elementsSetSelected(None)

    def elementsUpdateHistoryButtonsStatus(self):
        f = self.elements_history_index < len(self.history_slots)
        b = self.elements_history_index > 0
        return f, b

    def elementsSetCaptureFromContent(self):
        points = []
        for element in self.elementsFilterElementsForSelection():
            if element.type in [ToolID.removing, ToolID.multiframing]:
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
            self.input_POINT2, self.input_POINT1 = get_bounding_points(points)
            self.capture_region_rect = build_valid_rectF(self.input_POINT1, self.input_POINT2)

    def elementsDoRenderToBackground(self):
        subMenu = QMenu()
        subMenu.setStyleSheet(self.context_menu_stylesheet)
        action_extend = subMenu.addAction("Расширить картинку-фон, если контент будет превосходить её размеры")
        action_keep = subMenu.addAction("Оставить размеры картинки-фона как есть")
        action_crop = subMenu.addAction("Обрезать по рамке захвата")
        action_cancel = subMenu.addAction("Отмена")

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
            for element in self.elementsHistoryFilter():
                sel_area = element.get_canvas_space_selection_area()
                br = sel_area.boundingRect()

                points.append(br.topLeft())
                points.append(br.bottomRight())

            if points:
                content_rect = build_valid_rectF(*get_bounding_points(points))
            else:
                content_rect = QRectF()
            new_width = max(self.source_pixels.width(), content_rect.width())
            new_height = max(self.source_pixels.height(), content_rect.height())


        # рендер картинки
        if action == action_crop:
            self.elementsUpdateFinalPicture()
        elif action == action_keep:
            hs = self.history_slots[0]
            r = QRectF(QPointF(0, 0), QSizeF(hs.elements[0].pixmap.size()))
            self.elementsUpdateFinalPicture(capture_region_rect=r)
        elif action == action_extend:
            self.elementsUpdateFinalPicture(
                    capture_region_rect=QRectF(0, 0, new_width, new_height))

        # заменяем картинку
        self.source_pixels = self.elements_final_output.toImage()
        self.elementsCreateBackgroundPictures(update=True)

        # обновляем рамку, если по ней производилась обрезка
        if action == action_crop:
            w = self.capture_region_rect.width()
            h = self.capture_region_rect.height()
            self.input_POINT2, self.input_POINT1 = get_bounding_points([QPointF(0, 0), QPointF(w, h)])
            self.capture_region_rect = build_valid_rectF(self.input_POINT1, self.input_POINT2)

        # cleaning
        self.elementsSetSelected(None)

        self.elements_history_index = 1 # 1, а не 0, потому что оставляем слот с фоном
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

            element = self.elementsPrepareForModificationsIfNeeded(source_element, force_new=True)

            start_br = element.get_canvas_space_selection_area().boundingRect()

            if target_height is not None:
                scale = target_height / start_br.height()

            if target_width is not None:
                scale = target_width / start_br.width()

            element.element_scale_x = scale
            element.element_scale_y = scale

            br = element.get_canvas_space_selection_area().boundingRect()

            element.element_position = QPointF(pos) + QPointF(br.width()/2, br.height()/2)
            if target_height is not None:
                pos += QPointF(br.width(), 0)

            if target_width is not None:
                pos += QPointF(0, br.height())

            br = element.get_canvas_space_selection_area().boundingRect()

            points.append(br.topLeft())
            points.append(br.bottomRight())

        # обновление области захвата
        self.input_POINT2, self.input_POINT1 = get_bounding_points(points)
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
            if element.type == ToolID.picture:
                    elements.append(element)
        return elements

    def elementsSortPicturesByXPosition(self, elements):
        m = Element.get_canvas_space_selection_rect_with_no_rotation
        cmp_func = lambda e: m(e).center().x()
        return list(sorted(elements, key=cmp_func))

    def elementsAutoCollagePictures(self):
        subMenu = QMenu()
        subMenu.setStyleSheet(self.context_menu_stylesheet)
        horizontal = subMenu.addAction("По горизонтали")
        vertical = subMenu.addAction("По вертикали")
        action = subMenu.exec_(QCursor().pos())

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

    def elementsUpdateAfterReshot(self):
        # updating dependent elements
        for element in self.elements:
            if element.type in [ToolID.blurring]:
                self.elementsSetBlurredPixmap(element)
            if element.type in [ToolID.copypaste, ToolID.zoom_in_region]:
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
                element.element_position = pos + QPointF(pixmap.width()/2, pixmap.height()/2)
                element.calc_local_data()
                self.elementsSetSelected(element)
                self.elementsUpdatePanelUI()
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
            mapped_capture = self.elementsMapFromCanvasToViewportRectF(self.capture_region_rect)
            mapped_capture_center = mapped_capture.center()
            content_pos = mapped_capture_center - self.canvas_origin
        else:
            content_pos = QPointF(element.element_position.x()*canvas_scale_x, element.element_position.y()*canvas_scale_y)
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
