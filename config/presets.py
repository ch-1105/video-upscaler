"""
视频处理预设配置模块
定义三档处理预设：流畅/标准/高清
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class PresetLevel(Enum):
    """预设档位枚举"""
    FAST = "fast"        # 流畅档
    STANDARD = "standard"  # 标准档
    HIGH = "high"        # 高清档


@dataclass
class PresetConfig:
    """
    预设配置数据类
    
    Attributes:
        name: 预设名称
        description: 预设描述
        scale_factor: 超分倍数 (2x, 3x, 4x)
        target_fps: 目标帧率 (None表示保持原帧率)
        target_resolution: 目标分辨率 (如 "1920x1080", None表示自动计算)
        vram_required_gb: 显存需求(GB)
        tile_size: 分块大小 (0表示不分块)
        use_interpolation: 是否启用补帧
        encoder_preset: 编码器预设 (fast/medium/slow)
        encoder_quality: 编码质量 (CRF值，越低质量越高)
    """
    name: str
    description: str
    scale_factor: int
    target_fps: Optional[int]
    target_resolution: Optional[str]
    vram_required_gb: float
    tile_size: int
    use_interpolation: bool
    encoder_preset: str
    encoder_quality: int


# 预设配置定义
PRESETS = {
    PresetLevel.FAST: PresetConfig(
        name="流畅档",
        description="快速处理，适合720p/1080p视频，保留原帧率",
        scale_factor=2,
        target_fps=None,
        target_resolution="1920x1080",
        vram_required_gb=2.0,
        tile_size=0,  # 小分辨率无需分块
        use_interpolation=False,
        encoder_preset="fast",
        encoder_quality=23
    ),
    PresetLevel.STANDARD: PresetConfig(
        name="标准档",
        description="均衡画质与速度，输出1080p@60fps",
        scale_factor=2,
        target_fps=60,
        target_resolution="1920x1080",
        vram_required_gb=4.0,
        tile_size=400,  # 中等分块
        use_interpolation=True,
        encoder_preset="medium",
        encoder_quality=20
    ),
    PresetLevel.HIGH: PresetConfig(
        name="高清档",
        description="最高画质，输出4K@60fps",
        scale_factor=4,
        target_fps=60,
        target_resolution="3840x2160",
        vram_required_gb=6.0,
        tile_size=200,  # 小分块节省显存
        use_interpolation=True,
        encoder_preset="slow",
        encoder_quality=18
    )
}


def get_preset_config(preset_level: PresetLevel) -> PresetConfig:
    """
    获取指定档位的预设配置
    
    Args:
        preset_level: 预设档位
        
    Returns:
        PresetConfig: 预设配置对象
    """
    return PRESETS.get(preset_level, PRESETS[PresetLevel.STANDARD])


def get_preset_by_name(name: str) -> Optional[PresetConfig]:
    """
    根据名称获取预设配置
    
    Args:
        name: 预设名称 (fast/standard/high)
        
    Returns:
        PresetConfig or None: 预设配置对象
    """
    name_map = {
        "fast": PresetLevel.FAST,
        "standard": PresetLevel.STANDARD,
        "high": PresetLevel.HIGH,
        "流畅": PresetLevel.FAST,
        "标准": PresetLevel.STANDARD,
        "高清": PresetLevel.HIGH
    }
    level = name_map.get(name.lower())
    return PRESETS.get(level) if level else None


def list_presets() -> list[dict]:
    """
    列出所有可用预设
    
    Returns:
        list: 预设信息列表
    """
    return [
        {
            "level": level.value,
            "name": config.name,
            "description": config.description,
            "vram_required_gb": config.vram_required_gb,
            "target_resolution": config.target_resolution,
            "target_fps": config.target_fps
        }
        for level, config in PRESETS.items()
    ]


def estimate_processing_time(
    video_duration: float,
    preset_level: PresetLevel,
    has_gpu: bool = True
) -> float:
    """
    估算处理时间
    
    Args:
        video_duration: 视频时长(秒)
        preset_level: 预设档位
        has_gpu: 是否使用GPU
        
    Returns:
        float: 估算处理时间(秒)
    """
    config = get_preset_config(preset_level)
    
    # 基础倍速 (相对于实时)
    speed_multipliers = {
        PresetLevel.FAST: 2.0,      # 2倍实时
        PresetLevel.STANDARD: 0.5,   # 0.5倍实时
        PresetLevel.HIGH: 0.25      # 0.25倍实时
    }
    
    speed = speed_multipliers.get(preset_level, 0.5)
    
    # CPU处理更慢
    if not has_gpu:
        speed *= 0.1
    
    return video_duration / speed


def check_vram_compatibility(
    available_vram_gb: float,
    preset_level: PresetLevel
) -> tuple[bool, str]:
    """
    检查显存是否满足预设要求
    
    Args:
        available_vram_gb: 可用显存(GB)
        preset_level: 预设档位
        
    Returns:
        tuple: (是否兼容, 提示信息)
    """
    config = get_preset_config(preset_level)
    
    if available_vram_gb >= config.vram_required_gb:
        return True, f"✓ 显存充足 ({available_vram_gb:.1f}GB >= {config.vram_required_gb:.1f}GB)"
    elif available_vram_gb >= config.vram_required_gb * 0.8:
        return True, f"⚠ 显存紧张 ({available_vram_gb:.1f}GB，建议 {config.vram_required_gb:.1f}GB)"
    else:
        return False, f"✗ 显存不足 ({available_vram_gb:.1f}GB < {config.vram_required_gb:.1f}GB)"


if __name__ == "__main__":
    # 测试代码
    print("可用预设列表:")
    for preset in list_presets():
        print(f"  - {preset['name']}: {preset['description']}")
        print(f"    分辨率: {preset['target_resolution']}, 帧率: {preset['target_fps']}, 显存: {preset['vram_required_gb']}GB")
        print()
    
    # 测试获取配置
    config = get_preset_config(PresetLevel.STANDARD)
    print(f"标准档配置: {config}")
    
    # 测试显存检查
    compatible, msg = check_vram_compatibility(4.5, PresetLevel.HIGH)
    print(f"\n显存检查: {msg}")
