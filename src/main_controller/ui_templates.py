START_MENU_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Smart Desk Assistant</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #edf2f7 0%, #dbeafe 100%);
            padding: 20px;
        }
        .panel {
            width: 100%;
            max-width: 760px;
            background: #ffffff;
            border-radius: 16px;
            padding: 38px;
            box-shadow: 0 10px 35px rgba(15, 23, 42, 0.15);
        }
        h1 { color: #1f2937; font-size: 34px; margin-bottom: 10px; }
        p { color: #4b5563; margin-bottom: 26px; line-height: 1.5; }
        .actions { display: grid; grid-template-columns: 1fr; gap: 14px; margin-bottom: 26px; }
        button, a.button-link {
            width: 100%;
            border: none;
            border-radius: 12px;
            padding: 16px 20px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            text-align: center;
            text-decoration: none;
            transition: transform 0.15s ease, opacity 0.15s ease;
        }
        button:hover, a.button-link:hover { transform: translateY(-1px); }
        .btn-primary { background: #0f766e; color: white; }
        .btn-secondary { background: #1d4ed8; color: white; }
        .status-box {
            background: #f8fafc;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 18px;
        }
        .status-title { font-weight: 700; color: #111827; margin-bottom: 8px; }
        .status-row { color: #374151; margin-bottom: 5px; }
        .status-row:last-child { margin-bottom: 0; }
        @media (max-width: 600px) {
            .panel { padding: 24px; }
            h1 { font-size: 28px; }
        }
    </style>
</head>
<body>
    <div class="panel">
        <h1>Lock in... or Else</h1>
        

        <div class="actions">
            <button id="start-btn" class="btn-primary" onclick="startFaceRecognition()">START</button>
            <a class="button-link btn-secondary" href="/debug">Debug Mode</a>
        </div>

        <div class="status-box">
            <div class="status-title">Facial Recognition Status</div>
            <div class="status-row" id="status-text">Loading status...</div>
            <div class="status-row" id="status-started"></div>
            <div class="status-row" id="status-finished"></div>
        </div>
    </div>

    <script>
        let shouldAutoNavigate = false;
        let startRequestInFlight = false;

        function renderStatus(data) {
            document.getElementById('status-text').textContent = `State: ${data.status} | ${data.message}`;
            document.getElementById('status-started').textContent = data.last_started_at ? `Last started: ${data.last_started_at}` : '';
            document.getElementById('status-finished').textContent = data.last_finished_at ? `Last finished: ${data.last_finished_at}` : '';

            if (!startRequestInFlight && shouldAutoNavigate && data.status === 'completed' && data.next_route) {
                shouldAutoNavigate = false;
                window.location.href = data.next_route;
            }
        }

        function refreshStatus() {
            fetch('/face_recognition_status')
                .then(response => response.json())
                .then(renderStatus)
                .catch(() => {
                    document.getElementById('status-text').textContent = 'State: unknown | Unable to fetch status';
                });
        }

        function startFaceRecognition() {
            if (startRequestInFlight) {
                return;
            }

            startRequestInFlight = true;
            shouldAutoNavigate = false;
            const startBtn = document.getElementById('start-btn');
            startBtn.disabled = true;
            startBtn.style.opacity = '0.7';

            fetch('/start_face_recognition', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    startRequestInFlight = false;
                    shouldAutoNavigate = true;
                    renderStatus(data);
                })
                .catch(() => {
                    startRequestInFlight = false;
                    shouldAutoNavigate = false;
                    document.getElementById('status-text').textContent = 'State: error | Failed to start face recognition';
                })
                .finally(() => {
                    startBtn.disabled = false;
                    startBtn.style.opacity = '1';
                });
        }

        refreshStatus();
        setInterval(refreshStatus, 1500);
    </script>
</body>
</html>
"""

USER_ONBOARDING_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>User Onboarding</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #eef2ff; min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
        .card { max-width: 760px; width: 100%; background: white; border-radius: 14px; padding: 34px; box-shadow: 0 10px 28px rgba(0, 0, 0, 0.12); }
        h1 { color: #1f2937; margin-bottom: 10px; font-size: 30px; }
        p { color: #4b5563; margin-bottom: 20px; }
        .actions { display: grid; gap: 12px; margin-top: 18px; }
        .btn { display: inline-block; text-align: center; width: 100%; padding: 14px; border-radius: 10px; border: none; text-decoration: none; font-weight: 600; cursor: pointer; }
        .btn-primary { background: #0f766e; color: white; }
        .btn-secondary { background: #2563eb; color: white; }
        .btn-link { background: #e5e7eb; color: #111827; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Welcome to Lock in... or Else</h1>
        <p>It looks like you aren't registered. Register a new user or continue as guest.</p>
        <div class="actions">
            <form method="post" action="/user/continue_guest">
                <button class="btn btn-primary" type="submit">Continue as Guest</button>
            </form>
            <a class="btn btn-secondary" href="/user/register">Register New User</a>
            <a class="btn btn-link" href="/">Back to Start Menu</a>
        </div>
    </div>
</body>
</html>
"""

USER_REGISTER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Register User</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #f3f4f6; min-height: 100vh; padding: 20px; }
        .wrap { max-width: 780px; margin: 0 auto; }
        .card { margin-top: 24px; background: white; border-radius: 12px; padding: 28px; box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
        h1 { margin-bottom: 10px; color: #1f2937; }
        p { color: #4b5563; margin-bottom: 16px; }
        .msg { background: #ecfeff; border: 1px solid #99f6e4; color: #115e59; padding: 10px 12px; border-radius: 8px; margin-bottom: 14px; }
        .err { background: #fef2f2; border-color: #fecaca; color: #991b1b; }
        label { display: block; margin-bottom: 6px; color: #111827; font-weight: 600; }
        input { width: 100%; border: 1px solid #d1d5db; border-radius: 8px; padding: 10px; margin-bottom: 14px; }
        .btn { border: none; border-radius: 8px; padding: 12px 16px; font-weight: 600; cursor: pointer; margin-right: 8px; }
        .btn-save { background: #0f766e; color: white; }
        .btn-cam { background: #2563eb; color: white; }
        .btn-back { background: #e5e7eb; color: #111827; text-decoration: none; display: inline-block; }
        .camera-wrap { margin: 14px 0 16px; padding: 12px; border: 1px solid #d1d5db; border-radius: 10px; background: #f9fafb; }
        video { width: 100%; border-radius: 8px; background: #111827; margin-bottom: 10px; }
        .photo-preview { width: 100%; border-radius: 8px; border: 1px solid #d1d5db; margin-top: 8px; display: none; }
        .small { color: #6b7280; font-size: 13px; margin-top: 8px; }
        .cam-status { margin-top: 8px; padding: 8px 10px; border-radius: 8px; font-size: 13px; }
        .cam-status.ok { background: #ecfeff; color: #0f766e; border: 1px solid #99f6e4; }
        .cam-status.warn { background: #fff7ed; color: #9a3412; border: 1px solid #fdba74; }
        .cam-status.err { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
    </style>
</head>
<body>
    <div class="wrap">
        <div class="card">
            <h1>Register New User</h1>
            {% if message %}
            <div class="msg{% if is_error %} err{% endif %}">{{ message }}</div>
            {% endif %}
            <form method="post" action="/user/register" enctype="multipart/form-data">
                <label>Name</label>
                <input name="name" required>
                <label>Focus time (minutes)</label>
                <input name="focusTime" type="number" min="1" required>
                <label>Break time (minutes)</label>
                <input name="breakTime" type="number" min="1" required>

                <label>Profile photo</label>
                <div class="camera-wrap">
                    <video id="camera" autoplay playsinline></video>
                    <button class="btn btn-cam" type="button" onclick="startCamera()">Open Camera</button>
                    <button class="btn btn-cam" type="button" onclick="capturePhoto()">Capture Photo</button>
                    <button class="btn btn-cam" type="button" onclick="captureFromDeviceCamera()">Use Device Camera (Server)</button>
                    <input id="photo-data" name="photo_data" type="hidden">
                    <canvas id="snapshot-canvas" style="display:none;"></canvas>
                    <img id="photo-preview" class="photo-preview" alt="Captured preview">
                    <div id="cam-status" class="cam-status warn">Camera not started yet.</div>
                    <div class="small">If browser camera is blocked, click "Use Device Camera (Server)" to capture from Raspberry Pi camera directly.</div>
                </div>
                <label>Fallback: upload a photo file</label>
                <input id="photo-file" name="photo_file" type="file" accept="image/*">

                <button class="btn btn-save" type="submit">Register</button>
                <a class="btn btn-back" href="/user/onboarding">Cancel</a>
            </form>
        </div>
    </div>

    <script>
        let cameraStream = null;

        function setCamStatus(message, level) {
            const statusEl = document.getElementById('cam-status');
            statusEl.textContent = message;
            statusEl.className = `cam-status ${level}`;
        }

        function describeCameraError(err) {
            if (!err) return 'Unknown camera error.';
            if (err.name === 'NotAllowedError') return 'Camera permission denied. Allow camera access and retry.';
            if (err.name === 'NotFoundError') return 'No camera device was found.';
            if (err.name === 'NotReadableError') return 'Camera is busy or unavailable to this browser.';
            if (err.name === 'SecurityError') return 'Camera blocked by browser security policy.';
            if (err.name === 'OverconstrainedError') return 'Requested camera constraints are not supported.';
            return `Camera error: ${err.name || 'unknown'}`;
        }

        async function startCamera() {
            try {
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                    setCamStatus('Browser camera API not available here. Use photo upload fallback.', 'err');
                    return;
                }

                if (!window.isSecureContext && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
                    setCamStatus(`Camera prompt is blocked on insecure remote HTTP (${location.origin}). Use HTTPS, open from localhost/127.0.0.1, or use upload fallback.`, 'err');
                    return;
                }

                cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
                const video = document.getElementById('camera');
                video.srcObject = cameraStream;
                setCamStatus('Camera opened. Click Capture Photo when ready.', 'ok');
            } catch (err) {
                setCamStatus(describeCameraError(err), 'err');
            }
        }

        function capturePhoto() {
            const video = document.getElementById('camera');
            if (!video.srcObject) {
                setCamStatus('Open camera first, or use photo upload fallback.', 'warn');
                return;
            }

            const canvas = document.getElementById('snapshot-canvas');
            const context = canvas.getContext('2d');
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            context.drawImage(video, 0, 0, canvas.width, canvas.height);

            const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
            document.getElementById('photo-data').value = dataUrl;

            const preview = document.getElementById('photo-preview');
            preview.src = dataUrl;
            preview.style.display = 'block';
            setCamStatus('Photo captured successfully.', 'ok');
        }

        async function captureFromDeviceCamera() {
            try {
                setCamStatus('Capturing from device camera...', 'warn');
                const response = await fetch('/api/device_camera_snapshot', { method: 'POST' });
                const payload = await response.json();

                if (!response.ok || !payload.ok) {
                    throw new Error(payload.error || `HTTP ${response.status}`);
                }

                const dataUrl = payload.photo_data;
                document.getElementById('photo-data').value = dataUrl;

                const preview = document.getElementById('photo-preview');
                preview.src = dataUrl;
                preview.style.display = 'block';

                setCamStatus('Captured from device camera successfully.', 'ok');
            } catch (err) {
                setCamStatus(`Device camera capture failed: ${err.message || err}`, 'err');
            }
        }

        document.querySelector('form[action="/user/register"]').addEventListener('submit', function(event) {
            const hasCapturedPhoto = !!document.getElementById('photo-data').value;
            const hasUploadedPhoto = !!document.getElementById('photo-file').value;
            if (!hasCapturedPhoto && !hasUploadedPhoto) {
                event.preventDefault();
                setCamStatus('Please capture a photo or upload a photo file before submitting.', 'err');
            }
        });

        // Require explicit user click to avoid silent browser blocking behavior.
        window.addEventListener('load', function() {
            setCamStatus('Click Open Camera to request browser permission.', 'warn');
        });

        window.addEventListener('beforeunload', function() {
            if (cameraStream) {
                cameraStream.getTracks().forEach(track => track.stop());
            }
        });
    </script>
</body>
</html>
"""

USER_MENU_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>User Menu</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #eff6ff; min-height: 100vh; padding: 20px; }
        .wrap { max-width: 760px; margin: 0 auto; }
        .card { margin-top: 24px; background: white; border-radius: 12px; padding: 28px; box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
        h1 { color: #1f2937; margin-bottom: 14px; }
        .meta { color: #374151; margin-bottom: 8px; }
        .actions { margin-top: 16px; display: grid; gap: 10px; }
        .btn { display: inline-block; text-align: center; width: 100%; padding: 13px; border-radius: 9px; text-decoration: none; font-weight: 600; }
        .btn-1 { background: #0f766e; color: white; }
        .btn-2 { background: #2563eb; color: white; }
        .btn-3 { background: #9333ea; color: white; }
        .btn-4 { background: #e5e7eb; color: #111827; }
    </style>
</head>
<body>
    <div class="wrap">
        <div class="card">
            <h1>Welcome, {{ user.name }}!</h1>
            <div class="meta">Current rhythm: Focus time - {{ user.focusTime }} minutes, Break time - {{ user.breakTime }} minutes.</div>
            <div class="meta">Reports available: {{ user.reportCount }}</div>

            <div class="actions">
                <a class="btn btn-1" href="/user/focus_session">Start Focus Session</a>
                <a class="btn btn-2" href="/user/settings">Settings</a>
                <a class="btn btn-3" href="/user/sessions">View Reports</a>
                <a class="btn btn-4" href="/">Back to Start Menu</a>
            </div>
        </div>
    </div>
</body>
</html>
"""

USER_SETTINGS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>User Settings</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #f8fafc; min-height: 100vh; padding: 20px; }
        .wrap { max-width: 860px; margin: 0 auto; }
        .card { margin-top: 20px; background: white; border-radius: 12px; padding: 26px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
        h1 { margin-bottom: 14px; color: #111827; }
        h2 { margin: 16px 0 10px; color: #1f2937; font-size: 20px; }
        .msg { background: #ecfeff; border: 1px solid #99f6e4; color: #115e59; padding: 10px 12px; border-radius: 8px; margin-bottom: 12px; }
        .err { background: #fef2f2; border-color: #fecaca; color: #991b1b; }
        form { margin-bottom: 10px; }
        label { display: block; margin-bottom: 6px; font-weight: 600; color: #111827; }
        input { width: 100%; border: 1px solid #d1d5db; border-radius: 8px; padding: 10px; margin-bottom: 10px; }
        .row { display: grid; gap: 10px; grid-template-columns: 1fr 1fr; }
        .btn { border: none; border-radius: 8px; padding: 10px 14px; font-weight: 700; cursor: pointer; }
        .btn-save { background: #0f766e; color: white; }
        .btn-danger { background: #dc2626; color: white; }
        .btn-back { background: #e5e7eb; color: #111827; text-decoration: none; display: inline-block; margin-top: 8px; }
    </style>
</head>
<body>
    <div class="wrap">
        <div class="card">
            <h1>Settings Menu</h1>
            {% if message %}
            <div class="msg{% if is_error %} err{% endif %}">{{ message }}</div>
            {% endif %}

            <h2>Update Focus/Break Time</h2>
            <form method="post" action="/user/settings/update_timing">
                <div class="row">
                    <div>
                        <label>Focus time (minutes)</label>
                        <input name="focusTime" type="number" min="1" value="{{ user.focusTime }}" required>
                    </div>
                    <div>
                        <label>Break time (minutes)</label>
                        <input name="breakTime" type="number" min="1" value="{{ user.breakTime }}" required>
                    </div>
                </div>
                <button class="btn btn-save" type="submit">Save Times</button>
            </form>

            <h2>Delete Profile</h2>
            <form method="post" action="/user/settings/delete_profile">
                <button class="btn btn-danger" type="submit">Delete Profile</button>
            </form>

            <a class="btn btn-back" href="/">Back to Start Menu</a>
        </div>
    </div>
</body>
</html>
"""

USER_SESSIONS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Your Sessions</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #f1f5f9; min-height: 100vh; padding: 20px; }
        .wrap { max-width: 900px; margin: 0 auto; }
        .card { margin-top: 24px; background: white; border-radius: 12px; padding: 26px; box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
        h1 { color: #111827; margin-bottom: 20px; }
        .error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 12px; border-radius: 8px; margin-bottom: 16px; }
        .session-list { margin: 20px 0; }
        .session-item { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-bottom: 12px; cursor: pointer; transition: all 0.2s; text-decoration: none; display: block; }
        .session-item:hover { background: #f3f4f6; border-color: #d1d5db; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .session-header { display: flex; justify-content: space-between; align-items: center; }
        .session-id { font-weight: 700; color: #111827; font-size: 16px; }
        .session-meta { display: flex; gap: 20px; margin-top: 8px; font-size: 14px; color: #6b7280; }
        .btn { display: inline-block; text-decoration: none; background: #e5e7eb; color: #111827; padding: 10px 14px; border-radius: 8px; font-weight: 700; margin-top: 16px; }
        .muted { color: #6b7280; }
    </style>
</head>
<body>
    <div class="wrap">
        <div class="card">
            <h1>Your Sessions</h1>
            {% if error %}
            <div class="error">Error: {{ error }}</div>
            {% endif %}
            {% if sessions %}
            <div class="session-list">
                {% for session_id in sessions %}
                <a href="/user/session/{{ session_id }}/report" class="session-item">
                    <div class="session-header">
                        <div class="session-id">{{ session_id }}</div>
                    </div>
                </a>
                {% endfor %}
            </div>
            {% else %}
            <p class="muted">No sessions recorded yet.</p>
            {% endif %}
            <a class="btn" href="/user/menu">Back to User Menu</a>
        </div>
    </div>
</body>
</html>
"""

USER_SESSION_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Session Report</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #f1f5f9; min-height: 100vh; padding: 20px; }
        .wrap { max-width: 900px; margin: 0 auto; }
        .card { margin-top: 24px; background: white; border-radius: 12px; padding: 26px; box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
        h1 { color: #111827; margin-bottom: 20px; }
        .error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 12px; border-radius: 8px; margin-bottom: 16px; }
        .report-card { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
        .report-card h2 { color: #111827; margin-bottom: 16px; font-size: 18px; }
        .report-content { }
        .info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin-bottom: 20px; }
        .info-item { background: white; border: 1px solid #d1d5db; border-radius: 6px; padding: 12px; }
        .label { font-weight: 700; color: #374151; display: block; margin-bottom: 4px; }
        .value { color: #111827; font-size: 16px; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        th, td { text-align: left; padding: 10px; border-bottom: 1px solid #e5e7eb; }
        th { background: #f3f4f6; font-weight: 700; color: #111827; }
        td.center { text-align: center; }
        .section { margin-top: 20px; }
        .section h2 { color: #111827; margin-bottom: 12px; font-size: 16px; }
        .muted { color: #6b7280; }
        .btn { display: inline-block; text-decoration: none; background: #e5e7eb; color: #111827; padding: 10px 14px; border-radius: 8px; font-weight: 700; margin-top: 16px; }
        
        @media (max-width: 600px) {
            .info-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="wrap">
        <div class="card">
            <h1>Session Report</h1>
            {% if error %}
            <div class="error">Error: {{ error }}</div>
            {% else %}
            {{ report_html | safe }}
            {% endif %}
            <a class="btn" href="/user/sessions">Back to Sessions</a>
            <a class="btn" href="/">Back to Start Menu</a>
        </div>
    </div>
</body>
</html>
"""

USER_FOCUS_SESSION_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Focus Session</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #ecfeff; min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
        .card { background: white; border-radius: 12px; padding: 28px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
        h1 { margin-bottom: 12px; color: #111827; }
        p { color: #374151; margin-bottom: 10px; }
        .msg { background: #ecfeff; border: 1px solid #99f6e4; color: #115e59; padding: 10px 12px; border-radius: 8px; margin: 10px 0; }
        .warn { background: #fff7ed; border-color: #fdba74; color: #9a3412; }
        .err { background: #fef2f2; border-color: #fecaca; color: #991b1b; }
        .danger { background: #dc2626; color: white; border: none; border-radius: 8px; padding: 10px 14px; font-weight: 700; cursor: pointer; margin-top: 12px; }
        .btn { display: inline-block; margin-top: 12px; text-decoration: none; background: #e5e7eb; color: #111827; padding: 10px 14px; border-radius: 8px; font-weight: 700; }

        /* LED panel styles copied from debug menu */
        .mode-switch { display: flex; justify-content: center; gap: 20px; margin-bottom: 30px; }
        .mode-btn { padding: 12px 24px; font-size: 16px; border: none; border-radius: 10px; cursor: pointer; transition: background-color 0.3s; color: white; }
        .mode-btn.active { background-color: #4CAF50; }
        .mode-btn:not(.active) { background-color: #90a4ae; }
        .led-display { display: flex; justify-content: center; gap: 16px; margin-bottom: 26px; }
        .led-indicator { width: 52px; height: 52px; border-radius: 50%; border: 3px solid #37474f; background-color: #cfd8dc; transition: all 0.3s ease; }
        .led-indicator.on { background-color: #ffeb3b; box-shadow: 0 0 20px #ffeb3b; }
        .slider-container { margin-bottom: 24px; display: none; }
        .slider-container.active { display: block; }
        .slider { width: 100%; height: 20px; margin: 10px 0; }
        .led-status { padding: 14px; background-color: #e3f2fd; border-radius: 10px; color: #1565c0; font-size: 16px; margin-top: 14px; }

        @media (max-width: 900px) {
            .container { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>Focus Session</h1>
            {% if focus_started %}
            <div class="msg">{{ focus_message }}</div>
            {% else %}
            <div class="msg warn">{{ focus_message }}</div>
            {% endif %}
            {% if focus_status.last_error %}
            <div class="msg err">Last start error: {{ focus_status.last_error }}</div>
            {% endif %}
            <p id="focus-running">Running: {{ focus_status.running }}</p>
            <p id="focus-phase">Phase: {{ focus_status.phase }}</p>
            <p id="focus-cycle">Cycle count: {{ focus_status.cycle_count }}</p>
            <p id="focus-timing">Focus/Break (minutes): {{ focus_status.focus_minutes }} / {{ focus_status.break_minutes }}</p>
            <p id="focus-phase-progress">Current phase progress: --:-- / --:--</p>
            <p id="focus-total-runtime">Total session runtime: --:--</p>
            <p id="focus-pid">PID: {{ focus_status.pid if focus_status.pid else 'N/A' }}</p>
            <p id="focus-started">Last started at: {{ focus_status.last_started_at if focus_status.last_started_at else 'N/A' }}</p>
            {% if focus_status.running %}
            <a class="btn" id="debug-link" href="/debug">Open Debug LED/Pump Controls</a>
            {% endif %}
            <button class="danger" type="button" onclick="stopFocusSession()">Stop Focus Session Loop</button>
            <a class="btn" href="/user/menu">Back to Start Menu</a>
        </div>

        <div class="card">
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
            <div id="led-status" class="led-status">Loading system status...</div>
        </div>
    </div>
    <script>
        // Focus session status polling
        let latestFocusStatus = null;

        function formatDuration(seconds) {
            const safe = Math.max(0, Math.floor(Number(seconds) || 0));
            const hours = Math.floor(safe / 3600);
            const minutes = Math.floor((safe % 3600) / 60);
            const secs = safe % 60;
            if (hours > 0) {
                return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
            }
            return `${minutes}:${String(secs).padStart(2, '0')}`;
        }

        function renderFocusTimers(data) {
            const phaseEl = document.getElementById('focus-phase-progress');
            const totalEl = document.getElementById('focus-total-runtime');

            const nowEpoch = Date.now() / 1000;
            const phaseStarted = Number(data.phase_started_epoch || 0);
            const sessionStarted = Number(data.session_started_epoch || 0);
            const phase = String(data.phase || 'idle');

            let phaseDuration = 0;
            if (phase === 'focus') {
                phaseDuration = Math.max(1, Math.round(Number(data.focus_minutes || 0) * 60));
            } else if (phase === 'break') {
                phaseDuration = Math.max(1, Math.round(Number(data.break_minutes || 0) * 60));
            }

            if ((phase === 'focus' || phase === 'break') && phaseStarted > 0 && phaseDuration > 0) {
                const phaseElapsed = Math.max(0, nowEpoch - phaseStarted);
                phaseEl.textContent = `Current phase progress: ${formatDuration(phaseElapsed)} / ${formatDuration(phaseDuration)}`;
            } else {
                phaseEl.textContent = 'Current phase progress: --:-- / --:--';
            }

            if (sessionStarted > 0) {
                const totalElapsed = Math.max(0, nowEpoch - sessionStarted);
                totalEl.textContent = `Total session runtime: ${formatDuration(totalElapsed)}`;
            } else {
                totalEl.textContent = 'Total session runtime: --:--';
            }
        }

        async function refreshFocusStatus() {
            try {
                const response = await fetch('/user/focus_session_status');
                const data = await response.json();
                latestFocusStatus = data;
                document.getElementById('focus-running').textContent = `Running: ${data.running}`;
                document.getElementById('focus-phase').textContent = `Phase: ${data.phase}`;
                document.getElementById('focus-cycle').textContent = `Cycle count: ${data.cycle_count}`;
                document.getElementById('focus-timing').textContent = `Focus/Break (minutes): ${data.focus_minutes} / ${data.break_minutes}`;
                document.getElementById('focus-pid').textContent = `PID: ${data.pid || 'N/A'}`;
                document.getElementById('focus-started').textContent = `Last started at: ${data.last_started_at || 'N/A'}`;
                renderFocusTimers(data);
            } catch (err) {
                // Keep current UI if polling fails transiently.
            }
        }

        async function stopFocusSession() {
            try {
                const response = await fetch('/user/focus_session/stop', { method: 'POST' });
                const data = await response.json();
                if (data.report_url) {
                    window.location.href = data.report_url;
                    return;
                }
                await refreshFocusStatus();
            } catch (err) {
                // No-op; polling will update state once backend responds.
            }
        }

        function tickFocusTimers() {
            if (latestFocusStatus) {
                renderFocusTimers(latestFocusStatus);
            }
        }

        // LED controls copied from debug menu
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

        function updateLEDStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    const ledCount = data.led_count;
                    for (let i = 1; i <= 4; i++) {
                        document.getElementById(`led${i}`).classList.toggle('on', i <= ledCount);
                    }

                    let statusText = '';
                    if (data.mode === 'auto') {
                        statusText = `Auto Mode | Ambient Light: ${(data.light_value * 100).toFixed(0)}% | LEDs ON: ${ledCount}/4`;
                    } else {
                        statusText = `Manual Mode | LEDs ON: ${ledCount}/4`;
                    }
                    document.getElementById('led-status').textContent = statusText;

                    if (data.mode === 'manual') {
                        document.getElementById('led-slider').value = ledCount;
                        document.getElementById('led-value').textContent = ledCount;
                    }
                })
                .catch(() => {
                    document.getElementById('led-status').textContent = 'Unable to fetch LED status.';
                });
        }

        setInterval(refreshFocusStatus, 1500);
        setInterval(tickFocusTimers, 1000);
        setInterval(updateLEDStatus, 500);
        refreshFocusStatus();
        tickFocusTimers();
        updateLEDStatus();
    </script>
</body>
</html>
"""

DEBUG_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>LED & Water Pump Control System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background-color: #f0f4f8; min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }
        .control-card { background: white; padding: 50px 40px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); text-align: center; }
        h1 { color: #2d3748; margin-bottom: 30px; font-size: 28px; }
        h2 { color: #2d3748; margin-bottom: 30px; font-size: 24px; border-bottom: 2px solid #e2e8f0; padding-bottom: 15px; }
        
        /* LED Control Styles */
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
        .status { padding: 20px; background-color: #e3f2fd; border-radius: 10px; color: #1565c0; font-size: 18px; margin-top: 20px; }
        
        /* Pump Control Styles */
        .status-display { padding: 30px; border-radius: 12px; margin-bottom: 50px; font-size: 24px; font-weight: bold; }
        .status-ready { background-color: #fff3cd; color: #856404; }
        .status-firing { background-color: #d4edda; color: #155724; }
        .control-button { width: 100%; padding: 30px; font-size: 28px; font-weight: bold; border: none; border-radius: 12px; cursor: pointer; color: white; transition: all 0.2s ease; }
        .button-fire { background-color: #dc3545; }
        .button-fire:hover { background-color: #c82333; }
        .button-fire:disabled { background-color: #6c757d; cursor: not-allowed; }
    </style>
</head>
<body>
    <div class="container">
        <!-- LED Control Section (完全未改动) -->
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
            <div id="led-status" class="status">Loading system status...</div>
        </div>

        <!-- Water Pump Control Section -->
        <div class="control-card">
            <h1>Submersible Water Pump (Pulse Mode)</h1>
            <div id="pump-status" class="status-display status-ready">
                Pump Status: Ready
            </div>
            <button id="pump-control-btn" class="control-button button-fire" onclick="firePump()">
                FIRE (1.0s)
            </button>
        </div>
    </div>

    <script>
        // LED Control Variables and Functions (完全未改动)
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

        function updateLEDStatus() {
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
                    document.getElementById('led-status').textContent = statusText;
                    // Update slider
                    if (data.mode === 'manual') {
                        document.getElementById('led-slider').value = ledCount;
                        document.getElementById('led-value').textContent = ledCount;
                    }
                });
        }

        // Pump Control Variables and Functions
        let isPumping = false;
        function firePump() {
            if (isPumping) return;
            
            isPumping = true;
            const statusDiv = document.getElementById('pump-status');
            const controlBtn = document.getElementById('pump-control-btn');
            
            statusDiv.textContent = 'Pump Status: FIRING...';
            statusDiv.classList.remove('status-ready');
            statusDiv.classList.add('status-firing');
            controlBtn.textContent = 'Wait...';
            controlBtn.disabled = true;
            
            fetch('/fire_pump');
            
            setTimeout(() => {
                isPumping = false;
                statusDiv.textContent = 'Pump Status: Ready';
                statusDiv.classList.remove('status-firing');
                statusDiv.classList.add('status-ready');
                controlBtn.textContent = 'FIRE (1.0s)';
                controlBtn.disabled = false;
            }, 1000);
        }

        // Initial Load and Updates
        function init() {
            updateLEDStatus();
            setInterval(updateLEDStatus, 500);
        }

        window.onload = init;
    </script>
</body>
</html>
"""


