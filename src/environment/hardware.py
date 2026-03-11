# hardware.py 硬件驱动层（全gpiozero版本，兼容所有树莓派系统，无冲突）
from gpiozero import LED, LightSensor, DigitalInputDevice, Buzzer
import time

class HardwareController:
    def __init__(self):
        # ==================== 引脚定义（BCM编号，和你的接线1:1对应）====================
        # RGB LED：物理引脚11=GPIO17，13=GPIO27，15=GPIO22
        self.led_r = LED(17)
        self.led_g = LED(27)
        self.led_b = LED(22)
        
        # 有源蜂鸣器：物理引脚16=GPIO23
        self.buzzer = Buzzer(23)
        
        # 传感器初始化
        self.light_sensor = LightSensor(18)  # 光敏电阻：物理引脚12=GPIO18
        self.temp_sensor = DigitalInputDevice(4)  # NTC温敏电阻：物理引脚7=GPIO4
        
        # 初始状态：全部关闭
        self.turn_off_all_leds()
        self.turn_off_buzzer()
        
        print("[硬件] 初始化完成")

    # ==================== RGB LED控制 ====================
    def set_led_color(self, color):
        """设置LED颜色：可选'red'/'green'/'blue'/'off'"""
        self.turn_off_all_leds()
        if color == 'red':
            self.led_r.on()
        elif color == 'green':
            self.led_g.on()
        elif color == 'blue':
            self.led_b.on()
        print(f"[硬件] LED设为: {color}")

    def turn_off_all_leds(self):
        """关闭所有LED"""
        self.led_r.off()
        self.led_g.off()
        self.led_b.off()

    # ==================== 蜂鸣器控制 ====================
    def turn_on_buzzer(self):
        """开启蜂鸣器"""
        self.buzzer.on()
        print("[硬件] 蜂鸣器开启")

    def turn_off_buzzer(self):
        """关闭蜂鸣器"""
        self.buzzer.off()
        print("[硬件] 蜂鸣器关闭")

    # ==================== 传感器数据读取 ====================
    def get_light_level(self):
        """获取光照强度：返回0-1的数值，越亮数值越大"""
        return self.light_sensor.value

    def is_temp_extreme(self):
        """获取温度状态：True=温度异常（过冷/过热），False=温度正常"""
        return self.temp_sensor.value

    # ==================== 资源释放 ====================
    def cleanup(self):
        """程序退出时释放所有硬件资源"""
        self.turn_off_all_leds()
        self.turn_off_buzzer()
        self.led_r.close()
        self.led_g.close()
        self.led_b.close()
        self.buzzer.close()
        self.light_sensor.close()
        self.temp_sensor.close()
        print("[硬件] 资源已释放")
