# 4-LED Environmental Light Control System (Fixed GPIO Busy)
from flask import Flask, render_template_string, request
from gpiozero import LED, LightSensor
import threading
import time
import atexit

# ==================== HARDWARE CONFIGURATION ====================
# Use conflict-free GPIO pins
LED_PINS = [5, 6, 13, 19]
leds = [LED(pin) for pin in LED_PINS]

LIGHT_SENSOR_PIN = 26
light_sensor = LightSensor(LIGHT_SENSOR_PIN)

# ==================== GLOBAL VARIABLES ====================
app = Flask(__name__)
system_mode = "auto"
manual_led_level = 0
system_running = True

# ==================== SAFE SHUTDOWN FUNCTION ====================
def safe_shutdown():
    global system_running
    print("\nInitiating safe shutdown...")
    system_running = False
    # Turn off all LEDs and release GPIO
    for led in leds:
        led.off()
        led.close()
    try:
        light_sensor.close()
    except:
        pass
    print("System shut down safely, GPIO released")

# Register shutdown function
atexit.register(safe_shutdown)

# ==================== LED CONTROL FUNCTION ====================
def set_led_level(level):
    level = max(0, min(4, level))
    for i in range(4):
        if i < level:
            leds[i].on()
        else:
            leds[i].off()

# ==================== AUTO MODE THREAD ====================
def auto_mode_thread():
    global system_mode, system_running
    while system_running:
        if system_mode == "auto":
            try:
                light_level = light_sensor.value
                led_level = int((1.0 - light_level) * 4)
                set_led_level(led_level)
            except Exception as e:
                print(f"Auto mode error: {str(e)}")
        time.sleep(0.2)

# ==================== WEB UI TEMPLATE ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>4-LED Environmental Light Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
        }
        body {
            background-color: #f0f4f8;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .control-card {
            background: white;
            padding: 50px 40px;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            max-width: 600px;
            width: 100%;
            text-align: center;
        }
        h1 {
            color: #2d3748;
            margin-bottom: 30px;
            font-size: 28px;
        }
        .mode-switch {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 40px;
        }
        .mode-btn {
            padding: 15px 30px;
            font-size: 18px;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: background-color 0.3s;
            color: white;
        }
        .mode-btn.active {
            background-color: #4CAF50;
        }
        .mode-btn:not(.active) {
            background-color: #90a4ae;
        }
        .led-display {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 40px;
        }
        .led-indicator {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            border: 3px solid #37474f;
            background-color: #cfd8dc;
            transition: all 0.3s ease;
        }
        .led-indicator.on {
            background-color: #ffeb3b;
            box-shadow: 0 0 20px #ffeb3b;
        }
        .slider-container {
            margin-bottom: 40px;
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
            padding: 20px;
            background-color: #e3f2fd;
            border-radius: 10px;
            color: #1565c0;
            font-size: 18px;
        }
    </style>
</head>
<body>
    <div class="control-card">
        <h1>4-LED Environmental Light Control</h1>
        
        <div class="mode-switch">
            <button id="auto-btn" class="mode-btn active" onclick="setMode('auto')">Auto Mode</button>
            <button id="manual-btn" class="mode-btn" onclick="setMode('manual')">Manual Mode</button>
        </div>
        
        <div class="led-display">
            <div class="led-indicator {{ 'on' if led_level >= 1 else '' }}"></div>
            <div class="led-indicator {{ 'on' if led_level >= 2 else '' }}"></div>
            <div class="led-indicator {{ 'on' if led_level >= 3 else '' }}"></div>
            <div class="led-indicator {{ 'on' if led_level >= 4 else '' }}"></div>
        </div>
        
        <div id="slider-container" class="slider-container">
            <label for="led-slider">Manual LED Control (0-4):</label>
            <input type="range" id="led-slider" class="slider" min="0" max="4" value="{{ manual_level }}" oninput="setManualLevel(this.value)">
            <p>LEDs ON: <span id="led-value">{{ manual_level }}</span>/4</p>
        </div>
        
        <div id="status" class="status">
            Loading system status...
        </div>
    </div>

    <script>
        let currentMode = 'auto';
        
        function setMode(mode) {
            currentMode = mode;
            document.getElementById('auto-btn').classList.toggle('active', mode === 'auto');
            document.getElementById('manual-btn').classList.toggle('active', mode === 'manual');
            document.getElementById('slider-container').classList.toggle('active', mode === 'manual');
            fetch('/set_mode?mode=' + mode);
        }
        
        function setManualLevel(value) {
            document.getElementById('led-value').textContent = value;
            fetch('/set_manual_level?level=' + value);
        }
        
        function updateStatus() {
            fetch('/get_status')
                .then(response => response.json())
                .then(data => {
                    const indicators = document.querySelectorAll('.led-indicator');
                    indicators.forEach((indicator, index) => {
                        indicator.classList.toggle('on', index < data.led_level);
                    });
                    
                    let statusText = '';
                    if (data.mode === 'auto') {
                        statusText = `Auto Mode | Ambient Light: ${(data.light_level * 100).toFixed(0)}% | LEDs ON: ${data.led_level}/4`;
                    } else {
                        statusText = `Manual Mode | LEDs ON: ${data.led_level}/4`;
                    }
                    document.getElementById('status').textContent = statusText;
                    
                    if (data.mode === 'manual') {
                        document.getElementById('led-slider').value = data.manual_level;
                        document.getElementById('led-value').textContent = data.manual_level;
                    }
                });
        }
        
        setInterval(updateStatus, 500);
        updateStatus();
    </script>
</body>
</html>
"""

# ==================== WEB ROUTES ====================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, led_level=0, manual_level=0)

@app.route('/set_mode')
def set_mode():
    global system_mode
    system_mode = request.args.get('mode', 'auto')
    return "OK"

@app.route('/set_manual_level')
def set_manual_level():
    global manual_led_level, system_mode
    if system_mode == "manual":
        try:
            level = int(request.args.get('level', 0))
            manual_led_level = level
            set_led_level(level)
        except:
            pass
    return "OK"

@app.route('/get_status')
def get_status():
    global system_mode, manual_led_level
    light_level = 0.0
    led_level = 0
    
    if system_mode == "auto":
        try:
            light_level = light_sensor.value
            led_level = int((1.0 - light_level) * 4)
        except:
            pass
    else:
        led_level = manual_led_level
    
    return jsonify({
        'mode': system_mode,
        'light_level': light_level,
        'led_level': led_level,
        'manual_level': manual_led_level
    })

# ==================== MAIN PROGRAM ====================
if __name__ == '__main__':
    try:
        print("=== 4-LED Environmental Light System Starting ===")
        set_led_level(0)
        
        auto_thread = threading.Thread(target=auto_mode_thread)
        auto_thread.daemon = True
        auto_thread.start()
        
        print("System started successfully!")
        print("Access Web UI at: http://raspberrypi.local:5000")
        print("Press Ctrl+C to stop the system\n")
        
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
        
    except KeyboardInterrupt:
        safe_shutdown()
