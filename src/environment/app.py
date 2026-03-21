# Desktop Environmental Light System - Main Program
# Web UI + Auto/Manual Dual Mode
from flask import Flask, render_template_string, request, jsonify
import board
import neopixel
from gpiozero import LightSensor
import threading
import time

# ==================== HARDWARE CONFIGURATION (100% MATCHES WIRING) ====================
# LED Strip Configuration
LED_PIN = board.D18    # GPIO18, corresponds to Raspberry Pi Physical Pin 12
NUM_LEDS = 10          # Change to 60 if you didn't cut the strip
MAX_BRIGHTNESS = 0.7   # Max brightness 70%, safe and sufficient

# Light Sensor Configuration
LIGHT_SENSOR_PIN = 17  # GPIO17, corresponds to Raspberry Pi Physical Pin 11

# ==================== GLOBAL VARIABLES ====================
app = Flask(__name__)
pixels = None
light_sensor = None
mode = "auto"  # "auto" or "manual"
manual_brightness = 0.5  # Manual mode brightness (0-1)
running = True

# ==================== HARDWARE INITIALIZATION ====================
def init_hardware():
    global pixels, light_sensor
    
    # Initialize LED strip
    pixels = neopixel.NeoPixel(
        LED_PIN,
        NUM_LEDS,
        brightness=0.0,
        auto_write=False,
        pixel_order=neopixel.GRB
    )
    pixels.fill((0, 0, 0))
    pixels.show()
    
    # Initialize light sensor
    light_sensor = LightSensor(LIGHT_SENSOR_PIN)

# ==================== LED CONTROL FUNCTION ====================
def set_led_brightness(brightness):
    """Set LED strip brightness (0-1)"""
    brightness = max(0.0, min(1.0, brightness))
    safe_brightness = brightness * MAX_BRIGHTNESS
    
    # Warm white color (GRB format for WS2812B)
    red = int(255 * brightness)
    green = int(255 * brightness)
    blue = int(255 * brightness)
    
    pixels.brightness = safe_brightness
    pixels.fill((green, red, blue))
    pixels.show()

# ==================== AUTO MODE THREAD ====================
def auto_mode_thread():
    global mode, running
    while running:
        if mode == "auto":
            # Read light sensor: darker environment = brighter LED
            light_level = light_sensor.value
            led_brightness = 1.0 - light_level
            set_led_brightness(led_brightness)
            time.sleep(0.2)
        else:
            time.sleep(0.1)

# ==================== WEB UI INTERFACE ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Desktop Environmental Light System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 {
            text-align: center;
            color: #333;
        }
        .mode-switch {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 30px 0;
        }
        .mode-btn {
            padding: 15px 30px;
            font-size: 18px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .mode-btn.active {
            background-color: #4CAF50;
            color: white;
        }
        .mode-btn:not(.active) {
            background-color: #ddd;
            color: #333;
        }
        .slider-container {
            margin: 30px 0;
            display: none;
        }
        .slider-container.active {
            display: block;
        }
        .slider {
            width: 100%;
            height: 20px;
            margin: 10px 0;
        }
        .status {
            text-align: center;
            margin-top: 30px;
            padding: 15px;
            background-color: #e7f3fe;
            border-radius: 5px;
            color: #31708f;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Desktop Environmental Light System</h1>
        
        <div class="mode-switch">
            <button id="auto-btn" class="mode-btn active" onclick="setMode('auto')">Auto Mode</button>
            <button id="manual-btn" class="mode-btn" onclick="setMode('manual')">Manual Mode</button>
        </div>
        
        <div id="slider-container" class="slider-container">
            <label for="brightness-slider">Manual Brightness Control:</label>
            <input type="range" id="brightness-slider" class="slider" min="0" max="100" value="50" oninput="setManualBrightness(this.value)">
            <p>Current Brightness: <span id="brightness-value">50</span>%</p>
        </div>
        
        <div id="status" class="status">
            Loading...
        </div>
    </div>

    <script>
        let currentMode = 'auto';
        
        function setMode(mode) {
            currentMode = mode;
            
            // Update button styles
            document.getElementById('auto-btn').classList.toggle('active', mode === 'auto');
            document.getElementById('manual-btn').classList.toggle('active', mode === 'manual');
            
            // Show/hide slider
            document.getElementById('slider-container').classList.toggle('active', mode === 'manual');
            
            // Send request to backend
            fetch('/set_mode?mode=' + mode);
        }
        
        function setManualBrightness(value) {
            document.getElementById('brightness-value').textContent = value;
            fetch('/set_manual_brightness?brightness=' + (value / 100));
        }
        
        // Periodically update status
        function updateStatus() {
            fetch('/get_status')
                .then(response => response.json())
                .then(data => {
                    let statusText = '';
                    if (data.mode === 'auto') {
                        statusText = 'Auto Mode | Ambient Light: ' + (data.light_level * 100).toFixed(0) + '% | LED Brightness: ' + (data.led_brightness * 100).toFixed(0) + '%';
                    } else {
                        statusText = 'Manual Mode | LED Brightness: ' + (data.led_brightness * 100).toFixed(0) + '%';
                    }
                    document.getElementById('status').textContent = statusText;
                });
        }
        
        // Update status every 500ms
        setInterval(updateStatus, 500);
        updateStatus();
    </script>
</body>
</html>
"""

# ==================== WEB ROUTES ====================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/set_mode')
def set_mode():
    global mode
    mode = request.args.get('mode', 'auto')
    return "OK"

@app.route('/set_manual_brightness')
def set_manual_brightness():
    global manual_brightness, mode
    if mode == "manual":
        brightness = float(request.args.get('brightness', 0.5))
        manual_brightness = brightness
        set_led_brightness(brightness)
    return "OK"

@app.route('/get_status')
def get_status():
    global mode, manual_brightness
    light_level = 0.0
    led_brightness = 0.0
    
    if mode == "auto":
        try:
            light_level = light_sensor.value
            led_brightness = 1.0 - light_level
        except:
            pass
    else:
        led_brightness = manual_brightness
    
    return jsonify({
        'mode': mode,
        'light_level': light_level,
        'led_brightness': led_brightness
    })

# ==================== MAIN PROGRAM ENTRY ====================
if __name__ == '__main__':
    try:
        print("=== Desktop Environmental Light System Starting... ===")
        init_hardware()
        
        # Start auto mode thread
        auto_thread = threading.Thread(target=auto_mode_thread)
        auto_thread.daemon = True
        auto_thread.start()
        
        print("System started successfully!")
        print("Access the UI in your browser at: http://raspberrypi.local:5000")
        print("Press Ctrl+C to stop the system\n")
        
        # Start Flask web server
        app.run(host='0.0.0.0', port=5000, debug=False)
        
    except KeyboardInterrupt:
        print("\n\nStopping system...")
        running = False
        if pixels:
            pixels.fill((0, 0, 0))
            pixels.show()
            pixels.deinit()
        print("System stopped safely")
