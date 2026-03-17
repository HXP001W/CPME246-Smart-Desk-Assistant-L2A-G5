# light_led_test.py: 光敏电阻+WS2812B灯带极简测试
import time
import board
import neopixel
from gpiozero import LightSensor

# ==================== 硬件参数（和接线完全对应，不用改） ====================
# LED灯带参数
LED_PIN = board.D18  # 树莓派12号物理引脚
NUM_LEDS = 60        # 1米60灯
MAX_BRIGHTNESS = 0.7 # 安全亮度上限，避免过载

# 光敏电阻参数
LIGHT_SENSOR_PIN = 17  # 树莓派11号物理引脚

# ==================== 硬件初始化 ====================
# 初始化LED灯带
pixels = neopixel.NeoPixel(
    LED_PIN,
    NUM_LEDS,
    brightness=0.0,
    auto_write=False
)

# 初始化光敏电阻
light_sensor = LightSensor(LIGHT_SENSOR_PIN)

# ==================== 安全初始化：灯带先全灭 ====================
pixels.fill((0, 0, 0))
pixels.show()
print("=== 光敏+LED灯带测试开始 ===")
print("操作说明：用手盖住光敏 → 灯带变亮；用手电筒照光敏 → 灯带变暗")
print("按 Ctrl+C 停止测试\n")

# ==================== 主测试循环 ====================
try:
    while True:
        # 1. 读取光敏数值（0=全黑，1=最亮）
        light_level = light_sensor.value
        
        # 2. 计算LED亮度：环境越暗，灯带越亮
        led_brightness = 1.0 - light_level
        # 限制最大亮度，避免过载
        safe_brightness = led_brightness * MAX_BRIGHTNESS
        
        # 3. 设置灯带亮度（WS2812B是GRB颜色顺序）
        red = int(255 * led_brightness)
        green = int(255 * led_brightness)
        blue = int(255 * led_brightness)
        pixels.brightness = safe_brightness
        pixels.fill((green, red, blue))
        pixels.show()
        
        # 4. 终端打印实时数值，方便排查
        print(f"环境亮度：{light_level:.2f} | 灯带亮度：{led_brightness:.2f}", end="\r")
        
        # 0.2秒刷新一次
        time.sleep(0.2)

# ==================== 停止测试，安全关闭硬件 ====================
except KeyboardInterrupt:
    print("\n\n测试结束，正在关闭灯带...")
    pixels.fill((0, 0, 0))
    pixels.show()
    pixels.deinit()
    print("灯带已安全关闭")
