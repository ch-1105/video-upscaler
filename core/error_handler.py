"""
错误处理和健壮性改进
统一的错误处理和恢复机制
"""
import os
import sys
import traceback
import logging
from functools import wraps
from typing import Optional, Callable, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class VideoUpscalerError(Exception):
    """基础错误类"""
    
    def __init__(self, message: str, error_code: str = "UNKNOWN", details: dict = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}
        self.original_error = None
    
    def __str__(self):
        msg = f"[{self.error_code}] {super().__str__()}"
        if self.details:
            msg += f"\n详情: {self.details}"
        return msg


class ModelError(VideoUpscalerError):
    """模型相关错误"""
    pass


class VideoError(VideoUpscalerError):
    """视频处理错误"""
    pass


class MemoryError(VideoUpscalerError):
    """内存/显存错误"""
    pass


class FileSystemError(VideoUpscalerError):
    """文件系统错误"""
    pass


class EnvironmentError(VideoUpscalerError):
    """环境错误"""
    pass


# 错误代码定义
ERROR_CODES = {
    # 模型错误 (M系列)
    "M001": "模型文件不存在",
    "M002": "模型加载失败",
    "M003": "模型版本不兼容",
    "M004": "模型下载失败",
    
    # 视频错误 (V系列)
    "V001": "视频文件不存在",
    "V002": "视频格式不支持",
    "V003": "视频解码失败",
    "V004": "视频编码失败",
    "V005": "帧提取失败",
    
    # 内存错误 (X系列)
    "X001": "显存不足",
    "X002": "系统内存不足",
    "X003": "磁盘空间不足",
    
    # 文件系统错误 (F系列)
    "F001": "无法创建目录",
    "F002": "文件读取失败",
    "F003": "文件写入失败",
    "F004": "权限不足",
    
    # 环境错误 (E系列)
    "E001": "FFmpeg未安装",
    "E002": "CUDA不可用",
    "E003": "依赖缺失",
}


def handle_errors(
    error_code: str = "UNKNOWN",
    fallback_return: Any = None,
    reraise: bool = False,
    log_level: str = "error"
):
    """错误处理装饰器
    
    Args:
        error_code: 错误代码
        fallback_return: 失败时的返回值
        reraise: 是否重新抛出异常
        log_level: 日志级别
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except VideoUpscalerError:
                raise
            except Exception as e:
                # 获取错误描述
                error_desc = ERROR_CODES.get(error_code, "未知错误")
                
                # 构建错误详情
                details = {
                    "function": func.__name__,
                    "exception": str(e),
                    "traceback": traceback.format_exc()
                }
                
                # 记录日志
                log_func = getattr(logger, log_level, logger.error)
                log_func(f"{error_desc} [{error_code}]: {e}")
                
                if reraise:
                    raise VideoUpscalerError(
                        error_desc,
                        error_code=error_code,
                        details=details
                    ) from e
                
                return fallback_return
        
        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    *args,
    fallback_return: Any = None,
    error_msg: str = "操作失败",
    **kwargs
) -> Any:
    """安全执行函数
    
    Args:
        func: 要执行的函数
        fallback_return: 失败时的返回值
        error_msg: 错误消息
    
    Returns:
        函数返回值或fallback_return
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"{error_msg}: {e}")
        return fallback_return


class ErrorRecovery:
    """错误恢复管理器"""
    
    def __init__(self):
        self.recovery_strategies = {}
        self.max_retries = 3
        self.retry_delay = 1.0  # 秒
    
    def register_recovery(self, error_code: str, strategy: Callable):
        """注册恢复策略
        
        Args:
            error_code: 错误代码
            strategy: 恢复函数
        """
        self.recovery_strategies[error_code] = strategy
    
    def attempt_recovery(self, error: VideoUpscalerError, context: dict = None) -> bool:
        """尝试恢复
        
        Args:
            error: 错误对象
            context: 上下文信息
        
        Returns:
            是否恢复成功
        """
        strategy = self.recovery_strategies.get(error.error_code)
        if strategy:
            try:
                return strategy(error, context)
            except Exception as e:
                logger.error(f"恢复策略失败: {e}")
        
        return False


