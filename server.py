import time
import threading
import io
import base64
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from mss import mss
from PIL import Image
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Variables for screen capture
frame_rate = 10
scale = 1.0
mouse = MouseController()
keyboard = KeyboardController()
screen_width, screen_height = 1920, 1080  # Default values, set to actual resolution

@app.route("/")
def index():
    return render_template("index.html")

def capture_screen():
    global scale, frame_rate, screen_width, screen_height
    with mss() as sct:
        monitor = sct.monitors[1]
        screen_width, screen_height = monitor["width"], monitor["height"]
        
        while True:
            start_time = time.time()
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            width, height = img.size
            img = img.resize((int(width * scale), int(height * scale)))

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")
            img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

            socketio.emit('screen_update', {'img': img_str})
            time.sleep(max(0, 1 / frame_rate - (time.time() - start_time)))

@socketio.on('mouse_event')
def handle_mouse_event(data):
    try:
        # Scale client coordinates to server screen dimensions
        x = int(data['x'] / 100 * screen_width)
        y = int(data['y'] / 100 * screen_height)
        if data['type'] == 'move':
            mouse.position = (x, y)
        elif data['type'] == 'click':
            mouse.click(Button.left)
    except Exception as e:
        print("Mouse event error:", e)

@socketio.on('keyboard_event')
def handle_keyboard_event(data):
    try:
        key, action = data.get('key'), data.get('action')
        if action == 'press':
            keyboard.press(key)
        elif action == 'release':
            keyboard.release(key)
    except Exception as e:
        print("Keyboard event error:", e)

@socketio.on('set_frame_rate')
def set_frame_rate(data):
    global frame_rate
    frame_rate = max(1, min(30, int(data.get('frame_rate', 10))))

@socketio.on('set_resolution')
def set_resolution(data):
    global scale
    scale = max(0.1, min(1.0, float(data.get('scale', 1.0))))

if __name__ == "__main__":
    threading.Thread(target=capture_screen, daemon=True).start()
    socketio.run(app, host="0.0.0.0", port=5000)
