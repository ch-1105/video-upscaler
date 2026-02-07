"""
视频处理工作线程
整合解帧 -> 超分 -> 补帧 -> 编码 完整流程
"""
import os
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Optional, Callable
from PyQt6.QtCore import QThread, pyqtSignal

from .video_engine import VideoEngine, ProcessingOptions
from .upscaler import UpscalerEngine
from .interpolator import InterpolatorEngine

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
        target_fps: Optional[int] = None,
        ffmpeg_path: str = "ffmpeg",
        model_dir: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)

        self.input_path = input_path
        self.output_path = output_path
        self.preset = preset
        self.enable_interpolate = enable_interpolate
        self.target_fps = target_fps  # 补帧目标帧率
        self.ffmpeg_path = ffmpeg_path
        self.model_dir = model_dir

        self._is_running = True
        self._temp_dir = None
        self.video_engine = None
        self.upscaler = None
        self.interpolator = None
        self.video_info = None
        self.processing_options = None
    
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
        """处理流程: 解帧 -> 超分 -> 补帧 -> 编码"""
        # 1. 初始化引擎
        self.status.emit("初始化...")
        self.video_engine = VideoEngine(self.ffmpeg_path)

        # 获取视频信息
        self.status.emit("分析视频...")
        self.video_info = self.video_engine.get_video_info(self.input_path)
        source_fps = self.video_info["fps"]
        logger.info(f"Video info: {self.video_info}")

        # 2. 创建临时目录
        self._temp_dir = tempfile.mkdtemp(prefix="upscaler_")
        logger.info(f"Temp dir: {self._temp_dir}")

        # 3. 解帧
        if not self._is_running:
            return

        self.status.emit("提取视频帧...")
        
        # 创建处理选项
        from config.presets import get_preset_by_name
        preset_config = get_preset_by_name(self.preset)
        if preset_config:
            self.processing_options = ProcessingOptions(preset_config)
        else:
            self.processing_options = ProcessingOptions()
        
        frame_count, output_fps, frames_dir = self.video_engine.extract_frames(
            self.input_path,
            self._temp_dir,
            options=self.processing_options
        )
        logger.info(f"Extracted {frame_count} frames at {source_fps}fps")
        self.progress.emit(10, 100)  # 解帧完成 10%

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
            progress_callback=self._on_upscale_progress
        )

        logger.info(f"Upscaled {success}/{total} frames")

        if success < total:
            self.status.emit(f"警告: {total - success} 帧超分失败")
        
        # 清理解帧目录节省空间
        self._cleanup_frame_dir(frames_dir)
        
        self.progress.emit(60, 100)  # 超分完成 60%

        # 5. 补帧（可选）- 在超分后进行
        interpolated_dir = upscaled_dir
        final_fps = output_fps
        
        if self.enable_interpolate and self._is_running:
            self.status.emit("补帧处理...")
            
            interpolated_dir = os.path.join(self._temp_dir, "interpolated")
            
            # 初始化补帧引擎
            self.interpolator = InterpolatorEngine(
                device="cuda",
                use_fp16=True
            )
            
            if self.interpolator.is_available():
                try:
                    frame_count_interp, final_fps = self.interpolator.interpolate_frames(
                        input_dir=upscaled_dir,
                        output_dir=interpolated_dir,
                        source_fps=output_fps,
                        progress_callback=self._on_interpolate_progress
                    )
                    
                    logger.info(f"Interpolated to {final_fps}fps, {frame_count_interp} frames")
                    self.status.emit(f"补帧完成: {final_fps}fps")
                    
                    # 清理超分目录
                    self._cleanup_frame_dir(upscaled_dir)
                    
                except Exception as e:
                    logger.error(f"Interpolation failed: {e}")
                    self.status.emit(f"补帧失败，使用原帧率")
                    interpolated_dir = upscaled_dir
                    final_fps = output_fps
            else:
                self.status.emit("补帧引擎不可用，使用简单插值")
                # 使用简单插值
                frame_count_interp, final_fps = self.interpolator.interpolate_frames(
                    input_dir=upscaled_dir,
                    output_dir=interpolated_dir,
                    source_fps=output_fps
                )
        
        self.progress.emit(80, 100)  # 补帧完成 80%

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
            interpolated_dir,
            self.output_path,
            final_fps,  # 使用补帧后的帧率
            audio_source=self.input_path,
            options=self.processing_options,
            codec=codec
        )

        logger.info(f"Output saved: {self.output_path}")
        self.status.emit("完成!")
        self.finished.emit(True, f"成功处理: {self.output_path}")
    
    def _on_upscale_progress(self, current: int, total: int):
        """超分进度回调"""
        self.frame_progress.emit(current, total)
        # 超分阶段占 10% - 60%
        progress = 10 + int(current / total * 50)
        self.progress.emit(progress, 100)
    
    def _on_interpolate_progress(self, current: int, total: int):
        """补帧进度回调"""
        self.frame_progress.emit(current, total)
        # 补帧阶段占 60% - 80%
        progress = 60 + int(current / total * 20)
        self.progress.emit(progress, 100)
    
    def _on_frame_progress(self, current: int, total: int):
        """帧处理进度回调（兼容旧代码）"""
        self.frame_progress.emit(current, total)
        self.progress.emit(10 + int(current / total * 70), 100)
    
    def _cleanup_frame_dir(self, frame_dir: str):
        """清理帧目录以节省空间"""
        if frame_dir and os.path.exists(frame_dir):
            try:
                shutil.rmtree(frame_dir, ignore_errors=True)
                logger.info(f"Cleaned up frame dir: {frame_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup frame dir: {e}")

    def _cleanup(self):
        """清理临时文件和资源"""
        # 停止处理标志
        self._is_running = False
        
        # 清理补帧引擎
        if self.interpolator:
            try:
                del self.interpolator
                self.interpolator = None
                logger.info("Interpolator engine released")
            except Exception as e:
                logger.warning(f"Failed to release interpolator: {e}")
        
        # 清理超分引擎
        if self.upscaler:
            try:
                del self.upscaler
                self.upscaler = None
                logger.info("Upscaler engine released")
            except Exception as e:
                logger.warning(f"Failed to release upscaler: {e}")
        
        # 清理临时目录
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                logger.info(f"Cleaned up temp dir: {self._temp_dir}")
            except Exception as e:
                logger.warning(f"Cleanup failed: {e}")
        
        # 强制垃圾回收
        import gc
        gc.collect()
        
        # 清理CUDA缓存
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("CUDA cache cleared")
        except:
            pass
