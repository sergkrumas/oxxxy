
# Важно:

Туториал частично устарел с выходом версии 0.92, так как код был переработан и доработан, но общие принципы описанные в туториале все ещё актуальны.
## Обзор кода инструментов ~~*Пупа*~~*Копипейст* и *Лупа*



Этот раздел пригодится тем, кто захочет разработать свой инструмент для этого скриншотера, но перед этим им нужно будет попытаться разобраться с исходным кодом.

Здесь я буду рассматривать два похожих по методу ввода инструмента - **Копипейст** (неофициальное название - **Пупа**) и **Лупа** - их идентификаторы `copypaste` и `zoom_in_region` соответственно.




### Код для объявления нового инструмента, вставки кнопки на панель, отрисовки кнопки и подсказки

Чтобы в панели инструментов появилась кнопка инструмента нужно объявить в отдельном списке её идентификатор латиницей, название и описание на русском. В свою очередь этот список надо сделать элементом в списке `editor_buttons_data`. 

Ниже пример того, как это сделано для инструментов **Копипейст** и **Лупа**:
```python
editor_buttons_data = [
    ...,
    ...,
    ["zoom_in_region", "Лупа", "Размещает увеличенную копию необходимой области изображения в любом месте"],

    ["copypaste", "Копипейст", "Копирует область изображения в любое место без увеличения"]

]
```

Кнопки появятся на панели инструментов, при наведении на них курсора мышки появится подсказка. Но на этих кнопках  ещё нужно что-то нарисовать. Для этого нужно дополнить метод `draw_button` в классе `CustomPushButton`, добавив пару elif-веток с заданными выше идентификаторами инструментов. Обратите внимание на использование `main_color` и `self.rect()` - `main_color` меняется в зависимости от того, выбран данный инструмент или нет, и находится ли над кнопкой инструмента курсор мыши:

```python
    elif tool_id == "zoom_in_region":

        rect = self.rect().adjusted(5, 5, -20, -20)
        w_ = 3
        painter.setPen(QPen(main_color, w_))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(rect)
        painter.drawLine(
            rect.topLeft()/2 + rect.topRight()/2 + QPoint(0, 6),
            rect.bottomLeft()/2 + rect.bottomRight()/2 + QPoint(0, -6)
        )
        painter.drawLine(
            rect.topLeft()/2 + rect.bottomLeft()/2 + QPoint(6, 0),
            rect.topRight()/2 + rect.bottomRight()/2 + QPoint(-6, 0)
        )
        w_ = 6
        pen = QPen(main_color, w_)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setClipping(True)
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))
        path.addEllipse(QRectF(rect))
        painter.setClipPath(path)
        painter.drawLine(
            rect.bottomRight() - QPoint(10, 10),
            self.rect().bottomRight() - QPoint(8, 8)
        )
        painter.setClipping(False)

    elif tool_id == "copypaste":

        pen = QPen(main_color, 1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        set_font(painter, 1900, pixel_size=12)
        painter.drawText(QPoint(2, 25), "COPY")
        painter.drawText(QPoint(5, 36), "PASTE")
```






### Код нанесения пометки с помощью левой кнопки мыши

В методе `define_class_Element` задаются атрибуты и их изначальные значения для элементов (каждая отдельная пометка или эффект называются "элементами" в коде) под каждый инструмент. Здесь нас интересуют атрибуты `type, finished, copy_pos, zoom_second_input, choose_default_subelement`:

```python
def define_class_Element(self):
    def __init__(self, _type, elements_list):
        self.textbox = None
        self.type = _type
        self.finished = False

        self.copy_pos = None
        self.zoom_second_input = False

        self.rotation = 0

        elements_list.append(self)

        n = 0
        for el in elements_list:
            if el.type == "numbering":
                n += 1
        self.number = n

        if hasattr(type(self), "_counter"):
            type(self)._counter += 1
        else:
            type(self)._counter = 0
        self.unique_index = type(self)._counter

        self.choose_default_subelement = True # for copypaste and zoom_in_region

    return type("Element", (), {"__init__": __init__})

```

Метод `elementsBuildSubelementRect` вызывается из многих мест и вынесен в одну функцию, чтобы соблюсти принцип DRY: 
```python
def elementsBuildSubelementRect(self, element, copy_pos):
    _rect = build_valid_rect(element.start_point, element.end_point)
    if element.type == "zoom_in_region":
        factor = 1.0 + element.size*4.0
        _rect.setWidth(int(_rect.width()*factor))
        _rect.setHeight(int(_rect.height()*factor))
    _rect.moveCenter(copy_pos)
    return _rect
```

