# app.py Flask Web UI 界面层
from flask import Flask, render_template_string, request, jsonify
from logic import EnvController
import threading

# 创建Flask应用
app = Flask(__name__)

# 全局变量：环境控制器实例
env_controller = None

# Web UI HTML模板（优化无刷新状态更新）
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能环境控制系统</title>
    <style>
        * { 
            box-sizing: border-box; 
            margin: 0; 
            padding: 0; 
        }
        body { 
            font-family: Arial, sans-serif; 
            max-width: 800px; 
            margin: 0 auto; 
            padding: 20px; 
            background-color: #fafafa;
        }
        h1 { 
            text-align: center; 
            margin: 20px 0; 
            color: #2c3e50; 
        }
        .card { 
            margin: 15px 0; 
            padding: 20px; 
            border: 1px solid #eee; 
            border-radius: 10px; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            background-color: white;
        }
        .card h2 {
            margin-bottom: 15px;
            color: #34495e;
            font-size: 20px;
        }
        .status { 
            font-size: 18px; 
            margin: 10px 0; 
            padding: 12px 15px; 
            background: #f8f9fa; 
            border-radius: 6px;
            line-height: 1.5;
        }
        .btn-group { 
            display: flex; 
            flex-wrap: wrap; 
            gap: 10px; 
            margin: 10px 0; 
        }
        .btn { 
            padding: 12px 24px; 
            font-size: 16px; 
            border: none; 
            border-radius: 6px; 
            cursor: pointer; 
            color: white; 
            transition: opacity 0.2s;
        }
        .btn:hover {
            opacity: 0.85;
        }
        .btn-red { background: #e74c3c; }
        .btn-green { background: #27ae60; }
        .btn-blue { background: #3498db; }
        .btn-gray { background: #7f8c8d; }
        .btn-black { background: #2c3e50; }
        .btn-warning { background: #f39c12; }
    </style>
</head>
<body>
    <h1>智能环境控制系统</h1>
    
    <!-- 系统实时状态卡片 -->
    <div class="card">
        <h2>当前系统状态</h2>
        <div class="status" id="status-mode">运行模式：{{ status.mode }}</div>
        <div class="status" id="status-light">光照强度：{{ status.light_level }}（0-1，越亮数值越大）</div>
        <div class="status" id="status-temp">温度过高：{{ status.temp_high }}</div>
    </div>
    
    <!-- 模式切换卡片 -->
    <div class="card">
        <h2>运行模式切换</h2>
        <div class="btn-group">
            <button class="btn btn-black" onclick="setMode('auto')">自动模式</button>
            <button class="btn btn-black" onclick="setMode('manual')">手动模式</button>
        </div>
    </div>
    
    <!-- 手动控制LED卡片 -->
    <div class="card">
        <h2>手动控制LED灯（仅手动模式生效）</h2>
        <div class="btn-group">
            <button class="btn btn-red" onclick="setLed('red')">红灯</button>
            <button class="btn btn-green" onclick="setLed('green')">绿灯</button>
            <button class="btn btn-blue" onclick="setLed('blue')">蓝灯</button>
            <button class="btn btn-gray" onclick="setLed('off')">关闭灯光</button>
        </div>
    </div>
    
    <!-- 手动控制蜂鸣器卡片 -->
    <div class="card">
        <h2>手动控制蜂鸣器（仅手动模式生效）</h2>
        <div class="btn-group">
            <button class="btn btn-warning" onclick="setBuzzer(true)">开启蜂鸣器</button>
            <button class="btn btn-gray" onclick="setBuzzer(false)">关闭蜂鸣器</button>
        </div>
    </div>

    <script>
        // 无刷新更新页面状态
        function refreshStatus() {
            fetch('/status')
                .then(res => {
                    if (!res.ok) throw new Error('请求失败');
                    return res.json();
                })
                .then(status => {
                    document.getElementById('status-mode').textContent = `运行模式：${status.mode}`;
                    document.getElementById('status-light').textContent = `光照强度：${status.light_level}（0-1，越亮数值越大）`;
                    document.getElementById('status-temp').textContent = `温度过高：${status.temp_high}`;
                })
                .catch(err => console.error('状态刷新失败：', err));
        }

        // 切换系统运行模式
        function setMode(mode) {
            fetch('/mode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({mode: mode})
            })
            .then(res => res.json())
            .then(() => refreshStatus())
            .catch(err => console.error('模式切换失败：', err));
        }

        // 手动设置LED颜色
        function setLed(color) {
            fetch('/led', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({color: color})
            })
            .then(res => res.json())
            .then(() => refreshStatus())
            .catch(err => console.error('LED设置失败：', err));
        }

        // 手动设置蜂鸣器开关
        function setBuzzer(on) {
            fetch('/buzzer', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({on: on})
            })
            .then(res => res.json())
            .then(() => refreshStatus())
            .catch(err => console.error('蜂鸣器设置失败：', err));
        }

        // 页面加载完成后立即刷新状态，之后每3秒自动刷新
        window.onload = refreshStatus;
        setInterval(refreshStatus, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """主页：渲染Web UI界面"""
    return render_template_string(HTML_TEMPLATE, status=env_controller.get_status())

@app.route('/status')
def get_status():
    """API：获取系统实时状态"""
    return jsonify(env_controller.get_status())

@app.route('/mode', methods=['POST'])
def set_mode():
    """API：切换系统运行模式"""
    data = request.json
    env_controller.set_mode(data['mode'])
    return jsonify({'success': True})

@app.route('/led', methods=['POST'])
def set_led():
    """API：手动设置LED颜色"""
    data = request.json
    env_controller.set_manual_led(data['color'])
    return jsonify({'success': True})

@app.route('/buzzer', methods=['POST'])
def set_buzzer():
    """API：手动开关蜂鸣器"""
    data = request.json
    env_controller.set_manual_buzzer(data['on'])
    return jsonify({'success': True})

if __name__ == '__main__':
    try:
        # 初始化环境控制器
        print("[系统] 正在初始化环境控制器...")
        env_controller = EnvController()

        # 启动控制器后台线程
        controller_thread = threading.Thread(target=env_controller.run, daemon=True)
        controller_thread.start()

        # 启动Web服务
        print("[系统] Web服务器已启动！")
        print("[系统] 请在同一局域网的浏览器访问：http://树莓派IP地址:5000")
        app.run(host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        print(f"[系统] 启动失败！错误信息：{e}")
        if env_controller is not None:
            env_controller.stop()
