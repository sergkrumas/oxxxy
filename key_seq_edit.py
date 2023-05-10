import sys


from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

class KeySequenceEdit(QLineEdit):

    def __init__(self, keySequence, defaultKeySequence, callback, *args):
        super(KeySequenceEdit, self).__init__(*args)
        self.setText(keySequence)
        self.defaultKeySequence = defaultKeySequence
        self.npressed = 0
        self.callback = callback
        self.keys = set()

    def keyPressEvent(self, event):
        self.keyPressEvent_handler(event)

    def keyReleaseEvent(self, event):
        self.keyReleaseEvent_handler(event)

    def keyPressEvent_handler(self, event):

        key = event.key()

        if key == Qt.Key_Backspace:
            self.setText(self.defaultKeySequence)
            return

        self.npressed += 1

        if key == Qt.Key_unknown:
            print("Unknown key from a macro probably", flush=True)
            return

        # the user have clicked just and only the special keys
        # Ctrl, Shift, Alt, Meta.
        if (key == Qt.Key_Control or
            key == Qt.Key_Shift or
            key == Qt.Key_Alt or
            key == Qt.Key_Meta):
            return

        modifiers = event.modifiers()
        if modifiers & Qt.ShiftModifier:
            key += Qt.SHIFT
        if modifiers & Qt.ControlModifier:
            key += Qt.CTRL
        if modifiers & Qt.AltModifier:
            key += Qt.ALT
        if modifiers & Qt.MetaModifier:
            key += Qt.META
        self.keys.add(key)

    def keyReleaseEvent_handler(self, event):

        self.npressed -= 1

        if self.npressed <= 0:# or Qt.Key_Print in self.keys:
            pt = QKeySequence.PortableText
            keySequence = QKeySequence(*self.keys)
            key_set_str = keySequence.toString(pt)
            if key_set_str.strip():
                self.setText(key_set_str)
            else:
                self.setText(self.defaultKeySequence)
            if self.callback:
                self.callback(self.text())
            self.keys = set()
            self.npressed = 0

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = KeySequenceEdit('Ctrl+C', 'Ctrl+M', lambda: True,)
    w.show()
    sys.exit(app.exec_())
