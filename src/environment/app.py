from flask import Flask, render_template_string, request, jsonify
from gpiozero import LED, LightSensor, Device
from gpiozero.pins.rpigpio import RPiGPIOFactory
import threading
import time
import atexit

# ==================== FORCE STABLE GPIO BACKEND ====================
try:
    if Device.pin_factory is not None:
        Device.pin_factory.close()
except Exception:
    pass

Device.pin_factory = RPiGPIOFactory()

# ==================== HARDWARE CONFIGURATION ====================
LED_PINS = [22, 23, 24, 25]
LIGHT_SENSOR_PIN = 27

# ==================== GLOBAL VARIABLES ====================
app = Flask(__name__)
system_mode = "auto"
manual_led_level = 0
system_running = True


leds = []
light_sensor = None
# ==================== HARDWARE SETUP ====================
def setup_hardware():
    global leds, light_sensor

    for led in leds:
        try:
            led.off()
            led.close()
        except Exception:
            pass
    leds.clear()

    if light_sensor is not None:
        try:
            light_sensor.close()
        except Exception:
            pass
        light_sensor = None

    try:
        leds = [
            LED(pin, initial_value=False, pin_factory=Device.pin_factory)
            for pin in LED_PINS
        ]
        print(f"LEDs initialized on GPIO {LED_PINS}")
    except Exception as e:
        raise RuntimeError(f"LED initialization failed: {e}")
 
    try:
        light_sensor = LightSensor(LIGHT_SENSOR_PIN, pin_factory=Device.pin_factory)
        print(f"Light sensor initialized on GPIO{LIGHT_SENSOR_PIN}")
    except Exception as e:
        for led in leds:
            try:
                led.off()
                led.close()
            except Exception:
                pass
        leds.clear()
        raise RuntimeError(f"Light sensor initialization failed: {e}")

# ==================== SAFE SHUTDOWN ====================
def safe_shutdown():
    global system_running, leds, light_sensor
    print("\n=== SAFE SHUTDOWN STARTED ===")
    system_running = False

    for idx, led in enumerate(leds):
        try:
            led.off()
            led.close()
            print(f"LED {idx+1} (GPIO{LED_PINS[idx]}) released")
        except Exception as e:
            print(f"Failed to release LED {idx+1}: {e}")

    leds.clear()

    if light_sensor is not None:
        try:
            light_sensor.close()
            print("Light sensor released")
        except Exception as e:
            print(f"Failed to release light sensor: {e}")
        light_sensor = None

    try:
        if Device.pin_factory is not None:
            Device.pin_factory.close()
            print("GPIO factory closed")
    except Exception as e:
        print(f"Failed to close pin factory: {e}")

    print("=== SAFE SHUTDOWN COMPLETE ===")

atexit.register(safe_shutdown)

# ==================== LED CONTROL ====================
def set_led_level(level):
    level = max(0, min(4, int(level)))
    for i in range(min(4, len(leds))):
        if i < level:
            leds[i].on()
        else:
            leds[i].off()

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
    global system_mode, system_running, light_sensor
    while system_running:
        if system_mode == "auto" and light_sensor is not None:
            try:
                ambient_light = light_sensor.value
                target_led_count = int((1.0 - ambient_light) * 4)
                set_led_level(target_led_count)
            except Exception:
                pass
        time.sleep(0.2)

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
    light_value_text = "Unavailable"

    if light_sensor is not None:
        try:
            light_value_text = f"{light_sensor.value:.2f}"
        except Exception:
            light_value_text = "Read error"

    return {
        'mode': system_mode,
        'led_count': get_current_led_count(),
        'light_value': light_value_text
    }

# ==================== MAIN PROGRAM ====================
if __name__ == '__main__':
    try:
        print("=" * 50)
        print("4-LED Environmental Light System Starting")
        print("=" * 50)
        print("Using RPi.GPIO backend")
        print("Initializing hardware...")

        setup_hardware()
        set_led_level(0)

        auto_thread = threading.Thread(target=auto_mode_loop)
        auto_thread.daemon = True
        auto_thread.start()

        print("System started successfully!")
        print("Access Web UI at: http://raspberrypi.local:5000")
        print("Press Ctrl+C to stop")
        print("=" * 50 + "\n")

        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

    except KeyboardInterrupt:
        print("\nReceived stop command")
        safe_shutdown()
    except Exception as e:
        print(f"\nStartup failed: {e}")
        safe_shutdown()
