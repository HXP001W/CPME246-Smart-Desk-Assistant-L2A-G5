# src/environment/test_env_system.py
"""
环境检测系统一键测试脚本 | One-Click Test Script for Environment Detection System
在电脑上直接运行，无需树莓派硬件 | Run directly on PC, no Raspberry Pi hardware required
覆盖所有核心功能：数据采集、调光、配置修改、观察者模式、日志记录 | Covers all core functions: data collection, dimming, config modification, observer pattern, logging
"""
import threading
import sys
from environment_monitor import EnvironmentMonitor
from environment_logger import EnvironmentLogger

def main():
    # ==================== 1. 系统初始化 | System Initialization ====================
    print("="*60)
    print("智能桌面助手 - 环境检测系统模拟测试 | Smart Desk Assistant - Env Detection System Mock Test")
    print("="*60)
    
    # 初始化环境监测核心类 | Initialize environment monitor core class
    env_monitor = EnvironmentMonitor()
    # 初始化环境日志管理器 | Initialize environment logger
    env_logger = EnvironmentLogger()

    # ==================== 2. 注册观察者回调 | Register Observer Callbacks ====================
    # 回调1：环境数据写入本地日志 | Callback 1: Write env data to local log
    def log_callback(data):
        env_logger.write_data(data)
    
    # 回调2：实时打印环境数据到终端 | Callback 2: Print real-time env data to terminal
    def print_callback(data):
        print(f"\r[实时数据 | Real-Time Data] 温度|Temp:{data['temperature']}℃ | 湿度|Humidity:{data['humidity']}%RH | "
              f"光照|Light:{data['lux']}lux | 告警|Warning:{data['temp_warning']}", end="")
    
    # 回调3：高温告警触发 | Callback 3: High temperature warning trigger
    def warning_callback(data):
        if data["temp_warning"]:
            print(f"\n⚠️  [温度告警 | Temp Warning] 当前温度|Current Temp {data['temperature']}℃ 超过阈值|Exceeds Threshold！")

    # 注册所有观察者 | Register all observers
    env_monitor.register_observer(log_callback)
    env_monitor.register_observer(print_callback)
    env_monitor.register_observer(warning_callback)

    # ==================== 3. 启动独立监测线程 | Start Separate Monitor Thread ====================
    monitor_thread = threading.Thread(target=env_monitor.run_monitor_loop, daemon=True)
    monitor_thread.start()

    # ==================== 4. 交互式测试菜单 | Interactive Test Menu ====================
    print("\n📋 测试菜单 | Test Menu（输入指令后按回车 | Enter command and press Enter）：")
    print("-"*60)
    print("1. lux [数值|value]   - 模拟环境光照变化 | Mock ambient light change (test adaptive dimming)")
    print("2. temp [数值|value]  - 模拟环境温度变化 | Mock ambient temperature change (test warning)")
    print("3. config [key] [value] - 修改系统配置 | Modify system config")
    print("   示例|Example：config target_lux 600, config auto_light_enabled False")
    print("4. profile      - 模拟人脸识别加载用户配置 | Mock face recognition to load user profile")
    print("5. exit         - 退出测试 | Exit test")
    print("-"*60)

    # 交互式循环 | Interactive loop
    try:
        while True:
            cmd = input("\n> ").strip().split()
            if not cmd:
                continue

            # 指令1：模拟光照变化 | Command 1: Mock light change
            if cmd[0] == "lux" and len(cmd) >= 2:
                try:
                    new_lux = float(cmd[1])
                    env_monitor.light_sensor.set_mock_lux(new_lux)
                except ValueError:
                    print("❌ 请输入有效的数字 | Please enter a valid number")

            # 指令2：模拟温度变化 | Command 2: Mock temperature change
            elif cmd[0] == "temp" and len(cmd) >= 2:
                try:
                    new_temp = float(cmd[1])
                    env_monitor.dht_device.set_mock_environment(temp=new_temp)
                except ValueError:
                    print("❌ 请输入有效的数字 | Please enter a valid number")

            # 指令3：修改系统配置 | Command 3: Modify system config
            elif cmd[0] == "config" and len(cmd) >= 3:
                key = cmd[1]
                value = cmd[2]
                # 自动类型转换 | Auto type conversion
                if value.lower() == "true":
                    parsed_value = True
                elif value.lower() == "false":
                    parsed_value = False
                elif value.replace(".", "").isdigit():
                    parsed_value = float(value)
                else:
                    parsed_value = value
                env_monitor.update_config({key: parsed_value})

            # 指令4：模拟加载用户配置 | Command 4: Mock load user profile
            elif cmd[0] == "profile":
                mock_user_profile = {
                    "target_lux": 600.0,
                    "light_color": (255, 240, 200),
                    "auto_light_enabled": True
                }
                print("\n👤 模拟人脸识别成功 | Mock Face Recognition Success，加载用户|Loading User 'Haowei'的配置...")
                env_monitor.load_user_profile(mock_user_profile)

            # 指令5：退出测试 | Command 5: Exit test
            elif cmd[0] == "exit":
                print("\n👋 正在退出测试 | Exiting test...")
                break

            # 未知指令 | Unknown command
            else:
                print("❌ 未知指令 | Unknown command，请重新输入 | Please re-enter")

    # 处理Ctrl+C中断 | Handle Ctrl+C interrupt
    except KeyboardInterrupt:
        print("\n👋 检测到中断 | Interrupt Detected，正在退出 | Exiting...")
    finally:
        # 安全释放资源 | Safe resource release
        env_monitor.cleanup()
        sys.exit(0)

if __name__ == "__main__":
    main()
