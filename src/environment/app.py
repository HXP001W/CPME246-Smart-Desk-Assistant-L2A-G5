# app.py Flask Web UI，已适配新需求
from flask import Flask, render_template_string, request, jsonify
from logic import EnvController
import threading

# 创建Flask应用
app = Flask(__name__)

# 初始化环境控制器
env_controller = EnvController()

# 启动控制器后台线程（不阻塞Web服务）
controller_thread = threading.Thread(target=env_controller.run, daemon=True)
controller_thread.start()

# Web UI HTML模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>智能环境控制系统</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { text-align: center; margin: 20px 0; color: #333; }
        .card { margin: 15px 0; padding: 20px; border: 1px solid #eee; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .status { font-size: 18px; margin: 10px 0; padding: 10px; background: #f5f5f5; border-radius: 5px; }
        .btn-group { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0; }
        .btn { padding: 12px 24px; font-size: 16px; border: none; border-radius: 5px; cursor: pointer; color: white; }
        .btn-red { background: #ff4444; }
        .btn-green { background: #4CAF50; }
        .btn-blue { background: #2196F3; }
        .btn-gray { background: #666; }
        .btn-black { background: #333; }
        .btn-warning { background: #ff9800; }
    </style>
</head>
<body>
    <h1>智能环境控制系统</h1>
    
    <!-- 系统状态 -->
    <div class="card">
        <h2>当前状态</h2>
        <div class="status">运行模式：{{ status.mode }}</div>
        <div class="status">光照强度：{{ status.light_level }}（0-1，越亮数值越大）</div>
        <div class="status">温度过高：{{ status.temp_high }}</div>
    </div>
    
    <!-- 模式切换 -->
    <div class="card">
        <h2>模式切换</h2>
        <div class="btn-group">
            <button class="btn btn-black" onclick="setMode('auto')">自动模式</button>
            <button class="btn btn-black" onclick="setMode('manual')">手动模式</button>
        </div>
    </div>
    
    <!-- 手动控制LED -->
    <div class="card">
        <h2>手动控制LED</h2>
        <div class="btn-group">
            <button class="btn btn-red" onclick="setLed('red')">红灯</button>
            <button class="btn btn-green" onclick="setLed('green')">绿灯</button>
            <button class="btn btn-blue" onclick="setLed('blue')">蓝灯</button>
            <button class="btn btn-gray" onclick="setLed('off')">关灯</button>
        </div>
    </div>
    
    <!-- 手动控制蜂鸣器 -->
    <div class="card">
        <h2>手动控制蜂鸣器</h2>
        <div class="btn-group">
            <button class="btn btn-warning" onclick="setBuzzer(true)">开启蜂鸣器</button>
            <button class="btn btn-gray" onclick="setBuzzer(false)">关闭蜂鸣器</button>
        </div>
    </div>

    <script>
        // 刷新状态
        function refreshStatus() {
            fetch('/status').then(res => res.json()).then(() => location.reload());
        }
        // 切换模式
        function setMode(mode) {
            fetch('/mode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({mode: mode})
            }).then(refreshStatus);
        }
        // 设置LED
        function setLed(color) {
            fetch('/led', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({color: color})
            }).then(refreshStatus);
        }
        // 设置蜂鸣器
        function setBuzzer(on) {
            fetch('/buzzer', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({on: on})
            }).then(refreshStatus);
        }
        // 每3秒自动刷新状态
        setInterval(refreshStatus, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """主页，显示UI"""
    return render_template_string(HTML_TEMPLATE, status=env_controller.get_status())

@app.route('/status')
def get_status():
    """获取系统状态API"""
    return jsonify(env_controller.get_status())

@app.route('/mode', methods=['POST'])
def set_mode():
    """切换模式API"""
    data = request.json
    env_controller.set_mode(data['mode'])
    return jsonify({'success': True})

@app.route('/led', methods=['POST'])
def set_led():
    """设置LED API"""
    data = request.json
    env_controller.set_manual_led(data['color'])
    return jsonify({'success': True})

@app.route('/buzzer', methods=['POST'])
def set_buzzer():
    """设置蜂鸣器 API"""
    data = request.json
    env_controller.set_manual_buzzer(data['on'])
    return jsonify({'success': True})

if __name__ == '__main__':
    # 启动Web服务，监听所有网络接口，端口5000
    print("[UI] Web服务器已启动，浏览器访问：http://树莓派IP:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
