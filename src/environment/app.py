# 桌面环境灯光检测系统 - 主程序
# Web UI + 自动/手动双模式
from flask import Flask, render_template_string, request, jsonify
import board
import neopixel
from gpiozero import LightSensor
import threading
import time

# ==================== 硬件配置（和接线100%匹配） ====================
# 灯带配置
LED_PIN = board.D18    # GPIO18，对应树莓派12号物理引脚
NUM_LEDS = 10          # 假设你剪了10个灯，没剪的话改成60
MAX_BRIGHTNESS = 0.7   # 最大亮度70%，安全够用

# 光敏配置
LIGHT_SENSOR_PIN = 17  # GPIO17，对应树莓派11号物理引脚

# ==================== 全局变量 ====================
app = Flask(__name__)
pixels = None
light_sensor = None
mode = "auto"  # "auto" 或 "manual"
manual_brightness = 0.5  # 手动模式亮度（0-1）
running = True

# ==================== 硬件初始化 ====================
def init_hardware():
    global pixels, light_sensor
    
    # 初始化灯带
    pixels = neopixel.NeoPixel(
        LED_PIN,
        NUM_LEDS,
        brightness=0.0,
        auto_write=False,
        pixel_order=neopixel.GRB
    )
    pixels.fill((0, 0, 0))
    pixels.show()
    
    # 初始化光敏
    light_sensor = LightSensor(LIGHT_SENSOR_PIN)

# ==================== 灯带控制函数 ====================
def set_led_brightness(brightness):
    """设置灯带亮度（0-1）"""
    brightness = max(0.0, min(1.0, brightness))
    safe_brightness = brightness * MAX_BRIGHTNESS
    
    # 暖白色（GRB格式）
    red = int(255 * brightness)
    green = int(255 * brightness)
    blue = int(255 * brightness)
    
    pixels.brightness = safe_brightness
    pixels.fill((green, red, blue))
    pixels.show()

# ==================== 自动模式线程 ====================
def auto_mode_thread():
    global mode, running
    while running:
        if mode == "auto":
            # 读取光敏数值，环境越暗，灯带越亮
            light_level = light_sensor.value
            led_brightness = 1.0 - light_level
            set_led_brightness(led_brightness)
            time.sleep(0.2)
        else:
            time.sleep(0.1)

# ==================== Web UI 界面 ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>桌面环境灯光系统</title>
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
        <h1>💡 桌面环境灯光系统</h1>
        
        <div class="mode-switch">
            <button id="auto-btn" class="mode-btn active" onclick="setMode('auto')">自动模式</button>
            <button id="manual-btn" class="mode-btn" onclick="setMode('manual')">手动模式</button>
        </div>
        
        <div id="slider-container" class="slider-container">
            <label for="brightness-slider">手动亮度调节：</label>
            <input type="range" id="brightness-slider" class="slider" min="0" max="100" value="50" oninput="setManualBrightness(this.value)">
            <p>当前亮度：<span id="brightness-value">50</span>%</p>
        </div>
        
        <div id="status" class="status">
            正在加载...
        </div>
    </div>

    <script>
        let currentMode = 'auto';
        
        function setMode(mode) {
            currentMode = mode;
            
            // 更新按钮样式
            document.getElementById('auto-btn').classList.toggle('active', mode === 'auto');
            document.getElementById('manual-btn').classList.toggle('active', mode === 'manual');
            
            // 显示/隐藏滑块
            document.getElementById('slider-container').classList.toggle('active', mode === 'manual');
            
            // 发送请求到后端
            fetch('/set_mode?mode=' + mode);
        }
        
        function setManualBrightness(value) {
            document.getElementById('brightness-value').textContent = value;
            fetch('/set_manual_brightness?brightness=' + (value / 100));
        }
        
        // 定期更新状态
        function updateStatus() {
            fetch('/get_status')
                .then(response => response.json())
                .then(data => {
                    let statusText = '';
                    if (data.mode === 'auto') {
                        statusText = '🤖 自动模式 | 环境亮度：' + (data.light_level * 100).toFixed(0) + '% | 灯带亮度：' + (data.led_brightness * 100).toFixed(0) + '%';
                    } else {
                        statusText = '✋ 手动模式 | 灯带亮度：' + (data.led_brightness * 100).toFixed(0) + '%';
                    }
                    document.getElementById('status').textContent = statusText;
                });
        }
        
        // 每500ms更新一次状态
        setInterval(updateStatus, 500);
        updateStatus();
    </script>
</body>
</html>
"""

# ==================== Web 路由 ====================
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

# ==================== 主程序入口 ====================
if __name__ == '__main__':
    try:
        print("=== 桌面环境灯光系统启动中... ===")
        init_hardware()
        
        # 启动自动模式线程
        auto_thread = threading.Thread(target=auto_mode_thread)
        auto_thread.daemon = True
        auto_thread.start()
        
        print("✅ 系统启动成功！")
        print("📱 在浏览器中访问：http://raspberrypi.local:5000")
        print("按 Ctrl+C 停止系统\n")
        
        # 启动Flask Web服务器
        app.run(host='0.0.0.0', port=5000, debug=False)
        
    except KeyboardInterrupt:
        print("\n\n正在停止系统...")
        running = False
        if pixels:
            pixels.fill((0, 0, 0))
            pixels.show()
            pixels.deinit()
        print("✅ 系统已安全停止")
