# src/environment/mock_hardware.py
"""
模拟硬件驱动层 | Mock Hardware Driver Layer
完全替代树莓派的board、adafruit_dht、adafruit_tsl2591、neopixel库 | Fully replaces Raspberry Pi hardware libraries
支持手动修改模拟环境值，方便无硬件时测试业务逻辑 | Support manual mock value modification for logic test without hardware
"""
import random
import time
from typing import Tuple

# ==================== 1. 模拟树莓派引脚定义 | Mock Raspberry Pi Pin Definition ====================
class MockBoard:
    """
    模拟树莓派board库，统一引脚定义 | Mock Raspberry Pi board library, unified pin definition
    真机替换时直接删除，导入原生board库即可 | Directly replace with native board library when using real Raspberry Pi
    """
    D17 = "GPIO17"  # DHT22温湿度传感器数据引脚 | DHT22 Temperature & Humidity Sensor Data Pin
    D18 = "GPIO18"  # WS2812B灯带PWM控制引脚 | WS2812B LED Strip PWM Control Pin
    I2C = "I2C_BUS_1" # TSL2591光照传感器I2C总线 | TSL2591 Light Sensor I2C Bus

# 导出模拟board实例，和原生库用法完全一致 | Export mock board instance, same usage as native library
board = MockBoard()

# ==================== 2. 模拟DHT22温湿度传感器 | Mock DHT22 Temperature & Humidity Sensor ====================
class MockDHT22:
    """
    模拟DHT22温湿度传感器驱动 | Mock DHT22 Temperature & Humidity Sensor Driver
    模拟真实传感器的随机波动、小概率读取失败特性 | Simulate real sensor's random fluctuation and low-probability read failure
    """
    def __init__(self, pin):
        self.pin = pin  # 传感器连接的GPIO引脚 | GPIO pin connected to the sensor
        # 模拟基础温湿度基准值 | Mock base temperature & humidity value
        self._base_temp = 22.0  # 基础温度22℃ | Base Temperature 22℃
        self._base_humidity = 45.0 # 基础湿度45%RH | Base Humidity 45%RH
        self._error_rate = 0.05 # 模拟5%的读取错误率，贴近真实硬件 | Mock 5% read error rate, close to real hardware

    @property
    def temperature(self):
        """
        模拟温度读取，带随机波动和小概率错误 | Mock temperature read with random fluctuation and low-probability error
        返回值：温度值（单位℃，保留1位小数） | Return: Temperature value (Unit: ℃, 1 decimal place)
        """
        if random.random() < self._error_rate:
            raise RuntimeError("模拟DHT22读取错误：校验和失败 | Mock DHT22 Read Error: Checksum Failed")
        # 温度在基准值上下±2℃范围内随机波动 | Temperature fluctuates within ±2℃ of base value
        return round(self._base_temp + random.uniform(-2.0, 2.0), 1)
    
    @property
    def humidity(self):
        """
        模拟湿度读取，带随机波动和小概率错误 | Mock humidity read with random fluctuation and low-probability error
        返回值：湿度值（单位%RH，保留1位小数） | Return: Humidity value (Unit: %RH, 1 decimal place)
        """
        if random.random() < self._error_rate:
            raise RuntimeError("模拟DHT22读取错误：校验和失败 | Mock DHT22 Read Error: Checksum Failed")
        # 湿度在基准值上下±5%RH范围内随机波动 | Humidity fluctuates within ±5%RH of base value
        return round(self._base_humidity + random.uniform(-5.0, 5.0), 1)
    
    def set_mock_environment(self, temp: float = None, humidity: float = None):
        """
        手动设置模拟环境值，用于边界场景测试 | Manually set mock environment value for boundary scenario test
        :param temp: 目标温度值 | Target temperature value
        :param humidity: 目标湿度值 | Target humidity value
        """
        if temp is not None:
            self._base_temp = temp
        if humidity is not None:
            self._base_humidity = humidity
        print(f"[模拟DHT22 | Mock DHT22] 环境已更新 | Env Updated：温度|Temp={self._base_temp}℃, 湿度|Humidity={self._base_humidity}%RH")

    def exit(self):
        """模拟传感器资源释放 | Mock sensor resource release"""
        print("[模拟DHT22 | Mock DHT22] 传感器已释放 | Sensor Released")

