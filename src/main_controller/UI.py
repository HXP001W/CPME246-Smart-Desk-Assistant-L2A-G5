# Combined 4-LED + Water Pump + Buzzer Control System (English Version)
from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from gpiozero import LED, Device, OutputDevice, Buzzer
import threading
import time
import atexit
import os
import sys
import base64
import cv2
import subprocess
import importlib.util


try:
    from gpiozero.pins.rpigpio import RPiGPIOFactory
    Device.pin_factory = RPiGPIOFactory()
    print("Using RPi.GPIO backend (stable)")
except:
    print("RPi.GPIO not found, using native backend")
    pass


# LED Configuration
LED_PINS = [22, 23, 24, 25]
LIGHT_SENSOR_PIN = 27  # Physical Pin 13

# Water Pump Configuration (修改1：active_high改为True)
PUMP_PIN = 18  # Physical Pin 11, connected to relay IN
pump = OutputDevice(PUMP_PIN, active_high=True, initial_value=False)
pump_timer = None
buzzer_timer = None


BUZZER_PIN = 26  # 对应树莓派37号物理引脚
buzzer = Buzzer(BUZZER_PIN, active_high=True, initial_value=False)


app = Flask(__name__)
system_mode = "auto"
manual_led_level = 0
system_running = True

# Web user session state (single active user on device)
web_user_lock = threading.Lock()
web_user_state = {
    'mode': 'guest',
    'user_id': -1,
}

# Face recognition job state
face_recognition_lock = threading.Lock()
face_recognition_state = {
    'running': False,
    'status': 'idle',
    'message': 'Ready to start face recognition.',
    'last_started_at': None,
    'last_finished_at': None,
    'outcome': 'idle',
    'next_route': '',
}

# Focus session subprocess state
focus_session_lock = threading.Lock()
focus_session_process = None
focus_session_loop_thread = None
focus_session_stop_event = threading.Event()
focus_session_state = {
    'running': False,
    'phase': 'idle',
    'message': 'Focus session not started.',
    'last_started_at': None,
    'last_error': '',
    'focus_minutes': 0,
    'break_minutes': 0,
    'cycle_count': 0,
    'pid': None,
    'session_id': '',
    'user_id': -1,
    'user_name': 'Guest',
}


_logging_module_cache = None


def _load_logging_module():
    """Load shared logging module from logging/logger.py."""
    global _logging_module_cache
    if _logging_module_cache is not None:
        return _logging_module_cache

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    logger_path = os.path.join(project_root, 'logging', 'logger.py')
    if not os.path.exists(logger_path):
        return None

    spec = importlib.util.spec_from_file_location('project_event_logger', logger_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _logging_module_cache = module
    return module


_report_generator_module_cache = None


def _load_report_generator_module():
    """Load report generator module from logging/report_generator.py."""
    global _report_generator_module_cache
    if _report_generator_module_cache is not None:
        return _report_generator_module_cache

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    report_gen_path = os.path.join(project_root, 'logging', 'report_generator.py')
    if not os.path.exists(report_gen_path):
        return None

    spec = importlib.util.spec_from_file_location('project_report_generator', report_gen_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _report_generator_module_cache = module
    return module


def _new_event_logger(session_id, module_name):
    """Create logger instance for a module within one session."""
    logging_module = _load_logging_module()
    if logging_module is None:
        return None

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    log_dir = os.path.join(project_root, 'logging', 'logs')
    try:
        return logging_module.EventLogger(session_id=session_id, module_name=module_name, log_dir=log_dir)
    except Exception:
        return None


def _ui_log_event(session_id, module_name, event_type, value, details=None, user_id=None, user_name=None, duration_seconds=None):
    logger = _new_event_logger(session_id, module_name)
    if logger is None:
        return
    try:
        logger.log_event(
            event_type=event_type,
            value=value,
            details=details or {},
            user_id=user_id,
            user_name=user_name,
            duration_seconds=duration_seconds,
        )
    except Exception:
        pass


def _create_focus_session_id():
    logging_module = _load_logging_module()
    if logging_module is not None:
        try:
            return logging_module.create_session_id(prefix='focus_session')
        except Exception:
            pass
    return time.strftime('%Y-%m-%d_%H-%M-%S_focus_session')


def _load_face_recognition_module():
    """Load local face recognition module from src/face_recognition."""
    face_module_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'face_recognition')
    )
    if face_module_dir not in sys.path:
        sys.path.insert(0, face_module_dir)
    import Identify
    return Identify


def _load_user_profile_modules():
    """Load local face recognition user/profile modules."""
    face_module_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'face_recognition')
    )
    if face_module_dir not in sys.path:
        sys.path.insert(0, face_module_dir)
    import testmain
    import User
    return testmain, User


def _set_active_user(mode='guest', user_id=-1):
    with web_user_lock:
        web_user_state['mode'] = mode
        web_user_state['user_id'] = user_id


def _get_active_user():
    """Return current active user object and registration flag."""
    testmain, User = _load_user_profile_modules()
    with web_user_lock:
        mode = web_user_state['mode']
        user_id = web_user_state['user_id']

    if mode == 'registered':
        for user in testmain.userList:
            if user.userID == user_id:
                return user, True

    return testmain.guestUser, False


def _build_user_overview(user):
    return {
        'name': user.name or 'Guest',
        'focusTime': user.focusTime,
        'breakTime': user.breakTime,
        'reportCount': len(user.reportData),
    }


