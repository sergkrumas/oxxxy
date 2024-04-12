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

from collections import namedtuple
from enum import Enum
import datetime
import sys
import os
import subprocess
import time
import ctypes
import itertools
import traceback
import locale
import argparse
import importlib.util
import math

import pyperclip
from pynput import keyboard


from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *



import lorem



# QTextLine currentTextLine(const QTextCursor &cursor)
# {
#     const QTextBlock block = cursor.block();
#     if (!block.isValid())
#         return QTextLine();

#     const QTextLayout *layout = block.layout();
#     if (!layout)
#         return QTextLine();

#     const int relativePos = cursor.position() - block.position();
#     return layout->lineForTextPosition(relativePos);
# }


class QMyWidget(QWidget):

    def paintEvent(self, event):


        painter = QPainter()
        painter.begin(self)

        # painter.fillRect(self.rect(), QColor(200, 50, 50, 125))

        self.doc.drawContents(painter, QRectF(self.rect()))

        for rect in self.rects:
            painter.drawRect(rect)

        block = self.doc.begin()
        end = self.doc.end()


        while block != end:
            if block.contains(self.result):
                cursor_pos = self.result - block.position()
                block.layout().drawCursor(painter, QPointF(0,0), cursor_pos, 4)
            block = block.next()



        l = len(self.note_item_selection_rect)
        for n, r in enumerate(self.note_item_selection_rect):
            painter.fillRect(r, QColor(200, 50, 50, max(35, int(255*n/l) ) ))
            # painter.fillRect(r, QColor(0.9, 0.15, 0.15, n/l))

        painter.end()

    def mousePressEvent(self, event):


        if event.button() == Qt.LeftButton:

            self.result = self.doc.documentLayout().hitTest(event.pos(), Qt.FuzzyHit)

            # print(self.result)
            # self.doc.setTextWidth(event.x())

            # self.get_info()
            self.update()
            self.text_cursor.setPosition(self.result)


        else:
            self.cursor = QTextCursor(self.doc)
            self.text_cursor.beginEditBlock()
            self.text_cursor.insertText("Hello")
            # self.text_cursor.insertText("World")
            self.text_cursor.endEditBlock()

            self.update()


        # !!!!!!!!!!!! DOCUMENT SIZE!!!!!!!!!
        # print(self.doc.size().toSize())

    def mouseMoveEvent(self, event):
        self.mouse_move(event)

    def mouseReleaseEvent(self, event):
        self.mouse_move(event)

    def mouse_move(self, event):
        self.result = self.doc.documentLayout().hitTest(event.pos(), Qt.FuzzyHit)
        self.text_cursor.setPosition(self.result, QTextCursor.KeepAnchor)

        print('s end', self.text_cursor.selectionEnd(), '\ns start', self.text_cursor.selectionStart())
        print(self.text_cursor.position(), self.text_cursor.anchor())

        print('selected text:', self.text_cursor.selectedText())

        self.get_info()

        self.update()


    def __init__(self, ):
        super().__init__()

        self.result = 0

        self.cursor_pos = 0

        text = "text " + "text\n "
        # text = "\n\n"
        text = lorem.text().replace("\n\n", "\n - ")

        text = lorem.text().replace("\n\n", "\n")
        text = lorem.sentence() + '\n' + lorem.sentence() + '\n' + lorem.sentence()
        self.font = font = QFont('Arial')
        # self.textLayout = QTextLayout(text, font)
        self.doc = QTextDocument()

        # margin надо задавать до задания текста, иначе прямоугольники будут неправильными
        self.doc.setDocumentMargin(30)

        self.doc.setDefaultFont(font)
        # self.plain_layout = QPlainTextDocumentLayout(self.doc)
        # self.plain_layout = QTextLayout(text, font)
        # self.doc.setDocumentLayout(self.plain_layout)
        self.doc.setPlainText(text)
        # print(self.textLayout.documentSize())

        self.doc.setTextWidth(200)

        self.text_cursor = QTextCursor(self.doc)
        self.text_cursor.setPosition(5)
        self.text_cursor.setPosition(1, QTextCursor.KeepAnchor)
        # self.text_cursor.setPosition(5)
        # self.text_cursor.beginEditBlock()
        # self.text_cursor.insertText("Hello")
        # self.text_cursor.insertText("World")
        # self.text_cursor.select(QTextCursor.WordUnderCursor)


        # self.text_cursor.endEditBlock()
        # print('a',  len(self.doc.toPlainText()))

        # block = self.doc.begin()
        # print(dir(block))
        # print(block.position(), block.text(), block.length(), len(block.text()), block.isValid())

        self.rects = []
        self.get_info()




    def get_info(self):

        block = self.doc.begin()
        end = self.doc.end()
        docLayout = self.doc.documentLayout()

        self.rects.clear()


