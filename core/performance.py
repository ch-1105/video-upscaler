"""
性能优化工具
多线程解码和CPU优化
"""
import os
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import List, Callable, Optional
import logging

logger = logging.getLogger(__name__)


class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self):
        self.cpu_count = multiprocessing.cpu_count()
        self.gpu_workers = 1  # GPU任务通常只需要1个工作进程
        self.cpu_workers = max(1, self.cpu_count - 2)  # 保留2个核心给系统
        self.io_workers = min(4, self.cpu_count)  # IO密集型任务
        
    def get_optimal_workers(self, task_type: str = "cpu") -> int:
        """获取最佳工作进程数
        
        Args:
            task_type: "cpu" | "gpu" | "io"
        
        Returns:
            推荐的工作进程数
        """
        if task_type == "gpu":
            return self.gpu_workers
        elif task_type == "io":
            return self.io_workers
        else:
            return self.cpu_workers
    
    def optimize_ffmpeg_args(self, base_args: List[str], preset: str = "medium") -> List[str]:
        """优化FFmpeg参数以获得更好性能
        
        Args:
            base_args: 基础FFmpeg参数
            preset: 编码预设 (ultrafast, superfast, veryfast, faster, fast, medium, slow)
        
        Returns:
            优化后的参数列表
        """
        optimized = base_args.copy()
        
        # 添加线程优化
        if "-threads" not in " ".join(optimized):
            optimized.extend(["-threads", str(self.cpu_workers)])
        
        # 对于解码，使用多线程
        if any(arg in optimized for arg in ["-i", "-c:v"]):
            if "-thread_type" not in " ".join(optimized):
                optimized.insert(-2 if optimized[-1].startswith("-") else -1, "-thread_type")
                optimized.insert(-2 if optimized[-1].startswith("-") else -1, "slice")
        
        return optimized
    
    def parallel_process(
        self,
        items: List,
        process_func: Callable,
        max_workers: Optional[int] = None,
        use_processes: bool = False
    ):
        """并行处理列表项
        
        Args:
            items: 要处理的项列表
            process_func: 处理函数
            max_workers: 最大工作进程数
            use_processes: 是否使用进程池（CPU密集型任务）
        
        Returns:
            处理结果列表
        """
        if max_workers is None:
            max_workers = self.cpu_workers if use_processes else self.io_workers
        
        Executor = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
        
        results = []
        with Executor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_func, item) for item in items]
            for future in futures:
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Parallel processing error: {e}")
                    results.append(None)
        
        return results
    
    def get_system_info(self) -> dict:
        """获取系统信息"""
        import psutil
        
        memory = psutil.virtual_memory()
        
        info = {
            "cpu_count": self.cpu_count,
            "cpu_workers": self.cpu_workers,
            "memory_total_gb": memory.total / (1024**3),
            "memory_available_gb": memory.available / (1024**3),
            "memory_percent": memory.percent
        }
        
        # GPU信息
        try:
            import torch
            if torch.cuda.is_available():
                info["cuda_available"] = True
                info["cuda_device"] = torch.cuda.get_device_name(0)
                info["cuda_memory_gb"] = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            else:
                info["cuda_available"] = False
        except ImportError:
            info["cuda_available"] = False
        
        return info


class FrameBuffer:
    """帧缓冲区 - 用于异步IO优化"""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.buffer = []
        self._lock = False
        
    def put(self, frame):
        """放入帧"""
        while len(self.buffer) >= self.max_size:
            import time
            time.sleep(0.001)  # 短暂等待
        self.buffer.append(frame)
    
    def get(self):
        """获取帧"""
        if self.buffer:
            return self.buffer.pop(0)
        return None
    
    def clear(self):
        """清空缓冲区"""
        self.buffer.clear()
    
    def __len__(self):
        return len(self.buffer)


class AsyncIOProcessor:
    """异步IO处理器"""
    
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = []
    
    def submit(self, func, *args, **kwargs):
        """提交任务"""
        future = self.executor.submit(func, *args, **kwargs)
        self.futures.append(future)
        return future
    
    def wait_for_all(self, timeout: Optional[float] = None):
        """等待所有任务完成"""
        from concurrent.futures import wait, ALL_COMPLETED
        if self.futures:
            wait(self.futures, timeout=timeout, return_when=ALL_COMPLETED)
            self.futures.clear()
    
    def shutdown(self, wait: bool = True):
        """关闭执行器"""
        self.executor.shutdown(wait=wait)


def get_optimal_tile_size(
    image_width: int,
    image_height: int,
    available_memory_gb: float,
    scale: int = 4
) -> int:
    """根据可用显存计算最佳tile大小
    
    Args:
        image_width: 图片宽度
        image_height: 图片高度
        available_memory_gb: 可用显存(GB)
        scale: 超分倍数
    
    Returns:
        推荐的tile大小
    """
    # 估算每张图所需显存 (输入 + 输出 + 中间特征)
    # 粗略估算: 像素数 * 3通道 * 4字节(float32) * 10(系数)
    pixels = image_width * image_height * scale * scale
    estimated_mb = (pixels * 3 * 4 * 10) / (1024 * 1024)
    
    available_mb = available_memory_gb * 1024
    
    # 保留30%的余量
    safe_mb = available_mb * 0.7
    
    if estimated_mb > safe_mb:
        # 需要分块
        import math
        # 计算需要的块数
        n_tiles = math.ceil(estimated_mb / safe_mb)
        tile_pixels = pixels / n_tiles
        tile_size = int(math.sqrt(tile_pixels))
        
        # 对齐到64的倍数
        tile_size = (tile_size // 64) * 64
        tile_size = max(64, min(tile_size, 512))
        
        return tile_size
    
    return 0  # 不需要分块


# 全局性能优化器实例
optimizer = PerformanceOptimizer()


if __name__ == "__main__":
    # 测试
    info = optimizer.get_system_info()
    print("系统信息:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    print(f"\n推荐工作进程数:")
    print(f"  CPU密集型: {optimizer.get_optimal_workers('cpu')}")
    print(f"  IO密集型: {optimizer.get_optimal_workers('io')}")
    print(f"  GPU任务: {optimizer.get_optimal_workers('gpu')}")
