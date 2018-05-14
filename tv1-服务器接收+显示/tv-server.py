#coding: utf-8
import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import socket
import time, json
import threading
import os
from queue import Queue
from datetime import datetime
from PIL import Image, ImageQt
from io import BytesIO, StringIO
from pprint import pprint


class WSHandler(tornado.websocket.WebSocketHandler):
    info = None
    n = 0

    def open(self):
        print('new connection')
        self.opened = 1
        self.write_message('connect success')

    def on_message(self, message):
        print('Client:', message[:30])
        if isinstance(message, bytes):
            _ = message.split(b'<-------->')
            if _[0] == b'screen':
                q_screen.put((_[1], _[2]))

    def on_close(self):
        print('connection closed')
        self.opened = 0


tapp = tornado.web.Application(
    handlers=[
        (r'/ws', WSHandler),
    ],
    template_path=os.path.join(os.path.dirname(__file__), "templates")
)


def qt(q):
    import sys
    from time import sleep
    from PyQt5 import QtWidgets, QtGui, Qt, QtCore
    from PyQt5.QtWidgets import QPushButton

    app = QtWidgets.QApplication(sys.argv)
    w = QtWidgets.QWidget()
    w.setGeometry(640, 100, 800, 500)
    w.setWindowTitle('tv')

    def create_pic(w, x, y):
        def show(label):
            last_img = None
            sleep(3)
            w_width, w_height = None, None
            while 1:
                box, img = q.get()
                box = eval(box.decode())
                img_io = BytesIO(img)
                img = Image.open(img_io)
                if last_img:
                    if not box: continue
                    last_img.paste(img, box)
                else:
                    last_img = img
                print(box)
                imgqt = ImageQt.ImageQt(last_img)
                qimg = QtGui.QImage(imgqt)
                pix = QtGui.QPixmap(qimg)
                
                width, height = int(w.width()), int(w.height())
                if (w_width, w_height) != (width, height):
                    w_width, w_height = width, height
                    l1.setFixedHeight(w_height)
                    l1.setFixedWidth(w_width)
                pix = pix.scaled(w_width, w_height)
                label.setPixmap(pix)

        l1 = QtWidgets.QLabel(w)
        l1.move(x, y)
        l1.show()
        threading._start_new_thread(show, (l1,))

    create_pic(w, 0, 0)

    # 显示窗口
    w.show()
    # 退出整个app
    print(111)
    app.exit(app.exec_())

if __name__ == "__main__":
    q_screen = Queue()
    threading._start_new_thread(qt, (q_screen,))

    http_server = tornado.httpserver.HTTPServer(tapp)
    http_server.listen(9095)
    tornado.ioloop.IOLoop.instance().start()
