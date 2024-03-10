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




class QMyWidget(QWidget):

    def paintEvent(self, event):


        painter = QPainter()
        painter.begin(self)

        self.doc.drawContents(painter, QRectF(self.rect()))

        for rect in self.rects:
            painter.drawRect(rect)

        block = self.doc.begin()
        end = self.doc.end()

        while block != end:

            if block.contains(self.result):
                    block.layout().drawCursor(painter, QPointF(0,0), self.result, 4)
 
            block = block.next()


        painter.end()

    def mousePressEvent(self, event):


        if event.button() == Qt.LeftButton:

            self.result = self.doc.documentLayout().hitTest(event.pos(), Qt.FuzzyHit)

            print(self.result)
            self.doc.setTextWidth(event.x())

            self.get_info()
            self.update()

            self.cursor_pos += 1

        else:
            self.cursor = QTextCursor(self.doc)
            self.cursor.setPosition(self.result)
            self.cursor.beginEditBlock()
            self.cursor.insertText("Hello")
            # self.cursor.insertText("World")
            self.cursor.endEditBlock()

            self.update()


    def __init__(self, ):
        super().__init__()
        
        self.result = 0

        self.cursor_pos = 0

        text = "text " + "text\n " * 5
        # text = "\n\n"
        text = lorem.text().replace("\n\n", "\n - ")

        text = lorem.text().replace("\n\n", "\n")
        font = QFont('Arial')
        # self.textLayout = QTextLayout(text, font)
        self.doc = QTextDocument()
        self.doc.setDefaultFont(font)
        # self.plain_layout = QPlainTextDocumentLayout(self.doc)
        # self.plain_layout = QTextLayout(text, font)
        # self.doc.setDocumentLayout(self.plain_layout)
        self.doc.setPlainText(text)
        # print(self.textLayout.documentSize())

        self.doc.setTextWidth(200)

        self.cursor = QTextCursor(self.doc)
        self.cursor.setPosition(0)
        self.cursor.beginEditBlock()
        # self.cursor.insertText("Hello")
        # self.cursor.insertText("World")
        self.cursor.endEditBlock()
        # print('a',  len(self.doc.toPlainText()))

        block = self.doc.begin()
        # print(dir(block))
        print(block.position(), block.text(), block.length(), len(block.text()), block.isValid())

        self.rects = []
        self.get_info()

        self.doc.setDocumentMargin(30)


    def get_info(self):

        block = self.doc.begin()
        end = self.doc.end()
        docLayout = self.doc.documentLayout()

        self.rects.clear()


        while block != end:
            # if not block.text():
            #     continue

            blockRect = docLayout.blockBoundingRect(block)
            # print(type(block))
            self.rects.append(blockRect)
            # print(blockRect, block.position(), block.lineCount(),)

            # if  block.lineCount() != 3:
            #     block.setLineCount(3)
            # for i in range(block.lineCount()):

            # !!!!! 
            # !!!!! https://doc.qt.io/qt-5/qtextblock.html
            # !!!!! Note that the returned QTextLayout object can only be modified from the documentChanged implementation of a QAbstractTextDocumentLayout subclass. Any changes applied from the outside cause undefined behavior.
            # !!!!!
            # !!!!!
            # !!!!!

            if True:
                block.layout().beginLayout()
                # line = block.layout().createLine()
                # line.setNumColumns(5)
                # line.setLineWidth(40)
                h = 0
                for i in range(10):
                    line = block.layout().createLine()
                    line.setNumColumns(5)                    
                    # line.setPosition(QPointF(20, 20*i))

                    line.setPosition(QPointF(0, h))
                    h += line.height()

                line = block.layout().createLine()
                # line.setNumColumns(5)
                line.setPosition(QPointF(20, 20*(i+1)))

                    # print(dir(line))
                block.layout().endLayout()
#
             # dir(block)) #dir(block))
            block = block.next()

        return
        borderRects = []
        lastBorderRects = []
        lastBorder = None
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
                fmt = fragment.charFormat()


                if True:
                    blockLayout = block.layout()
                    fragPos = fragment.position() - block.position()
                    fragEnd = fragPos + fragment.length()
                    while True:
                        line = blockLayout.lineForTextPosition(
                            fragPos)
                        if line.isValid():
                            x, _ = line.cursorToX(fragPos)
                            right, lineEnd = line.cursorToX(fragEnd)
                            print('s', x, right, block, block.text(), fragPos, fragEnd, block.position())
                            rect = QRectF(
                                blockX + x, blockY + line.y(), 
                                right - x, line.height()
                            )
                            lastBorderRects.append(rect)
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
        fm = QFontMetrics(font)
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


