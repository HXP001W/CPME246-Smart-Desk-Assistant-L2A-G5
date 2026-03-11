# hardware.py: Hardware Driver for Smart Desk Assistant
# Full English version, optimized for Raspberry Pi GPIO compatibility
from gpiozero import LED, LightSensor, DigitalInputDevice, Buzzer
import atexit

class HardwareController:
    def __init__(self):
        # ==================== PIN DEFINITIONS (BCM NUMBERING) ====================
        # RGB LED Pins (matches your physical wiring):
        # Physical Pin 11 = BCM GPIO17 (Red Channel)
        # Physical Pin 13 = BCM GPIO27 (Green Channel)
        # Physical Pin 15 = BCM GPIO22 (Blue Channel)
        self.led_red = LED(17)
        self.led_green = LED(27)
        self.led_blue = LED(22)
        
        # Active Buzzer Pin: Physical Pin 16 = BCM GPIO23
        self.buzzer = Buzzer(23)
        
        # Sensor Pins
        # Photoresistor (Light Sensor): Physical Pin 12 = BCM GPIO18
        self.light_sensor = LightSensor(18)
        # NTC Temperature Sensor: Physical Pin 7 = BCM GPIO4
        self.temp_sensor = DigitalInputDevice(4)
        
        # Auto-cleanup GPIO resources when program exits
        atexit.register(self.cleanup)
        
        # Initialize all devices to OFF state
        self.turn_off_all_leds()
        self.turn_off_buzzer()
        
        print("[Hardware] Initialization completed successfully")

    # ==================== RGB LED Control Functions ====================
    def set_led_color(self, color):
        """
        Set the color of the RGB LED
        Valid options: 'red', 'green', 'blue', 'off'
        """
        self.turn_off_all_leds()
        if color == 'red':
            self.led_red.on()
        elif color == 'green':
            self.led_green.on()
        elif color == 'blue':
            self.led_blue.on()
        print(f"[Hardware] LED set to: {color}")

    def turn_off_all_leds(self):
        """Turn off all RGB LED channels"""
        self.led_red.off()
        self.led_green.off()
        self.led_blue.off()

    # ==================== Buzzer Control Functions ====================
    def turn_on_buzzer(self):
        """Activate the active buzzer"""
        self.buzzer.on()
        print("[Hardware] Buzzer activated")

    def turn_off_buzzer(self):
        """Deactivate the active buzzer"""
        self.buzzer.off()
        print("[Hardware] Buzzer deactivated")

    # ==================== Sensor Data Reading Functions ====================
    def get_light_level(self):
        """
        Get current ambient light level
        Returns: float between 0 (total darkness) and 1 (maximum brightness)
        """
        return self.light_sensor.value

    def is_temperature_extreme(self):
        """
        Check if temperature is out of normal range
        Returns: True = Too hot/too cold; False = Normal temperature
        """
        return self.temp_sensor.value

    # ==================== Resource Cleanup ====================
    def cleanup(self):
        """Safely release all GPIO resources when program exits"""
        self.turn_off_all_leds()
        self.turn_off_buzzer()
        self.led_red.close()
        self.led_green.close()
        self.led_blue.close()
        self.buzzer.close()
        self.light_sensor.close()
        self.temp_sensor.close()
        print("[Hardware] All GPIO resources released successfully")