def _apply_face_recognition_result(registered_user, user_id):
    """Map Identify._startup callback result into web user state."""
    if registered_user and user_id != -1:
        _set_active_user(mode='registered', user_id=user_id)
        with face_recognition_lock:
            face_recognition_state['outcome'] = 'matched'
            face_recognition_state['next_route'] = '/user/menu'
            face_recognition_state['message'] = f'Recognized user profile: {user_id}. Open User Menu to continue.'
    else:
        _set_active_user(mode='guest', user_id=-1)
        with face_recognition_lock:
            face_recognition_state['outcome'] = 'no_match'
            face_recognition_state['next_route'] = '/user/onboarding'
            face_recognition_state['message'] = 'No match found. Guest profile is active. Open User Menu to continue.'


def run_face_recognition_job():
    """Run facial recognition flow and update shared job state."""
    with face_recognition_lock:
        face_recognition_state['running'] = True
        face_recognition_state['status'] = 'running'
        face_recognition_state['outcome'] = 'running'
        face_recognition_state['next_route'] = ''
        face_recognition_state['message'] = 'Face recognition is running. Follow camera prompts on the device.'
        face_recognition_state['last_started_at'] = time.strftime('%Y-%m-%d %H:%M:%S')

    try:
        identify_module = _load_face_recognition_module()
        original_startup = getattr(identify_module, '_startup', None)

        def _web_startup(registeredUser=False, userID=-1):
            _apply_face_recognition_result(registeredUser, userID)

        identify_module._startup = _web_startup
        identify_module.identity_test()
        if original_startup is not None:
            identify_module._startup = original_startup
        with face_recognition_lock:
            face_recognition_state['status'] = 'completed'
            if face_recognition_state['outcome'] == 'running':
                face_recognition_state['outcome'] = 'completed'
                face_recognition_state['next_route'] = ''
                face_recognition_state['message'] = 'Face recognition flow completed. User profile logic has been executed.'
    except Exception as exc:
        if 'identify_module' in locals() and 'original_startup' in locals() and original_startup is not None:
            identify_module._startup = original_startup
        with face_recognition_lock:
            face_recognition_state['status'] = 'failed'
            face_recognition_state['outcome'] = 'error'
            face_recognition_state['next_route'] = ''
            face_recognition_state['message'] = f'Face recognition failed: {exc}'
    finally:
        with face_recognition_lock:
            face_recognition_state['running'] = False
            face_recognition_state['last_finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S')


