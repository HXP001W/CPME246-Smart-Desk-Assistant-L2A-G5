# app.py: Flask Web UI for Smart Desk Assistant
# Full English version, provides web interface for monitoring and manual control
from flask import Flask, render_template_string, request, jsonify
from logic import DeskController

# Initialize Flask application
app = Flask(__name__)

# Initialize and start the desk controller
controller = DeskController()
controller.start()

# Web UI HTML Template (Full English)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Desk Assistant</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
        }
        body {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            text-align: center;
            color: #333;
            margin: 20px 0;
        }
        .card {
            background: white;
            margin: 15px 0;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .card h2 {
            color: #333;
            margin-bottom: 15px;
        }
        .status-item {
            font-size: 18px;
            margin: 10px 0;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 5px;
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
            border-radius: 5px;
            cursor: pointer;
            color: white;
            transition: opacity 0.2s;
        }
        .btn:hover {
            opacity: 0.9;
        }
        .btn-red { background: #dc3545; }
        .btn-green { background: #198754; }
        .btn-blue { background: #0d6efd; }
        .btn-gray { background: #6c757d; }
        .btn-dark { background: #212529; }
        .btn-warning { background: #ffc107; color: #212529; }
    </style>
</head>
<body>
    <h1>Smart Desk Assistant</h1>
    
    <!-- System Status Card -->
    <div class="card">
        <h2>Current System Status</h2>
        <div class="status-item">Operation Mode: {{ status.mode }}</div>
        <div class="status-item">Ambient Light Level: {{ status.light_level }} (0 = Dark, 1 = Bright)</div>
        <div class="status-item">Temperature Abnormal: {{ status.temp_extreme }}</div>
    </div>
    
    <!-- Mode Switch Card -->
    <div class="card">
        <h2>Operation Mode Switch</h2>
        <div class="btn-group">
            <button class="btn btn-dark" onclick="setMode('auto')">Auto Mode</button>
            <button class="btn btn-dark" onclick="setMode('manual')">Manual Mode</button>
        </div>
    </div>
    
    <!-- Manual LED Control Card -->
    <div class="card">
        <h2>Manual LED Control</h2>
        <div class="btn-group">
            <button class="btn btn-red" onclick="setLed('red')">Red (Too Bright)</button>
            <button class="btn btn-green" onclick="setLed('green')">Green (Normal)</button>
            <button class="btn btn-blue" onclick="setLed('blue')">Blue (Too Dark)</button>
            <button class="btn btn-gray" onclick="setLed('off')">Turn Off</button>
        </div>
    </div>
    
    <!-- Manual Buzzer Control Card -->
    <div class="card">
        <h2>Manual Buzzer Control</h2>
        <div class="btn-group">
            <button class="btn btn-warning" onclick="setBuzzer(true)">Turn On Buzzer</button>
            <button class="btn btn-gray" onclick="setBuzzer(false)">Turn Off Buzzer</button>
        </div>
    </div>

    <script>
        // Auto-refresh page every 3 seconds to update status
        function refreshStatus() {
            fetch('/status').then(() => location.reload());
        }
        setInterval(refreshStatus, 3000);

        // Switch operation mode
        function setMode(mode) {
            fetch('/mode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({mode: mode})
            }).then(refreshStatus);
        }

        // Set LED color
        function setLed(color) {
            fetch('/led', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({color: color})
            }).then(refreshStatus);
        }

        // Control buzzer
        function setBuzzer(active) {
            fetch('/buzzer', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({on: active})
            }).then(refreshStatus);
        }
    </script>
</body>
</html>
"""

# Web Routes
@app.route('/')
def index():
    """Main page: display system status and control UI"""
    return render_template_string(HTML_TEMPLATE, status=controller.get_system_status())

@app.route('/status')
def get_status():
    """API endpoint: get current system status in JSON format"""
    return jsonify(controller.get_system_status())

@app.route('/mode', methods=['POST'])
def set_mode():
    """API endpoint: switch system operation mode"""
    data = request.get_json()
    controller.set_mode(data['mode'])
    return jsonify({'success': True})

@app.route('/led', methods=['POST'])
def set_led():
    """API endpoint: set LED color in manual mode"""
    data = request.get_json()
    controller.set_manual_led(data['color'])
    return jsonify({'success': True})

@app.route('/buzzer', methods=['POST'])
def set_buzzer():
    """API endpoint: control buzzer on/off in manual mode"""
    data = request.get_json()
    controller.set_manual_buzzer(data['on'])
    return jsonify({'success': True})

# Program entry point
if __name__ == '__main__':
    print("[UI] Web server started successfully!")
    print("[UI] Access the UI in your browser at: http://raspberrypi.local:5000")
    # Run web server on all network interfaces, port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
