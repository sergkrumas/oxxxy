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
        self.blinkingCursorTimer.timeout.connect(self.board_TextElementCursorBlinkingCycleHandler)
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








    def elementsDeactivateTextElement(self):
        if self.active_element:
            if self.active_element.oxxxy_type == self.ToolID.text:
                self.active_element = None
                # не нужно вызывать здесь self.elementsSetSelected(None),
                # потому что elementsDeactivateTextElement вызывается
                # в начале работы инструмента «выделение и перемещение»
                self.update()
                return True
        return False

    def elementsTextElementGetFontPixelSize(self, elem):
        return int(20+10*elem.size)

    def elementsTextElementInputEvent(self, event):
        ae = self.active_element
        if ae is None or ae.oxxxy_type != self.ToolID.text:
            return

        if event.modifiers() == Qt.ControlModifier and check_scancode_for(event, "V"):
            text = ""
            app = QApplication.instance()
            cb = app.clipboard()
            mdata = cb.mimeData()
            if mdata and mdata.hasText():
                text = mdata.text()
        else:
            text = event.text()

        _cursor = QTextCursor(ae.text_doc)
        _cursor.setPosition(ae.text_doc_cursor_pos)

        if event.key() in [Qt.Key_Left, Qt.Key_Right]:
            if event.key() == Qt.Key_Left:
                ae.text_doc_cursor_pos -= 1
                ae.text_doc_cursor_pos = max(ae.text_doc_cursor_pos, 0)
            elif event.key() == Qt.Key_Right:
                ae.text_doc_cursor_pos += 1
                ae.text_doc_cursor_pos = min(ae.text_doc_cursor_pos, len(ae.text_doc.toPlainText()))
        elif event.key() == Qt.Key_Backspace:
            _cursor.deletePreviousChar()
            ae.text_doc_cursor_pos -= 1
        else:
            _cursor.beginEditBlock()
            _cursor.insertText(text)
            ae.text_doc_cursor_pos += len(text)
            _cursor.endEditBlock()

        ae.plain_text = ae.text_doc.toPlainText()
        if self.Globals.USE_PIXMAP_PROXY_FOR_TEXT_ELEMENTS:
            self.elementsTextElementUpdateProxyPixmap(ae)

        self.elementsTextElementRecalculateGabarit(ae)
        self.update_selection_bouding_box()
        self.elementsFixArrowStartPositionIfNeeded(ae)
        self.update()

    def elementsTextElementRecalculateGabarit(self, element):
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
        tweakedDrawContents(text_doc, painter, None) # text_doc.drawContents(painter, QRectF())

    def elementsTextElementUpdateProxyPixmap(self, element):
        element.proxy_pixmap = QPixmap(element.text_doc.size().toSize())
        element.proxy_pixmap.fill(Qt.transparent)
        p = QPainter()
        p.begin(element.proxy_pixmap)
        self.elementsTextElementDraw(p, element)
        p.end()

    def elementsTextElementCurrentTextLine(self, cursor):
        block = cursor.block()
        if not block.isValid():
            return QTextLine()

        layout = block.layout()
        if not layout:
            return QTextLine()

        relativePos = cursor.position() - block.position()
        return layout.lineForTextPosition(relativePos)

    def elementsTextElementIsInputEvent(self, event):
        is_event = self.active_element is not None and self.active_element.oxxxy_type == self.ToolID.text
        is_event = is_event and event.key() != Qt.Key_Escape
        is_event = is_event and event.key() not in [Qt.Key_Delete, Qt.Key_Insert, Qt.Key_Home, Qt.Key_End, Qt.Key_PageDown, Qt.Key_PageUp]
        is_event = is_event and (bool(event.text()) or (event.key() in [Qt.Key_Left, Qt.Key_Right]))
        is_event = is_event and ((not event.modifiers()) or \
                    (Qt.ShiftModifier == event.modifiers()) or \
                    (event.modifiers() == Qt.ControlModifier and check_scancode_for(event, "V")))
        return is_event

    def elementsImplantTextElement(self, elem):
        text_doc = QTextDocument()
        elem.text_doc = text_doc
        # elem.text_doc.setDefaultFont(self.Globals.SEVEN_SEGMENT_FONT)
        text_doc.setPlainText(elem.plain_text)
        self.elementsTextElementInit(elem)

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
