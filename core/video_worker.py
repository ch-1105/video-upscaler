"""
视频处理工作线程
整合解帧 -> 超分 -> 编码 完整流程
"""
import os
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Optional, Callable
from PyQt6.QtCore import QThread, pyqtSignal

from .video_engine import VideoEngine
from .upscaler import UpscalerEngine

logger = logging.getLogger(__name__)


class VideoWorker(QThread):
    """视频处理工作线程"""
    
    # 信号定义
    progress = pyqtSignal(int, int)  # current, total
    status = pyqtSignal(str)  # 状态文本
    frame_progress = pyqtSignal(int, int)  # frame_current, frame_total
    finished = pyqtSignal(bool, str)  # success, message
    
    def __init__(
        self,
        input_path: str,
        output_path: str,
        preset: str = "标准",
        enable_interpolate: bool = False,
        ffmpeg_path: str = "ffmpeg",
        model_dir: str = None,
        parent=None
    ):
        super().__init__(parent)
        
        self.input_path = input_path
        self.output_path = output_path
        self.preset = preset
        self.enable_interpolate = enable_interpolate
        self.ffmpeg_path = ffmpeg_path
        self.model_dir = model_dir
        
        self._is_running = True
        self._temp_dir = None
        self.video_engine = None
        self.upscaler = None
    
    def stop(self):
        """停止处理"""
        self._is_running = False
        self.status.emit("正在停止...")
    
    def is_running(self) -> bool:
        return self._is_running
    
    def run(self):
        """主处理流程"""
        try:
            self._process()
        except Exception as e:
            logger.exception("Processing failed")
            self.finished.emit(False, str(e))
        finally:
            self._cleanup()
    
    def _process(self):
        """处理流程"""
        # 1. 初始化引擎
        self.status.emit("初始化...")
        self.video_engine = VideoEngine(self.ffmpeg_path)
        
        # 获取视频信息
        self.status.emit("分析视频...")
        video_info = self.video_engine.get_video_info(self.input_path)
        logger.info(f"Video info: {video_info}")
        
        # 2. 创建临时目录
        self._temp_dir = tempfile.mkdtemp(prefix="upscaler_")
        logger.info(f"Temp dir: {self._temp_dir}")
        
        # 3. 解帧
        if not self._is_running:
            return
        
        self.status.emit("提取视频帧...")
        frame_count, fps, frames_dir = self.video_engine.extract_frames(
            self.input_path,
            self._temp_dir
        )
        logger.info(f"Extracted {frame_count} frames at {fps}fps")
        
        # 4. 超分
        if not self._is_running:
            return
        
        self.status.emit("超分辨率处理...")
        upscaled_dir = os.path.join(self._temp_dir, "upscaled")
        
        self.upscaler = UpscalerEngine(
            preset=self.preset,
            device="cuda",
            use_fp16=True
        )
        
        success, total = self.upscaler.upscale_batch(
            frames_dir,
            upscaled_dir,
            progress_callback=self._on_frame_progress
        )
        
        logger.info(f"Upscaled {success}/{total} frames")
        
        if success < total:
            self.status.emit(f"警告: {total - success} 帧处理失败")
        
        # 5. 补帧（可选）
        if self.enable_interpolate and self._is_running:
            self.status.emit("补帧处理...")
            # TODO: RIFE 补帧实现
            pass
        
        # 6. 编码输出
        if not self._is_running:
            return
        
        self.status.emit("编码视频...")
        
        # 选择编码器
        output_suffix = Path(self.output_path).suffix.lower()
        if output_suffix in ['.hevc', '.mkv']:
            codec = "hevc_nvenc"
        else:
            codec = "h264_nvenc"
        
        self.video_engine.encode_video(
            upscaled_dir,
            self.output_path,
            fps,
            audio_source=self.input_path,
            codec=codec,
            crf=18
        )
        
        logger.info(f"Output saved: {self.output_path}")
        self.status.emit("完成!")
        self.finished.emit(True, f"成功处理 {success} 帧")
    
    def _on_frame_progress(self, current: int, total: int):
        """帧处理进度回调"""
        self.frame_progress.emit(current, total)
        # 计算总进度: 解帧10% + 超分70% + 编码20%
        progress = 10 + int(current / total * 70)
        self.progress.emit(progress, 100)
    
    def _cleanup(self):
        """清理临时文件"""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                logger.info(f"Cleaned up {self._temp_dir}")
            except Exception as e:
                logger.warning(f"Cleanup failed: {e}")
        
        # 释放显存
        if self.upscaler:
            del self.upscaler
            self.upscaler = None
