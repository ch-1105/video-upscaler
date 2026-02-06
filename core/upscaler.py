"""
超分核心引擎
基于 Real-ESRGAN + Tile 分块处理
"""
import os
import gc
import logging
from pathlib import Path
from typing import Optional, Callable, Tuple
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class UpscalerEngine:
    """超分引擎"""
    
    # 预设配置：scale, tile_size, tile_pad
    PRESETS = {
        "流畅": {"scale": 2, "tile": 512, "pad": 10},   # 720p/1080p
        "标准": {"scale": 4, "tile": 512, "pad": 10},   # 1080p60
        "高清": {"scale": 4, "tile": 256, "pad": 10}    # 4K60 (256是平衡选择)
    }
    
    def __init__(
        self,
        model_path: str = None,
        model_name: str = "RealESRGAN_x4plus",
        preset: str = "标准",
        device: str = "cuda",
        use_fp16: bool = True
    ):
        """
        Args:
            model_path: 模型文件路径
            model_name: 模型名称
            preset: 预设档位（流畅/标准/高清）
            device: cuda/cpu
            use_fp16: 使用半精度
        """
        self.model_path = model_path
        self.model_name = model_name
        self.preset = preset
        self.device = device
        self.use_fp16 = use_fp16
        
        self.config = self.PRESETS.get(preset, self.PRESETS["标准"])
        self.tile_size = self.config["tile"]
        self.tile_pad = self.config["pad"]
        self.scale = self.config["scale"]
        
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """加载模型"""
        try:
            import torch
            from realesrgan import RealESRGANer
            
            # 确定模型路径
            if self.model_path and os.path.exists(self.model_path):
                model_path = self.model_path
            else:
                # 使用默认模型搜索
                model_path = self._find_model()
            
            # 初始化 Real-ESRGAN
            self.model = RealESRGANer(
                scale=self.scale,
                model_path=model_path,
                model=self.model_name,
                tile=self.tile_size,
                tile_pad=self.tile_pad,
                pre_pad=0,
                half=self.use_fp16,
                device=self.device
            )
            
        except ImportError:
            raise RuntimeError("realesrgan not installed. Run: pip install realesrgan")
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {e}")
    
    def _find_model(self) -> str:
        """查找模型文件"""
        # 常见位置
        search_paths = [
            "models/",
            "~/.local/share/video-upscaler/models/",
            "/usr/local/share/video-upscaler/models/",
        ]
        
        model_files = {
            "RealESRGAN_x4plus": "RealESRGAN_x4plus.pth",
            "RealESRGAN_x2plus": "RealESRGAN_x2plus.pth",
            "RealESRGAN_anime_6B": "RealESRGAN_animevideov3.pth",
        }
        
        model_file = model_files.get(self.model_name, "RealESRGAN_x4plus.pth")
        
        for path in search_paths:
            path = os.path.expanduser(path)
            full_path = os.path.join(path, model_file)
            if os.path.exists(full_path):
                return full_path
        
        raise FileNotFoundError(
            f"Model {model_file} not found. "
            f"Run: python scripts/download_models.py"
        )
    
    def upscale_image(
        self,
        image_path: str,
        output_path: str,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> str:
        """
        超分单张图片
        
        Args:
            image_path: 输入图片路径
            output_path: 输出图片路径
            progress_callback: 进度回调 (0-100)
        
        Returns:
            输出文件路径
        """
        import cv2
        
        # 读取图片
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        # 超分
        try:
            output, _ = self.model.enhance(img, outscale=self.scale)
        except RuntimeError as e:
            if "out of memory" in str(e):
                # 显存不足，减小 tile 重试
                self._reduce_tile_size()
                output, _ = self.model.enhance(img, outscale=self.scale)
            else:
                raise
        
        # 保存
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        cv2.imwrite(output_path, output)
        
        return output_path
    
    def upscale_batch(
        self,
        input_dir: str,
        output_dir: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[int, int]:
        """
        批量超分图片
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            progress_callback: 进度回调 (current, total)
        
        Returns:
            (成功数, 总数)
        """
        # 获取所有图片
        image_files = []
        for ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff"):
            image_files.extend(Path(input_dir).glob(f"*{ext}"))
        
        image_files = sorted(image_files)
        total = len(image_files)
        success = 0
        
        os.makedirs(output_dir, exist_ok=True)
        
        for i, img_path in enumerate(image_files):
            output_path = os.path.join(output_dir, img_path.name)
            try:
                self.upscale_image(str(img_path), output_path)
                success += 1
            except Exception as e:
                logger.error(f"Failed to upscale {img_path}: {e}")
                
            # 每10帧清理一次显存，平衡速度和内存
            if (i + 1) % 10 == 0 and self.device == "cuda":
                import torch
                torch.cuda.empty_cache()
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return success, total
    
    def _reduce_tile_size(self):
        """减小 tile size 以节省显存"""
        if self.tile_size > 64:
            self.tile_size = max(64, self.tile_size // 2)
            self.model.tile = self.tile_size
            logger.warning(f"Reduced tile size to {self.tile_size} due to OOM")
    
    def get_memory_usage(self) -> dict:
        """获取显存使用情况"""
        if self.device != "cuda":
            return {"device": "cpu", "allocated": 0, "cached": 0}
        
        import torch
        return {
            "device": "cuda",
            "allocated_mb": torch.cuda.memory_allocated() / 1024 / 1024,
            "cached_mb": torch.cuda.memory_reserved() / 1024 / 1024,
            "total_mb": torch.cuda.get_device_properties(0).total_memory / 1024 / 1024
        }
    
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
