

from PyQt5.QtWidgets import (QMenu, QFileDialog, QApplication)
from PyQt5.QtCore import (QPoint, QPointF, QRect, Qt, QSize, QSizeF, QRectF, QFile, QDataStream,
                                                                            QIODevice, QMarginsF)
from PyQt5.QtGui import (QPainterPath, QColor, QBrush, QPixmap, QPainter, QImage, QTransform,
    QPen, QFont, QCursor, QPolygonF, QVector2D, QTextDocument, QAbstractTextDocumentLayout,
                                            QPalette, QTextCursor, QTextLine, QPainterPathStroker)

from _utils import (convex_hull, check_scancode_for, calculate_tangent_points, build_valid_rect,
    build_valid_rectF, get_nearest_point_on_rect, capture_rotated_rect_from_pixmap, squarize_rect,
    fit_rect_into_rect, constraint45Degree, get_bounding_pointsF, load_svg, is_webp_file_animated,
                                                                apply_blur_effect, get_rect_corners)




class ElementsTextEditElementMixin():

    def elementsDeactivateTextElements(self):
        for element in self.elementsFilter():
            if element.type == self.ToolID.text:
                pass

    def elementsDeactivateTextField(self):
        if self.active_element:
            if self.active_element.type == self.ToolID.text:
                self.active_element = None
                # не нужно вызывать здесь self.elementsSetSelected(None),
                # потому что elementsDeactivateTextField вызывается 
                # в начале работы инструмента «выделение и перемещение»
                self.update()
                return True
        return False

    def elementsTextDocSetParameters(self, elem):
        if elem.text_doc is not None:
            self.elementsTextDocSetFont(elem)

    def elementsGetFontPixelSize(self, elem):
        return int(20+10*elem.size)

    def elementsTextFieldInputEvent(self, event):
        ae = self.active_element
        if ae is None or ae.type != self.ToolID.text:
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

        # text_line = self.currentTextLine(_cursor)
        # print('text_line', text_line.lineNumber())
        ae.plain_text = ae.text_doc.toPlainText()
        if self.Globals.USE_PIXMAP_PROXY_FOR_TEXT_ELEMENTS:
            self.elementsTextDocUpdateProxyPixmap(ae)

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
        content_rect.moveCenter(element.element_position)
        element.start_point = content_rect.topLeft()
        element.end_point = content_rect.bottomRight()
        element.element_scale_x = 1.0
        element.element_scale_y = 1.0
        element.calc_local_data()

    def elementsTextDocDraw(self, painter, element):

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

    def elementsTextDocUpdateProxyPixmap(self, element):
        element.proxy_pixmap = QPixmap(element.text_doc.size().toSize())
        element.proxy_pixmap.fill(Qt.transparent)
        p = QPainter()
        p.begin(element.proxy_pixmap)
        self.elementsTextDocDraw(p, element)
        p.end()

    def currentTextLine(self, cursor):
        block = cursor.block()
        if not block.isValid():
            return QTextLine()

        layout = block.layout()
        if not layout:
            return QTextLine()

        relativePos = cursor.position() - block.position()
        return layout.lineForTextPosition(relativePos)

    def elementsIsTextFieldInputEvent(self, event):
        is_event = self.active_element is not None and self.active_element.type == self.ToolID.text
        is_event = is_event and event.key() != Qt.Key_Escape
        is_event = is_event and event.key() not in [Qt.Key_Delete, Qt.Key_Insert, Qt.Key_Home, Qt.Key_End, Qt.Key_PageDown, Qt.Key_PageUp]
        is_event = is_event and (bool(event.text()) or (event.key() in [Qt.Key_Left, Qt.Key_Right]))
        is_event = is_event and ((not event.modifiers()) or \
                    (Qt.ShiftModifier == event.modifiers()) or \
                    (event.modifiers() == Qt.ControlModifier and check_scancode_for(event, "V")))
        return is_event

    def elementsCreateTextDoc(self, elem):
        text_doc = QTextDocument()
        elem.text_doc = text_doc
        # elem.text_doc.setDefaultFont(self.Globals.SEVEN_SEGMENT_FONT)
        text_doc.setPlainText(elem.plain_text)
        self.elementsTextDocInit(elem)

    def elementsTextDocSetFont(self, element):
        font = QFont()
        font_pixel_size = self.elementsGetFontPixelSize(element)
        font.setPixelSize(font_pixel_size)
        element.text_doc.setDefaultFont(font)

    def elementsTextDocSetCursorPosByClick(self, event):
        ae = self.active_element
        if ae.draw_transform is not None:
            viewport_cursor_pos = event.pos()
            inv, ok = ae.draw_transform.inverted()
            if ok:
                pos = inv.map(viewport_cursor_pos)
                text_cursor_pos = ae.text_doc.documentLayout().hitTest(pos, Qt.FuzzyHit)
                ae.text_doc_cursor_pos = text_cursor_pos

    def elementsTextDocInit(self, elem):
        text_doc = elem.text_doc
        self.elementsTextDocSetFont(elem)
        text_doc.setTextWidth(-1)
        elem.text_doc_cursor_pos = 0