`elementsIsSpecialCase` - вспомогательный метод-функция. Используется в `elementsMousePressEvent` и в `eventFilter`. В первом случае её вызов даёт реализовать поэтапный ввод данных: сначала - границ области для копирования через зажатую левую кнопку мыши, а потом позиции копии через клик левой кнопки мыши. Всё это реализовано в методе `elementsMousePressEvent`:

```python
def elementsIsSpecialCase(self, element):
    special_case = element is not None
    special_case = special_case and element.type in ["zoom_in_region", "copypaste"]
    special_case = special_case and not element.finished
    return special_case

def elementsMousePressEvent(self, event):
    ...
    ...
    el = self.elementsGetLastElement()
    if self.current_tool == "transform":
        element = None # код выбора элемента ниже
    elif self.elementsIsSpecialCase(el):
        # zoom_in_region and copypaste case, when it needs more additional clicks
        element = el
    else:
        # default case
        element = self.elementsCreateNew(self.current_tool, start_drawing=True)
    # #######
    ...
    ...
    elif tool in ["zoom_in_region", "copypaste"]:
        if not element.zoom_second_input:
            self.elementsMousePressEventDefault(element, event)
        elif not element.finished:
            element.copy_pos = event.pos()
    ...
    ...
```

В `elementsMouseMoveEvent` пользователю даётся возможность задавать границы захвата через мышку с зажатой левой кнопкой. Стоит заметить, что этот метод вызывается только при зажатой левой кнопке мыши. Здесь тоже прописан поэтапный ввод данных:
```python
def elementsMouseMoveEvent(self, event):
    ...
    ...
    element = self.elementsGetLastElement()
    if element is None:
        return
    ...
    elif tool in ["zoom_in_region", "copypaste"]:
        if not element.zoom_second_input:
            element.end_point = event.pos()
        elif not element.finished:
            element.copy_pos = event.pos()
    ...
    ...
```

В `elementsMouseReleaseEvent` задаётся переход с первого этапа ввода данных на второй, и переход со второго этапа на немедленное завершение работы инструмента:
```python
def elementsMouseReleaseEvent(self, event):
    ...
    ...
    element = self.elementsGetLastElement()
    if element is None:
        return
    ...
    ...
    ...
    elif tool in ["zoom_in_region", "copypaste"]:
        if not element.zoom_second_input:
            element.end_point = event.pos()
            element.zoom_second_input = True
        elif not element.finished:
            element.copy_pos = event.pos()
            element.finished = True
    ...
    ...
    ...
```










### Код отрисовки пометки

Пометки инструментов надо как-то отрисовывать в редакторе и на финальном скриншоте. Делать это нужно в методе `elementsDrawMain` под соответствующими ветками. Для удобства и соблюдения DRY ветки двух описываемых инструментов были объеденены. 

Если что-то необходимо рисовать только в редакторе, но не на финальном скриншоте, то для этого нужно запрашивать значение аргумента `final`. У инструмента **Копипейст** *зона захвата копии* отрисовывается только в режиме редактора для удобства пользователя, а на финальном скриншоте обрисовывать её рамкой ни к чему:
```python
def elementsDrawMain(self, painter, final=False):
  ...
  ...
  elif el_type in ["zoom_in_region", "copypaste"]:
      input_rect = build_valid_rect(element.start_point, element.end_point)
      curpos = QCursor().pos()
      final_pos = element.copy_pos if element.finished else self.mapFromGlobal(curpos)
      final_version_rect = self.elementsBuildSubelementRect(element, final_pos)
      painter.setBrush(Qt.NoBrush)
      if el_type == "zoom_in_region":
          painter.setPen(QPen(element.color, 1))
      if el_type == "copypaste":
          painter.setPen(QPen(Qt.red, 1, Qt.DashLine))
      if el_type == "zoom_in_region" or \
                      (el_type == "copypaste" and not final):
          painter.drawRect(input_rect)
      if element.zoom_second_input or element.finished:
          if element.backplate and el_type == "zoom_in_region":
              points = []
              attrs_names = ["topLeft", "topRight", "bottomLeft", "bottomRight"]
              for corner_attr_name in attrs_names:
                  p1 = getattr(input_rect, corner_attr_name)()
                  p2 = getattr(final_version_rect, corner_attr_name)()
                  points.append(p1)
                  points.append(p2)
              coords = convex_hull(points)
              for n, coord in enumerate(coords[:-1]):
                  painter.drawLine(coord, coords[n+1])
          source_pixels = self.source_pixels
          painter.drawImage(final_version_rect, source_pixels, input_rect)
          if el_type == "zoom_in_region":
              painter.drawRect(final_version_rect)
  ...
  ...
```









