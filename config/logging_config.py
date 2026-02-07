"""
日志配置模块
统一配置应用程序日志系统
"""

import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class LoggingConfig:
    """
    日志配置类
    管理应用程序日志配置
    """
    
    DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    DEFAULT_LEVEL = logging.INFO
    
    def __init__(
        self,
        log_level: int = logging.INFO,
        log_dir: str = "logs",
        log_to_file: bool = True,
        log_to_console: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        """
        初始化日志配置
        
        Args:
            log_level: 日志级别
            log_dir: 日志目录
            log_to_file: 是否写入文件
            log_to_console: 是否输出到控制台
            max_bytes: 单个日志文件最大大小
            backup_count: 备份文件数量
        """
        self.log_level = log_level
        self.log_dir = log_dir
        self.log_to_file = log_to_file
        self.log_to_console = log_to_console
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        
        self.log_file: Optional[str] = None
    
    def setup(self) -> logging.Logger:
        """
        配置并返回根日志器
        
        Returns:
            logging.Logger: 配置好的根日志器
        """
        # 配置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 创建格式化器
        formatter = logging.Formatter(
            fmt=self.DEFAULT_LOG_FORMAT,
            datefmt=self.DEFAULT_DATE_FORMAT
        )
        
        # 添加控制台处理器
        if self.log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.log_level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        # 添加文件处理器
        if self.log_to_file:
            log_path = self._ensure_log_dir()
            self.log_file = log_path
            
            try:
                from logging.handlers import RotatingFileHandler
                file_handler = RotatingFileHandler(
                    log_path,
                    maxBytes=self.max_bytes,
                    backupCount=self.backup_count,
                    encoding='utf-8'
                )
                file_handler.setLevel(self.log_level)
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)
            except Exception as e:
                root_logger.warning(f"Failed to create file handler: {e}")
        
        # 配置第三方库日志级别
        logging.getLogger("PIL").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        
        return root_logger
    
    def _ensure_log_dir(self) -> str:
        """确保日志目录存在"""
        log_dir = Path(self.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成日志文件名
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = log_dir / f"video_upscaler_{timestamp}.log"
        
        return str(log_file)
    
    def get_logger(self, name: str = "VideoUpscaler") -> logging.Logger:
        """
        获取命名日志器
        
        Args:
            name: 日志器名称
            
        Returns:
            logging.Logger: 日志器
        """
        return logging.getLogger(name)


# 全局配置实例
_config: Optional[LoggingConfig] = None


def init_logging(
    log_level: int = logging.INFO,
    log_dir: str = "logs",
    **kwargs
) -> logging.Logger:
    """
    初始化日志系统
    
    Args:
        log_level: 日志级别
        log_dir: 日志目录
        **kwargs: 其他配置参数
        
    Returns:
        logging.Logger: 根日志器
    """
    global _config
    _config = LoggingConfig(log_level=log_level, log_dir=log_dir, **kwargs)
    return _config.setup()


def get_logger(name: str = "VideoUpscaler") -> logging.Logger:
    """
    获取日志器
    
    Args:
        name: 日志器名称
        
    Returns:
        logging.Logger: 日志器
    """
    if _config is None:
        # 自动初始化
        init_logging()
    return logging.getLogger(name)


def get_log_file() -> Optional[str]:
    """
    获取当前日志文件路径
    
    Returns:
        str or None: 日志文件路径
    """
    if _config is None:
        return None
    return _config.log_file


def set_log_level(level: int):
    """
    设置日志级别
    
    Args:
        level: 日志级别 (logging.DEBUG/INFO/WARNING/ERROR/CRITICAL)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    for handler in root_logger.handlers:
        handler.setLevel(level)


# 快捷方法
def debug(msg: str, *args, **kwargs):
    """记录调试日志"""
    get_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    """记录信息日志"""
    get_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """记录警告日志"""
    get_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """记录错误日志"""
    get_logger().error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    """记录严重错误日志"""
    get_logger().critical(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs):
    """记录异常日志（带堆栈）"""
    get_logger().exception(msg, *args, **kwargs)


if __name__ == "__main__":
    # 测试代码
    print("测试日志配置...")
    
    # 初始化
    logger = init_logging(log_level=logging.DEBUG)
    logger.info("日志系统初始化完成")
    
    # 测试各级别日志
    logger.debug("这是一条调试日志")
    logger.info("这是一条信息日志")
    logger.warning("这是一条警告日志")
    logger.error("这是一条错误日志")
    
    # 测试快捷方法
    info("使用快捷方法记录的信息")
    warning("使用快捷方法记录的警告")
    
    # 测试异常日志
    try:
        1 / 0
    except Exception:
        exception("发生异常")
    
    print(f"日志文件: {get_log_file()}")
