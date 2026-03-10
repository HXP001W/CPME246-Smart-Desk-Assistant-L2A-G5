# logic.py 核心业务逻辑，已适配新需求
from hardware import HardwareController
import time

class EnvController:
    def __init__(self):
        # 初始化硬件控制器
        self.hw = HardwareController()
        
        # 系统模式：auto=自动模式，manual=手动模式（UI控制）
        self.mode = 'auto'
        
        # 阈值设置（可通过UI修改）
        self.light_high = 0.7   # 光照>0.7=太亮
        self.light_low = 0.3    # 光照<0.3=太暗
        
        # 手动模式状态
        self.manual_led = 'off'
        self.manual_buzzer_on = False
        
        # 运行状态
        self._running = False

    def set_mode(self, mode):
        """切换系统模式：'auto'/'manual'"""
        self.mode = mode
        print(f"[逻辑] 模式切换为: {mode}")

    def set_manual_led(self, color):
        """手动模式设置LED颜色"""
        self.manual_led = color
        if self.mode == 'manual':
            self.hw.set_led_color(color)

    def set_manual_buzzer(self, on):
        """手动模式开关蜂鸣器"""
        self.manual_buzzer_on = on
        if self.mode == 'manual':
            self.hw.turn_on_buzzer() if on else self.hw.turn_off_buzzer()

    def auto_control(self):
        """
        自动控制核心逻辑（完全适配你的需求）
        1. 光照控制LED：太亮→红灯，正常→绿灯，太暗→蓝灯（和蜂鸣器完全无关）
        2. 温度控制蜂鸣器：温度过高→响，正常→关（和亮度完全无关）
        """
        if self.mode != 'auto':
            return

        # 读取传感器数据
        light_level = self.hw.get_light_level()
        temp_high = self.hw.get_temp_high()

        # ==================== 1. 光照控制LED（仅控制灯，不碰蜂鸣器）====================
        if light_level >= self.light_high:
            # 光照太亮：红灯亮
            self.hw.set_led_color('red')
        elif light_level <= self.light_low:
            # 光照太暗：蓝灯亮
            self.hw.set_led_color('blue')
        else:
            # 光照正常：绿灯亮
            self.hw.set_led_color('green')

        # ==================== 2. 温度控制蜂鸣器（仅温度触发，和亮度完全无关）====================
        if temp_high:
            # 温度过高：开启蜂鸣器
            self.hw.turn_on_buzzer()
        else:
            # 温度正常：关闭蜂鸣器
            self.hw.turn_off_buzzer()

        print(f"[逻辑] 自动控制 | 光照: {light_level:.2f} | 温度过高: {temp_high}")

    def get_status(self):
        """获取系统当前状态，供UI显示"""
        return {
            'mode': self.mode,
            'light_level': round(self.hw.get_light_level(), 2),
            'temp_high': self.hw.get_temp_high(),
            'manual_led': self.manual_led,
            'manual_buzzer_on': self.manual_buzzer_on
        }

    def run(self):
        """启动控制器主循环"""
        self._running = True
        print("[逻辑] 环境控制器已启动")
        try:
            while self._running:
                if self.mode == 'auto':
                    self.auto_control()
                time.sleep(1)  # 每秒更新一次
        except KeyboardInterrupt:
            print("[逻辑] 检测到中断，正在停止")
        finally:
            self.stop()

    def stop(self):
        """停止控制器，释放资源"""
        self._running = False
        self.hw.cleanup()
        print("[逻辑] 控制器已停止")