### Код перемещения пометки с помощью виджета транформации

В программе существует инструмент **Перемещение**, который позволяет поменять позицию пометки/эффекта и некоторые её/его параметры - цвет, размер/интенсивность/величину уже после нанесения пометки/эффекта. Но чтобы изменять пометку, её надо ещё выбрать из имеющихся. Дело дополнительно усложняется тем, что и инструмент Копипейст, и инструмент Лупа за одно применение в результате создадут две субпометки (при том не каждая из них отрисуется на финальном скриншоте), и отсюда назревает необходимость перемещать эти субпометки отдельно друг от друга. Для этого заводится атрибут `choose_default_subelement`, который хранится в данных самой пометки и инициализируется значением по умолчанию при создании прям перед непосредственным началом ввода поэтапного ввода данных для пометки. 

Если `is_mouse_over` это `True`, то пометка и одна из её составляющих субпометок вместе как одно целое включатся в список элементов, находящихся в данный момент под курсором мыши:
```python
def elementsGetElementsUnderMouse(self, cursor_pos):
    elements_under_mouse = []
    for el in self.elementsHistoryFilter():
        ...
        ...
        elif el.type in ["zoom_in_region", "copypaste"]:
            is_mouse_over1 = build_valid_rect(el.start_point, el.end_point).contains(cursor_pos)
            is_mouse_over2 = False
            if is_mouse_over1:
                el.choose_default_subelement = True
            elif el.copy_pos:
                sub_element_rect = self.elementsBuildSubelementRect(el, el.copy_pos)
                is_mouse_over2 = sub_element_rect.contains(cursor_pos)
                if is_mouse_over2:
                    el.choose_default_subelement = False
            is_mouse_over = is_mouse_over1 or is_mouse_over2
        ...
        ...
```

Когда из всех элементов под курсором очередь дошла именно до нашего (то есть он выбран при очередном щелчке левой кнопки мыши на одном и том же месте), то для одной из двух субпометкок нашего элемента мы должны отобразить соответствующий виджет. Так как для субпометки для копии требуется только позиция, то полновесный виджет для неё не нужен, и нам хватит простой точки в центре (`center_point_only=True`), за которой мы и будем эту копию тягать. А вот для субпометки для зоны захвата копии нужен полноценный виджет, здесь эти вопросы как раз решаются: 
```python
def init_transform_widget(self):
    ...
    ...
    if se.type in ["copypaste", "zoom_in_region"]:
      if se.choose_default_subelement:
          r = build_valid_rect(se.start_point, se.end_point)
          return TransformWidget(r, center_point_only=False)
      else:
          subelement_rect = self.elementsBuildSubelementRect(se, se.copy_pos)
          points = (subelement_rect.topLeft(), subelement_rect.bottomRight())
          return TransformWidget(points, center_point_only=True)            
    ...
    ...
```

Во время манипуляций с виджетом трансформации нам надо передавать обновлённые позиции в данные элемента (пометки), чтобы пометка, а точнее её субпометки отрисовывались так, как это ожидает пользователь. Поэтому здесь снова возвращаемся к методу `elementsMouseMoveEvent`, но уже к ветке для инструмента **Перемещение** (идентификатор инструмента - `transform`), связанной с виджетом трансформации. Здесь тоже учитываются различия между двумя субпометками при копировании информации:
```python
def elementsMouseMoveEvent(self, event):
    elif tool == "transform":
        if self.transform_widget and self.widget_activated:
            ...
            ...
            elif sel_elem.type in ["copypaste", "zoom_in_region"]:
                if element.choose_default_subelement:
                    sel_elem.start_point = self.transform_widget.pA.point
                    sel_elem.end_point = self.transform_widget.pB.point
                else:
                    sel_elem.copy_pos = self.transform_widget.pCenter.point
            ...
            ...
```

















### Другой вспомогательный код для управления UI

