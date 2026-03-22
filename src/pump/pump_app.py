# 电池盒版 潜水泵Web控制系统
from flask import Flask, render_template_string, request
from gpiozero import OutputDevice
import atexit

# ==================== 硬件配置（和接线完全对应，不用改） ====================
PUMP_PIN = 18  # 对应树莓派11号物理引脚，接继电器IN
# 光耦继电器默认低电平触发，点击没反应就改成 True
pump = OutputDevice(PUMP_PIN, active_high=False, initial_value=False)

# ==================== 全局变量 ====================
app = Flask(__name__)

# ==================== 安全关机机制 ====================
def safe_shutdown():
    print("\n正在安全关机...")
    pump.off()
    pump.close()
    print("✅ 水泵已关闭，GPIO已释放")

atexit.register(safe_shutdown)

# ==================== Web UI界面 ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>潜水泵电池版控制</title>
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
            padding: 60px 40px;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            max-width: 500px;
            width: 100%;
            text-align: center;
        }
        h1 {
            color: #2d3748;
            margin-bottom: 50px;
            font-size: 32px;
        }
        .status-display {
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 50px;
            font-size: 24px;
            font-weight: bold;
        }
        .status-on {
            background-color: #d4edda;
            color: #155724;
        }
        .status-off {
            background-color: #f8d7da;
            color: #721c24;
        }
        .control-button {
            width: 100%;
            padding: 30px;
            font-size: 28px;
            font-weight: bold;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            color: white;
            transition: all 0.2s ease;
        }
        .button-on {
            background-color: #28a745;
        }
        .button-on:hover {
            background-color: #218838;
        }
        .button-off {
            background-color: #dc3545;
        }
        .button-off:hover {
            background-color: #c82333;
        }
    </style>
</head>
<body>
    <div class="control-card">
        <h1>潜水泵电池版控制</h1>
        
        <div id="status" class="status-display status-off">
            水泵状态：已关闭
        </div>
        
        <button id="control-btn" class="control-button button-on" onclick="togglePump()">
            启动水泵
        </button>
    </div>

    <script>
        let pumpIsOn = false;
        
        function togglePump() {
            pumpIsOn = !pumpIsOn;
            updateUI();
            fetch('/toggle?state=' + (pumpIsOn ? 'on' : 'off'));
        }
        
        function updateUI() {
            const statusDiv = document.getElementById('status');
            const controlBtn = document.getElementById('control-btn');
            
            if (pumpIsOn) {
                statusDiv.textContent = '水泵状态：运行中';
                statusDiv.classList.remove('status-off');
                statusDiv.classList.add('status-on');
                controlBtn.textContent = '关闭水泵';
                controlBtn.classList.remove('button-on');
                controlBtn.classList.add('button-off');
            } else {
                statusDiv.textContent = '水泵状态：已关闭';
                statusDiv.classList.remove('status-on');
                statusDiv.classList.add('status-off');
                controlBtn.textContent = '启动水泵';
                controlBtn.classList.remove('button-off');
                controlBtn.classList.add('button-on');
            }
        }
        
        // 页面加载同步状态
        fetch('/status')
            .then(response => response.json())
            .then(data => {
                pumpIsOn = data.is_on;
                updateUI();
            });
    </script>
</body>
</html>
"""

# ==================== Web路由 ====================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/toggle')
def toggle_pump():
    state = request.args.get('state', 'off')
    pump.on() if state == 'on' else pump.off()
    return "OK"

@app.route('/status')
def get_status():
    return {'is_on': pump.is_active}

# ==================== 主程序入口 ====================
if __name__ == '__main__':
    print("="*50)
    print("电池版潜水泵控制系统 启动成功")
    print("="*50)
    print("✅ 光耦继电器初始化完成，GPIO17")
    print("✅ 水泵初始状态：已关闭")
    print("🌐 Web控制地址：http://raspberrypi.local:5000")
    print("⏹️  按Ctrl+C停止系统")
    print("="*50 + "\n")
    
    # 启动Flask服务
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
