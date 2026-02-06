"""
全局配置
"""
import os
from pathlib import Path


class Settings:
    """应用配置"""
    
    # 版本
    VERSION = "1.0.0"
    APP_NAME = "Video Upscaler"
    
    # 默认输出格式
    DEFAULT_CODEC = "h264_nvenc"  # hevc_nvenc, libx264
    DEFAULT_CRF = 18  # 18-23 is good quality
    
    # 显存限制 (MB)
    VRAM_LIMITS = {
        "流畅": 2048,   # 2GB
        "标准": 4096,   # 4GB
        "高清": 6144,   # 6GB (4050极限)
    }
    
    # 最大同时处理数 (RTX 4050 建议单任务)
    MAX_WORKERS = 1
    
    # 临时文件保留时间 (秒)
    TEMP_RETENTION = 3600 * 24  # 24小时
    
    @classmethod
    def get_models_dir(cls) -> Path:
        """获取模型目录"""
        # 项目目录优先
        project_models = Path(__file__).parent.parent / "models"
        if project_models.exists():
            return project_models
        
        # 用户目录
        home = Path.home()
        user_dir = home / ".video-upscaler" / "models"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    
    @classmethod
    def get_temp_dir(cls) -> Path:
        """获取临时目录"""
        import tempfile
        temp = Path(tempfile.gettempdir()) / "video-upscaler"
        temp.mkdir(exist_ok=True)
        return temp
    
    @classmethod
    def get_output_path(cls, input_path: str, preset: str) -> str:
        """生成输出路径"""
        from pathlib import Path
        
        path = Path(input_path)
        suffix = path.suffix
        stem = path.stem
        
        # 后缀标记
        suffix_map = {
            "流畅": "_720p",
            "标准": "_1080p60",
            "高清": "_4K"
        }
        marker = suffix_map.get(preset, "_upscaled")
        
        output_name = f"{stem}{marker}{suffix}"
        return str(path.parent / output_name)
