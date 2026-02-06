"""
超分核心 - Real-ESRGAN 封装
"""
import numpy as np
import cv2
import torch
from typing import Union, Tuple
import os


class RealESRGANUpscaler:
    """Real-ESRGAN 超分器"""
    
    def __init__(self, model_path: str = None, scale: int = 2):
        self.scale = scale
        self.model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"[Upscaler] 使用设备: {self.device}")
        
        # 默认模型路径
        if model_path is None:
            model_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
            model_name = f'RealESRGAN_x{scale}plus.pth'
            model_path = os.path.join(model_dir, model_name)
        
        self.load_model(model_path)
    
    def load_model(self, model_path: str):
        """加载模型"""
        try:
            from realesrgan import RealESRGANer
            from basicsr.archs.rrdbnet_arch import RRDBNet
            
            # 模型配置
            model = RRDBNet(
                num_in_ch=3, num_out_ch=3,
                num_feat=64, num_block=23, num_grow_ch=32, scale=self.scale
            )
            
            self.upsampler = RealESRGANer(
                scale=self.scale,
                model_path=model_path,
                model=model,
                tile=0,  # 不切片，显存够的情况
                tile_pad=10,
                pre_pad=0,
                half=True,  # FP16
                device=self.device
            )
            
            print(f"[Upscaler] 模型加载成功: {model_path}")
            
        except Exception as e:
            print(f"[Upscaler] 模型加载失败: {e}")
            self.upsampler = None
    
    def upscale(self, img: np.ndarray) -> np.ndarray:
        """
        超分单帧
        
        Args:
            img: BGR格式图像
            
        Returns:
            超分后的图像
        """
        if self.upsampler is None:
            print("[Upscaler] 模型未加载，返回原图")
            return img
        
        try:
            output, _ = self.upsampler.enhance(img, outscale=self.scale)
            return output
        except Exception as e:
            print(f"[Upscaler] 超分失败: {e}")
            return img
    
    def set_tile_size(self, tile_size: int):
        """
        设置切片大小（显存优化）
        
        RTX 4050 6GB 建议:
        - 720p -> tile=256
        - 1080p -> tile=128
        - 4K -> tile=64
        """
        if self.upsampler:
            self.upsampler.tile = tile_size
            print(f"[Upscaler] 切片大小设置为: {tile_size}")


class TileProcessor:
    """Tile 分块处理器 - 显存优化核心"""
    
    def __init__(self, upscaler: RealESRGANUpscaler):
        self.upscaler = upscaler
        self.tile_size = 256
        self.overlap = 16  # 重叠区域，避免接缝
        self.max_vram_gb = 4  # 最大显存限制
    
    def detect_optimal_tile(self, h: int, w: int) -> int:
        """根据分辨率自动选择最佳 tile 大小"""
        pixels = h * w
        
        if pixels <= 1280 * 720:  # 720p
            return 256
        elif pixels <= 1920 * 1080:  # 1080p
            return 128
        elif pixels <= 3840 * 2160:  # 4K
            return 64
        else:
            return 32
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """处理单帧，自动分块"""
        h, w = frame.shape[:2]
        
        # 自动检测 tile 大小
        optimal_tile = self.detect_optimal_tile(h, w)
        self.upscaler.set_tile_size(optimal_tile)
        
        # 超分
        return self.upscaler.upscale(frame)
    
    def process_frame_with_tiling(self, frame: np.ndarray, tile_size: int = None) -> np.ndarray:
        """
        手动分块处理（极端显存不足时）
        
        Args:
            frame: 输入帧
            tile_size: 每块大小
            
        Returns:
            处理后的帧
        """
        if tile_size is None:
            tile_size = self.tile_size
        
        h, w = frame.shape[:2]
        scale = self.upscaler.scale
        
        # 输出尺寸
        out_h, out_w = h * scale, w * scale
        output = np.zeros((out_h, out_w, 3), dtype=np.uint8)
        
        # 分块处理
        for y in range(0, h, tile_size - self.overlap):
            for x in range(0, w, tile_size - self.overlap):
                # 提取块
                y1 = min(y, h - tile_size) if y + tile_size > h else y
                x1 = min(x, w - tile_size) if x + tile_size > w else x
                y2 = min(y1 + tile_size, h)
                x2 = min(x1 + tile_size, w)
                
                tile = frame[y1:y2, x1:x2]
                
                # 处理块
                upscaled_tile = self.upscaler.upscale(tile)
                
                # 计算输出位置（考虑 overlap）
                out_y1 = y1 * scale
                out_x1 = x1 * scale
                out_y2 = out_y1 + upscaled_tile.shape[0]
                out_x2 = out_x1 + upscaled_tile.shape[1]
                
                # 粘贴到输出（取中心，避免边界缝）
                if y > 0 and x > 0:
                    # 非首行/列，去除重叠
                    edge = self.overlap * scale // 2
                    out_y1 += edge
                    out_x1 += edge
                    tile_roi = upscaled_tile[edge:, edge:] if upscaled_tile.shape[0] > edge and upscaled_tile.shape[1] > edge else upscaled_tile
                    output[out_y1:out_y1+tile_roi.shape[0], out_x1:out_x1+tile_roi.shape[1]] = tile_roi
                else:
                    output[out_y1:out_y2, out_x1:out_x2] = upscaled_tile
        
        return output
