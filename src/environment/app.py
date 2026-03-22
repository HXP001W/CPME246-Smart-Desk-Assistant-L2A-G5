# 4-LED System with Simple Light Sensor (No Interrupts) - High Sensitivity Version
from flask import Flask, render_template_string, request, jsonify
from gpiozero import LED
import threading
import time
import atexit

# ==================== HARDWARE CONFIG ====================
LED_PINS = [22, 23, 24, 25]
leds = [LED(pin, initial_value=False) for pin in LED_PINS]
LIGHT_PIN = 27  # Physical Pin 13

# ==================== GLOBAL VARIABLES ====================
app = Flask(__name__)
system_mode = "auto"
manual_level = 0
running = True

# ==================== FILTER HISTORY (NEW) ====================
light_history = []

# ==================== SAFE SHUTDOWN ====================
def safe_shutdown():
    global running
    print("\nShutting down...")
    running = False
    for led in leds:
        led.off()
        led.close()
    print("All LEDs off")

atexit.register(safe_shutdown)

# ==================== SIMPLE LIGHT READ (No Interrupts!) - WITH FILTER (MODIFIED) ====================
def read_light():
    """带滤波的光敏读数，解决跳变问题"""
    global light_history
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(LIGHT_PIN, GPIO.OUT)
        GPIO.output(LIGHT_PIN, GPIO.LOW)
        time.sleep(0.05)
        
        GPIO.setup(LIGHT_PIN, GPIO.IN)
        start = time.time()
        while GPIO.input(LIGHT_PIN) == GPIO.LOW and (time.time() - start) < 0.1:
            pass
        charge_time = time.time() - start
        
        GPIO.cleanup(LIGHT_PIN)
        
        # 原始亮度值
        raw = 1.0 - min(1.0, charge_time * 10)
        
        # 滑动平均滤波：存最近5次读数，取平均
        light_history.append(raw)
        if len(light_history) > 5:
            light_history.pop(0)
        average = sum(light_history) / len(light_history)
        
        return max(0.0, min(1.0, average))
    except:
        return 0.5

# ==================== LED CONTROL ====================
def set_leds(level):
    level = max(0, min(4, int(level)))
    for i in range(4):
        leds[i].on() if i < level else leds[i].off()

# ==================== AUTO MODE THREAD - WITH HIGH SENSITIVITY (MODIFIED) ====================
def auto_loop():
    global system_mode, running
    while running:
        if system_mode == "auto":
            light = read_light()
            
            # ==================== 高灵敏度映射 ====================
            # 超过80%亮度：灯全灭
            if light >= 0.8:
                level = 0
            # 低于20%亮度：灯全亮
            elif light <= 0.2:
                level = 4
            # 中间区间：放大灵敏度，稍微暗一点就亮灯
            else:
                # 把20%-80%的亮度区间，映射到0-4的LED数量
                normalized = (light - 0.2) / (0.8 - 0.2)
                # 反转：越暗灯越亮，再放大1.5倍灵敏度
                level = int((1.0 - normalized) * 1.5 * 4)
                level = max(0, min(4, level))
            # =====================================================
            
            set_leds(level)
        time.sleep(0.2)

# ==================== WEB UI ====================
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
        <h1>4-LED Light Control</h1>
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
            <label for="led-slider">LED Control (0-4):</label>
            <input type="range" id="led-slider" class="slider" min="0" max="4" value="0" oninput="setLevel(this.value)">
            <p>LEDs ON: <span id="led-value">0</span>/4</p>
        </div>
        <div id="status" class="status">Loading...</div>
    </div>
    <script>
        let mode = 'auto';
        function setMode(m) {
            mode = m;
            document.getElementById('auto-btn').classList.toggle('active', m === 'auto');
            document.getElementById('manual-btn').classList.toggle('active', m === 'manual');
            document.getElementById('slider-container').classList.toggle('active', m === 'manual');
            fetch('/mode?m=' + m);
        }
        function setLevel(value) {
            document.getElementById('led-value').textContent = value;
            fetch('/set?l=' + value);
        }
        function update() {
            fetch('/status').then(r => r.json()).then(data => {
                for(let i=1; i<=4; i++) {
                    document.getElementById(`led${i}`).classList.toggle('on', i <= data.leds);
                }
                let text = '';
                if(data.mode === 'auto') {
                    text = `Auto | Light: ${(data.light*100).toFixed(0)}% | LEDs: ${data.leds}/4`;
                } else {
                    text = `Manual | LEDs: ${data.leds}/4`;
                }
                document.getElementById('status').textContent = text;
                if(data.mode === 'manual') {
                    document.getElementById('led-slider').value = data.leds;
                    document.getElementById('led-value').textContent = data.leds;
                }
            });
        }
        setInterval(update, 500);
        update();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/mode')
def set_mode():
    global system_mode
    system_mode = request.args.get('m', 'auto')
    return "OK"

@app.route('/set')
def set_level():
    global manual_level, system_mode
    if system_mode == 'manual':
        manual_level = int(request.args.get('l', 0))
        set_leds(manual_level)
    return "OK"

@app.route('/status')
def status():
    light = read_light()
    leds_on = 0
    if system_mode == 'auto':
        # 这里也用同样的高灵敏度映射，保持UI和实际一致
        if light >= 0.8:
            leds_on = 0
        elif light <= 0.2:
            leds_on = 4
        else:
            normalized = (light - 0.2) / (0.8 - 0.2)
            leds_on = int((1.0 - normalized) * 1.5 * 4)
            leds_on = max(0, min(4, leds_on))
    else:
        leds_on = manual_level
    return jsonify({
        'mode': system_mode,
        'light': light,
        'leds': leds_on
    })

if __name__ == '__main__':
    print("="*50)
    print("4-LED Light Control System")
    print("="*50)
    print("LEDs initialized")
    print("Starting auto thread...")
    threading.Thread(target=auto_loop, daemon=True).start()
    print("Access Web UI at: http://raspberrypi.local:5000")
    print("Press Ctrl+C to stop")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
