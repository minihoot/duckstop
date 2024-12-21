import time
import threading
import io
import base64
import argparse
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
current_frame = None
frame_lock = threading.Lock()
screen_width = None
screen_height = None

# Command-line argument parser
parser = argparse.ArgumentParser(description="Screen sharing server with optional Web UI.")
parser.add_argument('--webui', action='store_true', help="Run the server with Web UI.")
args = parser.parse_args()

if args.webui:
    @app.route("/")
    def index():
        return render_template("index.html")
else:
	print("starting in non ui mode")

def capture_screen():
    global current_frame, screen_width, screen_height
    
    with mss() as sct:
        monitor = sct.monitors[1]
        screen_width, screen_height = monitor["width"], monitor["height"]
        print(f"Detected screen resolution: {screen_width}x{screen_height}")
        
        while True:
            start_time = time.time()
            
            try:
                # Capture screen and convert to RGB
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                # Store the original image in memory
                with frame_lock:
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=95)  # High quality base image
                    current_frame = {
                        'buffer': buffer.getvalue(),
                        'width': screen_width,
                        'height': screen_height,
                        'timestamp': time.time()
                    }
                
                # Broadcast frame availability to all clients
                socketio.emit('frame_ready', {
                    'timestamp': current_frame['timestamp'],
                    'width': screen_width,
                    'height': screen_height
                })
                
                time.sleep(max(0, 1 / frame_rate - (time.time() - start_time)))
                
            except Exception as e:
                print(f"Screen capture error: {e}")
                time.sleep(1)

@socketio.on('request_frame')
def handle_frame_request(data):
    """Handle client frame requests with specific quality/scale requirements"""
    try:
        requested_quality = int(data.get('quality', 85))  # Default to 85% quality
        requested_scale = float(data.get('scale', 1.0))   # Default to full scale
        client_timestamp = data.get('timestamp', 0)
        
        with frame_lock:
            if not current_frame or client_timestamp >= current_frame['timestamp']:
                return
            
            # Load the original frame
            img = Image.open(io.BytesIO(current_frame['buffer']))
            
            # Scale if requested
            if requested_scale != 1.0:
                new_width = int(screen_width * requested_scale)
                new_height = int(screen_height * requested_scale)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Compress to requested quality
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=requested_quality)
            img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            
            # Send frame only to requesting client
            emit('screen_update', {
                'img': img_str,
                'width': screen_width,
                'height': screen_height,
                'timestamp': current_frame['timestamp']
            })
            
    except Exception as e:
        print(f"Frame request error: {e}")

def get_key_from_code(key_code):
    """Convert web key codes to pynput keys with improved handling for regular typing"""
    # Special keys mapping
    key_map = {
        'Space': Key.space,
        'Enter': Key.enter,
        'Backspace': Key.backspace,
        'Tab': Key.tab,
        'ShiftLeft': Key.shift_l,  # Using specific left/right keys
        'ShiftRight': Key.shift_r,
        'ControlLeft': Key.ctrl_l,
        'ControlRight': Key.ctrl_r,
        'AltLeft': Key.alt_l,
        'AltRight': Key.alt_r,
        'CapsLock': Key.caps_lock,
        'Escape': Key.esc,
        'Delete': Key.delete,
        'ArrowUp': Key.up,
        'ArrowDown': Key.down,
        'ArrowLeft': Key.left,
        'ArrowRight': Key.right,
        'Home': Key.home,
        'End': Key.end,
        'PageUp': Key.page_up,
        'PageDown': Key.page_down,
        'Insert': Key.insert,
        'NumLock': Key.num_lock,
        'PrintScreen': Key.print_screen,
        'ScrollLock': Key.scroll_lock,
        'Pause': Key.pause
    }
    
    # Direct mapping for function keys
    if key_code.startswith('F') and key_code[1:].isdigit():
        try:
            num = int(key_code[1:])
            if 1 <= num <= 12:
                return getattr(Key, f'f{num}')
        except ValueError:
            pass

    # Check special keys first
    if key_code in key_map:
        return key_map[key_code]
    
    # Handle regular character keys
    if key_code.startswith('Key'):
        return KeyCode.from_char(key_code[-1].lower())
    elif key_code.startswith('Digit'):
        return KeyCode.from_char(key_code[-1])
    elif key_code == 'Minus':
        return KeyCode.from_char('-')
    elif key_code == 'Equal':
        return KeyCode.from_char('=')
    elif key_code == 'BracketLeft':
        return KeyCode.from_char('[')
    elif key_code == 'BracketRight':
        return KeyCode.from_char(']')
    elif key_code == 'Semicolon':
        return KeyCode.from_char(';')
    elif key_code == 'Quote':
        return KeyCode.from_char("'")
    elif key_code == 'Backquote':
        return KeyCode.from_char('`')
    elif key_code == 'Backslash':
        return KeyCode.from_char('\\')
    elif key_code == 'Comma':
        return KeyCode.from_char(',')
    elif key_code == 'Period':
        return KeyCode.from_char('.')
    elif key_code == 'Slash':
        return KeyCode.from_char('/')
    
    # For any other characters, try direct mapping
    try:
        if len(key_code) == 1:
            return KeyCode.from_char(key_code.lower())
    except:
        print(f"Unable to map key: {key_code}")
        return None

@socketio.on('keyboard_event')
def handle_keyboard_event(data):
    """Handle keyboard events with better tracking of modifier keys"""
    try:
        key_code = data.get('key')
        action = data.get('action')
        print(f"Received keyboard event: {key_code} - {action}")  # Debug logging
        
        key = get_key_from_code(key_code)
        if key:
            if action == 'press':
                keyboard.press(key)
                print(f"Pressed key: {key}")  # Debug logging
            elif action == 'release':
                keyboard.release(key)
                print(f"Released key: {key}")  # Debug logging
                
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

@socketio.on('set_frame_rate')
def set_frame_rate(data):
    global frame_rate
    frame_rate = max(1, min(30, int(data.get('frame_rate', 10))))

if __name__ == "__main__":
    threading.Thread(target=capture_screen, daemon=True).start()
    socketio.run(app, host="0.0.0.0", port=5000)
