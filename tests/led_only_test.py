# WS2812B灯带 极简点亮测试代码
# 只做一件事：把整条灯带点亮成暖白色，无任何其他逻辑
import time
import board
import neopixel

# ==================== 灯带参数（和你的接线完全对应，不用改） ====================
LED_PIN = board.D18    # 对应树莓派12号物理引脚，GPIO18
NUM_LEDS = 60          # 你的灯带是1米60灯
BRIGHTNESS = 0.5       # 亮度50%，安全不烧树莓派，可改成0.1-1.0之间

# ==================== 初始化灯带 ====================
# WS2812B的颜色顺序是GRB，不是RGB！这里必须写对
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
print("=== 灯带点亮测试开始 ===")
print("如果灯带亮了，说明硬件和接线完全正常！")
print("按 Ctrl+C 停止测试，关闭灯带\n")

# ==================== 主循环：常亮暖白色 ====================
try:
    while True:
        # GRB格式：(绿色, 红色, 蓝色)，暖白色：(200, 255, 200)
        pixels.fill((200, 255, 200))
        pixels.show()
        print("✅ 灯带已点亮！", end="\r")
        time.sleep(0.5)

# ==================== 停止测试，安全关闭灯带 ====================
except KeyboardInterrupt:
    print("\n\n测试结束，正在关闭灯带...")
    pixels.fill((0, 0, 0))
    pixels.show()
    pixels.deinit()
    print("✅ 灯带已安全关闭")
