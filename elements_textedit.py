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

from PyQt5.QtWidgets import (QApplication,)
from PyQt5.QtCore import (QPoint, QPointF, QRect, Qt, QRectF)
from PyQt5.QtGui import (QPainterPath, QColor, QBrush, QPixmap, QPainter, QTransform, QFont,
                    QTextDocument, QAbstractTextDocumentLayout, QPalette, QTextCursor, QTextLine)

from _utils import (check_scancode_for,)


def elementsTextElementRecalculateGabarit_______________Old(self, element):
    # обновление габаритов виджета трансформации
    s = element.text_doc.size()
    width = s.width()
    height = s.height()
    content_rect = QRectF(QPointF(0, 0), s)
    content_rect.moveCenter(element.position)
    element.start_point = content_rect.topLeft()
    element.end_point = content_rect.bottomRight()
    element.scale_x = 1.0
    element.scale_y = 1.0
    element.calc_local_data()


class ElementsTextEditElementMixin():

    # keep in sync with IMAGE VIEWER: BOARDS
    # https://github.com/sergkrumas/image_viewer

    def elementsTextElementInitModule(self):
        """
            extern method
        """
        self.blinkingCursorTimer = QTimer()
        self.blinkingCursorTimer.setInterval(600)
        self.blinkingCursorTimer.timeout.connect(self.elementsTextElementCursorBlinkingCycleHandler)
        self.blinkingCursorTimer.start()
        self.blinkingCursorHidden = False

        self.board_ni_text_cursor = None
        self.board_ni_selection_rects = []
        self.board_ni_colors_buttons = None
        self.board_ni_inside_op_ongoing = False
        self.board_ni_ts_dragNdrop_ongoing = False
        self.board_ni_ts_dragNdrop_cancelled = False
        self.board_ni_temp_cursor_pos = 0
        self.board_ni_temp_start_cursor_pos = None

    def elementsTextElementLoadCursors(self, cursors_folderpath):
        """
            extern method
        """
        filepath_arrow_png = os.path.join(cursors_folderpath, "arrow.png")

        arrow_rastr_source = QPixmap(filepath_arrow_png)

        if not arrow_rastr_source.isNull():
            SIZE = 30
            arrow_rastr_source = arrow_rastr_source.scaled(SIZE, SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            def draw_sub_icon(text, bold=False):
                source = arrow_rastr_source
                SIGN_HEIGHT = 11
                out_pix = QPixmap(source.width(), source.height()+SIGN_HEIGHT)
                out_pix.fill(Qt.transparent)
                p = QPainter()
                p.begin(out_pix)
                p.drawPixmap(QPoint(0, 0), source)
                alignment = Qt.AlignRight | Qt.AlignTop
                font = p.font()
                if bold:
                    font.setWeight(1900)
                font.setPixelSize(SIGN_HEIGHT)
                p.setFont(font)
                text_rect = p.boundingRect(QRect(), alignment, text)
                text_rect.setWidth(text_rect.width()+5)
                text_rect.moveBottomRight(QPoint(out_pix.rect().width(), out_pix.rect().height()))
                p.setBrush(QBrush(Qt.white))
                p.setPen(QPen(Qt.black))
                p.drawRect(text_rect)
                p.drawText(text_rect, Qt.AlignHCenter | Qt.AlignVCenter, text)
                p.end()
                return out_pix
            self.arrow_move_cursor = QCursor(draw_sub_icon("➜"))
            self.arrow_copy_cursor = QCursor(draw_sub_icon("+", bold=True))

    def elementsTextElementCursorSetterNeeded(self):
        """
            extern method
        """
        return self.board_ni_ts_dragNdrop_ongoing

    def elementsTextElementCursorSetter(self):
        """
            extern method
        """
        if self.board_ni_ts_dragNdrop_cancelled:
            return Qt.ArrowCursor
        else:
            modifiers = QApplication.queryKeyboardModifiers()
            if bool(modifiers & Qt.ControlModifier):
                return self.arrow_copy_cursor
            elif modifiers == Qt.NoModifier:
                return self.arrow_move_cursor

    def elementsTextElementResetColorsButtons(self):
        """
            extern method
        """
        self.board_ni_colors_buttons = None

    def elementsTextElementTextSelectionDragNDropOngoing(self):
        """
            extern method
        """
        return self.board_ni_ts_dragNdrop_ongoing and not self.board_ni_ts_dragNdrop_cancelled

    def elementsTextElementCancelTextSelectionDragNDrop(self):
        """
            extern method
        """
        self.board_ni_ts_dragNdrop_cancelled = True

        # 
        # 
        # 
        # здесь нужно вызывать функцию задания курсора,
        # если она потребуется
        # 
        # 
        # 

    def elementsTextElementCursorBlinkingCycleHandler(self):
        ae = self.active_element
        if ae is not None and ae.oxxxy_type == self.ToolID.text:
            self.blinkingCursorHidden = not self.blinkingCursorHidden
            self.update()


    def elementsTextElementDeactivateEditMode(self):
        """
            extern method
        """
        if self.elementsTextElementIsActiveElement():
            if self.active_element.editing:
                self.active_element.editing = False
                self.board_ni_text_cursor = None
                self.board_ni_selection_rects = []
                # self.active_element = None
                # не нужно вызывать здесь self.board_SetSelected(None),
                # потому что elementsDeactivateTextElement вызывается
                # в начале работы инструмента «выделение и перемещение»
                self.update()
                return True
        return False

    def elementsTextElementActivateEditMode(self, elem):
        """
            extern method
        """
        self.active_element = elem
        self.board_ni_text_cursor = QTextCursor(elem.text_doc)
        self.board_ni_text_cursor.select(QTextCursor.Document)
        elem.editing = True
        self.elementsTextElementDefineSelectionRects()

    def elementsTextElementIsElementActiveElement(self, elem):
        if elem and elem.type == self.ToolID.text:
            return True
        return False

    def elementsTextElementIsActiveElement(self):
        """
            extern method for BOARDS, local method for OXXXY
        """
        return self.elementsTextElementIsElementActiveElement(self.active_element)

    def elementsTextElementGetFontPixelSize(self, elem):
        return int(20+10*elem.size)

    def elementsTextElementCurrentTextLine(self, pos, text_doc):
        cursor = QTextCursor(text_doc)
        cursor.setPosition(pos)

        cursor.movePosition(QTextCursor.StartOfLine)
        lines = 0

        lines_text = cursor.block().text().splitlines()
        lines_pos = 0
        for line_text in lines_text:
            lines_pos += len(line_text) + 1
            if lines_pos > cursor.position() - cursor.block().position():
                break
            lines += 1

        block = cursor.block().previous()
        while block.isValid():
            lines += block.lineCount()
            block = block.previous()
        return lines

    def elementsTextElementKeyPressEventHandler(self, event):
        """
            extern method
        """
        key = event.key()

        if self.elementsTextElementIsInputEvent(event):
            self.elementsTextElementInputEvent(event)
            self.is_board_text_input_event = True
            return True

        if key == Qt.Key_Control:
            # for note item selection drag&drop

            # 
            # 
            # 
            # ЗАМЕНИТЬ ВЫЗОВ
            # 
            # 
            # 
            # 
            # self.board_cursor_setter()
            return False

        return False

    def elementsTextElementInputEvent(self, event):
        ae = self.active_element
        if not (self.elementsTextElementIsActiveElement() and ae.editing):
            return

        if self.board_ni_ts_dragNdrop_ongoing or \
            self.board_ni_ts_dragNdrop_cancelled:
            return

        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        shift = bool(event.modifiers() & Qt.ShiftModifier)

        if ctrl and check_scancode_for(event, "V"):
            text = ""
            app = QApplication.instance()
            cb = app.clipboard()
            mdata = cb.mimeData()
            if mdata and mdata.hasText():
                text = mdata.text()
        else:
            text = event.text()

        _cursor = self.board_ni_text_cursor

        if event.key() in [Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down]:
            if shift:
                move_mode = QTextCursor.KeepAnchor
            else:
                move_mode = QTextCursor.MoveAnchor

            if event.key() == Qt.Key_Left:
                if ctrl:
                    _cursor.movePosition(QTextCursor.PreviousWord, move_mode)
                else:
                    new_pos = max(_cursor.position()-1, 0)
                    _cursor.setPosition(new_pos, move_mode)

            elif event.key() == Qt.Key_Right:
                if ctrl:
                    _cursor.movePosition(QTextCursor.NextWord, move_mode)
                else:
                    new_pos = min(_cursor.position()+1, len(ae.text_doc.toPlainText()))
                    _cursor.setPosition(new_pos, move_mode)

            elif event.key() == Qt.Key_Up:
                if self.elementsTextElementCurrentTextLine(_cursor.position(), ae.text_doc) == 0:
                    _cursor.movePosition(QTextCursor.Start, move_mode)
                _cursor.movePosition(QTextCursor.Up, move_mode)

            elif event.key() == Qt.Key_Down:
                # если строки будут образовываться переносами, то придётся
                # считать общее количество строк по-другому
                lines_count = len(ae.text_doc.toPlainText().split('\n'))
                if self.elementsTextElementCurrentTextLine(_cursor.position(), ae.text_doc) + 1 == lines_count:
                    _cursor.movePosition(QTextCursor.End, move_mode)
                _cursor.movePosition(QTextCursor.Down, move_mode)

            self.blinkingCursorHidden = False

        elif event.key() == Qt.Key_Backspace:
            _cursor.deletePreviousChar()
        elif ctrl and check_scancode_for(event, "Z"):
            if ae.text_doc:
                ae.text_doc.undo()
        elif ctrl and check_scancode_for(event, "Y"):
            if ae.text_doc:
                ae.text_doc.redo()
        else:
            _cursor.beginEditBlock()
            _cursor.insertText(text)
            _cursor.endEditBlock()

        # text_line = self.elementsTextElementCurrentTextLine(_cursor.position(), ae.text_doc)
        # print(f'!> linenum {text_line} ')

        self.elementsTextElementUpdateAfterInput()

    def elementsTextElementUpdateAfterInput(self):
        ae = self.active_element
        ae.plain_text = ae.text_doc.toPlainText()
        if self.Globals.USE_PIXMAP_PROXY_FOR_TEXT_ELEMENTS:
            self.elementsTextElementUpdateProxyPixmap(ae)

        self.elementsTextElementRecalculateGabarit(ae)
        self.elementsTextElementDefineSelectionRects()
        self.update_selection_bouding_box()

        self.update()

    def elementsTextElementInitAfterLoadFromFile(self, elem):
        """
            extern method
        """
        # 
        # 
        # 
        # !!!!!!!!!!!!!!!!!!!!!!!!!!
        # 
        # 
        # 
        # 
        elem.editing = False
        self.elementsImplantTextElement(elem)
        self.elementsTextElementRecalculateGabarit(elem)

    def elementsTextElementRecalculateGabarit(self, element):
        # обновление габаритов виджета трансформации

        s = element.text_doc.size()
        content_rect = QRectF(QPointF(0, 0), s)
        content_rect.moveCenter(element.position)
        element.start_point = content_rect.topLeft()
        element.end_point = content_rect.bottomRight()
        if False:
            element.scale_x = 1.0
            element.scale_y = 1.0
        element.calc_local_data()

    def elementsGetPenFromElement(self, element):
        color = element.font_color
        size = element.size
        PEN_SIZE = 25
        pen = QPen(color, 1+PEN_SIZE*size)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen, color, size

    def elementsTextElementDraw(self, painter, element):

        def tweakedDrawContents(text_document, _painter_, rect):
            # дефолтный drawContents не поддерживает изменение текста
            _painter_.save()
            ctx = QAbstractTextDocumentLayout.PaintContext()
            ctx.palette.setColor(QPalette.Text, _painter_.pen().color())
            # у нас всегда отображается всё, поэтому смысла в этом нет
            # if rect.isValid():
            #     _painter_.setClipRect(rect)
            #     ctx.clip = rect
            text_document.documentLayout().draw(_painter_, ctx)
            _painter_.restore()

        pen, color, size = self.elementsGetPenFromElement(element)
        painter.setPen(pen)
        painter.setBrush(QBrush(color))

        text_doc = element.text_doc
        # рисуем сам текст
        text_opacity = color.alpha()/255
        painter.setOpacity(text_opacity)
        tweakedDrawContents(text_doc, painter, None) # text_doc.drawContents(painter, QRectF())
        painter.setOpacity(1.0)

    def elementsTextElementUpdateProxyPixmap(self, element):
        element.proxy_pixmap = QPixmap(element.text_doc.size().toSize())
        element.proxy_pixmap.fill(Qt.transparent)
        p = QPainter()
        p.begin(element.proxy_pixmap)
        self.elementsTextElementDraw(p, element)
        p.end()

    def elementsTextElementIsInputEvent(self, event):
        ae = self.active_element
        redo_undo = check_scancode_for(event, "Z") or check_scancode_for(event, "Y")
        is_event = self.elementsTextElementIsActiveElement() and ae.editing
        is_event = is_event and event.key() != Qt.Key_Escape
        is_event = is_event and event.key() not in [Qt.Key_Delete, Qt.Key_Insert, Qt.Key_Home, Qt.Key_End, Qt.Key_PageDown, Qt.Key_PageUp]
        is_event = is_event and (bool(event.text()) or (event.key() in [Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down]))
        is_event = is_event and ((not event.modifiers()) or \
                    ((Qt.ShiftModifier | Qt.ControlModifier) & event.modifiers() ) or \
                    (event.modifiers() == Qt.ControlModifier and ( check_scancode_for(event, "V")) or redo_undo ))
        return is_event

    def elementsTextElementAttributesInitOnCreation(self, elem):
        """
            extern method
        """
        # 
        # 
        # 
        # 
        # вставить метод в код создания
        # 
        # 
        # 
        # 
        self.elementsTextElementSetDefaults(elem)
        elem.calc_local_data()
        self.elementsImplantTextElement(elem)
        self.elementsTextElementRecalculateGabarit(elem)
        self.elementsTextElementActivateEditMode(elem)

    def elementsImplantTextElement(self, elem):
        text_doc = QTextDocument()
        elem.text_doc = text_doc
        # elem.text_doc.setDefaultFont(self.Globals.SEVEN_SEGMENT_FONT)
        self.elementsTextElementInit(elem)
        text_doc.setPlainText(elem.plain_text)

    def elementsTextElementSetDefaults(self, elem, plain_text=None):
        if plain_text is None:
            elem.plain_text = 'Note'
        else:
            elem.plain_text = plain_text
        elem.size = 10.0
        elem.margin_value = 5
        elem.proxy_pixmap = None
        elem.editing = False
        elem.font_color = QColor(self.selection_color)
        elem.backplate_color = QColor(0, 0, 0, 0)
        elem.start_point = elem.position
        elem.end_point = elem.position + QPointF(200, 50)

    def elementsTextElementSetFont(self, element):
        font = QFont()
        font_pixel_size = self.elementsTextElementGetFontPixelSize(element)
        font.setPixelSize(font_pixel_size)
        element.text_doc.setDefaultFont(font)











    def elementsTextElementInit(self, elem):
        text_doc = elem.text_doc
        self.elementsTextElementSetFont(elem)
        text_doc.setTextWidth(-1)
        elem.text_doc_cursor_pos = 0

    def elementsTextElementDrawOnCanvas(self, painter, element, final):
        if element.text_doc is not None:
            text_doc = element.text_doc

            size_obj = text_doc.size().toSize()
            height = size_obj.height()
            pos = element.local_end_point - QPointF(0, height)

            s = text_doc.size().toSize()

            # смещение к середине
            offset_x = s.width()/2
            offset_y = s.height()/2
            offset_translation = QTransform()
            offset_translation.translate(-offset_x, -offset_y)

        element_transform = element.get_transform_obj(canvas=self)
        if element.text_doc is not None:
            element_transform = offset_translation * element_transform
        element.draw_transform = element_transform
        painter.setTransform(element_transform)
        painter.save()

        if element.text_doc:
            text_doc = element.text_doc

            # подложка
            if element.toolbool:
                painter.save()
                painter.setPen(Qt.NoPen)
                content_rect = QRect(QPoint(), s)

                path = QPainterPath()
                path.addRoundedRect(QRectF(content_rect), element.margin_value,
                    element.margin_value)
                painter.fillPath(path, QBrush(QColor(200, 200, 200)))
                painter.restore()

            # текст и курсор
            if self.Globals.USE_PIXMAP_PROXY_FOR_TEXT_ELEMENTS:
                if element.proxy_pixmap is None:
                    self.elementsTextElementUpdateProxyPixmap(element)
                painter.drawPixmap(QPoint(0, 0), element.proxy_pixmap)
            else:
                self.elementsTextElementDraw(painter, element)

            # рисуем курсор
            doc_layout = text_doc.documentLayout()
            cursor_pos = element.text_doc_cursor_pos
            block = text_doc.begin()
            end = text_doc.end()
            while block != end:
                # block_rect = doc_layout.blockBoundingRect(block)
                # painter.drawRect(block_rect)
                if self.active_element is element and not final:
                    if block.contains(cursor_pos):
                        local_cursor_pos = cursor_pos - block.position()
                        block.layout().drawCursor(painter, QPointF(0,0), local_cursor_pos, 1)
                block = block.next()

        painter.restore()
        painter.resetTransform()


# для запуска программы прямо из этого файла при разработке и отладке
if __name__ == '__main__':
    import subprocess
    subprocess.Popen([sys.executable, "-u", "oxxxy.py"])
    sys.exit()