def _get_focus_session_runtime():
    """Resolve Python executable and script path for focus session prototype."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    script_path = os.path.join(project_root, 'tests', 'Casey', 'combined_focus_prototype_v5.py')

    default_python = os.path.join(project_root, '.venv-mediapipe', 'bin', 'python')
    python_exec = os.getenv('FOCUS_SESSION_PYTHON', default_python if os.path.exists(default_python) else sys.executable)
    return project_root, python_exec, script_path


def _stop_focus_session_process(proc):
    """Terminate focus subprocess safely."""
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=3)
    except Exception:
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass


def _focus_session_status():
    """Return focus-session process status for rendering in UI."""
    with focus_session_lock:
        status = dict(focus_session_state)
        if status.get('running'):
            status['pid'] = focus_session_process.pid if focus_session_process is not None and focus_session_process.poll() is None else None
        return status


def _focus_session_loop_worker(focus_minutes, break_minutes, session_id, user_id, user_name):
    """Run repeated focus/break cycles using combined_focus_prototype_v5.py."""
    global focus_session_process
    project_root, python_exec, script_path = _get_focus_session_runtime()
    focus_seconds = max(1, int(focus_minutes * 60))
    break_seconds = max(1, int(break_minutes * 60))
    session_started_at = time.time()

    with focus_session_lock:
        focus_session_state['running'] = True
        focus_session_state['phase'] = 'focus'
        focus_session_state['message'] = 'Starting focus session loop.'
        focus_session_state['last_started_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        focus_session_state['last_error'] = ''
        focus_session_state['focus_minutes'] = focus_minutes
        focus_session_state['break_minutes'] = break_minutes
        focus_session_state['cycle_count'] = 0
        focus_session_state['pid'] = None
        focus_session_state['session_id'] = session_id
        focus_session_state['user_id'] = user_id
        focus_session_state['user_name'] = user_name or 'Guest'

    _ui_log_event(
        session_id,
        'session_manager',
        'session_started',
        'focus_loop_started',
        details={
            'focus_minutes': focus_minutes,
            'break_minutes': break_minutes,
            'planned_focus_seconds': focus_seconds,
            'planned_break_seconds': break_seconds,
        },
        user_id=user_id,
        user_name=user_name,
    )

    try:
        while not focus_session_stop_event.is_set():
            with focus_session_lock:
                focus_session_state['phase'] = 'focus'
                focus_session_state['cycle_count'] += 1
                cycle_no = focus_session_state['cycle_count']

            try:
                child_env = os.environ.copy()
                child_env['FOCUS_SESSION_ID'] = str(session_id)
                child_env['FOCUS_USER_ID'] = str(user_id)
                child_env['FOCUS_USER_NAME'] = str(user_name or 'Guest')

                _ui_log_event(
                    session_id,
                    'session_manager',
                    'focus_cycle_started',
                    f'cycle_{cycle_no}',
                    details={
                        'cycle_no': cycle_no,
                        'focus_minutes': focus_minutes,
                        'planned_duration_seconds': focus_seconds,
                    },
                    user_id=user_id,
                    user_name=user_name,
                )

                focus_session_process = subprocess.Popen(
                    [python_exec, script_path],
                    cwd=project_root,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=child_env,
                )
                with focus_session_lock:
                    focus_session_state['pid'] = focus_session_process.pid
                    focus_session_state['message'] = (
                        f'Cycle {cycle_no}: focus running for {focus_minutes} minute(s) '
                        f'(PID {focus_session_process.pid}).'
                    )
            except Exception as exc:
                with focus_session_lock:
                    focus_session_state['last_error'] = str(exc)
                    focus_session_state['message'] = f'Failed to launch focus process: {exc}'
                    focus_session_state['running'] = False
                    focus_session_state['phase'] = 'error'
                _ui_log_event(
                    session_id,
                    'session_manager',
                    'focus_launch_failed',
                    'error',
                    details={'error': str(exc), 'cycle_no': cycle_no},
                    user_id=user_id,
                    user_name=user_name,
                )
                return

            focus_cycle_started_at = time.time()
            focus_deadline = time.time() + focus_seconds
            while time.time() < focus_deadline and not focus_session_stop_event.is_set():
                if focus_session_process.poll() is not None:
                    break
                time.sleep(0.5)

            _stop_focus_session_process(focus_session_process)
            with focus_session_lock:
                focus_session_state['pid'] = None

            _ui_log_event(
                session_id,
                'session_manager',
                'focus_cycle_ended',
                f'cycle_{cycle_no}',
                details={
                    'cycle_no': cycle_no,
                    'planned_duration_seconds': focus_seconds,
                    'actual_duration_seconds': round(time.time() - focus_cycle_started_at, 2),
                },
                user_id=user_id,
                user_name=user_name,
                duration_seconds=round(time.time() - focus_cycle_started_at, 2),
            )

            if focus_session_stop_event.is_set():
                break

            with focus_session_lock:
                focus_session_state['phase'] = 'break'
                focus_session_state['message'] = (
                    f'Cycle {cycle_no}: break for {break_minutes} minute(s). '
                    'Focus will resume automatically.'
                )

            _ui_log_event(
                session_id,
                'session_manager',
                'break_started',
                f'cycle_{cycle_no}',
                details={
                    'cycle_no': cycle_no,
                    'break_minutes': break_minutes,
                    'planned_duration_seconds': break_seconds,
                },
                user_id=user_id,
                user_name=user_name,
            )

            break_started_at = time.time()
            break_deadline = time.time() + break_seconds
            while time.time() < break_deadline and not focus_session_stop_event.is_set():
                time.sleep(0.5)

            _ui_log_event(
                session_id,
                'session_manager',
                'break_ended',
                f'cycle_{cycle_no}',
                details={
                    'cycle_no': cycle_no,
                    'planned_duration_seconds': break_seconds,
                    'actual_duration_seconds': round(time.time() - break_started_at, 2),
                },
                user_id=user_id,
                user_name=user_name,
                duration_seconds=round(time.time() - break_started_at, 2),
            )
    finally:
        _stop_focus_session_process(focus_session_process)
        with focus_session_lock:
            focus_session_process = None
            focus_session_state['pid'] = None
            focus_session_state['running'] = False
            if focus_session_state['phase'] != 'error':
                focus_session_state['phase'] = 'stopped'
                focus_session_state['message'] = 'Focus session loop stopped.'

        _ui_log_event(
            session_id,
            'session_manager',
            'session_ended',
            'focus_loop_stopped',
            details={
                'phase': focus_session_state.get('phase', 'unknown'),
                'total_duration_seconds': round(time.time() - session_started_at, 2),
            },
            user_id=user_id,
            user_name=user_name,
            duration_seconds=round(time.time() - session_started_at, 2),
        )


def _start_focus_session_loop_if_needed(focus_minutes, break_minutes, user_id, user_name):
    """Start repeated focus/break loop if not already running."""
    global focus_session_loop_thread
    project_root, python_exec, script_path = _get_focus_session_runtime()
    session_id = _create_focus_session_id()

    with focus_session_lock:
        already_running = focus_session_loop_thread is not None and focus_session_loop_thread.is_alive()
        if already_running:
            return False, 'Focus session loop is already running.'

        if not os.path.exists(script_path):
            focus_session_state['last_error'] = f'Focus script not found: {script_path}'
            focus_session_state['phase'] = 'error'
            focus_session_state['message'] = focus_session_state['last_error']
            return False, focus_session_state['last_error']

        if not os.path.exists(python_exec):
            focus_session_state['last_error'] = f'Python executable not found: {python_exec}'
            focus_session_state['phase'] = 'error'
            focus_session_state['message'] = focus_session_state['last_error']
            return False, focus_session_state['last_error']

        focus_session_stop_event.clear()
        focus_session_state['session_id'] = session_id
        focus_session_state['user_id'] = user_id
        focus_session_state['user_name'] = user_name or 'Guest'
        focus_session_loop_thread = threading.Thread(
            target=_focus_session_loop_worker,
            args=(focus_minutes, break_minutes, session_id, user_id, user_name),
            daemon=True,
        )
        focus_session_loop_thread.start()

        return True, (
            f'Starting focus session loop: {focus_minutes} minute(s) focus, '
            f'{break_minutes} minute(s) break. Session ID: {session_id}'
        )


def _stop_focus_session_loop():
    """Request focus/break loop stop and terminate active focus subprocess."""
    focus_session_stop_event.set()
    with focus_session_lock:
        _stop_focus_session_process(focus_session_process)
        focus_session_state['message'] = 'Stopping focus session loop...'
        session_id = focus_session_state.get('session_id', '')
        user_id = focus_session_state.get('user_id', -1)
        user_name = focus_session_state.get('user_name', 'Guest')

    if session_id:
        _ui_log_event(
            session_id,
            'session_manager',
            'session_stopped',
            'manual_stop',
            details={},
            user_id=user_id,
            user_name=user_name,
        )

# Hardware objects
leds = []
light_sensor_pin = None
light_sensor_available = False


def read_light_level():
    """
    Simple light sensor reading without any interrupts.
    Returns 0.0 (full dark) to 1.0 (full bright).
    """
    if not light_sensor_available:
        return 0.5
    
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(LIGHT_SENSOR_PIN, GPIO.OUT)
        GPIO.output(LIGHT_SENSOR_PIN, GPIO.LOW)
        time.sleep(0.1)
        
        GPIO.setup(LIGHT_SENSOR_PIN, GPIO.IN)
        start_time = time.time()
        while GPIO.input(LIGHT_SENSOR_PIN) == GPIO.LOW and (time.time() - start_time) < 0.1:
            pass
        charge_time = time.time() - start_time
        
        GPIO.setup(LIGHT_SENSOR_PIN, GPIO.IN)
        
        light_level = 1.0 - min(1.0, charge_time * 10)
        return max(0.0, min(1.0, light_level))
    except:
        return 0.5


def setup_hardware():
    global leds, light_sensor_available

    # Clean up existing LEDs
    for led in leds:
        try:
            led.off()
            led.close()
        except Exception:
            pass
    leds.clear()

    # Initialize LEDs
    try:
        leds = [LED(pin, initial_value=False) for pin in LED_PINS]
        print(f" LEDs initialized on GPIO {LED_PINS}")
    except Exception as e:
        raise RuntimeError(f" LED initialization failed: {str(e)}")

    # Light sensor info
    print("\n Check light sensor wiring:")
    print("  - Light sensor pin 1 -> 3.3V (Physical Pin 1)")
    print("  - Light sensor pin 2 -> GPIO27 (Physical Pin 13) + 10k resistor")
    print("  - 10kΩ resistor -> GND (Physical Pin 9)")
    
    light_sensor_available = True
    print(" Light sensor initialized (polling mode, no interrupts)")
    
    # Pump initialization
    print(f" Water pump initialized on GPIO {PUMP_PIN} (Pulse Mode: 1.0 seconds, Active HIGH)")
    
    # 蜂鸣器初始化
    print(f" 2-Pin Buzzer initialized on GPIO {BUZZER_PIN}")


def safe_shutdown():
    global system_running, leds, pump_timer
    print("\n=== SAFE SHUTDOWN STARTED ===")
    system_running = False

    # Release all LEDs
    for idx, led in enumerate(leds):
        try:
            led.off()
            led.close()
            print(f"LED {idx+1} (GPIO{LED_PINS[idx]}) released")
        except Exception as e:
            print(f"Failed to release LED {idx+1}: {str(e)}")
    leds.clear()

    # Release pump
    try:
        pump.off()
        pump.close()
        print(f"Water pump (GPIO{PUMP_PIN}) released")
    except Exception as e:
        print(f"Failed to release water pump: {str(e)}")
    
    # 蜂鸣器安全释放
    try:
        buzzer.off()
        buzzer.close()
        print(f"Buzzer (GPIO{BUZZER_PIN}) released")
    except Exception as e:
        print(f"Failed to release buzzer: {str(e)}")

    # Clean up GPIO
    try:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
        print("GPIO cleaned up")
    except:
        pass

    print("=== SAFE SHUTDOWN COMPLETE ===")

atexit.register(safe_shutdown)


def set_led_level(level):
    level = max(0, min(4, int(level)))
    for i in range(min(4, len(leds))):
        leds[i].on() if i < level else leds[i].off()

def get_current_led_count():
    count = 0
    for led in leds:
        try:
            if led.value == 1:
                count += 1
        except Exception:
            pass
    return count


def auto_mode_loop():
    global system_mode, system_running
    while system_running:
        if system_mode == "auto" and light_sensor_available:
            try:
                ambient_light = read_light_level()
                target_led_count = int((1.0 - ambient_light) * 4)
                set_led_level(target_led_count)
            except Exception:
                pass
        time.sleep(0.2)


def pump_pulse():
    """启动水泵1秒，同时蜂鸣器响，然后自动同步关闭"""
    global pump_timer
    try:
        pump.on()
        buzzer.on()
        time.sleep(1.0)
        pump.off()
        buzzer.off()
    except Exception as e:
        print(f"Pump pulse error: {str(e)}")
        pump.off()
        buzzer.off()
    finally:
        pump_timer = None


def buzzer_pulse(duration_seconds=1.0):
    """Trigger buzzer for a short pulse without pump."""
    global buzzer_timer
    try:
        buzzer.on()
        time.sleep(max(0.1, float(duration_seconds)))
        buzzer.off()
    except Exception as e:
        print(f"Buzzer pulse error: {str(e)}")
        try:
            buzzer.off()
        except Exception:
            pass
    finally:
        buzzer_timer = None


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
        <h1>Smart Desk Assistant</h1>
        <p>Choose an operating mode. Debug Mode opens the current hardware UI. Facial Recognition starts camera identification and applies user profile logic.</p>

        <div class="actions">
            <button class="btn-primary" onclick="startFaceRecognition()">Begin Facial Recognition</button>
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
        function renderStatus(data) {
            document.getElementById('status-text').textContent = `State: ${data.status} | ${data.message}`;
            document.getElementById('status-started').textContent = data.last_started_at ? `Last started: ${data.last_started_at}` : '';
            document.getElementById('status-finished').textContent = data.last_finished_at ? `Last finished: ${data.last_finished_at}` : '';

            if (data.status === 'completed' && data.next_route) {
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
            fetch('/start_face_recognition', { method: 'POST' })
                .then(response => response.json())
                .then(renderStatus)
                .catch(() => {
                    document.getElementById('status-text').textContent = 'State: error | Failed to start face recognition';
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
        <h1>Welcome to FocusBuddy</h1>
        <p>It looks like you are a new user. Register a new user or continue as guest.</p>
        <div class="actions">
            <form method="post" action="/user/continue_guest">
                <button class="btn btn-primary" type="submit">1. Continue as Guest</button>
            </form>
            <a class="btn btn-secondary" href="/user/register">2. Register New User</a>
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
            <p>This mirrors the terminal registration flow. On submit, camera capture opens. Press SPACE to take photo, C to switch camera, or Q to cancel.</p>
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

                <button class="btn btn-save" type="submit">Register and Capture Photo</button>
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
                <a class="btn btn-1" href="/user/focus_session">1. Start Focus Session</a>
                <a class="btn btn-2" href="/user/settings">2. Settings</a>
                <a class="btn btn-3" href="/user/reports">3. View Reports</a>
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

            <h2>1. Update Focus/Break Time</h2>
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

            <h2>2. Delete Profile</h2>
            <form method="post" action="/user/settings/delete_profile">
                <button class="btn btn-danger" type="submit">Delete Profile</button>
            </form>

            <a class="btn btn-back" href="/user/menu">3. Back to Options</a>
        </div>
    </div>
</body>
</html>
"""

