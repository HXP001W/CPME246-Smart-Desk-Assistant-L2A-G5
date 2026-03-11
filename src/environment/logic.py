# logic.py: Core Business Logic for Smart Desk Assistant
# Full English version, handles Auto and Manual operation modes
from hardware import HardwareController
import time
import threading

class DeskController:
    def __init__(self):
        # Initialize hardware controller
        self.hw = HardwareController()
        
        # System operation mode: 'auto' (default) or 'manual'
        self.mode = 'auto'
        
        # Auto Mode Thresholds (adjust these values for your environment)
        self.light_threshold_high = 0.7   # Light > 0.7 = Too Bright
        self.light_threshold_low = 0.3    # Light < 0.3 = Too Dark
        
        # Manual Mode State
        self.manual_led_color = 'off'
        self.manual_buzzer_active = False
        
        # Runtime control
        self._running = False
        self._control_thread = None

    def set_mode(self, mode):
        """Switch system operation mode between 'auto' and 'manual'"""
        if mode not in ['auto', 'manual']:
            print(f"[Logic] Invalid mode: {mode}, must be 'auto' or 'manual'")
            return
        self.mode = mode
        print(f"[Logic] System mode switched to: {mode}")

    def set_manual_led(self, color):
        """Set LED color (only active in Manual Mode)"""
        self.manual_led_color = color
        if self.mode == 'manual':
            self.hw.set_led_color(color)

    def set_manual_buzzer(self, active):
        """Control buzzer on/off (only active in Manual Mode)"""
        self.manual_buzzer_active = active
        if self.mode == 'manual':
            if active:
                self.hw.turn_on_buzzer()
            else:
                self.hw.turn_off_buzzer()

    def auto_control_loop(self):
        """Main loop for Auto Mode: auto-control LED and buzzer from sensor data"""
        while self._running:
            if self.mode == 'auto':
                # Read real-time sensor data
                current_light = self.hw.get_light_level()
                temp_is_extreme = self.hw.is_temperature_extreme()

                # Control LED based on ambient light level
                if current_light >= self.light_threshold_high:
                    self.hw.set_led_color('red')
                elif current_light <= self.light_threshold_low:
                    self.hw.set_led_color('blue')
                else:
                    self.hw.set_led_color('green')

                # Control buzzer based on temperature status
                if temp_is_extreme:
                    self.hw.turn_on_buzzer()
                else:
                    self.hw.turn_off_buzzer()

                # Print real-time status for debugging
                print(f"[Logic] Auto Mode | Light Level: {current_light:.2f} | Temperature Abnormal: {temp_is_extreme}")
            
            # 1 second delay between sensor checks
            time.sleep(1)

    def get_system_status(self):
        """Get current system status for Web UI display"""
        return {
            'mode': self.mode,
            'light_level': round(self.hw.get_light_level(), 2),
            'temp_extreme': self.hw.is_temperature_extreme(),
            'manual_led_color': self.manual_led_color,
            'manual_buzzer_active': self.manual_buzzer_active
        }

    def start(self):
        """Start the system control loop in a background thread"""
        if self._running:
            print("[Logic] System is already running")
            return
        self._running = True
        self._control_thread = threading.Thread(target=self.auto_control_loop, daemon=True)
        self._control_thread.start()
        print("[Logic] Smart Desk Assistant started successfully")

    def stop(self):
        """Stop the system and safely release all resources"""
        self._running = False
        if self._control_thread:
            self._control_thread.join()
        self.hw.cleanup()
        print("[Logic] Smart Desk Assistant stopped successfully")
