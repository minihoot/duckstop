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

# screen config
frame_rate = 30
scale = 1.0
mouse = MouseController()
keyboard = KeyboardController()

# Initialize screen dimensions
screen_width = None
screen_height = None

@app.route("/")
def index():
    return render_template("index.html")

def capture_screen():
    global scale, frame_rate, screen_width, screen_height
    
    with mss() as sct:
        monitor = sct.monitors[1]
        screen_width, screen_height = monitor["width"], monitor["height"]
        print(f"Detected screen resolution: {screen_width}x{screen_height}")
        
        while True:
            start_time = time.time()
            
            try:
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                if scale != 1.0:
                    new_width = int(screen_width * scale)
                    new_height = int(screen_height * scale)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
                
                socketio.emit('screen_update', {
                    'img': img_str,
                    'width': screen_width,
                    'height': screen_height
                })
                
                time.sleep(max(0, 1 / frame_rate - (time.time() - start_time)))
                
            except Exception as e:
                print(f"Screen capture error: {e}")
                time.sleep(1)

@socketio.on('mouse_event')
def handle_mouse_event(data):
    try:
        event_type = data.get('type')
        
        # Handle mouse position updates
        if 'x' in data and 'y' in data:
            x = int(data['x'] * screen_width / 100)
            y = int(data['y'] * screen_height / 100)
            x = max(0, min(x, screen_width))
            y = max(0, min(y, screen_height))
            mouse.position = (x, y)
        
        # Handle mouse button events
        if event_type == 'down':
            button = Button.right if data.get('button') == 2 else Button.left
            mouse.press(button)
        elif event_type == 'up':
            button = Button.right if data.get('button') == 2 else Button.left
            mouse.release(button)
            
    except Exception as e:
        print(f"Mouse event error: {e}")

@socketio.on('keyboard_event')
def handle_keyboard_event(data):
    try:
        key, action = data.get('key'), data.get('action')
        if action == 'press':
            keyboard.press(key)
        elif action == 'release':
            keyboard.release(key)
    except Exception as e:
        print(f"Keyboard event error: {e}")

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
