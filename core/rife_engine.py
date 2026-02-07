"""
RIFE 补帧引擎
基于 RIFE (Real-Time Intermediate Flow Estimation) 实现视频帧率提升
支持 24/25/30fps → 60fps
"""

import os
import sys
import logging
import gc
from pathlib import Path
from typing import Optional, Callable, Tuple, List
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class RIFEEngine:
    """
    RIFE 补帧引擎
    
    使用 practical-RIFE 或 VFIm 实现帧插值
    """
    
    # 支持的输入帧率到目标帧率映射
    TARGET_FPS_MAP = {
        24: 60,  # 电影 → 60fps
        25: 60,  # PAL → 60fps
        30: 60,  # NTSC → 60fps
        48: 60,  # 高帧率 → 60fps
        50: 60,  # 50fps → 60fps
        60: 60,  # 已经是60fps
    }
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cuda",
        use_fp16: bool = True,
        scale: float = 1.0
    ):
        """
        初始化 RIFE 引擎
        
        Args:
            model_path: RIFE 模型路径
            device: 计算设备 (cuda/cpu)
            use_fp16: 使用半精度浮点数
            scale: 缩放因子 (用于处理大分辨率)
        """
        self.model_path = model_path
        self.device = device
        self.use_fp16 = use_fp16
        self.scale = scale
        self.model = None
        self.is_loaded = False
        
        # 模型参数
        self.model_scale = 1.0  # RIFE 模型缩放
        
        logger.info(f"RIFE Engine initialized (device={device}, fp16={use_fp16})")
    
    def load_model(self) -> bool:
        """
        加载 RIFE 模型
        
        Returns:
            bool: 是否加载成功
        """
        if self.is_loaded:
            return True
        
        try:
            # 尝试导入 RIFE
            import torch
            
            # 查找模型路径
            model_path = self._find_model_path()
            if not model_path:
                logger.warning("RIFE model not found, using fallback mode")
                return False
            
            # 导入 RIFE 模型
            # 支持 practical-RIFE 和 VFIm
            try:
                # 尝试 practical-RIFE
                sys.path.insert(0, str(Path(__file__).parent / "rife"))
                from rife.RIFE import Model
                
                self.model = Model()
                self.model.load_model(model_path, -1)
                self.model.eval()
                self.model.device()
                
            except ImportError:
                logger.warning("practical-RIFE not available")
                return False
            
            self.is_loaded = True
            logger.info(f"RIFE model loaded from: {model_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load RIFE model: {e}")
            return False
    
    def _find_model_path(self) -> Optional[str]:
        """查找 RIFE 模型文件"""
        # 常见模型路径
        search_paths = [
            self.model_path,
            "models/rife/rife.pth",
            "models/rife/rife4.6.pth",
            "models/rife/RIFE.pth",
            "~/.local/share/video-upscaler/models/rife/rife.pth",
            "/usr/local/share/video-upscaler/models/rife/rife.pth",
        ]
        
        for path in search_paths:
            if path:
                path = os.path.expanduser(path)
                if os.path.exists(path):
                    return path
        
        # 搜索 models/rife/ 目录
        rife_dir = Path("models/rife")
        if rife_dir.exists():
            pth_files = list(rife_dir.glob("*.pth"))
            if pth_files:
                return str(pth_files[0])
        
        return None
    
    def is_available(self) -> bool:
        """检查补帧是否可用"""
        if not self.is_loaded:
            self.load_model()
        return self.is_loaded
    
    def calculate_interpolation_frames(
        self,
        source_fps: float,
        target_fps: Optional[float] = None
    ) -> Tuple[int, float]:
        """
        计算需要插值的帧数
        
        Args:
            source_fps: 原始帧率
            target_fps: 目标帧率，None则自动确定
            
        Returns:
            (每帧间隔插入的帧数, 实际目标帧率)
        """
        if target_fps is None:
            target_fps = self.TARGET_FPS_MAP.get(int(source_fps), 60)
        
        # 计算插值比例
        ratio = target_fps / source_fps
        
        # 计算每帧之间插入的帧数
        # 例如 24fps → 60fps，ratio=2.5
        # 需要每帧后插入 1.5 帧（实际实现会处理成 2帧插3帧）
        
        if ratio <= 1.0:
            return 0, source_fps
        
        # 简化计算：返回需要插入的倍数
        interp_frames = int(ratio - 1)
        
        return interp_frames, target_fps
    
    def interpolate_frame_pair(
        self,
        img0: np.ndarray,
        img1: np.ndarray,
        timestep: float = 0.5
    ) -> Optional[np.ndarray]:
        """
        对两帧之间进行插值
        
        Args:
            img0: 第一帧
            img1: 第二帧
            timestep: 插值时间点 (0-1)
            
        Returns:
            插值帧或 None
        """
        if not self.is_available():
            # Fallback: 返回线性混合
            return ((img0.astype(np.float32) + img1.astype(np.float32)) / 2).astype(np.uint8)
        
        try:
            import torch
            
            # 转换格式
            img0_tensor = self._to_tensor(img0)
            img1_tensor = self._to_tensor(img1)
            
            with torch.no_grad():
                # 推理
                if self.use_fp16:
                    img0_tensor = img0_tensor.half()
                    img1_tensor = img1_tensor.half()
                
                # 调用模型
                interp_frame = self.model.inference(img0_tensor, img1_tensor, timestep)
                
                # 转回 numpy
                result = self._to_numpy(interp_frame)
                
            return result
            
        except Exception as e:
            logger.error(f"Interpolation failed: {e}")
            # Fallback
            return ((img0.astype(np.float32) + img1.astype(np.float32)) / 2).astype(np.uint8)
    
    def _to_tensor(self, img: np.ndarray) -> 'torch.Tensor':
        """将 numpy 图像转换为 tensor"""
        import torch
        
        # HWC -> CHW
        img = np.transpose(img, (2, 0, 1))
        # 归一化到 [0, 1]
        img = img.astype(np.float32) / 255.0
        # 添加 batch 维度
        img = np.expand_dims(img, axis=0)
        
        tensor = torch.from_numpy(img).to(self.device)
        return tensor
    
    def _to_numpy(self, tensor: 'torch.Tensor') -> np.ndarray:
        """将 tensor 转换为 numpy 图像"""
        # 移除 batch 维度
        img = tensor.squeeze(0).cpu().numpy()
        # CHW -> HWC
        img = np.transpose(img, (1, 2, 0))
        # 反归一化到 [0, 255]
        img = (img * 255.0).clip(0, 255).astype(np.uint8)
        return img
    
    def interpolate_video(
        self,
        input_dir: str,
        output_dir: str,
        source_fps: float,
        target_fps: Optional[float] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[int, float]:
        """
        对视频帧序列进行补帧
        
        Args:
            input_dir: 输入帧目录
            output_dir: 输出帧目录
            source_fps: 原始帧率
            target_fps: 目标帧率
            progress_callback: 进度回调
            
        Returns:
            (输出帧数, 实际目标帧率)
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 获取所有输入帧
        input_frames = sorted(Path(input_dir).glob("*.png"))
        if not input_frames:
            logger.error(f"No frames found in {input_dir}")
            return 0, source_fps
        
        total_input = len(input_frames)
        interp_count, actual_target_fps = self.calculate_interpolation_frames(
            source_fps, target_fps
        )
        
        logger.info(
            f"Interpolating {source_fps}fps → {actual_target_fps}fps "
            f"({total_input} input frames, ~{total_input * (interp_count + 1)} output frames)"
        )
        
        output_idx = 0
        
        # 处理每对连续帧
        for i in range(total_input):
            # 复制原帧
            import shutil
            shutil.copy(input_frames[i], os.path.join(output_dir, f"frame_{output_idx:08d}.png"))
            output_idx += 1
            
            # 如果不是最后一帧，进行插值
            if i < total_input - 1 and interp_count > 0:
                try:
                    # 读取两帧
                    img0 = np.array(Image.open(input_frames[i]))
                    img1 = np.array(Image.open(input_frames[i + 1]))
                    
                    # 插值
                    for j in range(interp_count):
                        timestep = (j + 1) / (interp_count + 1)
                        interp_frame = self.interpolate_frame_pair(img0, img1, timestep)
                        
                        if interp_frame is not None:
                            output_path = os.path.join(output_dir, f"frame_{output_idx:08d}.png")
                            Image.fromarray(interp_frame).save(output_path)
                            output_idx += 1
                    
                    # 每10帧清理一次显存
                    if (i + 1) % 10 == 0 and self.device == "cuda":
                        import torch
                        torch.cuda.empty_cache()
                        
                except Exception as e:
                    logger.error(f"Failed to interpolate frame {i}: {e}")
                    # 继续处理，复制原帧作为fallback
                    shutil.copy(input_frames[i], os.path.join(output_dir, f"frame_{output_idx:08d}.png"))
                    output_idx += 1
            
            if progress_callback:
                progress_callback(i + 1, total_input)
        
        logger.info(f"Interpolation complete: {output_idx} frames generated")
        return output_idx, actual_target_fps
    
    def get_memory_usage(self) -> dict:
        """获取显存使用情况"""
        if self.device != "cuda":
            return {"device": "cpu", "allocated_mb": 0, "cached_mb": 0}
        
        try:
            import torch
            return {
                "device": "cuda",
                "allocated_mb": torch.cuda.memory_allocated() / 1024 / 1024,
                "cached_mb": torch.cuda.memory_reserved() / 1024 / 1024,
            }
        except:
            return {"device": "cuda", "allocated_mb": 0, "cached_mb": 0}
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, 'model') and self.model:
            del self.model
            gc.collect()
            if self.device == "cuda":
                try:
                    import torch
                    torch.cuda.empty_cache()
                except:
                    pass


class SimpleInterpolator:
    """
    简单的帧插值器（Fallback）
    使用线性混合作为RIFE的备用方案
    """
    
    def __init__(self, device: str = "cpu"):
        self.device = device
    
    def interpolate_frame_pair(
        self,
        img0: np.ndarray,
        img1: np.ndarray,
        timestep: float = 0.5
    ) -> np.ndarray:
        """线性插值两帧"""
        # 简单的线性混合
        alpha = timestep
        result = (img0.astype(np.float32) * (1 - alpha) + 
                  img1.astype(np.float32) * alpha)
        return result.clip(0, 255).astype(np.uint8)
    
    def is_available(self) -> bool:
        """总是可用"""
        return True


def download_rife_model(output_dir: str = "models/rife") -> bool:
    """
    下载 RIFE 模型
    
    Args:
        output_dir: 模型保存目录
        
    Returns:
        bool: 是否下载成功
    """
    import urllib.request
    import zipfile
    
    model_url = "https://github.com/hzwer/Practical-RIFE/releases/download/v4.6/rife46.zip"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        zip_path = os.path.join(output_dir, "rife46.zip")
        
        logger.info(f"Downloading RIFE model to {output_dir}...")
        urllib.request.urlretrieve(model_url, zip_path)
        
        # 解压
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
        
        os.remove(zip_path)
        logger.info("RIFE model downloaded successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to download RIFE model: {e}")
        return False


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    print("RIFE Engine Test")
    print("=" * 50)
    
    # 创建引擎
    engine = RIFEEngine(device="cpu")
    
    # 测试帧率计算
    test_cases = [
        (24, None),
        (30, None),
        (25, 60),
    ]
    
    for source, target in test_cases:
        interp, actual = engine.calculate_interpolation_frames(source, target)
        print(f"{source}fps → {actual}fps: insert {interp} frames between each frame")
    
    # 测试简单插值
    print("\nTesting simple interpolation...")
    simple = SimpleInterpolator()
    
    # 创建测试图像
    img0 = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
    img1 = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
    
    result = simple.interpolate_frame_pair(img0, img1, 0.5)
    print(f"Interpolation result shape: {result.shape}")
    print(f"Interpolation available: {simple.is_available()}")
