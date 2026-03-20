# 极简WS2812B点亮代码
# 只做一件事：把整条灯带点亮成暖白色
import time
import board
import neopixel

# ==================== 灯带参数（和接线100%匹配，不用改） ====================
LED_PIN = board.D18    # 对应树莓派12号物理引脚
NUM_LEDS = 60          # 1米60灯
BRIGHTNESS = 0.3       # 亮度30%，先低亮度测试，安全不烧

# ==================== 初始化灯带 ====================
# WS2812B颜色顺序是GRB，必须写对
pixels = neopixel.NeoPixel(
    LED_PIN,
    NUM_LEDS,
    brightness=BRIGHTNESS,
    auto_write=False,
    pixel_order=neopixel.GRB
)

# ==================== 安全初始化：先全灭 ====================
pixels.fill((0, 0, 0))
pixels.show()
print("=== 极简灯带测试开始 ===")
print("🔴 先摸一下灯带第一个灯珠，不烫再继续！")
print("按 Ctrl+C 停止测试\n")

# ==================== 主循环：常亮暖白色 ====================
try:
    # 先等1秒，确认不烫
    time.sleep(1)
    
    while True:
        # GRB格式：(绿色, 红色, 蓝色)，暖白色
        pixels.fill((200, 255, 200))
        pixels.show()
        print("✅ 灯带已点亮！", end="\r")
        time.sleep(0.5)

# ==================== 停止测试，安全关闭 ====================
except KeyboardInterrupt:
    print("\n\n测试结束，正在关闭灯带...")
    pixels.fill((0, 0, 0))
    pixels.show()
    pixels.deinit()
    print("✅ 灯带已安全关闭")
