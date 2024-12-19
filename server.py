import time
import threading
import io
import base64
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from mss import mss
from PIL import Image
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key, KeyCode
from pynput.keyboard._win32 import KeyCode as WinKeyCode  # For Windows special keys

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Controllers
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

def get_key_from_code(key_code):
    # Map of common key codes to pynput keys
    key_map = {
        'Space': Key.space,
        'Enter': Key.enter,
        'Backspace': Key.backspace,
        'Tab': Key.tab,
        'ShiftLeft': Key.shift_l,
        'ShiftRight': Key.shift_r,
        'ControlLeft': Key.ctrl_l,
        'ControlRight': Key.ctrl_r,
        'AltLeft': Key.alt_l,
        'AltRight': Key.alt_r,
        'CapsLock': Key.caps_lock,
        'Escape': Key.esc,
        'Delete': Key.delete,
    }
    
    if key_code in key_map:
        return key_map[key_code]
    elif key_code.startswith('Key'):
        # Handle regular keys (KeyA, KeyB, etc.)
        return KeyCode.from_char(key_code[-1].lower())
    elif key_code.startswith('Digit'):
        # Handle number keys
        return KeyCode.from_char(key_code[-1])
    else:
        # Try to handle any other keys
        try:
            return KeyCode.from_char(key_code[-1].lower())
        except:
            print(f"Unable to map key: {key_code}")
            return None

@socketio.on('keyboard_event')
def handle_keyboard_event(data):
    try:
        key_code = data.get('key')
        action = data.get('action')
        
        key = get_key_from_code(key_code)
        if key:
            if action == 'press':
                keyboard.press(key)
            elif action == 'release':
                keyboard.release(key)
                
    except Exception as e:
        print(f"Keyboard event error: {e}")

@socketio.on('special_key_combo')
def handle_special_combo(data):
    try:
        combo = data.get('combo')
