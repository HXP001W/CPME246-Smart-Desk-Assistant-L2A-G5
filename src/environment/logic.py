# logic.py 核心业务逻辑
from hardware import HardwareController
import time

class DeskController:
    def __init__(self):
        self.hw = HardwareController()
        
        # 系统模式
        self.mode = 'auto'  # 'auto' 或 'manual'
        
        # 自动模式阈值
        self.light_high = 0.7   # 光照>0.7=太亮
        self.light_low = 0.3    # 光照<0.3=太暗
        
        # 手动模式状态
        self.manual_led = 'off'
        self.manual_buzzer_on = False
        
        # 运行状态
        self._running = False

    def set_mode(self, mode):
        """切换模式"""
        self.mode = mode
        print(f"[逻辑] 模式切换为: {mode}")

    def set_manual_led(self, color):
        """手动设置LED"""
        self.manual_led = color
        if self.mode == 'manual':
            self.hw.set_led_color(color)

    def set_manual_buzzer(self, on):
        """手动开关蜂鸣器"""
        self.manual_buzzer_on = on
        if self.mode == 'manual':
            self.hw.turn_on_buzzer() if on else self.hw.turn_off_buzzer()

    def auto_control(self):
        """
        自动控制逻辑：
        1. 亮度控制LED：太暗→蓝，正常→绿，太亮→红
        2. 温度控制蜂鸣器：异常→响，正常→关
        """
        if self.mode != 'auto':
            return

        # 读取传感器
        light = self.hw.get_light_level()
        temp_extreme = self.hw.is_temp_extreme()

        # 1. 亮度控制LED
        if light >= self.light_high:
            self.hw.set_led_color('red')
        elif light <= self.light_low:
            self.hw.set_led_color('blue')
        else:
            self.hw.set_led_color('green')

        # 2. 温度控制蜂鸣器
        if temp_extreme:
            self.hw.turn_on_buzzer()
        else:
            self.hw.turn_off_buzzer()

        print(f"[逻辑] 自动 | 光照: {light:.2f} | 温度异常: {temp_extreme}")

    def get_status(self):
        """获取系统状态供UI显示"""
        return {
            'mode': self.mode,
            'light_level': round(self.hw.get_light_level(), 2),
            'temp_extreme': self.hw.is_temp_extreme(),
            'manual_led': self.manual_led,
            'manual_buzzer_on': self.manual_buzzer_on
        }

    def run(self):
        """启动主循环"""
        self._running = True
        print("[逻辑] 桌面助手已启动")
        try:
            while self._running:
                if self.mode == 'auto':
                    self.auto_control()
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self._running = False
        self.hw.cleanup()
        print("[逻辑] 桌面助手已停止")
