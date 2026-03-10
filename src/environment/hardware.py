# hardware.py 硬件驱动层，已移除风扇功能
import RPi.GPIO as GPIO
from gpiozero import LightSensor, DigitalInputDevice
import atexit  # 程序退出时自动清理GPIO

class HardwareController:
    def __init__(self):
        print("[系统] 正在初始化环境控制器...")
        try:
            # ---------------------- GPIO 基础设置 ----------------------
            # 使用物理引脚编号（和你的接线表完全对应）
            GPIO.setmode(GPIO.BOARD)
            # 关闭警告（避免重复初始化提示）
            GPIO.setwarnings(False)
            # 注册程序退出时自动清理所有GPIO资源
            atexit.register(GPIO.cleanup)

            # ---------------------- 引脚定义（和你截图完全一致） ----------------------
            # RGB LED 引脚（物理引脚）
            self.LED_R = 11  # 11号物理引脚（GPIO17）- RGB红灯，串联220Ω电阻
            self.LED_G = 13  # 13号物理引脚（GPIO27）- RGB绿灯，串联220Ω电阻
            self.LED_B = 15  # 15号物理引脚（GPIO22）- RGB蓝灯，串联220Ω电阻
            # 有源蜂鸣器 引脚（物理引脚）
            self.BUZZER = 16  # 16号物理引脚（GPIO23）- 蜂鸣器正极，串联1kΩ电阻

            # ---------------------- 硬件初始化 ----------------------
            # RGB LED 设置为输出模式
            GPIO.setup(self.LED_R, GPIO.OUT)
            GPIO.setup(self.LED_G, GPIO.OUT)
            GPIO.setup(self.LED_B, GPIO.OUT)
            # 蜂鸣器 设置为输出模式，初始状态关闭（低电平）
            GPIO.setup(self.BUZZER, GPIO.OUT, initial=GPIO.LOW)

            # ---------------------- 传感器初始化（gpiozero用BCM编号） ----------------------
            # 光敏电阻：引脚2接12号物理引脚 → 对应BCM编号18
            self.light_sensor = LightSensor(18)
            # NTC温敏电阻：引脚2接7号物理引脚 → 对应BCM编号4
            self.temp_sensor = DigitalInputDevice(4)

            print("[硬件] 初始化成功！")
        except Exception as e:
            print(f"[硬件] 初始化失败！错误信息：'{e}'")
            print("[硬件] 请检查：1. 是否用sudo权限运行 2. 硬件接线是否正确 3. 传感器是否正常")
            raise  # 抛出异常，让上层知道初始化失败

    # ---------------------- 硬件控制方法 ----------------------
    def set_rgb(self, r, g, b):
        """设置RGB LED颜色（r/g/b为True/False，对应亮/灭）"""
        GPIO.output(self.LED_R, GPIO.HIGH if r else GPIO.LOW)
        GPIO.output(self.LED_G, GPIO.HIGH if g else GPIO.LOW)
        GPIO.output(self.LED_B, GPIO.HIGH if b else GPIO.LOW)

    def set_buzzer(self, state):
        """控制蜂鸣器（True=响，False=静音）"""
        GPIO.output(self.BUZZER, GPIO.HIGH if state else GPIO.LOW)

    def get_light_level(self):
        """获取光照强度（0~1，0=最暗，1=最亮）"""
        return self.light_sensor.value

    def get_temp_status(self):
        """获取温度传感器状态（True=激活，False=未激活）"""
        return self.temp_sensor.is_active
