"""
补帧引擎（兼容接口）
基于 RIFE - 视频帧率提升

这是向后兼容的接口层，实际实现见 rife_engine.py
"""

import os
import logging
from typing import Optional, Callable, Tuple
from pathlib import Path

# 导入新的 RIFE 引擎
try:
    from .rife_engine import RIFEEngine, SimpleInterpolator
except ImportError:
    from rife_engine import RIFEEngine, SimpleInterpolator

logger = logging.getLogger(__name__)


class InterpolatorEngine:
    """
    补帧引擎（兼容接口）
    
    提供与旧代码兼容的接口，内部使用 RIFEEngine
    """
    
    # 目标帧率映射
    TARGET_FPS = {
        24: 60,  # 电影 → 60fps
        25: 60,  # PAL → 60fps
        30: 60,  # NTSC → 60fps
    }
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cuda",
        use_fp16: bool = True
    ):
        """
        初始化补帧引擎
        
        Args:
            model_path: RIFE 模型路径
            device: cuda/cpu
            use_fp16: 使用半精度
        """
        self.model_path = model_path
        self.device = device
        self.use_fp16 = use_fp16
        
        # 初始化新的 RIFE 引擎
        self._rife_engine = None
        self._simple_interpolator = None
        
        self.target_fps = 60
        self._load_model()
    
    def _load_model(self):
        """加载 RIFE 模型"""
        try:
            # 尝试加载 RIFE 引擎
            self._rife_engine = RIFEEngine(
                model_path=self.model_path,
                device=self.device,
                use_fp16=self.use_fp16
            )
            
            if self._rife_engine.load_model():
                logger.info("RIFE model loaded successfully")
            else:
                logger.warning("RIFE model not available, using simple interpolation")
                self._rife_engine = None
                
        except Exception as e:
            logger.warning(f"Failed to load RIFE: {e}, using simple interpolation")
            self._rife_engine = None
    
    def is_available(self) -> bool:
        """检查补帧是否可用"""
        # RIFE 引擎或简单插值器可用即可
        if self._rife_engine and self._rife_engine.is_available():
            return True
        return self._simple_interpolator is not None or True  # 简单插值总是可用
    
    def interpolate_frames(
        self,
        input_dir: str,
        output_dir: str,
        source_fps: float,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[int, float]:
        """
        补帧处理
        
        Args:
            input_dir: 输入帧目录
            output_dir: 输出帧目录
            source_fps: 原始帧率
            progress_callback: 进度回调 (current, total)
            
        Returns:
            (输出帧数, 目标帧率)
        """
        # 确定目标帧率
        target_fps = self.TARGET_FPS.get(int(source_fps), 60)
        
        # 优先使用 RIFE 引擎
        if self._rife_engine and self._rife_engine.is_available():
            logger.info(f"Using RIFE engine for interpolation: {source_fps}fps → {target_fps}fps")
            return self._rife_engine.interpolate_video(
                input_dir=input_dir,
                output_dir=output_dir,
                source_fps=source_fps,
                target_fps=target_fps,
                progress_callback=progress_callback
            )
        
        # 使用简单插值作为 fallback
        logger.info(f"Using simple interpolation: {source_fps}fps → {target_fps}fps")
        return self._simple_interpolate(
            input_dir, output_dir, source_fps, target_fps, progress_callback
        )
    
    def _simple_interpolate(
        self,
        input_dir: str,
        output_dir: str,
        source_fps: float,
        target_fps: float,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[int, float]:
        """
        简单帧复制（Fallback）
        当 RIFE 不可用时使用
        """
        import shutil
        
        os.makedirs(output_dir, exist_ok=True)
        input_frames = sorted(Path(input_dir).glob("*.png"))
        
        if not input_frames:
            logger.error(f"No frames found in {input_dir}")
            return 0, source_fps
        
        # 计算需要插入的帧数
        ratio = target_fps / source_fps
        n_duplicates = int(ratio) - 1
        
        output_idx = 0
        total_input = len(input_frames)
        
        for i, frame in enumerate(input_frames):
            # 复制原帧
            shutil.copy(frame, os.path.join(output_dir, f"frame_{output_idx:08d}.png"))
            output_idx += 1
            
            # 复制额外帧以达到目标帧率
            for _ in range(n_duplicates):
                shutil.copy(frame, os.path.join(output_dir, f"frame_{output_idx:08d}.png"))
                output_idx += 1
            
            if progress_callback:
                progress_callback(i + 1, total_input)
        
        logger.info(f"Simple interpolation complete: {output_idx} frames")
        return output_idx, target_fps
    
    def _find_model(self) -> Optional[str]:
        """查找 RIFE 模型"""
        if self._rife_engine:
            return self._rife_engine._find_model_path()
        
        # 向后兼容
        search_paths = [
            "models/rife/",
            "~/.local/share/video-upscaler/models/rife/",
        ]
        
        for path in search_paths:
            path = os.path.expanduser(path)
            if os.path.exists(path):
                return path
        
        return None
    
    def get_memory_usage(self) -> dict:
        """获取显存使用情况"""
        if self._rife_engine:
            return self._rife_engine.get_memory_usage()
        return {"device": self.device, "allocated_mb": 0, "cached_mb": 0}
    
    def interpolate_frame_pair(
        self,
        img0,
        img1,
        timestep: float = 0.5
    ):
        """
        对两帧进行插值（高级接口）
        
        Args:
            img0: 第一帧 (numpy array)
            img1: 第二帧 (numpy array)
            timestep: 插值时间点 (0-1)
            
        Returns:
            插值帧 (numpy array)
        """
        if self._rife_engine and self._rife_engine.is_available():
            return self._rife_engine.interpolate_frame_pair(img0, img1, timestep)
        
        # Fallback: 简单混合
        import numpy as np
        alpha = timestep
        result = (img0.astype(np.float32) * (1 - alpha) + 
                  img1.astype(np.float32) * alpha)
        return result.clip(0, 255).astype(np.uint8)


# 便捷函数
def create_interpolator(
    model_path: Optional[str] = None,
    device: str = "cuda",
    use_fp16: bool = True
) -> InterpolatorEngine:
    """
    创建补帧引擎
    
    Args:
        model_path: 模型路径
        device: 设备
        use_fp16: 使用半精度
        
    Returns:
        InterpolatorEngine: 补帧引擎实例
    """
    return InterpolatorEngine(model_path, device, use_fp16)


if __name__ == "__main__":
    # 测试代码
    import tempfile
    import numpy as np
    from PIL import Image
    
    logging.basicConfig(level=logging.INFO)
    
    print("Interpolator Engine Test")
    print("=" * 50)
    
    # 创建测试帧
    with tempfile.TemporaryDirectory() as tmpdir:
        input_dir = os.path.join(tmpdir, "input")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(input_dir, exist_ok=True)
        
        # 生成10帧测试图像
        for i in range(10):
            img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            Image.fromarray(img).save(os.path.join(input_dir, f"frame_{i:08d}.png"))
        
        # 创建引擎
        engine = InterpolatorEngine(device="cpu")
        
        print(f"Engine available: {engine.is_available()}")
        
        # 测试补帧
        frame_count, target_fps = engine.interpolate_frames(
            input_dir, output_dir, 24.0
        )
        
        print(f"Output frames: {frame_count}")
        print(f"Target FPS: {target_fps}")
        
        # 验证输出
        output_files = list(Path(output_dir).glob("*.png"))
        print(f"Actual output files: {len(output_files)}")
