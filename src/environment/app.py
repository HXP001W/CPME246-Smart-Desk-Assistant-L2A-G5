# 4-LED Environmental Light Control System - Bookworm Perfect Version
from flask import Flask, render_template_string, request, jsonify
from gpiozero import LED, Device
import threading
import time
import atexit

# ==================== GPIO BACKEND SETUP (Bookworm Compatible) ====================
# Try RPi.GPIO first, fall back to native if not available
try:
    from gpiozero.pins.rpigpio import RPiGPIOFactory
    Device.pin_factory = RPiGPIOFactory()
    print("Using RPi.GPIO backend (stable)")
except:
    print("RPi.GPIO not found, using native backend")
    pass

# ==================== HARDWARE CONFIGURATION ====================
LED_PINS = [22, 23, 24, 25]
LIGHT_SENSOR_PIN = 27  # Physical Pin 13

# ==================== GLOBAL VARIABLES ====================
app = Flask(__name__)
system_mode = "auto"
manual_led_level = 0
system_running = True

# Hardware objects
leds = []
light_sensor_pin = None
light_sensor_available = False

# ==================== SIMPLE LIGHT SENSOR READER (No Interrupts!) ====================
# We use a simple analog-like reading via charge time, no edge detection
def read_light_level():
    """
    Simple light sensor reading without any interrupts.
    Returns 0.0 (full dark) to 1.0 (full bright).
    """
    if not light_sensor_available:
        return 0.5
    
    try:
        import RPi.GPIO as GPIO
        # Use direct RPi.GPIO for simple reading, no gpiozero LightSensor
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(LIGHT_SENSOR_PIN, GPIO.OUT)
        GPIO.output(LIGHT_SENSOR_PIN, GPIO.LOW)
        time.sleep(0.1)
        
        GPIO.setup(LIGHT_SENSOR_PIN, GPIO.IN)
        start_time = time.time()
        # Wait for pin to go high (charge time)
        while GPIO.input(LIGHT_SENSOR_PIN) == GPIO.LOW and (time.time() - start_time) < 0.1:
            pass
        charge_time = time.time() - start_time
        
        # Clean up
        GPIO.setup(LIGHT_SENSOR_PIN, GPIO.IN)
        
        # Map charge time to light level (longer charge = darker)
        light_level = 1.0 - min(1.0, charge_time * 10)
        return max(0.0, min(1.0, light_level))
    except:
        return 0.5

# ==================== HARDWARE SETUP ====================
def setup_hardware():
    global leds, light_sensor_available

    # Clean up existing LEDs
    for led in leds:
        try:
            led.off()
            led.close()
        except Exception:
            pass
    leds.clear()

    # Initialize LEDs first (very stable)
    try:
        leds = [LED(pin, initial_value=False) for pin in LED_PINS]
        print(f"✅ LEDs initialized on GPIO {LED_PINS}")
    except Exception as e:
        raise RuntimeError(f"❌ LED initialization failed: {str(e)}")
 
    # Check light sensor wiring (print reminder)
    print("\n📋 Check light sensor wiring:")
    print("  - Light sensor pin 1 -> 3.3V (Physical Pin 1)")
    print("  - Light sensor pin 2 -> GPIO27 (Physical Pin 13) + 10kΩ resistor")
    print("  - 10kΩ resistor -> GND (Physical Pin 9)")
    
    # Mark light sensor as available (we'll use our simple reader)
    light_sensor_available = True
    print("✅ Light sensor initialized (polling mode, no interrupts)")

# ==================== SAFE SHUTDOWN ====================
def safe_shutdown():
    global system_running, leds
    print("\n=== SAFE SHUTDOWN STARTED ===")
    system_running = False

    # Release all LEDs
    for idx, led in enumerate(leds):
        try:
            led.off()
            led.close()
            print(f"LED {idx+1} (GPIO{LED_PINS[idx]}) released")
        except Exception as e:
            print(f"Failed to release LED {idx+1}: {str(e)}")
    leds.clear()

    # Clean up GPIO
    try:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
        print("GPIO cleaned up")
    except:
        pass

    print("=== SAFE SHUTDOWN COMPLETE ===")

# Register shutdown
atexit.register(safe_shutdown)

# ==================== LED CONTROL ====================
def set_led_level(level):
    level = max(0, min(4, int(level)))
    for i in range(min(4, len(leds))):
        leds[i].on() if i < level else leds[i].off()

def get_current_led_count():
    count = 0
    for led in leds:
        try:
            if led.value == 1:
                count += 1
        except Exception:
            pass
    return count

# ==================== AUTO MODE THREAD ====================
def auto_mode_loop():
    global system_mode, system_running
    while system_running:
        if system_mode == "auto" and light_sensor_available:
            try:
                ambient_light = read_light_level()
                target_led_count = int((1.0 - ambient_light) * 4)
                set_led_level(target_led_count)
            except Exception:
                pass
        time.sleep(0.2)

