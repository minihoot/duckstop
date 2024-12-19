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
    # Enhanced map of key codes to pynput keys
    key_map = {
        'Space': Key.space,
        'Enter': Key.enter,
        'Backspace': Key.backspace,
        'Tab': Key.tab,
        'ShiftLeft': Key.shift,
        'ShiftRight': Key.shift,
        'ControlLeft': Key.ctrl,
        'ControlRight': Key.ctrl,
        'AltLeft': Key.alt,
        'AltRight': Key.alt,
        'CapsLock': Key.caps_lock,
        'Escape': Key.esc,
        'Delete': Key.delete,
        # Add more special keys
        'ArrowUp': Key.up,
        'ArrowDown': Key.down,
        'ArrowLeft': Key.left,
        'ArrowRight': Key.right,
        'Home': Key.home,
        'End': Key.end,
        'PageUp': Key.page_up,
        'PageDown': Key.page_down,
    }
    
    if key_code in key_map:
        return key_map[key_code]
    elif key_code.startswith('Key'):
        # Handle regular letter keys (KeyA, KeyB, etc.)
        return key_code[-1].lower()
    elif key_code.startswith('Digit'):
        # Handle number keys
        return key_code[-1]
    else:
        try:
            # Handle any other character keys
            return key_code[-1].lower()
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
        if combo == 'ctrl_alt_del':
            # For Linux, we might want to simulate Ctrl+Alt+Backspace or another combination
            keyboard.press(Key.ctrl)
            keyboard.press(Key.alt)
            keyboard.press(Key.delete)
            time.sleep(0.1)
            keyboard.release(Key.delete)
            keyboard.release(Key.alt)
            keyboard.release(Key.ctrl)
            
    except Exception as e:
        print(f"Special key combo error: {e}")

@socketio.on('mouse_event')
def handle_mouse_event(data):
    try:
        event_type = data.get('type')
        
        if event_type == 'scroll':
            # Convert percentage coordinates to actual screen coordinates
            x = int((data.get('x', 0) / 100) * screen_width)
            y = int((data.get('y', 0) / 100) * screen_height)
            
            # Move mouse to position before scrolling
            mouse.position = (x, y)
            
            # Perform scroll action
            deltaY = data.get('deltaY', 0)
            deltaX = data.get('deltaX', 0)
            
            # Vertical scrolling
            if deltaY != 0:
                mouse.scroll(0, deltaY)
            
            # Horizontal scrolling (if supported)
            if deltaX != 0:
                mouse.scroll(deltaX, 0)
                
        elif event_type == 'move':
            # Existing move handling code...
            x = int((data.get('x', 0) / 100) * screen_width)
            y = int((data.get('y', 0) / 100) * screen_height)
            mouse.position = (x, y)
            
        elif event_type in ['down', 'up']:
            # Existing click handling code...
            button = data.get('button', 0)
            button_map = {
                0: Button.left,
                1: Button.middle,
                2: Button.right
            }
            if button in button_map:
                if event_type == 'down':
                    mouse.press(button_map[button])
                else:
                    mouse.release(button_map[button])
                    
    except Exception as e:
        print(f"Mouse event error: {e}")
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
