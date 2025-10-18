import socket, json, threading, platform, mss, cv2, ctypes, sys, time
import pyautogui as pa
from PyQt5.QtCore import Qt
from PIL import ImageDraw,Image
import numpy as np
from threading import Lock

def run_as_admin():# 获取管理员权限
    if ctypes.windll.shell32.IsUserAnAdmin():
        print("已是管理员权限。")
    else:
        print("正在尝试以管理员身份重新运行...")
        params = ' '.join([f'"{arg}"' for arg in sys.argv])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        sys.exit()

class FrameProducer:
    def __init__(self):
        self.screen_lock = Lock()
        self.screen_running = True
        self.camera_lock = Lock()
        self.camera_running = True
        self.latest_screen_frame = None
        self.latest_camera_frame = None
        self.camera_instance = None
        self.data_size = None
        self.get_camera_instance()
        # 启动屏幕捕获线程
        self.screen_thread = threading.Thread(target=self.capture_screen, daemon=True)
        # 启动摄像头捕获线程
        self.camera_thread = threading.Thread(target=self.capture_camera, daemon=True)

    def capture_screen(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            print(f"使用显示器: {monitor}")
            # 发送屏幕尺寸信息
            size = (monitor['width'], monitor['height'])
            self.data_size = json.dumps(size).encode('utf-8')

            prev_frame = None
            while self.screen_running:
                try:
                    # 捕获屏幕截图
                    screenshot = sct.grab(monitor)
                    
                    # 转换为PIL图像
                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                    
                    # 绘制鼠标指针
                    draw = ImageDraw.Draw(img)
                    mouse_x, mouse_y = pa.position()
                    draw.ellipse(
                        [(mouse_x - 8, mouse_y - 8), (mouse_x + 8, mouse_y + 8)],
                        outline="red", width=2
                    )
                    
                    # 转换为OpenCV格式
                    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                    
                    # 差异检测 - 减少不必要的编码
                    if prev_frame is not None:
                        diff = cv2.absdiff(cv_img, prev_frame)
                        non_zero = np.count_nonzero(diff)
                        if non_zero < 1000:  # 变化很小，跳过编码
                            time.sleep(1/30)  # 降低CPU使用率
                            continue
                    
                    prev_frame = cv_img.copy()
                    # 编码为JPEG
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
                    result, encoded_frame = cv2.imencode('.jpg', cv_img, encode_param)
                    if result:
                        with self.screen_lock:
                            self.latest_screen_frame = encoded_frame.tobytes()
                    # 控制帧率
                    time.sleep(1/30)  # 约30fps
                    
                except Exception as e:
                    print(f"屏幕捕获错误: {e}")

    def get_camera_instance(self):# 获取单例摄像头实例
        if self.camera_instance is None:
            self.camera_instance = cv2.VideoCapture(0)
            if not self.camera_instance.isOpened():
                print("无法打开摄像头")
                return None
            # 设置分辨率
            self.camera_instance.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera_instance.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def capture_camera(self):
        """摄像头捕获线程"""
        if self.camera_instance is None:
            return
        
        while self.camera_running and self.camera_instance.isOpened():
            try:
                ret, frame = self.camera_instance.read()
                if not ret:
                    print("无法读取摄像头帧")
                    time.sleep(0.1)
                    continue
                
                # 编码为JPEG
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
                result, encoded_frame = cv2.imencode('.jpg', frame, encode_param)
                
                if result:
                    with self.camera_lock:
                        self.latest_camera_frame = encoded_frame.tobytes()
                
                time.sleep(1/30)  # 30fps
                
            except Exception as e:
                print(f"摄像头捕获错误: {e}")
                time.sleep(0.1)

class Server:
    def __init__(self):
        run_as_admin()
        self.server_1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_1.bind(('0.0.0.0', 12345))#绑定的IP和端口
        self.server_1.listen(3)#监听的最大连接数
        self.server_2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_2.bind(('0.0.0.0', 6666))
        self.server_2.listen(3)
        self.server_3 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_3.bind(('0.0.0.0', 8888))
        self.server_3.listen(3)
        self.server_4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_4.bind(('0.0.0.0', 10086))
        self.server_4.listen(3)
        local_ip = self.get_local_ip()
        self.key_clients = []  # 存储所有键盘控制客户端
        self.mouse_clients = []  # 存储所有鼠标控制客户端
        self.screen_clients = []  # 存储所有屏幕查看客户端
        self.camera_clients = []  # 存储所有摄像头查看客户端
        self.frame_producer = FrameProducer()
        print(f"服务器ip:{local_ip}已启动，等待连接...")

    def get_local_ip(self):#获取本机在局域网中的IP地址
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            return ip
        except:
            return "127.0.0.1"

    def accepting(self):
        # 接受键盘控制客户端
        threading.Thread(target=self.accept_keyboard_clients, daemon=True).start()
        # 鼠标控制
        threading.Thread(target=self.accept_mouse_clients, daemon=True).start()
        # 摄像头查看
        threading.Thread(target=self.accept_camera_clients, daemon=True).start()
        # 屏幕查看
        self.accept_screen_clients()

    def accept_keyboard_clients(self):
        while True:
            client, addr = self.server_1.accept()
            print(f"键盘控制客户端已连接: {addr}")
            self.key_clients.append(client)
            threading.Thread(target=self.handle_key_client, args=(client,)).start()

    def accept_mouse_clients(self):
        while True:
            client, addr = self.server_3.accept()
            print(f"鼠标控制客户端已连接: {addr}")
            self.mouse_clients.append(client)
            threading.Thread(target=self.handle_mouse_client, args=(client,)).start()

    def accept_screen_clients(self):
        self.frame_producer.screen_thread.start()
        while True:
            client, addr = self.server_2.accept()
            print(f"屏幕查看客户端已连接: {addr}")
            self.screen_clients.append(client)
            threading.Thread(target=self.send_picture, args=(client,), daemon=True).start()

    def accept_camera_clients(self):
        self.frame_producer.camera_thread.start()
        while True:
            client, addr = self.server_4.accept()
            print(f"摄像头查看客户端已连接: {addr}")
            self.camera_clients.append(client)
            threading.Thread(target=self.send_camera, args=(client,), daemon=True).start()

    def send_camera(self, client):
        try:
            while self.camera_clients:
                with self.frame_producer.camera_lock:
                    encoded_frame = self.frame_producer.latest_camera_frame
                    if encoded_frame:
                        data_size = len(encoded_frame)
                        client.sendall(data_size.to_bytes(4, byteorder='big'))
                        client.sendall(encoded_frame)
                        time.sleep(1/30)
        except Exception as e:
            print(f"摄像头传输结束: {e}")

    def send_picture(self, client):
        try:
            data_size = self.frame_producer.data_size
            client.sendall(len(data_size).to_bytes(4, byteorder='big'))
            client.sendall(data_size)
            while self.screen_clients:
                with self.frame_producer.screen_lock:
                    encoded_frame = self.frame_producer.latest_screen_frame
                    if encoded_frame:
                        data_size = len(encoded_frame)
                        client.sendall(data_size.to_bytes(4, byteorder='big'))
                        client.sendall(encoded_frame)
                        # 动态调整质量基于网络条件
                        # 这里可以添加网络延迟检测和自适应质量调整逻辑
                        time.sleep(1/30)  # 控制帧率   
        except Exception as e:
            print(f"传输结束: {e}")

    def handle_mouse_client(self, client):# 处理鼠标事件客户端连接
        try:
            while True:
                data = self.receive_mouse_json(client)
                try:
                    mouse_data = json.loads(data.decode('utf-8'))# 解析JSON数据
                    self.process_mouse_event(mouse_data)
                except json.JSONDecodeError:
                    print("接收到无效的鼠标JSON数据")    
        except Exception as e:
            print(f"处理鼠标客户端时出错: {e}")
        finally:
            client.close()
            self.mouse_clients.remove(client)
            print("鼠标客户端连接已关闭")

    def receive_mouse_json(self, client):
        length_data = client.recv(4)
        if not length_data:
            raise ConnectionError("鼠标连接已关闭")
        length = int.from_bytes(length_data, byteorder='big')
        # 根据长度接收数据
        response = b''
        received = 0
        while received < length:
            chunk = client.recv(min(1024, length - received))
            if not chunk:
                break
            response += chunk
            received += len(chunk)
        return response
    
    def process_mouse_event(self, mouse_data):
        """处理鼠标事件"""
        event_type = mouse_data.get("type", "")
        x = mouse_data.get("x", 0)
        y = mouse_data.get("y", 0)
        button = mouse_data.get("button", "")
        scroll = mouse_data.get("scroll", 0)
           
        if event_type == "press":
            print(f"鼠标按下: 按钮={button}, 位置=({x}, {y})")
            if button == "left":
                print('鼠标左键按下')
                pa.mouseDown(x, y, button='left')
            elif button == "right":
                print('鼠标右键按下')
                pa.mouseDown(x, y, button='right')
            elif button == "middle":
                print('鼠标中键按下')
                pa.mouseDown(x, y, button='middle')
                
        elif event_type == "release":
            print(f"鼠标释放: 按钮={button}, 位置=({x}, {y})")
            if button == "left":
                print('鼠标左键抬起')
                pa.mouseUp(x, y, button='left')
            elif button == "right":
                print('鼠标右键抬起')
                pa.mouseUp(x, y, button='right')
            elif button == "middle":
                print('鼠标中键抬起')
                pa.mouseUp(x, y, button='middle')
                
        elif event_type == "scroll":
            print(f"鼠标滚轮: 滚动={scroll}")
            pa.scroll(scroll)

    def handle_key_client(self,client):
        """处理键盘连接"""
        try:
            while True:
                data = self.receive_key_json(client)
                try:
                    key_data = json.loads(data.decode('utf-8'))# 解析JSON数据
                    self.process_key_event(key_data)
                except json.JSONDecodeError:
                    print("接收到无效的JSON数据")    
        except Exception as e:
            print(f"处理客户端键盘连接时出错: {e}")
        finally:
            client.close()
            self.key_clients.remove(client)
            print("客户端连接已关闭")

    def receive_key_json(self, client):
        length_data = client.recv(4)
        if not length_data:
            raise ConnectionError("连接已关闭")
        length = int.from_bytes(length_data, byteorder='big')
        # 根据长度接收数据
        response = b''
        received = 0
        while received < length:
            chunk = client.recv(min(1024, length - received))
            if not chunk:
                break
            response += chunk
            received += len(chunk)
        return response

    def process_key_event(self, key_data):#处理接收到的按键事件
        event_type = key_data.get("type", "")
        key_char = key_data.get("key_char", "")
        modifiers = key_data.get("modifiers", "")
        key_name = key_data.get("key_name", "")
        # 这里可以根据按键事件执行控制操作
        # 例如：控制远程计算机、机器人、智能设备等
        
        if event_type == "key_press":
            print(f"按键按下: {key_name} (字符: '{key_char}', 修饰键: {modifiers})")
            self.press_action(key_data)

        elif event_type == "key_release":
            print(f"按键释放: {key_name}")
            self.release_action(key_data)

    def press_action(self, key_data):# 执行控制操作 - 处理热键和单键
        key_code = key_data.get("key_code", 0)
        modifiers = key_data.get("modifiers", "")
        char = key_data.get("key_char", "")

        print(f"按键码: {key_code}, 修饰键: {modifiers}, 字符: '{char}'")

        # 处理修饰键组合
        if modifiers:
            modifier_list = modifiers.split('+')
            
            # 将Qt键码转换为pyautogui可识别的键名
            key_name = self.qt_key_to_pyautogui(key_code)
            
            if key_name:
                try:
                    # 如果有明确的键名，使用键名
                    if key_name not in modifier_list:  # 避免重复添加修饰键
                        modifier_list.append(key_name)
                    
                    # 执行热键组合
                    pa.hotkey(*modifier_list)
                    print(f"执行热键: {'+'.join(modifier_list)}")
                except Exception as e:
                    print(f"执行热键失败: {e}")
            else:
                print(f"无法识别的键码: {key_code}")
                
        # 处理单键
        else:
            key_name = self.qt_key_to_pyautogui(key_code)
            if key_name:
                try:
                    pa.press(key_name)
                    print(f"执行单键: {key_name}")
                except Exception as e:
                    print(f"执行单键失败: {e}")
            else:
                # 尝试使用字符
                if char and ord(char) >= 32:  # 可打印字符
                    try:
                        pa.press(char)
                        print(f"执行字符: {char}")
                    except Exception as e:
                        print(f"执行字符失败: {e}")
                else:
                    print(f"无法识别的按键: 键码={key_code}, 字符='{char}'")
            
    def qt_key_to_pyautogui(self, key_code):# 将Qt键码转换为pyautogui可识别的键名
        # 字母键 (A-Z)
        if Qt.Key_A <= key_code <= Qt.Key_Z:
            return chr(ord('a') + (key_code - Qt.Key_A)).lower()
        # 数字键 (0-9)
        if Qt.Key_0 <= key_code <= Qt.Key_9:
            return str(key_code - Qt.Key_0)
        # 功能键 (F1-F12)
        if Qt.Key_F1 <= key_code <= Qt.Key_F12:
            return f"f{key_code - Qt.Key_F1 + 1}"
        # 特殊键映射
        key_map = {
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
            Qt.Key_Space: "space",
            Qt.Key_Return: "enter",
            Qt.Key_Enter: "enter",
            Qt.Key_Escape: "escape",
            Qt.Key_Tab: "tab",
            Qt.Key_Backspace: "backspace",
            Qt.Key_Delete: "delete",
            Qt.Key_Shift: "shift",
            Qt.Key_Control: "ctrl",
            Qt.Key_Alt: "alt",
            Qt.Key_Meta: "win" if platform.system() == "Windows" else "command",
            Qt.Key_Home: "home",
            Qt.Key_End: "end",
            Qt.Key_PageUp: "pageup",
            Qt.Key_PageDown: "pagedown",
            Qt.Key_Insert: "insert",
            Qt.Key_CapsLock: "capslock",
            Qt.Key_NumLock: "numlock",
            Qt.Key_ScrollLock: "scrolllock",
            Qt.Key_Pause: "pause",
            Qt.Key_Print: "printscreen",
            Qt.Key_QuoteDbl: '"',
            Qt.Key_QuoteLeft: '`',
            Qt.Key_Minus: '-',
            Qt.Key_Plus: '+',
            Qt.Key_Equal: '=',
            Qt.Key_BracketLeft: '[',
            Qt.Key_BracketRight: ']',
            Qt.Key_Backslash: '\\',
            Qt.Key_Semicolon: ';',
            Qt.Key_Apostrophe: "'",
            Qt.Key_Comma: ',',
            Qt.Key_Period: '.',
            Qt.Key_Slash: '/',
            Qt.Key_Question: '?',
            Qt.Key_Exclam: '!',
            Qt.Key_At: '@',
            Qt.Key_NumberSign: '#',
            Qt.Key_Dollar: '$',
            Qt.Key_Percent: '%',
            Qt.Key_AsciiCircum: '^',
            Qt.Key_Ampersand: '&',
            Qt.Key_Asterisk: '*',
            Qt.Key_ParenLeft: '(',
            Qt.Key_ParenRight: ')',
            Qt.Key_Underscore: '_',
            Qt.Key_BraceLeft: '{',
            Qt.Key_BraceRight: '}',
            Qt.Key_Bar: '|',
            Qt.Key_Colon: ':',
            Qt.Key_Less: '<',
            Qt.Key_Greater: '>',
            Qt.Key_QuoteDbl: '"',
        }
        return key_map.get(key_code)

    def release_action(self, key_data):
        modifiers=key_data.get("modifiers", "")
        if modifiers:
            modifier_list = modifiers.split('+')
            try:
                for mod in modifier_list:
                    print(f"释放修饰键: {mod}")
                    pa.keyUp(mod)
            except Exception as e:
                print(f"释放修饰键失败: {e}")

if __name__ == "__main__":
    try:
        server = Server()
        server.accepting()
    except KeyboardInterrupt:
        print("服务器已停止")