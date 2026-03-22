# 4-LED High-Sensitivity Light Control System
from flask import Flask, render_template_string, request, jsonify
from gpiozero import LED
import threading
import time
import atexit

# ==================== 灵敏度调节参数（直接改这里就行！） ====================
# 灵敏度增益：数值越大，越敏感（推荐1.0-3.0，默认2.0）
SENSITIVITY_GAIN = 2.0
# 最大亮度阈值：超过这个亮度，灯全灭（默认0.8 = 80%亮度）
MAX_BRIGHTNESS_THRESHOLD = 0.8
# 最小亮度阈值：低于这个亮度，灯全亮（默认0.1 = 10%亮度）
MIN_BRIGHTNESS_THRESHOLD = 0.1
# 滤波采样次数：数值越大，读数越稳，反应稍慢（默认5次）
FILTER_SAMPLES = 5

# ==================== HARDWARE CONFIG ====================
LED_PINS = [22, 23, 24, 25]
leds = [LED(pin, initial_value=False) for pin in LED_PINS]
LIGHT_PIN = 27  # Physical Pin 13

# ==================== GLOBAL VARIABLES ====================
app = Flask(__name__)
system_mode = "auto"
manual_level = 0
running = True
# 滤波用的历史读数缓存
light_readings_history = []

# ==================== SAFE SHUTDOWN ====================
def safe_shutdown():
    global running
    print("\nShutting down system safely...")
    running = False
    for led in leds:
        led.off()
        led.close()
    print("All LEDs turned off and GPIO released")

atexit.register(safe_shutdown)

# ==================== HIGH-SENSITIVITY LIGHT READING WITH FILTER ====================
def read_light_single():
    """单次光敏读数，优化采样逻辑"""
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        # 放电清零
        GPIO.setup(LIGHT_PIN, GPIO.OUT)
        GPIO.output(LIGHT_PIN, GPIO.LOW)
        time.sleep(0.01)
        
        # 开始充电计时
        GPIO.setup(LIGHT_PIN, GPIO.IN)
        start_time = time.time()
        # 等待引脚电平拉高，超时0.1秒
        while GPIO.input(LIGHT_PIN) == GPIO.LOW and (time.time() - start_time) < 0.1:
            pass
        charge_time = time.time() - start_time
        
        # 清理GPIO
        GPIO.cleanup(LIGHT_PIN)
        
        # 转换为亮度值：0=全黑，1=全亮
        raw_brightness = 1.0 - min(1.0, charge_time * 10)
        return max(0.0, min(1.0, raw_brightness))
    except Exception as e:
        print(f"Light read error: {str(e)}")
        return 0.5

def read_light_filtered():
    """带滑动平均滤波的亮度读数，解决跳变问题"""
    global light_readings_history
    # 单次采样
    current_reading = read_light_single()
    # 加入历史缓存
    light_readings_history.append(current_reading)
    # 限制缓存长度
    if len(light_readings_history) > FILTER_SAMPLES:
        light_readings_history.pop(0)
    # 取平均值
    average_reading = sum(light_readings_history) / len(light_readings_history)
    return average_reading

# ==================== LED CONTROL WITH SENSITIVITY MAPPING ====================
def map_brightness_to_leds(brightness):
    """把亮度值映射到LED数量，放大暗光灵敏度"""
    # 1. 先把亮度限制在阈值范围内
    if brightness >= MAX_BRIGHTNESS_THRESHOLD:
        # 超过最大亮度阈值，灯全灭
        return 0
    if brightness <= MIN_BRIGHTNESS_THRESHOLD:
        # 低于最小亮度阈值，灯全亮
        return 4
    
    # 2. 把有效亮度区间（MIN~MAX）映射到0-1的范围
    normalized_brightness = (brightness - MIN_BRIGHTNESS_THRESHOLD) / (MAX_BRIGHTNESS_THRESHOLD - MIN_BRIGHTNESS_THRESHOLD)
    
    # 3. 应用灵敏度增益，反转亮度（越暗灯越亮）
    target_level = (1.0 - normalized_brightness) * SENSITIVITY_GAIN * 4
    
    # 4. 限制在0-4范围内
    return max(0, min(4, round(target_level)))

def set_leds(level):
    """设置LED亮灯数量"""
    level = max(0, min(4, int(level)))
    for i in range(4):
        leds[i].on() if i < level else leds[i].off()

# ==================== AUTO MODE THREAD ====================
def auto_loop():
    global system_mode, running
    while running:
        if system_mode == "auto":
            # 读取滤波后的亮度值
            current_brightness = read_light_filtered()
            # 映射到LED数量
            led_level = map_brightness_to_leds(current_brightness)
            # 设置LED
            set_leds(led_level)
        time.sleep(0.2)

# ==================== WEB UI TEMPLATE ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>High-Sensitivity 4-LED Light Control</title>
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
        .status { padding: 20px; background-color: #e3f2fd; border-radius: 10px; color: #1565c0; font-size: 18px; margin-bottom: 10px; }
        .sensitivity-info { font-size: 14px; color: #666; text-align: left; padding: 15px; background: #f8f9fa; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="control-card">
        <h1>High-Sensitivity 4-LED Control</h1>
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
        <div id="status" class="status">Loading system status...</div>
        <div class="sensitivity-info">
            <b>灵敏度说明：</b><br>
            - 亮度超过80%：灯全灭<br>
            - 亮度低于10%：灯全亮<br>
            - 中间区间：亮度越低，灯越亮
        </div>
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
                // Update LED indicators
                for(let i=1; i<=4; i++) {
                    document.getElementById(`led${i}`).classList.toggle('on', i <= data.leds);
                }
                // Update status text
                let statusText = '';
                if(data.mode === 'auto') {
                    statusText = `Auto Mode | Ambient Light: ${(data.light*100).toFixed(0)}% | LEDs ON: ${data.leds}/4`;
                } else {
                    statusText = `Manual Mode | LEDs ON: ${data.leds}/4`;
                }
                document.getElementById('status').textContent = statusText;
                // Update slider in manual mode
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

# ==================== WEB ROUTES ====================
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
    current_brightness = read_light_filtered()
    leds_on = 0
    if system_mode == 'auto':
        leds_on = map_brightness_to_leds(current_brightness)
    else:
        leds_on = manual_level
    return jsonify({
        'mode': system_mode,
        'light': current_brightness,
        'leds': leds_on
    })

# ==================== MAIN PROGRAM ====================
if __name__ == '__main__':
    print("="*60)
    print("High-Sensitivity 4-LED Light Control System")
    print("="*60)
    print(f"Sensitivity Gain: {SENSITIVITY_GAIN}x")
    print(f"Brightness Threshold: {MIN_BRIGHTNESS_THRESHOLD*100}% ~ {MAX_BRIGHTNESS_THRESHOLD*100}%")
    print("LEDs initialized: All OFF")
    print("Starting auto control thread...")
    threading.Thread(target=auto_loop, daemon=True).start()
    print("✅ System started successfully!")
    print("🌐 Access Web UI at: http://raspberrypi.local:5000")
    print("⏹️  Press Ctrl+C to stop the system")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
