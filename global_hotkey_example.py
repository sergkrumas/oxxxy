#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sample PyQt5 app to demonstrate keybinder capabilities."""

import sys

from PyQt5 import QtWidgets
from PyQt5.QtCore import QAbstractNativeEventFilter, QAbstractEventDispatcher

from pyqtkeybind import keybinder


class WinEventFilter(QAbstractNativeEventFilter):
    def __init__(self, keybinder):
        self.keybinder = keybinder
        super().__init__()

    def nativeEventFilter(self, eventType, message):
        ret = self.keybinder.handler(eventType, message)
        return ret, 0


def main():
    app = QtWidgets.QApplication(sys.argv)

    print("Sample app for pyqtkeybind:")
    print("\tPress Ctrl+Shift+A or Print Screen any where to trigger a callback.")
    print("\tCtrl+Shift+F unregisters and re-registers previous callback.")
    print("\tCtrl+Shift+E exits the app.")

    # Setup a global keyboard shortcut to print "Hello World" on pressing
    # the shortcut
    keybinder.init()


    def callback():
        print("hello world")
        window.show()
        window.activateWindow()
    def callback_1():
        print("special callback")
    def exit_app():
        window.close()
    def unregister():
        keybinder.unregister_hotkey(0, "Shift+Ctrl+A")
        print("unregister and register previous binding")
        keybinder.register_hotkey(0, "Shift+Ctrl+A", callback)

    keybinder.register_hotkey(0, "Shift+Ctrl+A", callback)
    keybinder.register_hotkey(0, "Print Screen", callback)
    keybinder.register_hotkey(0, "Ctrl+Print Screen", callback_1)
    keybinder.register_hotkey(0, "Shift+Ctrl+E", exit_app)
    keybinder.register_hotkey(0, "Shift+Ctrl+F", unregister)

    # Install a native event filter to receive events from the OS
    win_event_filter = WinEventFilter(keybinder)
    event_dispatcher = QAbstractEventDispatcher.instance()
    event_dispatcher.installNativeEventFilter(win_event_filter)
    # window = QtWidgets.QMainWindow()
    # window.show()
    app.exec_()
    keybinder.unregister_hotkey(0, "Shift+Ctrl+A")
    keybinder.unregister_hotkey(0, "Shift+Ctrl+F" )
    keybinder.unregister_hotkey(0, "Shift+Ctrl+E")
    keybinder.unregister_hotkey(0, "Print Screen")


if __name__ == '__main__':
    main()
