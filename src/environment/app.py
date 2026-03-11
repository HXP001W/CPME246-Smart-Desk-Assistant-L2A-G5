# app.py Flask Web UI
from flask import Flask, render_template_string, request, jsonify
from logic import DeskController
import threading

app = Flask(__name__)
controller = DeskController()

# 启动控制器后台线程
threading.Thread(target=controller.run, daemon=True).start()

# HTML模板
HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>智能桌面助手</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { text-align: center; color: #333; }
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
    <h1>智能桌面助手</h1>
    
    <div class="card">
        <h2>当前状态</h2>
        <div class="status">模式：{{ status.mode }}</div>
        <div class="status">光照强度：{{ status.light_level }}（0-1，越亮越大）</div>
        <div class="status">温度异常：{{ status.temp_extreme }}</div>
    </div>
    
    <div class="card">
        <h2>模式切换</h2>
        <div class="btn-group">
            <button class="btn btn-black" onclick="setMode('auto')">自动模式</button>
            <button class="btn btn-black" onclick="setMode('manual')">手动模式</button>
        </div>
    </div>
    
    <div class="card">
        <h2>手动控制LED</h2>
        <div class="btn-group">
            <button class="btn btn-red" onclick="setLed('red')">红灯（太亮）</button>
            <button class="btn btn-green" onclick="setLed('green')">绿灯（正常）</button>
            <button class="btn btn-blue" onclick="setLed('blue')">蓝灯（太暗）</button>
            <button class="btn btn-gray" onclick="setLed('off')">关灯</button>
        </div>
    </div>
    
    <div class="card">
        <h2>手动控制蜂鸣器</h2>
        <div class="btn-group">
            <button class="btn btn-warning" onclick="setBuzzer(true)">开启蜂鸣器</button>
            <button class="btn btn-gray" onclick="setBuzzer(false)">关闭蜂鸣器</button>
        </div>
    </div>

    <script>
        function refresh() { fetch('/status').then(() => location.reload()); }
        function setMode(mode) {
            fetch('/mode', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mode})}).then(refresh);
        }
        function setLed(color) {
            fetch('/led', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({color})}).then(refresh);
        }
        function setBuzzer(on) {
            fetch('/buzzer', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({on})}).then(refresh);
        }
        setInterval(refresh, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML, status=controller.get_status())

@app.route('/status')
def get_status():
    return jsonify(controller.get_status())

@app.route('/mode', methods=['POST'])
def set_mode():
    controller.set_mode(request.json['mode'])
    return jsonify({'success': True})

@app.route('/led', methods=['POST'])
def set_led():
    controller.set_manual_led(request.json['color'])
    return jsonify({'success': True})

@app.route('/buzzer', methods=['POST'])
def set_buzzer():
    controller.set_manual_buzzer(request.json['on'])
    return jsonify({'success': True})

if __name__ == '__main__':
    print("[UI] 启动成功！浏览器访问：http://raspberrypi.local:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