#         while block != end:
#             # if not block.text():
#             #     continue

#             blockRect = docLayout.blockBoundingRect(block)
#             # print(type(block))
#             self.rects.append(blockRect)
#             # print(blockRect, block.position(), block.lineCount(),)

#             # if  block.lineCount() != 3:
#             #     block.setLineCount(3)
#             # for i in range(block.lineCount()):

#             # !!!!!
#             # !!!!! https://doc.qt.io/qt-5/qtextblock.html
#             # !!!!! Note that the returned QTextLayout object can only be modified from the documentChanged implementation of a QAbstractTextDocumentLayout subclass. Any changes applied from the outside cause undefined behavior.
#             # !!!!!
#             # !!!!!
#             # !!!!!

#             if True:
#                 block.layout().beginLayout()
#                 # line = block.layout().createLine()
#                 # line.setNumColumns(5)
#                 # line.setLineWidth(40)
#                 h = 0
#                 for i in range(10):
#                     line = block.layout().createLine()
#                     line.setNumColumns(5)
#                     # line.setPosition(QPointF(20, 20*i))

#                     line.setPosition(QPointF(0, h))
#                     h += line.height()

#                 line = block.layout().createLine()
#                 # line.setNumColumns(5)
#                 line.setPosition(QPointF(20, 20*(i+1)))

#                     # print(dir(line))
#                 block.layout().endLayout()
# #
#              # dir(block)) #dir(block))
#             block = block.next()

        block = self.doc.begin()

        # return

        self.note_item_selection_rect = []

        if self.text_cursor.anchor() != self.text_cursor.position():
            while block != end:
                if not block.text():
                    block = block.next()
                    continue

                blockRect = docLayout.blockBoundingRect(block)
                blockX = blockRect.x()
                blockY = blockRect.y()

                it = block.begin()
                while not it.atEnd():
                    fragment = it.fragment()

                    blockLayout = block.layout()
                    fragPos = fragment.position() - block.position()
                    fragEnd = fragPos + fragment.length()


                    start_frg = fragment.contains(self.text_cursor.selectionStart())
                    end_frg = fragment.contains(self.text_cursor.selectionEnd())
                    middle_frg = fragment.position() > self.text_cursor.selectionStart() and fragment.position() + fragment.length() <= self.text_cursor.selectionEnd()

                    if start_frg or end_frg or middle_frg:
                        if start_frg:
                            fragPos = self.text_cursor.selectionStart() - block.position()
                        if end_frg:
                            fragEnd = self.text_cursor.selectionEnd() - block.position()

                        while True:
                            line = blockLayout.lineForTextPosition(fragPos)
                            if line.isValid():
                                x, _ = line.cursorToX(fragPos)
                                right, lineEnd = line.cursorToX(fragEnd)
                                rect = QRectF(blockX + x, blockY + line.y(), right - x, line.height())
                                self.note_item_selection_rect.append(rect)
                                if lineEnd != fragEnd:
                                    fragPos = lineEnd
                                else:
                                    break
                            else:
                                break
                    it += 1
                block = block.next()





        self.margin = 10
        self.radius = min(self.width()/2.0, self.height()/2.0) - self.margin
        fm = QFontMetrics(self.font)
        lineHeight = fm.height()
        y = 0

        # self.text_edit = QTextEdit(self)
        # self.text_edit.resize(500, 500)

        # self.text_edit.setDocument(self.doc)


if __name__ == '__main__':

    app = QApplication(sys.argv)

    widget = QMyWidget()
    widget.show()

    app.exec()

    sys.exit()


