# src/environment/environment_logger.py
"""
环境数据日志记录类 | Environment Data Logger Class
对接团队DataLogger模块，按规范格式持久化存储环境数据 | Aligned with team DataLogger module, persist env data in standard format
为学习报告模块提供原始数据支撑 | Provide raw data support for study report module
"""
import csv
import os
from typing import Dict
from datetime import datetime

class EnvironmentLogger:
    """
    环境数据日志管理器 | Environment Data Log Manager
    按日期自动生成日志文件，支持按时段查询数据 | Auto generate log files by date, support time-range data query
    """
    def __init__(self, log_dir: str = "./data/environment_logs"):
        """
        初始化日志管理器 | Initialize log manager
        :param log_dir: 日志文件存储根目录 | Root directory for log files storage
        """
        self.log_dir = log_dir
        # 自动创建日志目录，不存在则新建 | Auto create log directory if not exists
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        # 当前日志文件路径 | Current log file path
        self.current_log_file = self._get_new_log_file()

    def _get_new_log_file(self) -> str:
        """
        按日期生成新的日志文件路径 | Generate new log file path by date
        :return: 日志文件绝对路径 | Absolute path of log file
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"env_data_{date_str}.csv")

    def write_data(self, data: Dict):
        """
        写入单条环境数据，对齐团队统一日志格式 | Write single env data, aligned with team unified log format
        :param data: EnvironmentMonitor.current_data 标准格式字典 | Standard format dict from EnvironmentMonitor.current_data
        """
        # 检查是否跨天，自动切换日志文件 | Check if date changed, auto switch log file
        self.current_log_file = self._get_new_log_file()
        
        # 检查文件是否存在，不存在则写入表头 | Check if file exists, write header if not
        file_exists = os.path.isfile(self.current_log_file)
        
        with open(self.current_log_file, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(data)
