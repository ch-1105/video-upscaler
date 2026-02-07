"""
视频处理引擎
负责 FFmpeg 调用、解帧、编码
"""
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Callable, Tuple
import json

from config.presets import PresetConfig, get_preset_config, PresetLevel


class ProcessingOptions:
    """
    处理选项配置类
    封装视频处理的各项参数
    """
    
    def __init__(self, preset_config: Optional[PresetConfig] = None):
        """
        初始化处理选项
        
        Args:
            preset_config: 预设配置，None则使用标准档
        """
        if preset_config is None:
            preset_config = get_preset_config(PresetLevel.STANDARD)
        
        self.preset_config = preset_config
        
        # 从预设复制参数
        self.scale_factor = preset_config.scale_factor
        self.target_fps = preset_config.target_fps
        self.target_resolution = preset_config.target_resolution
        self.tile_size = preset_config.tile_size
        self.use_interpolation = preset_config.use_interpolation
        self.encoder_preset = preset_config.encoder_preset
        self.encoder_quality = preset_config.encoder_quality
        
        # 视频属性（运行时确定）
        self.source_width = 0
        self.source_height = 0
        self.source_fps = 0
    
    @property
    def output_width(self) -> int:
        """计算输出宽度"""
        if self.target_resolution:
            # 从分辨率字符串提取宽度 (如 "1920x1080" -> 1920)
            width = int(self.target_resolution.split('x')[0])
            return width
        return self.source_width * self.scale_factor if self.source_width else 0
    
    @property
    def output_height(self) -> int:
        """计算输出高度"""
        if self.target_resolution:
            # 从分辨率字符串提取高度 (如 "1920x1080" -> 1080)
            height = int(self.target_resolution.split('x')[1])
            return height
        return self.source_height * self.scale_factor if self.source_height else 0
    
    @property
    def output_fps(self) -> float:
        """计算输出帧率"""
        return self.target_fps if self.target_fps else self.source_fps
    
    def get_encoder_params(self, codec: str = "h264_nvenc") -> list:
        """
        获取编码器参数
        
        Args:
            codec: 编码器名称
            
        Returns:
            list: FFmpeg编码参数列表
        """
        params = []
        
        if "nvenc" in codec:
            # NVIDIA硬件编码参数
            nvenc_preset_map = {
                "fast": "p1",
                "medium": "p4", 
                "slow": "p7"
            }
            preset = nvenc_preset_map.get(self.encoder_preset, "p4")
            
            params.extend([
                "-c:v", codec,
                "-preset", preset,
                "-cq", str(self.encoder_quality),
                "-pix_fmt", "yuv420p"
            ])
        else:
            # CPU编码参数
            params.extend([
                "-c:v", codec,
                "-crf", str(self.encoder_quality),
                "-preset", self.encoder_preset,
                "-pix_fmt", "yuv420p"
            ])
        
        return params
    
    def get_scale_filter(self) -> str:
        """获取缩放滤镜参数"""
        if self.output_width and self.output_height:
            return f"scale={self.output_width}:{self.output_height}:flags=lanczos"
        return ""