В метод `change_ui_text` надо вносить правки, если в инструменте используется галочка находящаяся между слайдером цвета и слайдером размера, и есть нужда сменить ей название на иное, более подходящее для этого инструмента: 
```python
def change_ui_text(self, new_tool):
    tool = new_tool or self.current_tool
    if tool == "zoom_in_region":
        self.chb_toolbool.setText("Линии")
    else:
        self.chb_toolbool.setText("Подложка")
```
В метод `set_ui_on_toolchange` надо вносить правки, если инструмент использует либо слайдер цвета, слайдер размера/величины и галочку, либо что-то одно, либо вообще ничего. Например, 
- **Затемнению**, **Размытию** и **Картинке** (ранее назывался **Штамп**) не нужен слайдер цвета, а всем остальным он нужен;
- инструменты **Текст** и **Лупа** используют галочку, а другим она не нужна;
- **Копипейсту** не нужны ни слайдер цвета, ни слайдер размера/величины, ни галочка:
```python
def set_ui_on_toolchange(self):
    if self.current_tool in ["blurring", "darkening", "picture"]:
        self.color_slider.setEnabled(False)
    else:
        self.color_slider.setEnabled(True)
    if self.current_tool in ["text", "zoom_in_region"]:
        self.chb_toolbool.setEnabled(True)
    else:
        self.chb_toolbool.setEnabled(False)
    if self.current_tool in ["copypaste"]:
        self.color_slider.setEnabled(False)
        self.size_slider.setEnabled(False)

    self.change_ui_text(None)
    self.parent().update()
```

В методе `tool_data_dict_from_ui` прописываются имена для параметров для каждого инструмента для последующего сохранения в файл настроек, а в `tool_data_dict_to_ui` всё то же самое, только наоборот - прописывается что и откуда надо выставлять в UI. Там же задаются значения по-умолчанию, если какой-то параметра будет не хватать:

```python
def tool_data_dict_from_ui(self):
    if self.current_tool in ["text", "zoom_in_region"]:
        data =  {
            "color_slider_value": self.color_slider.value,
            "size_slider_value": self.size_slider.value,
            "toolbool": self.chb_toolbool.isChecked()
        }
    elif self.current_tool == "picture":
        data =  {
            "size_slider_value": self.size_slider.value,
            "picture_id": self.parent().current_picture_id,
            "picture_angle": self.parent().current_picture_angle,
        }
    else:
        data =  {
            "color_slider_value": self.color_slider.value,
            "size_slider_value": self.size_slider.value,
        }
    return data

def tool_data_dict_to_ui(self, data):
    DEFAULT_COLOR_SLIDER_VALUE = 0.01
    DEFAULT_SIZE_SLIDER_VALUE = 0.4
    DEFAULT_TEXTBACK_VALUE = True
    DEFAULT_PICTURE_ID = self.parent().current_picture_id
    DEFAULT_PICTURE_ANGLE = self.parent().current_picture_angle
    self.color_slider.value = data.get("color_slider_value", DEFAULT_COLOR_SLIDER_VALUE)
    self.size_slider.value = data.get("size_slider_value", DEFAULT_SIZE_SLIDER_VALUE)
    self.chb_toolbool.setChecked(data.get("toolbool", DEFAULT_TEXTBACK_VALUE))
    if self.current_tool == ToolID.picture:
        main_window = self.parent()
        if main_window.current_picture_pixmap is None:
            picture_id = data.get("picture_id", DEFAULT_PICTURE_ID)
            picture_info = PictureInfo.load_from_id(picture_id)
            if picture_info:
                picture_info.load_from_file()
                main_window.current_picture_pixmap = picture_info.pixmap
                main_window.current_picture_id = picture_info.id
                main_window.current_picture_angle = data.get("picture_angle", DEFAULT_PICTURE_ANGLE)
                self.on_parameters_changed()
            else:
                main_window.current_picture_pixmap = None
                main_window.current_picture_id = None
                main_window.current_picture_angle = 0
    self.update()
```

`elementsMakeSureTheresNoUnfinishedElement` была создана для предотвращения багов, но потом её вытеснило условие в `eventFilter`, которое блокирует нажатие на кнопки панели инструментов до тех пор, пока не будет завершён двуэтапный ввод данных для инструментов **Лупа** и **Копипейст**. 
```python
def elementsMakeSureTheresNoUnfinishedElement(self):
    el = self.elementsGetLastElement()
    if el and el.type in ["zoom_in_region", "copypaste"] and not el.finished:
        self.elements.remove(el)

def eventFilter(self, obj, event):
    parent = self.parent()
    blocking = parent.elementsIsSpecialCase(parent.elementsGetLastElement())
    if obj.parent() == self and blocking and not isinstance(event, (QPaintEvent, QKeyEvent)):
        return True
    return False
```

### That's all, folks!

Если в процессе создания вашего инструмента и его отлаживания что-то навернётся, то всегда можно будет почитать об этом подробнее в файле `crash.log`, который будет лежать рядом с `launcher.pyw`, если вы работаете в режиме дебага. С его содержимым можно быстро ознакомиться в приложениях типа Github Desktop, если в папке есть git-репозиторий и эта папка с приложением добавлена в GitHub Desktop.

Читайте внимательно исходники и задавайте вопросы, если что непонятно.

# И на этом, пожалуй, у меня всё!
