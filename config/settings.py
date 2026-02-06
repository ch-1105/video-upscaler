"""
全局配置
"""
import os

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, 'models')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# 模型下载地址
MODEL_URLS = {
    'RealESRGAN_x2plus': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth',
    'RealESRGAN_x4plus': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
    'RealESRGAN_x4plus_anime_6B': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth',
    'GFPGANv1.4': 'https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth',
}

# 显存优化配置（RTX 4050 6GB）
VRAM_CONFIG = {
    'max_vram_gb': 4,  # 留2GB给系统
    'tile_sizes': {
        '720p': 256,
        '1080p': 128,
        '4k': 64,
    },
    'fp16': True,  # 使用半精度
    'batch_size': 1,
}

# 预设配置
PRESETS = {
    'fast': {
        'name': '流畅',
        'scale': 2,
        'enable_interpolation': False,
        'description': '720p/1080p，快速处理',
    },
    'standard': {
        'name': '标准',
        'scale': 2,
        'enable_interpolation': True,
        'target_fps': 60,
        'description': '1080p 60fps',
    },
    'high': {
        'name': '高清',
        'scale': 4,
        'enable_interpolation': True,
        'target_fps': 60,
        'description': '4K 60fps',
    },
}

# 视频编码配置
VIDEO_CONFIG = {
    'encoder': 'h264_nvenc',  # NVENC硬件编码
    'preset': 'p4',  # 质量优先
    'cq': 23,  # 质量参数
    'pix_fmt': 'yuv420p',
}

# 支持的输入格式
SUPPORTED_FORMATS = {
    'video': ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'],
    'image': ['.jpg', '.jpeg', '.png', '.bmp', '.tiff'],
}
