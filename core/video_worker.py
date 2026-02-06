"""
视频处理工作线程
"""
from PyQt6.QtCore import QThread, pyqtSignal
import cv2
import os
import tempfile
import shutil

from .upscaler import RealESRGANUpscaler, TileProcessor
from .interpolator import RIFEInterpolator


class VideoWorker(QThread):
    """视频处理工作线程"""
    
    progress = pyqtSignal(int)  # 进度 0-100
    frame_ready = pyqtSignal(object)  # 帧数据，用于预览
    finished = pyqtSignal(bool)  # 是否成功
    error = pyqtSignal(str)  # 错误信息
    
    def __init__(self, input_path: str, output_path: str = None, preset: str = "standard"):
        super().__init__()
        self.input_path = input_path
        self.preset = preset
        self.is_running = True
        
        # 输出路径
        if output_path is None:
            base, ext = os.path.splitext(input_path)
            suffix = "_upscaled"
            output_path = f"{base}{suffix}{ext}"
        self.output_path = output_path
        
        # 初始化处理器
        self.upscaler = None
        self.interpolator = None
    
    def stop(self):
        """停止处理"""
        self.is_running = False
    
    def run(self):
        """主处理流程"""
        try:
            self.process_video()
            self.finished.emit(True)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)
    
    def process_video(self):
        """处理视频"""
        # 1. 分析视频
        cap = cv2.VideoCapture(self.input_path)
        if not cap.isOpened():
            raise Exception(f"无法打开视频: {self.input_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"[Worker] 输入: {width}x{height}@{fps}fps, 共{total_frames}帧")
        
        # 2. 根据预设确定输出参数
        output_fps, scale, enable_interpolation = self.get_preset_params(fps)
        
        # 3. 创建临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            frames_dir = os.path.join(tmpdir, "frames")
            os.makedirs(frames_dir, exist_ok=True)
            
            # 4. 初始化模型
            self.upscaler = RealESRGANUpscaler(scale=scale)
            tile_processor = TileProcessor(self.upscaler)
            
            if enable_interpolation:
                self.interpolator = RIFEInterpolator()
            
            # 5. 处理每一帧
            processed = 0
            frame_idx = 0
            
            while self.is_running:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 超分
                upscaled = tile_processor.process_frame(frame)
                
                # 保存帧
                frame_path = os.path.join(frames_dir, f"frame_{frame_idx:08d}.png")
                cv2.imwrite(frame_path, upscaled)
                
                # 更新进度
                processed += 1
                progress = int(processed / total_frames * 50)  # 超分占50%
                self.progress.emit(progress)
                
                # 发射预览帧（每30帧显示一次）
                if frame_idx % 30 == 0:
                    self.frame_ready.emit(upscaled)
                
                frame_idx += 1
            
            cap.release()
            
            if not self.is_running:
                print("[Worker] 用户取消")
                return
            
            # 6. 补帧（如果启用）
            if enable_interpolation and self.interpolator:
                self.interpolator.interpolate_frames(frames_dir, output_fps / fps)
                self.progress.emit(75)  # 补帧占25%
            
            # 7. 编码输出
            self.encode_video(frames_dir, output_fps)
            self.progress.emit(100)
            
            print(f"[Worker] 输出完成: {self.output_path}")
    
    def get_preset_params(self, input_fps: float) -> tuple:
        """
        根据预设获取参数
        
        Returns:
            (output_fps, scale, enable_interpolation)
        """
        presets = {
            "fast": (input_fps, 2, False),      # 流畅档：2x超分，不补帧
            "standard": (60, 2, True),          # 标准档：2x超分+60fps
            "high": (60, 4, True),              # 高清档：4x超分+60fps
        }
        return presets.get(self.preset, presets["standard"])
    
    def encode_video(self, frames_dir: str, fps: float):
        """编码视频"""
        # 获取帧尺寸
        frames = sorted([f for f in os.listdir(frames_dir) if f.endswith('.png')])
        if not frames:
            raise Exception("没有可编码的帧")
        
        sample = cv2.imread(os.path.join(frames_dir, frames[0]))
        h, w = sample.shape[:2]
        
        # FFmpeg 编码
        import subprocess
        
        input_pattern = os.path.join(frames_dir, "frame_%08d.png")
        
        # 使用 NVENC 硬件编码
        cmd = [
            'ffmpeg', '-y',
            '-framerate', str(fps),
            '-i', input_pattern,
            '-c:v', 'h264_nvenc',
            '-preset', 'p4',  # 质量优先
            '-cq', '23',      # 质量设置
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            self.output_path
        ]
        
        print(f"[Worker] 编码命令: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[Worker] 编码错误: {result.stderr}")
            raise Exception(f"FFmpeg编码失败: {result.stderr[:500]}")
