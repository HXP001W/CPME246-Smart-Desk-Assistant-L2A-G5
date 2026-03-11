# src/environment/environment_monitor.py
"""
环境检测系统核心业务逻辑类 | Core Business Logic Class of Environment Detection System
完全对齐团队接口规范，拿到树莓派后仅需替换硬件库导入 | Fully aligned with team interface specs, only need to replace hardware library import on Raspberry Pi
实现：观察者模式、环境数据采集、自适应调光、用户配置管理 | Implements: Observer Pattern, Env Data Collection, Adaptive Dimming, User Config Management
"""
import time
from typing import Callable, List, Dict
from datetime import datetime

# ==================== 【真机替换关键 | Key for Real Hardware】====================
# 拿到树莓派后，删除下方模拟库导入，取消注释上方真实库导入即可
# When using real Raspberry Pi, delete mock import below, uncomment real import above
# 真实硬件库导入 | Real Hardware Library Import
# import board
# import adafruit_dht
# import adafruit_tsl2591
# import neopixel

# 模拟硬件库导入 | Mock Hardware Library Import
from mock_hardware import board, MockDHT22 as adafruit_dht
from mock_hardware import MockTSL2591 as adafruit_tsl2591
from mock_hardware import MockNeoPixel as neopixel

class EnvironmentMonitor:
    """
    环境监测系统主控制器 | Main Controller of Environment Monitoring System
    负责所有环境感知、灯光控制、数据分发的核心逻辑 | Responsible for core logic of env sensing, light control, data distribution
    完全符合课程面向对象设计、设计模式的考核要求 | Fully meets course requirements for OOP and design patterns
    """
    def __init__(self):
        # ==================== 1. 硬件初始化 | Hardware Initialization ====================
        # DHT22温湿度传感器，连接GPIO17 | DHT22 Temp&Humidity Sensor, connected to GPIO17
        self.dht_device = adafruit_dht.DHT22(board.D17)
        # TSL2591光照传感器，连接I2C总线 | TSL2591 Light Sensor, connected to I2C bus
        self.i2c = board.I2C
        self.light_sensor = adafruit_tsl2591.TSL2591(self.i2c)
        # WS2812B LED灯带，连接GPIO18，30颗灯珠 | WS2812B LED Strip, connected to GPIO18, 30 LEDs
        self.LED_COUNT = 30
        self.LED_PIN = board.D18
        self.led_strip = neopixel.NeoPixel(
            self.LED_PIN, self.LED_COUNT, brightness=1.0, auto_write=False
        )

        # ==================== 2. 系统配置 | System Configuration ====================
        # 可由UI/主系统动态修改，对接团队设置页面 | Can be dynamically modified by UI/Main Controller, aligned with team settings page
        self.config = {
            "target_lux": 450.0,       # 用户目标光照度 | User target illuminance (lux)
            "auto_light_enabled": True, # 自动调光功能开关 | Auto dimming function switch
            "data_update_interval": 1.0,# 数据更新频率（秒）| Data update interval (second)
            "temp_warning_threshold": 35.0, # 高温告警阈值 | High temperature warning threshold (℃)
            "light_color": (255, 220, 150) # 护眼暖白光RGB值 | Eye-friendly warm white RGB value
        }

        # ==================== 3. 观察者模式 | Observer Pattern ====================
        # 注册的观察者回调函数，数据更新时自动触发 | Registered observer callbacks, auto triggered on data update
        # 对接：主系统、UI界面、日志模块、告警模块 | Connect to: Main Controller, UI, Logger, Warning Module
        self._observers: List[Callable] = []

        # ==================== 4. 对外暴露的标准环境数据 | Standard Env Data Exposed Externally ====================
        # 完全对齐团队接口规范，所有模块统一使用该格式 | Fully aligned with team interface specs, unified format for all modules
        self.current_data = {
            "temperature": 0.0,    # 温度 | Temperature (Unit: ℃, 1 decimal)
            "humidity": 0.0,       # 湿度 | Humidity (Unit: %RH, 1 decimal)
            "lux": 0.0,            # 光照度 | Illuminance (Unit: lux, 1 decimal)
            "timestamp": "",       # 时间戳 | Timestamp (Format: %Y-%m-%d %H:%M:%S)
            "temp_warning": False, # 高温告警标志 | High temperature warning flag
            "auto_light_enabled": True # 自动调光状态 | Auto dimming status
        }

        # 系统运行状态标志 | System running status flag
        self._running = False

    # ==================== 观察者模式核心方法 | Core Methods of Observer Pattern ====================
    def register_observer(self, callback: Callable):
        """
        注册观察者，数据更新时自动调用回调函数 | Register observer, callback will be auto called on data update
        :param callback: 回调函数，入参为current_data字典 | Callback function, input is current_data dict
        """
        self._observers.append(callback)
        print(f"[环境系统 | Env System] 新观察者已注册 | New Observer Registered，当前总数 | Current Count：{len(self._observers)}")

    def _notify_observers(self):
        """
        通知所有观察者，触发数据更新回调 | Notify all observers, trigger data update callbacks
        传递数据副本，避免外部修改原始数据 | Pass data copy to avoid external modification of raw data
        """
        for callback in self._observers:
            try:
                callback(self.current_data.copy())
            except Exception as e:
                print(f"[环境系统 | Env System] 观察者回调错误 | Observer Callback Error：{e}")

    # ==================== 核心业务逻辑方法 | Core Business Logic Methods ====================
    def read_environment_data(self) -> bool:
        """
        读取温湿度、光照度数据，处理异常值和传感器抖动 | Read env data, handle outliers and sensor jitter
        :return: 读取成功返回True，失败返回False | Return True if read success, False if failed
        """
        try:
            # 从传感器读取原始数据 | Read raw data from sensors
            temperature = self.dht_device.temperature
            humidity = self.dht_device.humidity
            lux = self.light_sensor.lux

            # 数据合法性校验，过滤物理层面的异常值 | Data validity check, filter physical outliers
            if (temperature is not None and humidity is not None and lux is not None
                and -40 <= temperature <= 80 and 0 <= humidity <= 100):
                
                # 更新对外暴露的实时数据 | Update exposed real-time data
                self.current_data.update({
                    "temperature": round(temperature, 1),
                    "humidity": round(humidity, 1),
                    "lux": round(lux, 1),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "temp_warning": temperature >= self.config["temp_warning_threshold"],
                    "auto_light_enabled": self.config["auto_light_enabled"]
                })

                # 数据更新后通知所有观察者 | Notify all observers after data update
                self._notify_observers()
                return True

        except RuntimeError:
            # DHT22常见的瞬时读取错误，忽略后重试，不中断程序 | Common transient read error of DHT22, ignore and retry
            pass
        except Exception as e:
            print(f"[环境系统 | Env System] 数据读取错误 | Data Read Error：{e}")
        return False

    def adaptive_light_control(self):
        """
        自适应灯光调节核心逻辑 | Core Logic of Adaptive Light Control
        基于当前光照度和用户目标值，动态调节灯带亮度，避免频繁闪烁 | Dynamically adjust strip brightness based on current and target light, avoid frequent flicker
        """
        # 自动调光关闭时直接返回 | Return directly if auto dimming is disabled
        if not self.config["auto_light_enabled"]:
            return

        current_lux = self.current_data["lux"]
        target_lux = self.config["target_lux"]

        # 比例控制逻辑，设置±10%死区避免灯带频繁闪烁 | Proportional control, ±10% dead zone to avoid flicker
        if current_lux >= target_lux * 1.1:
            # 光照充足，线性降低亮度 | Sufficient light, linearly reduce brightness
            brightness_ratio = max(0.0, 1.0 - (current_lux - target_lux) / max(target_lux, 100))
        elif current_lux <= target_lux * 0.9:
            # 光照不足，线性提高亮度 | Insufficient light, linearly increase brightness
            brightness_ratio = min(1.0, target_lux / max(current_lux, 10))
        else:
            # 在目标值±10%范围内，保持亮度不变 | Within ±10% of target, keep brightness unchanged
            return

        # 执行灯带亮度调节 | Execute strip brightness adjustment
        self.led_strip.brightness = brightness_ratio
        self.led_strip.fill(self.config["light_color"])
        self.led_strip.show()

    def update_config(self, new_config: Dict):
        """
        更新系统配置，对接UI界面的用户设置 | Update system config, aligned with UI user settings
        :param new_config: 配置字典，仅更新传入的键值对 | Config dict, only update passed key-value pairs
        """
        self.config.update(new_config)
        print(f"[环境系统 | Env System] 配置已更新 | Config Updated：{self.config}")
        # 配置更新后立即执行一次调光 | Execute dimming immediately after config update
        self.adaptive_light_control()

    def load_user_profile(self, user_profile: Dict):
        """
        加载用户专属环境偏好配置，对接人脸识别模块 | Load user's exclusive env preference, aligned with face recognition module
        :param user_profile: 用户配置字典，包含光照、灯光、开关等偏好 | User profile dict, includes light, color, switch preferences
        """
        # 提取环境相关配置，过滤无关字段 | Extract env-related config, filter irrelevant fields
        user_env_config = {
            "target_lux": user_profile.get("target_lux", 450.0),
            "light_color": user_profile.get("light_color", (255, 220, 150)),
            "auto_light_enabled": user_profile.get("auto_light_enabled", True)
        }
        self.update_config(user_env_config)
        print(f"[环境系统 | Env System] 用户配置已加载 | User Profile Loaded")

    # ==================== 运行与资源清理方法 | Run & Resource Cleanup Methods ====================
    def run_monitor_loop(self):
        """
        核心监测循环，需在独立线程中运行，不阻塞主系统 | Core monitor loop, need to run in separate thread, no block to main system
        """
        self._running = True
        print("[环境系统 | Env System] 监测循环已启动 | Monitor Loop Started")
        while self._running:
            # 读取环境数据 | Read env data
            if self.read_environment_data():
                # 执行自适应灯光调节 | Execute adaptive light control
                self.adaptive_light_control()
            # 按设定间隔休眠 | Sleep by set interval
            time.sleep(self.config["data_update_interval"])

    def stop(self):
        """停止监测循环 | Stop monitor loop"""
        self._running = False
        print("[环境系统 | Env System] 监测循环已停止 | Monitor Loop Stopped")

    def cleanup(self):
        """
        程序退出时的资源释放，硬件安全关闭 | Resource release on program exit, safe hardware shutdown
        必须在程序退出前调用，避免硬件损坏 | Must be called before program exit to avoid hardware damage
        """
        self.stop()
        # 关闭所有灯珠，全灭 | Turn off all LEDs
        self.led_strip.fill((0, 0, 0))
        self.led_strip.show()
        # 释放DHT22传感器资源 | Release DHT22 sensor resource
        self.dht_device.exit()
        print("[环境系统 | Env System] 所有硬件资源已释放 | All Hardware Resources Released")
