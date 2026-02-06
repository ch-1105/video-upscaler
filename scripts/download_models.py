#!/usr/bin/env python3
"""
模型下载脚本
自动下载 Real-ESRGAN 预训练模型
"""
import os
import sys
import urllib.request
import hashlib
from pathlib import Path


MODELS = {
    "RealESRGAN_x4plus": {
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "filename": "RealESRGAN_x4plus.pth",
        "hash": "ab9d175d37af1c77ea5fbce902e882f27f02860f60c52a0e67eb82a8f154cad2",
        "size_mb": 64
    },
    "RealESRGAN_x2plus": {
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
        "filename": "RealESRGAN_x2plus.pth",
        "hash": None,
        "size_mb": 32
    },
    "RealESRGAN_animevideov3": {
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_animevideov3.pth",
        "filename": "RealESRGAN_animevideov3.pth",
        "hash": None,
        "size_mb": 18
    }
}


def get_models_dir() -> Path:
    """获取模型目录"""
    # 优先项目目录
    project_dir = Path(__file__).parent.parent / "models"
    if project_dir.exists() or os.access(project_dir.parent, os.W_OK):
        return project_dir
    
    # 用户目录
    home = Path.home()
    user_models = home / ".video-upscaler" / "models"
    return user_models


def check_sha256(file_path: str, expected_hash: str) -> bool:
    """验证文件哈希"""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest() == expected_hash


def download_file(url: str, dest: str, desc: str = ""):
    """下载文件带进度"""
    class ProgressBar:
        def __init__(self, total_mb: float):
            self.total = total_mb
            self.downloaded = 0
            self.last_percent = -1
        
        def __call__(self, block_num, block_size, total_size):
            self.downloaded = block_num * block_size / 1024 / 1024
            percent = int(self.downloaded / self.total * 100) if self.total else 0
            if percent != self.last_percent and percent % 10 == 0:
                print(f"{desc}: {percent}% ({self.downloaded:.1f}/{self.total:.1f} MB)")
                self.last_percent = percent
    
    total_mb = MODELS.get(desc, {}).get("size_mb", 100)
    urllib.request.urlretrieve(url, dest, ProgressBar(total_mb))


def download_model(name: str, models_dir: Path) -> bool:
    """下载单个模型"""
    if name not in MODELS:
        print(f"Unknown model: {name}")
        return False
    
    info = MODELS[name]
    dest_path = models_dir / info["filename"]
    
    # 检查是否已存在
    if dest_path.exists():
        if info["hash"] and check_sha256(str(dest_path), info["hash"]):
            print(f"✓ {name} already exists and verified")
            return True
        else:
            print(f"! {name} exists but hash mismatch, re-downloading...")
    
    # 下载
    print(f"\nDownloading {name}...")
    print(f"URL: {info['url']}")
    print(f"Dest: {dest_path}")
    
    try:
        os.makedirs(models_dir, exist_ok=True)
        download_file(info["url"], str(dest_path), name)
        
        # 验证
        if info["hash"] and not check_sha256(str(dest_path), info["hash"]):
            print(f"✗ {name} hash verification failed!")
            os.remove(dest_path)
            return False
        
        print(f"✓ {name} downloaded successfully")
        return True
        
    except Exception as e:
        print(f"✗ Failed to download {name}: {e}")
        if dest_path.exists():
            os.remove(dest_path)
        return False


def main():
    print("=" * 50)
    print("Video Upscaler - Model Downloader")
    print("=" * 50)
    
    models_dir = get_models_dir()
    print(f"\nModels directory: {models_dir}")
    
    # 下载所有模型
    success = 0
    for name in MODELS:
        if download_model(name, models_dir):
            success += 1
    
    # 结果
    print(f"\n{'=' * 50}")
    print(f"Downloaded: {success}/{len(MODELS)} models")
    
    if success == len(MODELS):
        print("✓ All models ready!")
        return 0
    else:
        print("✗ Some models failed, please retry")
        return 1


if __name__ == "__main__":
    sys.exit(main())