class ResourceMonitor:
    """资源监控器"""
    
    def __init__(
        self,
        min_free_disk_gb: float = 5.0,
        min_free_memory_gb: float = 2.0,
        min_free_vram_gb: float = 1.0
    ):
        self.min_free_disk_gb = min_free_disk_gb
        self.min_free_memory_gb = min_free_memory_gb
        self.min_free_vram_gb = min_free_vram_gb
    
    def check_disk_space(self, path: str) -> bool:
        """检查磁盘空间"""
        try:
            stat = os.statvfs(path)
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            
            if free_gb < self.min_free_disk_gb:
                logger.warning(f"磁盘空间不足: {free_gb:.2f}GB < {self.min_free_disk_gb}GB")
                return False
            return True
        except Exception as e:
            logger.error(f"检查磁盘空间失败: {e}")
            return True  # 无法检查时默认通过
    
    def check_memory(self) -> bool:
        """检查系统内存"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            free_gb = memory.available / (1024**3)
            
            if free_gb < self.min_free_memory_gb:
                logger.warning(f"系统内存不足: {free_gb:.2f}GB < {self.min_free_memory_gb}GB")
                return False
            return True
        except ImportError:
            return True
    
    def check_vram(self) -> bool:
        """检查显存"""
        try:
            import torch
            if not torch.cuda.is_available():
                return True
            
            free_gb = torch.cuda.get_device_properties(0).total_memory
            free_gb -= torch.cuda.memory_allocated()
            free_gb /= (1024**3)
            
            if free_gb < self.min_free_vram_gb:
                logger.warning(f"显存不足: {free_gb:.2f}GB < {self.min_free_vram_gb}GB")
                return False
            return True
        except:
            return True
    
    def check_all(self, work_dir: str) -> tuple:
        """检查所有资源
        
        Returns:
            (是否通过, 失败原因列表)
        """
        failures = []
        
        if not self.check_disk_space(work_dir):
            failures.append("磁盘空间不足")
        
        if not self.check_memory():
            failures.append("系统内存不足")
        
        if not self.check_vram():
            failures.append("显存不足")
        
        return len(failures) == 0, failures


class ValidationHelper:
    """验证辅助类"""
    
    @staticmethod
    def validate_video_path(path: str) -> bool:
        """验证视频路径"""
        if not path or not isinstance(path, str):
            return False
        
        if not os.path.exists(path):
            logger.error(f"视频文件不存在: {path}")
            return False
        
        # 检查扩展名
        ext = Path(path).suffix.lower()
        supported = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']
        if ext not in supported:
            logger.warning(f"不支持的格式: {ext}")
        
        return True
    
    @staticmethod
    def validate_output_path(path: str, check_parent: bool = True) -> bool:
        """验证输出路径"""
        if not path or not isinstance(path, str):
            return False
        
        if check_parent:
            parent = Path(path).parent
            if not parent.exists():
                try:
                    parent.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    logger.error(f"无法创建输出目录: {e}")
                    return False
        
        return True
    
    @staticmethod
    def validate_model_path(path: str) -> bool:
        """验证模型路径"""
        if not path or not isinstance(path, str):
            return False
        
        if not os.path.exists(path):
            logger.error(f"模型文件不存在: {path}")
            return False
        
        # 检查文件大小（模型文件通常很大）
        size_mb = os.path.getsize(path) / (1024 * 1024)
        if size_mb < 1:  # 小于1MB可能是错误的
            logger.warning(f"模型文件异常小: {size_mb:.2f}MB")
        
        return True


# 全局错误恢复管理器
recovery_manager = ErrorRecovery()
resource_monitor = ResourceMonitor()


# 注册一些常见的恢复策略
def recover_from_oom(error: MemoryError, context: dict = None) -> bool:
    """从OOM恢复"""
    try:
        import torch
        import gc
        
        # 清理缓存
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        logger.info("已清理显存缓存")
        return True
    except Exception as e:
        logger.error(f"OOM恢复失败: {e}")
        return False


recovery_manager.register_recovery("X001", recover_from_oom)


if __name__ == "__main__":
    # 测试
    @handle_errors(error_code="T001", fallback_return=0)
    def test_function(x):
        if x < 0:
            raise ValueError("x必须大于0")
        return x * 2
    
    print(test_function(5))  # 正常: 10
    print(test_function(-1))  # 错误: 0
    
    # 测试验证
    print("\n验证测试:")
    print(ValidationHelper.validate_video_path("test.mp4"))
    print(ValidationHelper.validate_output_path("/tmp/output.mp4"))