USER_REPORTS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>User Reports</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #f1f5f9; min-height: 100vh; padding: 20px; }
        .wrap { max-width: 780px; margin: 0 auto; }
        .card { margin-top: 24px; background: white; border-radius: 12px; padding: 26px; box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
        h1 { color: #111827; margin-bottom: 12px; }
        p { color: #374151; margin-bottom: 16px; }
        ul { margin: 14px 0 16px 18px; color: #374151; }
        li { margin-bottom: 6px; }
        .muted { color: #6b7280; }
        .btn { display: inline-block; text-decoration: none; background: #3b82f6; color: white; padding: 10px 14px; border-radius: 8px; font-weight: 700; margin-right: 8px; }
        .btn-secondary { background: #e5e7eb; color: #111827; }
    </style>
</head>
<body>
    <div class="wrap">
        <div class="card">
            <h1>Reports</h1>
            <p>Click below to view all your focus session reports:</p>
            <a class="btn" href="/user/sessions">View Sessions</a>
            {% if reports %}
            <h2 style="color: #111827; margin-top: 20px;">Legacy Reports</h2>
            <ul>
                {% for report in reports %}
                <li>Report {{ loop.index }}: {{ report }}</li>
                {% endfor %}
            </ul>
            {% endif %}
            <a class="btn btn-secondary" href="/user/menu">Back to Options</a>
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
            <a class="btn" href="/user/menu">Back to Menu</a>
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
            <a class="btn" href="/user/menu">Back to Menu</a>
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
            <p>Starting focus session for {{ user.focusTime }} minutes.</p>
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
            <p id="focus-pid">PID: {{ focus_status.pid if focus_status.pid else 'N/A' }}</p>
            <p id="focus-started">Last started at: {{ focus_status.last_started_at if focus_status.last_started_at else 'N/A' }}</p>
            {% if focus_status.running %}
            <a class="btn" id="debug-link" href="/debug">Open Debug LED/Pump Controls</a>
            {% endif %}
            <button class="danger" type="button" onclick="stopFocusSession()">Stop Focus Session Loop</button>
            <a class="btn" href="/user/menu">Back to Options</a>
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
        async function refreshFocusStatus() {
            try {
                const response = await fetch('/user/focus_session_status');
                const data = await response.json();
                document.getElementById('focus-running').textContent = `Running: ${data.running}`;
                document.getElementById('focus-phase').textContent = `Phase: ${data.phase}`;
                document.getElementById('focus-cycle').textContent = `Cycle count: ${data.cycle_count}`;
                document.getElementById('focus-timing').textContent = `Focus/Break (minutes): ${data.focus_minutes} / ${data.break_minutes}`;
                document.getElementById('focus-pid').textContent = `PID: ${data.pid || 'N/A'}`;
                document.getElementById('focus-started').textContent = `Last started at: ${data.last_started_at || 'N/A'}`;
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
        setInterval(updateLEDStatus, 500);
        refreshFocusStatus();
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


@app.route('/')
def index():
    return render_template_string(START_MENU_TEMPLATE)


@app.route('/debug')
def debug_mode():
    if not _focus_session_status().get('running', False):
        user, _ = _get_active_user()
        return render_template_string(
            USER_FOCUS_SESSION_TEMPLATE,
            user=_build_user_overview(user),
            focus_started=False,
            focus_message='Start a focus session to unlock Debug LED controls.',
            focus_status=_focus_session_status(),
        )
    return render_template_string(DEBUG_HTML_TEMPLATE)


@app.route('/start_face_recognition', methods=['POST'])
def start_face_recognition():
    with face_recognition_lock:
        if face_recognition_state['running']:
            return jsonify(face_recognition_state)

        worker = threading.Thread(target=run_face_recognition_job, daemon=True)
        worker.start()
        face_recognition_state['status'] = 'starting'
        face_recognition_state['outcome'] = 'starting'
        face_recognition_state['next_route'] = ''
        face_recognition_state['message'] = 'Launching face recognition...'

        return jsonify(face_recognition_state)


@app.route('/face_recognition_status')
def face_recognition_status():
    with face_recognition_lock:
        return jsonify(face_recognition_state)


@app.route('/user/onboarding')
def user_onboarding():
    with face_recognition_lock:
        if face_recognition_state.get('outcome') != 'no_match':
            return redirect(url_for('index'))
    return render_template_string(USER_ONBOARDING_TEMPLATE)


@app.route('/user/continue_guest', methods=['POST'])
def user_continue_guest():
    _set_active_user(mode='guest', user_id=-1)
    return redirect(url_for('user_menu'))


@app.route('/api/device_camera_snapshot', methods=['POST'])
def device_camera_snapshot():
    """Capture one frame from local device camera for web registration fallback."""
    candidate_indices = [0, 1, 2, 3, 4, 5]
    cap = None

    try:
        for idx in candidate_indices:
            for backend in (cv2.CAP_V4L2, cv2.CAP_ANY):
                probe = cv2.VideoCapture(idx, backend)
                if not probe.isOpened():
                    probe.release()
                    continue

                probe.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                probe.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                probe.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                ok, frame = probe.read()
                if not ok or frame is None or frame.size == 0:
                    probe.release()
                    continue

                cap = probe
                break

            if cap is not None:
                break

        if cap is None:
            return jsonify({'ok': False, 'error': 'No usable camera found on device.'}), 503

        ok, frame = cap.read()
        if not ok or frame is None or frame.size == 0:
            return jsonify({'ok': False, 'error': 'Failed to capture frame from device camera.'}), 500

        success, encoded = cv2.imencode('.jpg', frame)
        if not success:
            return jsonify({'ok': False, 'error': 'Failed to encode captured frame.'}), 500

        encoded_base64 = base64.b64encode(encoded.tobytes()).decode('utf-8')
        data_url = f'data:image/jpeg;base64,{encoded_base64}'
        return jsonify({'ok': True, 'photo_data': data_url})
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500
    finally:
        if cap is not None:
            cap.release()


@app.route('/user/register', methods=['GET', 'POST'])
def user_register():
    if request.method == 'GET':
        return render_template_string(USER_REGISTER_TEMPLATE, message='', is_error=False)

    testmain, User = _load_user_profile_modules()
    try:
        open_index = -1
        for i, existing_user in enumerate(testmain.userList):
            if existing_user.userID == -1:
                open_index = i
                break

        if open_index == -1:
            return render_template_string(
                USER_REGISTER_TEMPLATE,
                message='Maximum user capacity reached. Please delete a profile and try again.',
                is_error=True,
            )

        name = request.form.get('name', '').strip()
        focus_time = int(request.form.get('focusTime', '0'))
        break_time = int(request.form.get('breakTime', '0'))

        if not name or focus_time <= 0 or break_time <= 0:
            return render_template_string(
                USER_REGISTER_TEMPLATE,
                message='Please fill all fields with valid values.',
                is_error=True,
            )

        image_bytes = None
        photo_data = request.form.get('photo_data', '').strip()
        if photo_data:
            if ',' not in photo_data:
                return render_template_string(
                    USER_REGISTER_TEMPLATE,
                    message='Captured photo format is invalid. Please retake photo.',
                    is_error=True,
                )

            try:
                _, encoded_data = photo_data.split(',', 1)
                image_bytes = base64.b64decode(encoded_data)
            except Exception:
                return render_template_string(
                    USER_REGISTER_TEMPLATE,
                    message='Unable to decode captured photo. Please retake photo.',
                    is_error=True,
                )

        if image_bytes is None:
            uploaded_file = request.files.get('photo_file')
            if uploaded_file and uploaded_file.filename:
                image_bytes = uploaded_file.read()

        if not image_bytes:
            return render_template_string(
                USER_REGISTER_TEMPLATE,
                message='Please capture a photo or upload a photo file before submitting registration.',
                is_error=True,
            )

        os.makedirs(testmain.DB_PATH, exist_ok=True)
        timestamp = int(time.time())
        filename = f"{name.replace(' ', '_')}_{timestamp}.jpg"
        photo_path = os.path.join(testmain.DB_PATH, filename)

        try:
            with open(photo_path, 'wb') as img_file:
                img_file.write(image_bytes)
        except Exception as exc:
            return render_template_string(
                USER_REGISTER_TEMPLATE,
                message=f'Failed to save captured photo: {exc}',
                is_error=True,
            )

        new_user = User.User(
            userID=photo_path,
            name=name,
            focusTime=focus_time,
            breakTime=break_time,
        )
        testmain.userList[open_index] = new_user
        testmain.save_users()
        _set_active_user(mode='registered', user_id=photo_path)
        return redirect(url_for('user_menu'))
    except Exception as exc:
        return render_template_string(
            USER_REGISTER_TEMPLATE,
            message=f'Registration failed: {exc}',
            is_error=True,
        )


@app.route('/user/menu')
def user_menu():
    user, _ = _get_active_user()
    return render_template_string(USER_MENU_TEMPLATE, user=_build_user_overview(user))


@app.route('/user/focus_session')
def user_focus_session():
    user, _ = _get_active_user()
    focus_minutes = max(1, int(user.focusTime))
    break_minutes = max(1, int(user.breakTime))
    user_id = getattr(user, 'userID', -1)
    user_name = getattr(user, 'name', None) or 'Guest'
    focus_started, focus_message = _start_focus_session_loop_if_needed(focus_minutes, break_minutes, user_id, user_name)
    return render_template_string(
        USER_FOCUS_SESSION_TEMPLATE,
        user=_build_user_overview(user),
        focus_started=focus_started,
        focus_message=focus_message,
        focus_status=_focus_session_status(),
    )


@app.route('/user/focus_session_status')
def user_focus_session_status():
    return jsonify(_focus_session_status())


@app.route('/user/focus_session/stop', methods=['POST'])
def user_focus_session_stop():
    status_before_stop = _focus_session_status()
    session_id = status_before_stop.get('session_id', '')
    _stop_focus_session_loop()
    status_after_stop = _focus_session_status()

    payload = {'ok': True, **status_after_stop}
    if session_id:
        payload['report_url'] = url_for('user_session_report', session_id=session_id)

    return jsonify(payload)


@app.route('/user/settings', methods=['GET'])
def user_settings():
    user, _ = _get_active_user()
    message = request.args.get('message', '')
    is_error = request.args.get('error', '0') == '1'
    return render_template_string(
        USER_SETTINGS_TEMPLATE,
        user=_build_user_overview(user),
        message=message,
        is_error=is_error,
    )


def _settings_redirect(message, is_error=False):
    return redirect(url_for('user_settings', message=message, error='1' if is_error else '0'))


@app.route('/user/settings/update_timing', methods=['POST'])
def user_settings_update_timing():
    testmain, _ = _load_user_profile_modules()
    user, is_registered = _get_active_user()
    try:
        user.focusTime = int(request.form.get('focusTime', '0'))
        user.breakTime = int(request.form.get('breakTime', '0'))
        if user.focusTime <= 0 or user.breakTime <= 0:
            return _settings_redirect('Focus and break time must be greater than 0.', True)
        if is_registered:
            testmain.save_users()
        return _settings_redirect('Focus/break times updated successfully.')
    except Exception as exc:
        return _settings_redirect(f'Unable to update timing: {exc}', True)


@app.route('/user/settings/delete_profile', methods=['POST'])
def user_settings_delete_profile():
    testmain, _ = _load_user_profile_modules()
    user, is_registered = _get_active_user()
    if not is_registered:
        return _settings_redirect('Guest profile cannot be deleted.', True)

    if testmain.delete_profile(user):
        _set_active_user(mode='guest', user_id=-1)
        return redirect(url_for('user_onboarding'))
    return _settings_redirect('Profile deletion failed.', True)


@app.route('/user/reports')
def user_reports():
    user, _ = _get_active_user()
    return render_template_string(USER_REPORTS_TEMPLATE, reports=user.reportData)


@app.route('/user/sessions')
def user_sessions():
    """List all sessions for the current user."""
    user, _ = _get_active_user()
    if user is None or user.userID is None:
        return redirect(url_for('user_onboarding'))
    
    logging_module = _load_logging_module()
    if logging_module is None:
        return render_template_string(USER_SESSIONS_TEMPLATE, sessions=[], error="Logging module not available")
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    log_dir = os.path.join(project_root, 'logging', 'logs')
    
    try:
        sessions = logging_module.find_user_sessions(log_dir, str(user.userID))
    except Exception as e:
        return render_template_string(USER_SESSIONS_TEMPLATE, sessions=[], error=str(e))
    
    return render_template_string(USER_SESSIONS_TEMPLATE, sessions=sessions, user_id=user.userID)


@app.route('/user/session/<session_id>/report')
def user_session_report(session_id):
    """View a specific session's report."""
    user, _ = _get_active_user()
    if user is None or user.userID is None:
        return redirect(url_for('user_onboarding'))
    
    report_gen_module = _load_report_generator_module()
    logging_module = _load_logging_module()
    
    if report_gen_module is None or logging_module is None:
        return render_template_string(USER_SESSION_REPORT_TEMPLATE, 
                                    session_id=session_id, 
                                    report_html="", 
                                    error="Report generator module not available")
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    log_dir = os.path.join(project_root, 'logging', 'logs')
    report_dir = os.path.join(project_root, 'logging', 'reports')
    
    try:
        # Try to load an existing report summary, otherwise generate it
        summary = report_gen_module.load_report_summary(report_dir, session_id)
        if summary is None:
            events = report_gen_module.load_session_logs(log_dir, session_id)
            if not events:
                return render_template_string(USER_SESSION_REPORT_TEMPLATE, 
                                            session_id=session_id, 
                                            report_html="", 
                                            error="No logs found for this session")
            summary = report_gen_module.summarize_events(events)
            report_gen_module.save_summary(summary, report_dir, session_id)
        
        # Generate HTML report
        report_html = report_gen_module.generate_html_report(summary)
        
        return render_template_string(USER_SESSION_REPORT_TEMPLATE, 
                                    session_id=session_id, 
                                    report_html=report_html, 
                                    error=None)
    except Exception as e:
        return render_template_string(USER_SESSION_REPORT_TEMPLATE, 
                                    session_id=session_id, 
                                    report_html="", 
                                    error=f"Error loading report: {str(e)}")


# LED Routes (完全未改动)
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

# Pump Routes (完全未改动)
@app.route('/fire_pump')
def fire_pump():
    global pump_timer

    reason = request.args.get('reason', 'manual_debug')
    requested_session_id = request.args.get('session_id', '').strip()

    with focus_session_lock:
        active_session_id = focus_session_state.get('session_id', '')
        active_user_id = focus_session_state.get('user_id', -1)
        active_user_name = focus_session_state.get('user_name', 'Guest')

    session_id = requested_session_id or active_session_id or _create_focus_session_id()
    user_id = active_user_id
    user_name = active_user_name

    if pump_timer is None:
        pump_timer = threading.Thread(target=pump_pulse)
        pump_timer.daemon = True
        pump_timer.start()

        _ui_log_event(
            session_id,
            'hardware_control',
            'water_pump_triggered',
            'triggered',
            details={
                'reason': reason,
                'duration_seconds': 1.0,
                'source': 'ui_fire_pump_route',
            },
            user_id=user_id,
            user_name=user_name,
            duration_seconds=1.0,
        )

    return "OK"

@app.route('/toggle')
def toggle_pump():
    return fire_pump()

@app.route('/pump_status')
def get_pump_status():
    return {'is_on': pump.is_active}


@app.route('/fire_buzzer')
def fire_buzzer():
    global buzzer_timer

    reason = request.args.get('reason', 'warning_distraction')
    requested_session_id = request.args.get('session_id', '').strip()

    with focus_session_lock:
        active_session_id = focus_session_state.get('session_id', '')
        active_user_id = focus_session_state.get('user_id', -1)
        active_user_name = focus_session_state.get('user_name', 'Guest')

    session_id = requested_session_id or active_session_id or _create_focus_session_id()
    user_id = active_user_id
    user_name = active_user_name
    duration_seconds = 1.0

    if buzzer_timer is None:
        buzzer_timer = threading.Thread(target=buzzer_pulse, args=(duration_seconds,))
        buzzer_timer.daemon = True
        buzzer_timer.start()

        _ui_log_event(
            session_id,
            'hardware_control',
            'buzzer_triggered',
            'triggered',
            details={
                'reason': reason,
                'duration_seconds': duration_seconds,
                'source': 'ui_fire_buzzer_route',
            },
            user_id=user_id,
            user_name=user_name,
            duration_seconds=duration_seconds,
        )

    return "OK"

# STATUS HELPER (完全未改动)
def get_status_data():
    light_value = 0.5
    if light_sensor_available:
        light_value = read_light_level()
    return {
        'mode': system_mode,
        'led_count': get_current_led_count(),
        'light_value': light_value
    }

# MAIN (完全未改动)
if __name__ == '__main__':
    try:
        print("=" * 50)
        print("Combined LED & Water Pump & Buzzer Control System Starting")
        print("=" * 50)
        print("Initializing hardware...")

        setup_hardware()
        set_led_level(0)

        auto_thread = threading.Thread(target=auto_mode_loop)
        auto_thread.daemon = True
        auto_thread.start()

        print("\n System started successfully!")

        host = os.getenv('UI_HOST', '0.0.0.0')
        port = int(os.getenv('UI_PORT', '5000'))
        use_https = os.getenv('UI_USE_HTTPS', '0').lower() in ('1', 'true', 'yes')
        ssl_cert = os.getenv('UI_SSL_CERT')
        ssl_key = os.getenv('UI_SSL_KEY')

        ssl_context = None
        if use_https:
            if ssl_cert and ssl_key:
                ssl_context = (ssl_cert, ssl_key)
                print(f" HTTPS enabled with cert/key: {ssl_cert}, {ssl_key}")
            else:
                ssl_context = 'adhoc'
                print(" HTTPS enabled with adhoc certificate")

        if use_https:
            print(f" Access Web UI at: https://raspberrypi.local:{port}")
            print(" If browser warns about certificate, continue anyway for local development.")
        else:
            print(f" Access Web UI at: http://raspberrypi.local:{port}")
            print(" Note: remote browser camera access usually requires HTTPS.")

        print("Press Ctrl+C to stop")
        print("=" * 50 + "\n")

        app.run(host=host, port=port, debug=False, use_reloader=False, ssl_context=ssl_context)

    except KeyboardInterrupt:
        print("\nReceived stop command")
        safe_shutdown()
    except Exception as e:
        print(f"\n Startup failed: {str(e)}")
        safe_shutdown()
