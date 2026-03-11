# hardware.py 硬件驱动层
import RPi.GPIO as GPIO
from gpiozero import LightSensor, DigitalInputDevice
import time

class HardwareController:
    def __init__(self):
        # 使用物理引脚编号（BOARD），和接线表1:1对应
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)
        
        # ==================== 引脚定义 ====================
        # RGB LED引脚
        self.LED_R = 11
        self.LED_G = 13
        self.LED_B = 15
        # 蜂鸣器引脚
        self.BUZZER = 16
        
        # ==================== 硬件初始化 ====================
        # LED设置为输出
        GPIO.setup(self.LED_R, GPIO.OUT)
        GPIO.setup(self.LED_G, GPIO.OUT)
        GPIO.setup(self.LED_B, GPIO.OUT)
        # 蜂鸣器设置为输出，初始关闭
        GPIO.setup(self.BUZZER, GPIO.OUT, initial=GPIO.LOW)
        
        # 传感器初始化
        self.light_sensor = LightSensor(18)  # GPIO18对应物理引脚12
        self.temp_sensor = DigitalInputDevice(4)  # GPIO4对应物理引脚7
        
        # 初始状态：全部关闭
        self.turn_off_all_leds()
        self.turn_off_buzzer()
        
        print("[硬件] 初始化完成")

    # ==================== RGB LED控制 ====================
    def set_led_color(self, color):
        """设置LED颜色：'red'/'green'/'blue'/'off'"""
        self.turn_off_all_leds()
        if color == 'red':
            GPIO.output(self.LED_R, GPIO.HIGH)
        elif color == 'green':
            GPIO.output(self.LED_G, GPIO.HIGH)
        elif color == 'blue':
            GPIO.output(self.LED_B, GPIO.HIGH)
        print(f"[硬件] LED设为: {color}")

    def turn_off_all_leds(self):
        GPIO.output(self.LED_R, GPIO.LOW)
        GPIO.output(self.LED_G, GPIO.LOW)
        GPIO.output(self.LED_B, GPIO.LOW)

    # ==================== 蜂鸣器控制 ====================
    def turn_on_buzzer(self):
        GPIO.output(self.BUZZER, GPIO.HIGH)
        print("[硬件] 蜂鸣器开启")

    def turn_off_buzzer(self):
        GPIO.output(self.BUZZER, GPIO.LOW)
        print("[硬件] 蜂鸣器关闭")

    # ==================== 传感器数据读取 ====================
    def get_light_level(self):
        """获取光照强度：0-1，越亮越大"""
        return self.light_sensor.value

    def is_temp_extreme(self):
        """获取温度状态：True=温度异常（过冷/过热），False=正常"""
        return self.temp_sensor.value

    # ==================== 资源释放 ====================
    def cleanup(self):
        self.turn_off_all_leds()
        self.turn_off_buzzer()
        GPIO.cleanup()
        print("[硬件] 资源已释放")
