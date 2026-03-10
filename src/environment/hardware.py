# hardware.py 硬件驱动层 100%适配你的引脚接线表
import RPi.GPIO as GPIO
from gpiozero import LightSensor, DigitalInputDevice
import time

class HardwareController:
    def __init__(self):
        try:
            # GPIO设置：使用物理引脚编号，和你的接线表完全对应
            GPIO.setmode(GPIO.BOARD)
            GPIO.setwarnings(False)
            
            # ==================== 引脚定义（和你的接线表完全一致）====================
            # RGB LED 引脚（物理引脚）
            self.LED_R = 11    # 11号物理引脚（GPIO17）- RGB红灯，串联220Ω电阻
            self.LED_G = 13    # 13号物理引脚（GPIO27）- RGB绿灯，串联220Ω电阻
            self.LED_B = 15    # 15号物理引脚（GPIO22）- RGB蓝灯，串联220Ω电阻
            # 有源蜂鸣器 引脚（物理引脚）
            self.BUZZER = 16   # 16号物理引脚（GPIO23）- 蜂鸣器正极，串联1kΩ电阻
            
            # ==================== 硬件初始化 ====================
            # RGB LED 设置为输出模式
            GPIO.setup(self.LED_R, GPIO.OUT)
            GPIO.setup(self.LED_G, GPIO.OUT)
            GPIO.setup(self.LED_B, GPIO.OUT)
            # 蜂鸣器 设置为输出模式，初始状态关闭
            GPIO.setup(self.BUZZER, GPIO.OUT, initial=GPIO.LOW)
            
            # 传感器初始化（gpiozero库使用BCM编号，和你的接线表对应）
            # 光敏电阻：引脚2接12号物理引脚 → 对应BCM编号18
            self.light_sensor = LightSensor(18)
            # NTC温敏电阻：引脚2接7号物理引脚 → 对应BCM编号4
            self.temp_sensor = DigitalInputDevice(4)
            
            # 初始状态：关闭所有外设
            self.turn_off_all_leds()
            self.turn_off_buzzer()
            
            print("[硬件] 初始化完成，引脚已完全匹配接线表")
        except Exception as e:
            print(f"[硬件] 初始化失败！错误信息：{e}")
            print("[硬件] 请检查：1. 是否用sudo权限运行 2. 硬件接线是否正确 3. 传感器是否正常")
            raise  # 抛出异常，终止无效运行

    # ==================== RGB LED 控制函数 ====================
    def set_led_color(self, color):
        """设置LED颜色：可选值 'red'/'green'/'blue'/'off' """
        # 先关闭所有灯，避免多色同时亮
        self.turn_off_all_leds()
        if color == 'red':
            GPIO.output(self.LED_R, GPIO.HIGH)
        elif color == 'green':
            GPIO.output(self.LED_G, GPIO.HIGH)
        elif color == 'blue':
            GPIO.output(self.LED_B, GPIO.HIGH)
        print(f"[硬件] LED颜色已设置为: {color}")

    def turn_off_all_leds(self):
        """关闭所有RGB LED灯"""
        GPIO.output(self.LED_R, GPIO.LOW)
        GPIO.output(self.LED_G, GPIO.LOW)
        GPIO.output(self.LED_B, GPIO.LOW)

    # ==================== 蜂鸣器控制函数 ====================
    def turn_on_buzzer(self):
        """开启蜂鸣器（温度过高触发）"""
        GPIO.output(self.BUZZER, GPIO.HIGH)
        print("[硬件] 蜂鸣器已开启")

    def turn_off_buzzer(self):
        """关闭蜂鸣器"""
        GPIO.output(self.BUZZER, GPIO.LOW)
        print("[硬件] 蜂鸣器已关闭")

    # ==================== 传感器数据读取函数 ====================
    def get_light_level(self):
        """获取光照强度，返回0-1的数值，数值越大环境越亮"""
        return self.light_sensor.value

    def get_temp_high(self):
        """获取温度状态：True=温度过高，False=温度正常"""
        return self.temp_sensor.value

    # ==================== 资源释放函数 ====================
    def cleanup(self):
        """程序退出时，释放所有GPIO资源，关闭所有外设"""
        self.turn_off_all_leds()
        self.turn_off_buzzer()
        GPIO.cleanup()
        print("[硬件] 所有GPIO资源已释放，外设已全部关闭")
