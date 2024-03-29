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
import math

from _utils import (build_valid_rectF,)

from PyQt5.QtCore import (Qt, QPointF, QLineF)
from PyQt5.QtGui import (QPen, QColor, QCursor, QVector2D)


class Element2024Mixin():

    def calc_local_data_arrowstree(self):
        self.element_position = self.end_point
        self.element_width = 100
        self.element_height = 100
        self.local_start_point = QPointF(-50, -50)
        self.local_end_point = QPointF(50, 50)

class Elements2024ToolsMixin():

    def init2024Tools(self):
        self.arrows_trees_edges = []

    def elementsDrawArrowsTreeNode(self, painter, element, final):
        if not final:
            painter.setTransform(element.get_transform_obj(canvas=self))

            capture_rect = build_valid_rectF(element.local_start_point, element.local_end_point)
            painter.setBrush(Qt.NoBrush)
            color = QColor(Qt.magenta)
            # color.setAlpha(20)
            painter.setPen(QPen(color, 1))
            painter.drawRect(capture_rect)

            a = QPointF(0, -100)
            b = QPointF(0, 100)
            a1 = QPointF(-20, 35)
            a2 = QPointF(20, 35)
            painter.drawLine(a, b)
            painter.drawLine(a, a+a1)
            painter.drawLine(a, a+a2)

            painter.resetTransform()

    def elementsCreateEdgeWithNearestNode(self, new_element):
        at_ve = self.elementsGetArrowsTrees()
        at_ve.remove(new_element)
        cursor_pos = self.elementsMapToCanvas(QCursor().pos())
        distances = dict()
        if at_ve:
            for el in at_ve:
                distances[el] = QVector2D(cursor_pos-el.element_position).length()
            nearest_element = sorted(at_ve, key=lambda x: distances[x])[0]
            self.elementsAddArrowsTreeEdge(new_element, nearest_element)
            new_element.orient_to_element = nearest_element

    def elementsArrowsTreeNodeOrientToEdgeNeighbor(self, element):
        if hasattr(element, 'orient_to_element'):
            pos1 = element.orient_to_element.element_position
            pos2 = element.element_position
            direction = QVector2D(pos2 - pos1)
            angle_deg = math.degrees(math.atan2(direction.y(), direction.x()))
            element.element_rotation = angle_deg + 90

    def elementsArrowsTreeNodeClearInputData(self, element):
        if hasattr(element, 'orient_to_element'):
            del element.orient_to_element

    def elementsAddArrowsTreeEdge(self, el1, el2):
        self.arrows_trees_edges.append((el1.pass2_unique_index, el2.pass2_unique_index))

    def elementsDrawArrowTrees(self, painter, final):
        els = self.elementsGetArrowsTrees()
        index_elements = {el.pass2_unique_index:el for el in els}
        for node1_index, node2_index in self.arrows_trees_edges:

            node1 = index_elements.get(node1_index, None)
            node2 = index_elements.get(node2_index, None)
            if node1 and node2:
                painter.setPen(QPen(Qt.red, 5))
                a = node1.element_position
                b = node2.element_position
                a = self.elementsMapToViewport(a)
                b = self.elementsMapToViewport(b)
                painter.drawLine(a, b)

        painter.setPen(QPen(Qt.green, 1))

        for el in els:


            neighbors = []

            for node1_index, node2_index in self.arrows_trees_edges:
                node1 = index_elements.get(node1_index, None)
                node2 = index_elements.get(node2_index, None)
                if node1 and node2:
                    if node1 is el:
                        other = node2
                        neighbors.append(other)
                    elif node2 is el:
                        other = node1
                        neighbors.append(other)


            local_directions = []
            for neighbor in neighbors:
                s = QPointF(0, 0)
                e = self.elementsMapToViewport(neighbor.element_position) - self.elementsMapToViewport(el.element_position)
                middle = QLineF(s, e).pointAt(0.5)
                local_directions.append(QLineF(s, middle))

            if not local_directions:
                continue

            node_root_pos = self.elementsMapToViewport(el.element_position)

            angles_per_dir = dict()
            for direction_line in local_directions:
                p2 = direction_line.p2()
                angles_per_dir[id(direction_line)] = math.atan2(p2.y(), p2.x())
            ordered_directions = sorted(local_directions, key=lambda x: angles_per_dir[id(x)])


            # draw node center
            HALF_WIDTH = 10
            ordered_directions.append(ordered_directions[0])
            for n, direction_line in enumerate(ordered_directions[:-1]):

                line_translated = direction_line.translated(node_root_pos)
                dir_end1 = line_translated.p2()

                normal_to_dir1 = direction_line.normalVector()
                vec = -QVector2D(QPointF(normal_to_dir1.p2().x(), normal_to_dir1.p2().y()))
                end_point1 = dir_end1 + (vec.normalized()*HALF_WIDTH).toPointF()


                next_direction_line = ordered_directions[n+1]
                other_line_translated = next_direction_line.translated(node_root_pos)
                dir_end2 = other_line_translated.p2()

                normal_to_dir2 = next_direction_line.normalVector()
                vec = QVector2D(QPointF(normal_to_dir2.p2().x(), normal_to_dir2.p2().y()))
                end_point2 = dir_end2 + (vec.normalized()*HALF_WIDTH).toPointF()


                ray1 = line_translated.translated(end_point1 - dir_end1)
                ray2 = other_line_translated.translated(end_point2 - dir_end2)

                i = ray1.intersects(ray2)
                if i[0] != QLineF.NoIntersection:
                    cross_point = i[1]
                    painter.drawLine(end_point1, cross_point)
                    painter.drawLine(cross_point, end_point2)
                else:
                    painter.drawLine(end_point1, end_point2)

    def elementsGetArrowsTrees(self):
        all_visible_elements = self.elementsFilter()
        at_ve = [e for e in all_visible_elements if e.type == self.ToolID.arrowstree]
        return at_ve

    def elementsDrawArrowTreesTech(self, painter):
        at_ve = self.elementsGetArrowsTrees()
        for element in at_ve:
            self.elementsDrawArrowsTreeNode(painter, element, False)

# для запуска программы прямо из этого файла при разработке и отладке
if __name__ == '__main__':
    import subprocess
    subprocess.Popen([sys.executable, "-u", "oxxxy.py"])
    sys.exit()