class VideoEngine:
    """视频处理引擎"""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """检查 FFmpeg 是否可用"""
        try:
            result = subprocess.run(
                [self.ffmpeg, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RuntimeError("FFmpeg not found or not working")
        except Exception as e:
            raise RuntimeError(f"FFmpeg check failed: {e}")
    
    def get_video_info(self, video_path: str) -> dict:
        """获取视频信息"""
        cmd = [
            self.ffprobe,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration",
            "-show_entries", "format=duration",
            "-of", "json",
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to probe video: {result.stderr}")
        
        info = json.loads(result.stdout)
        stream = info.get("streams", [{}])[0]
        format_info = info.get("format", {})
        
        # 解析帧率
        fps_str = stream.get("r_frame_rate", "0/1")
        if "/" in fps_str:
            num, den = map(int, fps_str.split("/"))
            fps = num / den if den != 0 else 0
        else:
            fps = float(fps_str)
        
        return {
            "width": int(stream.get("width", 0)),
            "height": int(stream.get("height", 0)),
            "fps": round(fps, 2),
            "duration": float(format_info.get("duration") or stream.get("duration", 0)),
            "frames": int(stream.get("nb_frames", 0)) if stream.get("nb_frames") else None
        }
    
    def extract_frames(
        self,
        video_path: str,
        output_dir: str,
        options: Optional[ProcessingOptions] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[int, float, str]:
        """
        提取视频帧为图片

        Args:
            video_path: 输入视频路径
            output_dir: 输出目录
            options: 处理选项配置
            progress_callback: 进度回调 (current, total)

        Returns:
            (帧数, 帧率, 帧目录)
        """
        video_info = self.get_video_info(video_path)
        total_frames = video_info.get("frames") or int(video_info["duration"] * video_info["fps"])
        source_fps = video_info["fps"]
        
        # 如果提供了选项，更新选项中的源视频信息
        if options:
            options.source_width = video_info["width"]
            options.source_height = video_info["height"]
            options.source_fps = source_fps
            # 确定输出帧率
            output_fps = options.output_fps
        else:
            output_fps = source_fps

        # 创建帧目录
        frames_dir = os.path.join(output_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)

        # 提取帧 - 使用 png 无损
        cmd = [
            self.ffmpeg,
            "-hide_banner", "-loglevel", "error", # 减少输出
            "-i", video_path,
            "-vf", f"fps={source_fps}",
            "-pix_fmt", "rgb24", # 确保颜色正确
            os.path.join(frames_dir, "frame_%08d.png")
        ]

        # 运行并监控进度
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        # 简单等待完成（实际应用可以用更复杂的进度解析）
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {stderr}")

        # 统计实际帧数
        frame_count = len([f for f in os.listdir(frames_dir) if f.endswith('.png')])

        return frame_count, output_fps, frames_dir
    
    def encode_video(
        self,
        frames_dir: str,
        output_path: str,
        fps: float,
        audio_source: Optional[str] = None,
        options: Optional[ProcessingOptions] = None,
        codec: str = "h264_nvenc",
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> str:
        """
        将帧序列编码为视频

        Args:
            frames_dir: 帧目录
            output_path: 输出视频路径
            fps: 帧率
            audio_source: 音频源视频（复制音频）
            options: 处理选项配置（覆盖默认参数）
            codec: 编码器 h264_nvenc/hevc_nvenc/libx264

        Returns:
            输出文件路径
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        frame_pattern = os.path.join(frames_dir, "frame_%08d.png")

        # 构建命令
        cmd = [self.ffmpeg, "-y"]

        # 输入帧
        cmd.extend([
            "-framerate", str(fps),
            "-i", frame_pattern
        ])

        # 音频（可选）
        if audio_source and os.path.exists(audio_source):
            cmd.extend([
                "-i", audio_source,
                "-c:a", "copy", # 复制音频
                "-shortest" # 以最短为准
            ])

        # 视频编码参数 - 优先使用options中的配置
        if options:
            # 使用预设的编码参数
            cmd.extend(options.get_encoder_params(codec))
        else:
            # 使用默认参数
            if "nvenc" in codec:
                cmd.extend([
                    "-c:v", codec,
                    "-preset", "p4",
                    "-cq", "18",
                    "-pix_fmt", "yuv420p"
                ])
            else:
                cmd.extend([
                    "-c:v", codec,
                    "-crf", "18",
                    "-preset", "medium",
                    "-pix_fmt", "yuv420p"
                ])

        cmd.append(output_path)

        # 执行
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Encoding failed: {result.stderr}")

        return output_path
    
    @staticmethod
    def cleanup_temp(temp_dir: str):
        """清理临时文件"""
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
