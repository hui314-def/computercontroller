import socket, threading, time, json, sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QMessageBox, QLineEdit, QHBoxLayout
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt

class Receiver(QWidget):
    def __init__(self, main_win):
        super().__init__()
        self.camera = Camera(self) # 摄像头窗口
        self.win_key_pressed = False  # 跟踪Win键状态
        self.main_win = main_win # 主窗口
        self.setWindowTitle("屏幕截图")
        self.setGeometry(0, 0, 2560, 1440)
        self.run = True
        self.client_1 = None; self.client_2 = None;self.client_3 = None; self.client_4 = None; # 控制流，图片流，鼠标流，摄像头流
        self.ip = '172.26.201.76' #192.168.3.191
        self.lay = QVBoxLayout()
        self.lab = QLabel("等待图片...")
        self.lay.addWidget(self.lab)
        self.setLayout(self.lay)
        self.t = threading.Thread(target=self.print_picture)
        self.screen_size = None # 获取服务器屏幕大小
        self.once = True # 第一次运行获取屏幕大小，之后不用重新获取
    
    def connect(self):#连接主机ip地址和端口
        self.ip = self.main_win.insert.text().strip()
        if self.client_1 == None and self.client_2 == None:
            try:
                self.client_1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_1.connect((self.ip, 12345))
                self.client_2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_2.connect((self.ip, 6666))
                self.client_3 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_3.connect((self.ip, 8888))
                self.client_4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_4.connect((self.ip, 10086))
                QMessageBox.information(self, "提示", "连接成功，控制流和图片流、鼠标流、摄像头流均已连接")
                self.main_win.button_2.setText('重新连接')
            except Exception as e:
                QMessageBox.critical(self, "错误", f"连接失败: {e}")
                self.client_1 = None; self.client_2 = None;self.client_3 = None; self.client_4 = None
        else:
            try:
                self.close()
                self.client_1.close();self.client_2.close();self.client_3.close();self.client_4.close()
                self.client_1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_1.connect((self.ip, 12345))
                self.client_2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_2.connect((self.ip, 6666))
                self.client_3 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_3.connect((self.ip, 8888))
                self.client_4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_4.connect((self.ip, 10086))
                QMessageBox.information(self, "提示", "重连成功")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"重连失败: {e}")
                self.client_1 = None; self.client_2 = None;self.client_3 = None; self.client_4 = None

    def print_picture(self):# 打印图片流
        if self.once:
            data_size, _ = self.receive_picture()
            self.screen_size = json.loads(data_size.decode('utf-8'))
            self.once = False
        while self.run:
            a=time.time()
            img_data, length = self.receive_picture()
            pixmap = QPixmap(QImage.fromData(img_data)).scaled(self.screen_size[0], self.screen_size[1], Qt.KeepAspectRatio)
            self.lab.setPixmap(pixmap)
            b=time.time()
            print(f"\r平均传输速率：{length/(b-a)/1024/1024:.2f}MB/s",end='')

    def receive_picture(self):# 接收图片流
        length_data = self.client_2.recv(4)
        if not length_data:
            raise ValueError("未接收到长度信息")
        length = int.from_bytes(length_data, byteorder='big')
        # 根据长度接收数据
        response = b''
        received = 0
        while received < length:
            chunk = self.client_2.recv(min(1024, length - received))
            if not chunk:
                break
            response += chunk
            received += len(chunk)
        return response,length

    def send_mouse_event(self, event_data):
        """发送鼠标事件到服务器"""
        if not self.client_3:
            return
        try:
            json_data = json.dumps(event_data)
            length = len(json_data)
            length_bytes = length.to_bytes(4, byteorder='big')
            self.client_3.sendall(length_bytes)
            self.client_3.sendall(json_data.encode('utf-8'))
        except Exception as e:
            print("发送鼠标事件失败:", e)

    def mousePressEvent(self, event):
        """处理鼠标按下事件"""
        if not self.client_3:
            return
            
        # 计算在服务器屏幕上的坐标
        x, y = self.calculate_server_coordinates(event.x(), event.y())
        button = ""
        if event.button() == Qt.LeftButton:
            button = "left"
        elif event.button() == Qt.RightButton:
            button = "right"
        elif event.button() == Qt.MiddleButton:
            button = "middle"
            
        mouse_data = {
            "type": "press",
            "x": x,
            "y": y,
            "button": button
        }
        
        self.send_mouse_event(mouse_data)
        self.last_x = x
        self.last_y = y
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件"""
        if not self.client_3:
            return
            
        # 计算在服务器屏幕上的坐标
        x, y = self.calculate_server_coordinates(event.x(), event.y())
        
        button = ""
        if event.button() == Qt.LeftButton:
            button = "left"
        elif event.button() == Qt.RightButton:
            button = "right"
        elif event.button() == Qt.MiddleButton:
            button = "middle"
            
        mouse_data = {
            "type": "release",
            "x": x,
            "y": y,
            "button": button
        }
        
        self.send_mouse_event(mouse_data)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """处理鼠标滚轮事件"""
        if not self.client_3:
            return
            
        scroll = event.angleDelta().y()  # 标准化滚动值
        
        mouse_data = {
            "type": "scroll",
            "scroll": scroll
        }
        
        self.send_mouse_event(mouse_data)
        super().wheelEvent(event)

    def calculate_server_coordinates(self, client_x, client_y):
        """计算客户端坐标对应的服务器坐标"""
        if not self.screen_size or not self.lab.pixmap():
            return client_x, client_y
            
        # 获取QLabel的尺寸和图片的尺寸
        label_width = self.lab.width()
        label_height = self.lab.height()
        pixmap_width = self.lab.pixmap().width()
        pixmap_height = self.lab.pixmap().height()
        
        # 计算图片在QLabel中的偏移量（居中显示）
        x_offset = (label_width - pixmap_width) / 2
        y_offset = (label_height - pixmap_height) / 2
        
        # 如果点击位置不在图片区域内，返回上次的有效坐标
        if (client_x < x_offset or client_x > x_offset + pixmap_width or
            client_y < y_offset or client_y > y_offset + pixmap_height):
            return self.last_x, self.last_y
        
        # 计算在图片上的相对位置
        rel_x = client_x - x_offset
        rel_y = client_y - y_offset
        
        # 计算在服务器屏幕上的坐标
        server_x = int(rel_x * self.screen_size[0] / pixmap_width)
        server_y = int(rel_y * self.screen_size[1] / pixmap_height)
        
        return server_x, server_y

    def keyPressEvent(self, a0):
        key = a0.key()
        text = a0.text()
        # 获取修饰键状态
        modifiers = a0.modifiers()
        modifier_text = []
        
        if modifiers == Qt.ShiftModifier:
            modifier_text.append("Shift")
        if modifiers == Qt.ControlModifier:
            modifier_text.append("Ctrl")
        if modifiers == Qt.AltModifier:
            modifier_text.append("Alt")
        if self.win_key_pressed:
            modifier_text.append("win")
        modifier_str = "+".join(modifier_text) if modifier_text else "" # 热键处理

        # 对于控制字符，我们需要特殊处理
        key_data = {
            "type": "key_press",
            "key_code": key,
            "key_char": text,
            "modifiers": modifier_str,
            "key_name": str(key)
        }# 发送按键事件到服务端
        try:
            json_data = json.dumps(key_data) # 将数据转换为JSON格式并发送
            length=len(json_data)
            length=length.to_bytes(4, byteorder='big')
            self.client_1.sendall(length)
            self.client_1.sendall(json_data.encode('utf-8'))
        except Exception as e:
            print("发送按键事件失败:", e)
        return super().keyPressEvent(a0)

    def keyReleaseEvent(self, a0):# 处理键盘释放事件
        key = a0.key()
        text = a0.text()
        # 获取修饰键状态
        modifiers = a0.modifiers()
        modifier_text = []
        if modifiers & Qt.ShiftModifier:
            modifier_text.append("Shift")
        if modifiers & Qt.ControlModifier:
            modifier_text.append("Ctrl")
        if modifiers & Qt.AltModifier:
            modifier_text.append("Alt")
        if self.win_key_pressed:
            modifier_text.append("win")
        modifier_str = "+".join(modifier_text) if modifier_text else ""
        key_data = {
            "type": "key_release",
            "key_code": key,
            "key_char": text,
            "modifiers": modifier_str,
            "key_name": self.get_key_name(key)
        }
        try:
            json_data = json.dumps(key_data)
            length = len(json_data)
            length_bytes = length.to_bytes(4, byteorder='big')
            self.client_1.sendall(length_bytes)  # 发送到服务器
            self.client_1.sendall(json_data.encode('utf-8'))
        except Exception as e:
            print("发送按键事件失败:", e)
        super().keyReleaseEvent(a0)

    def get_key_name(self, key):# 将键码转换为可读的名称
        return Qt.Key(key).name.decode('utf-8') if hasattr(Qt.Key(key), 'name') else str(key)

    def closeEvent(self, event):# 重写关闭事件
        self.run = False
        self.t = threading.Thread(target=self.print_picture)
        if hasattr(self, 'main_win') and self.main_win:
            self.main_win.button.setText("启动屏幕截图")
        super().closeEvent(event)

    def __del__(self):# 重写析构函数
        self.run = False
        if self.client_1:
            self.client_1.close()
        if self.client_2:
            self.client_2.close()
        if self.client_3:
            self.client_3.close()
        if self.client_4:
            self.client_4.close()

class Main_Win(QWidget):
    def __init__(self):
        super().__init__()
        self.win = Receiver(self)
        self.setWindowTitle("控制台")
        self.setGeometry(800, 400, 320, 150)
        self.setWindowFlag(Qt.WindowStaysOnTopHint) # 窗口置顶
        lay = QVBoxLayout()
        lay_2 = QHBoxLayout()
        label = QLabel('服务端ip地址：')
        lay_2.addWidget(label)
        self.insert = QLineEdit()
        self.insert.setPlaceholderText("请输入服务器IP地址")
        self.insert.setText(self.win.ip)
        lay_2.addWidget(self.insert)
        lay.addLayout(lay_2)
        button_layout = QHBoxLayout()
        self.button_2 = QPushButton("连接")
        button_layout.addWidget(self.button_2)
        self.button_2.clicked.connect(self.win.connect)
        self.win_key_button = QPushButton("Win键: 关闭") # 添加Win键按钮
        self.win_key_button.setCheckable(True) # 设置为可切换状态
        self.win_key_button.clicked.connect(self.toggle_win_key)
        button_layout.addWidget(self.win_key_button)
        lay.addLayout(button_layout)
        self.button = QPushButton("启动屏幕截图")
        lay.addWidget(self.button)
        self.button.clicked.connect(self.set_btn_1)
        self.button_4 = QPushButton("全屏显示")
        self.button_4.clicked.connect(self.full_screen)
        self.button_5 = QPushButton("启动摄像头")
        self.button_5.clicked.connect(self.set_btn_2)
        lay_3 = QHBoxLayout()
        lay_3.addWidget(self.button_4)
        lay.addLayout(lay_3)
        lay.addWidget(self.button_5)
        self.setLayout(lay)
        self.show()

    def full_screen(self):
        if self.win.isFullScreen():
            self.win.showNormal()
            self.button_4.setText('全屏显示')
        else:
            self.win.showFullScreen()
            self.button_4.setText('退出全屏')


    def set_btn_1(self):# 按钮设置
        if self.win.client_1 and self.win.client_2:
            if self.button.text()=="启动屏幕截图":
                self.win.run = True
                self.win.t.start()
                self.button.setText("终止屏幕截图")
                self.win.show()
            else:
                self.win.close()
                self.win.run = False
                self.win.t = threading.Thread(target=self.win.print_picture)
                self.button.setText("启动屏幕截图")
        else:
            QMessageBox.critical(self, "错误", "请先连接服务器")

    def set_btn_2(self):# 获取摄像头
        if self.win.client_4:
            if self.button_5.text()=="启动摄像头":
                self.win.camera.run = True
                self.win.camera.t.start()
                self.win.camera.show()
                self.button_5.setText("终止摄像头")
            else:
                self.win.camera.close()
                self.win.camera.run = False
                self.win.camera.t = threading.Thread(target=self.win.camera.show_camera)
                self.button_5.setText("启动摄像头")
        else:
            QMessageBox.critical(self, "错误", "请先连接服务器")

    def toggle_win_key(self):# 切换Win键状态
        if self.win_key_button.isChecked():
            self.win.win_key_pressed = True
            self.win_key_button.setText("Win键: 开启")
            self.win_key_button.setStyleSheet("background-color: lightgreen")
        else:
            self.win.win_key_pressed = False
            self.win_key_button.setText("Win键: 关闭")
            self.win_key_button.setStyleSheet("")  # 恢复默认样式

    def closeEvent(self, event):# 当主窗口关闭时，退出整个应用
        self.win.__del__()
        QApplication.quit()
        super().closeEvent(event)

class Camera(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.win = parent
        self.lab = QLabel("等待摄像头...")
        self.setWindowTitle("摄像头")
        self.setWindowFlags(Qt.Window)
        self.run = False
        lay = QVBoxLayout()
        lay.addWidget(self.lab)
        self.setLayout(lay)
        self.t = threading.Thread(target=self.show_camera)

    def show_camera(self):
        while self.run:
            try:
                length_data = self.win.client_4.recv(4)
                if not length_data:
                    raise ValueError("未接收到长度信息")
                length = int.from_bytes(length_data, byteorder='big')
                response = b''
                received = 0
                while received < length:
                    chunk = self.win.client_4.recv(min(1024, length - received))
                    if not chunk:
                        break
                    response += chunk
                    received += len(chunk)
                pixmap = QPixmap(QImage.fromData(response)).scaled(640, 480, Qt.KeepAspectRatio)
                self.lab.setPixmap(pixmap)
            except Exception as e:
                print("摄像头连接断开:", e)
                self.run = False

    def closeEvent(self, event):
        self.run = False
        if hasattr(self, 't') and self.t.is_alive():
            self.t.join(timeout=1.0)  # 等待线程结束
        if hasattr(self, 'win') and self.win:
            self.win.main_win.button_5.setText("启动摄像头")
        self.t = threading.Thread(target=self.show_camera)
        super().closeEvent(event)

if __name__ == '__main__':
    app=QApplication([])
    client = Main_Win()
    sys.exit(app.exec_())