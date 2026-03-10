# logic.py 核心业务逻辑层
from hardware import HardwareController
import time

class EnvController:
    def __init__(self):
        # 初始化硬件控制器
        self.hw = HardwareController()
        
        # 系统运行模式：auto=自动模式，manual=手动模式（Web UI控制）
        self.mode = 'auto'
        
        # 自动模式阈值设置（可根据需求调整）
        self.light_high = 0.7   # 光照强度≥0.7 → 判定为环境太亮
        self.light_low = 0.3    # 光照强度≤0.3 → 判定为环境太暗
        
        # 手动模式状态记录
        self.manual_led = 'off'
        self.manual_buzzer_on = False
        
        # 控制器运行状态
        self._running = False

    def set_mode(self, mode):
        """切换系统运行模式：'auto' 自动模式 / 'manual' 手动模式"""
        self.mode = mode
        print(f"[逻辑] 系统模式已切换为: {mode}")
        
        # 切换到手动模式时，立即生效当前的手动设置
        if mode == 'manual':
            self.hw.set_led_color(self.manual_led)
            self.hw.turn_on_buzzer() if self.manual_buzzer_on else self.hw.turn_off_buzzer()

    def set_manual_led(self, color):
        """手动模式设置LED颜色，仅手动模式下生效"""
        self.manual_led = color
        if self.mode == 'manual':
            self.hw.set_led_color(color)

    def set_manual_buzzer(self, on):
        """手动模式开关蜂鸣器，仅手动模式下生效"""
        self.manual_buzzer_on = on
        if self.mode == 'manual':
            self.hw.turn_on_buzzer() if on else self.hw.turn_off_buzzer()

    def auto_control(self):
        """
        自动控制核心逻辑（完全匹配你的需求）
        1. 光照强度独立控制LED灯：太亮→红灯，正常→绿灯，太暗→蓝灯
        2. 温度状态独立控制蜂鸣器：温度过高→开启，温度正常→关闭
        两个逻辑完全独立，互不干扰
        """
        if self.mode != 'auto':
            return

        try:
            # 读取传感器实时数据
            light_level = self.hw.get_light_level()
            temp_high = self.hw.get_temp_high()

            # ==================== 1. 光照控制LED灯 ====================
            if light_level >= self.light_high:
                self.hw.set_led_color('red')
            elif light_level <= self.light_low:
                self.hw.set_led_color('blue')
            else:
                self.hw.set_led_color('green')

            # ==================== 2. 温度控制蜂鸣器 ====================
            if temp_high:
                self.hw.turn_on_buzzer()
            else:
                self.hw.turn_off_buzzer()

            print(f"[逻辑] 自动控制 | 光照强度: {light_level:.2f} | 温度过高: {temp_high}")
        except Exception as e:
            print(f"[逻辑] 自动控制执行出错！错误信息：{e}")

    def get_status(self):
        """获取系统当前全部状态，供Web UI显示"""
        return {
            'mode': self.mode,
            'light_level': round(self.hw.get_light_level(), 2),
            'temp_high': self.hw.get_temp_high(),
            'manual_led': self.manual_led,
            'manual_buzzer_on': self.manual_buzzer_on
        }

    def run(self):
        """启动控制器主循环（后台线程运行，不阻塞Web服务）"""
        self._running = True
        print("[逻辑] 环境控制器已启动")
        try:
            while self._running:
                self.auto_control()
                time.sleep(1)
        except KeyboardInterrupt:
            print("[逻辑] 检测到用户中断，正在停止控制器")
        finally:
            self.stop()

    def stop(self):
        """停止控制器，释放所有硬件资源"""
        self._running = False
        self.hw.cleanup()
        print("[逻辑] 控制器已完全停止")