# ==================== WEB UI TEMPLATE ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>4-LED Light Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background-color: #f0f4f8; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .control-card { background: white; padding: 50px 40px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); max-width: 600px; width: 100%; text-align: center; }
        h1 { color: #2d3748; margin-bottom: 30px; font-size: 28px; }
        .mode-switch { display: flex; justify-content: center; gap: 20px; margin-bottom: 40px; }
        .mode-btn { padding: 15px 30px; font-size: 18px; border: none; border-radius: 10px; cursor: pointer; transition: background-color 0.3s; color: white; }
        .mode-btn.active { background-color: #4CAF50; }
        .mode-btn:not(.active) { background-color: #90a4ae; }
        .led-display { display: flex; justify-content: center; gap: 20px; margin-bottom: 40px; }
        .led-indicator { width: 60px; height: 60px; border-radius: 50%; border: 3px solid #37474f; background-color: #cfd8dc; transition: all 0.3s ease; }
        .led-indicator.on { background-color: #ffeb3b; box-shadow: 0 0 20px #ffeb3b; }
        .slider-container { margin-bottom: 40px; display: none; }
        .slider-container.active { display: block; }
        .slider { width: 100%; height: 20px; margin: 10px 0; }
        .status { padding: 20px; background-color: #e3f2fd; border-radius: 10px; color: #1565c0; font-size: 18px; }
    </style>
</head>
<body>
    <div class="control-card">
        <h1>4-LED Light Control System</h1>
        <div class="mode-switch">
            <button id="auto-btn" class="mode-btn active" onclick="setMode('auto')">Auto Mode</button>
            <button id="manual-btn" class="mode-btn" onclick="setMode('manual')">Manual Mode</button>
        </div>
        <div class="led-display">
            <div class="led-indicator" id="led1"></div>
            <div class="led-indicator" id="led2"></div>
            <div class="led-indicator" id="led3"></div>
            <div class="led-indicator" id="led4"></div>
        </div>
        <div id="slider-container" class="slider-container">
            <label for="led-slider">Manual LED Control (0-4):</label>
            <input type="range" id="led-slider" class="slider" min="0" max="4" value="0" oninput="setManualLevel(this.value)">
            <p>LEDs ON: <span id="led-value">0</span>/4</p>
        </div>
        <div id="status" class="status">Loading system status...</div>
    </div>
    <script>
        let currentMode = 'auto';
        function setMode(mode) {
            currentMode = mode;
            document.getElementById('auto-btn').classList.toggle('active', mode === 'auto');
            document.getElementById('manual-btn').classList.toggle('active', mode === 'manual');
            document.getElementById('slider-container').classList.toggle('active', mode === 'manual');
            fetch('/set_mode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({mode: mode})
            });
        }
        function setManualLevel(value) {
            document.getElementById('led-value').textContent = value;
            fetch('/set_led', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({level: value})
            });
        }
        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    // Update LEDs
                    const ledCount = data.led_count;
                    for (let i=1; i<=4; i++) {
                        document.getElementById(`led${i}`).classList.toggle('on', i <= ledCount);
                    }
                    // Update status
                    let statusText = '';
                    if (data.mode === 'auto') {
                        statusText = `Auto Mode | Ambient Light: ${(data.light_value * 100).toFixed(0)}% | LEDs ON: ${ledCount}/4`;
                    } else {
                        statusText = `Manual Mode | LEDs ON: ${ledCount}/4`;
                    }
                    document.getElementById('status').textContent = statusText;
                    // Update slider
                    if (data.mode === 'manual') {
                        document.getElementById('led-slider').value = ledCount;
                        document.getElementById('led-value').textContent = ledCount;
                    }
                });
        }
        setInterval(updateStatus, 500);
        updateStatus();
    </script>
</body>
</html>
"""

# ==================== FLASK ROUTES ====================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/set_mode', methods=['POST'])
def set_mode():
    global system_mode
    data = request.get_json()
    mode = data.get('mode', 'auto')
    if mode in ['auto', 'manual']:
        system_mode = mode
    return jsonify(get_status_data())

@app.route('/set_led', methods=['POST'])
def set_led():
    global manual_led_level, system_mode
    data = request.get_json()
    level = int(data.get('level', 0))
    if system_mode == 'manual':
        manual_led_level = max(0, min(4, level))
        set_led_level(manual_led_level)
    return jsonify(get_status_data())

@app.route('/status')
def status():
    return jsonify(get_status_data())

# ==================== STATUS HELPER ====================
def get_status_data():
    light_value = 0.5
    if light_sensor_available:
        light_value = read_light_level()
    return {
        'mode': system_mode,
        'led_count': get_current_led_count(),
        'light_value': light_value
    }

# ==================== MAIN ====================
if __name__ == '__main__':
    try:
        print("=" * 50)
        print("4-LED Environmental Light System Starting")
        print("=" * 50)
        print("Initializing hardware...")

        setup_hardware()
        set_led_level(0)

        auto_thread = threading.Thread(target=auto_mode_loop)
        auto_thread.daemon = True
        auto_thread.start()

        print("\n✅ System started successfully!")
        print("🌐 Access Web UI at: http://raspberrypi.local:5000")
        print("⏹️  Press Ctrl+C to stop")
        print("=" * 50 + "\n")

        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

    except KeyboardInterrupt:
        print("\nReceived stop command")
        safe_shutdown()
    except Exception as e:
        print(f"\n❌ Startup failed: {str(e)}")
        safe_shutdown()