# ==================== 3. 模拟TSL2591光照传感器 | Mock TSL2591 Light Sensor ====================
class MockTSL2591:
    """
    模拟TSL2591高精度光照传感器驱动 | Mock TSL2591 High-Precision Light Sensor Driver
    模拟真实光照值的随机波动，支持手动设置基准值 | Simulate real light value fluctuation, support manual base value setting
    """
    def __init__(self, i2c_bus):
        self.i2c_bus = i2c_bus  # 传感器连接的I2C总线 | I2C bus connected to the sensor
        self._base_lux = 450.0 # 基础光照450lux（适合学习的标准亮度）| Base Light 450lux (Standard brightness for study)
        self._gain = 1.0 # 传感器增益 | Sensor gain

    @property
    def lux(self):
        """
        模拟光照度读取，带随机波动 | Mock illuminance read with random fluctuation
        返回值：光照度值（单位lux，保留1位小数） | Return: Illuminance value (Unit: lux, 1 decimal place)
        """
        # 光照在基准值上下±300lux范围内波动，最低为0 | Light fluctuates within ±300lux of base value, minimum 0
        return round(max(self._base_lux + random.uniform(-300.0, 300.0), 0.0), 1)
    
    def set_mock_lux(self, lux: float):
        """
        手动设置模拟光照值，测试自适应调光逻辑 | Manually set mock light value for adaptive dimming logic test
        :param lux: 目标光照度值 | Target illuminance value
        """
        self._base_lux = max(lux, 0.0)
        print(f"[模拟TSL2591 | Mock TSL2591] 光照已更新 | Light Updated：{self._base_lux}lux")

# ==================== 4. 模拟WS2812B LED灯带 | Mock WS2812B LED Strip ====================
class MockNeoPixel:
    """
    模拟WS2812B可寻址LED灯带驱动 | Mock WS2812B Addressable LED Strip Driver
    模拟灯带亮度、颜色控制，通过打印日志验证逻辑 | Simulate strip brightness & color control, verify logic via log print
    """
    def __init__(self, pin, n: int, brightness: float = 1.0, auto_write: bool = False):
        self.pin = pin  # 灯带连接的PWM引脚 | PWM pin connected to the strip
        self.n = n # 灯珠总数量 | Total number of LED beads
        self._brightness = brightness # 灯带全局亮度（0-1）| Global brightness of the strip (0-1)
        self.auto_write = auto_write # 是否自动刷新灯带显示 | Whether to auto refresh the strip display
        # 模拟灯珠颜色数据，初始全灭 | Mock LED color data, initial all off
        self._led_data = [(0, 0, 0)] * n

    @property
    def brightness(self):
        """获取灯带全局亮度 | Get global brightness of the strip"""
        return self._brightness
    
    @brightness.setter
    def brightness(self, value: float):
        """
        设置灯带全局亮度，自动限幅0-1 | Set global brightness, auto limit range 0-1
        :param value: 目标亮度值 | Target brightness value
        """
        self._brightness = max(0.0, min(1.0, value))
        if self.auto_write:
            self.show()

    def fill(self, color: Tuple[int, int, int]):
        """
        填充所有灯珠为同一颜色 | Fill all LEDs with the same color
        :param color: RGB颜色元组 (R, G, B) | RGB color tuple (R, G, B)
        """
        self._led_data = [color] * self.n
        if self.auto_write:
            self.show()

    def show(self):
        """
        模拟灯带刷新显示 | Mock strip display refresh
        真机上会直接驱动灯珠点亮，这里打印日志验证逻辑 | Drives LEDs on real hardware, here print log to verify logic
        """
        # 计算实际显示的颜色（考虑亮度系数）| Calculate actual display color (consider brightness factor)
        r, g, b = self._led_data[0]
        actual_r = int(r * self._brightness)
        actual_g = int(g * self._brightness)
        actual_b = int(b * self._brightness)
        print(f"[模拟WS2812B | Mock WS2812B] 灯带已更新 | Strip Updated：亮度|Brightness={self._brightness:.2f}, 颜色|Color=({actual_r}, {actual_g}, {actual_b})")
