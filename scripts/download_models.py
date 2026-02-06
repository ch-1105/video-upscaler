#!/usr/bin/env python3
"""
模型下载脚本
"""
import os
import sys
import urllib.request
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.settings import MODELS_DIR, MODEL_URLS


def download_file(url: str, dest: str) -> bool:
    """下载文件"""
    try:
        print(f"下载: {os.path.basename(dest)}")
        print(f"  URL: {url}")
        print(f"  到: {dest}")
        
        urllib.request.urlretrieve(url, dest)
        print(f"  ✓ 完成\n")
        return True
        
    except Exception as e:
        print(f"  ✗ 失败: {e}\n")
        return False


def main():
    """主函数"""
    print("=" * 50)
    print("Video Upscaler - 模型下载工具")
    print("=" * 50)
    
    # 创建模型目录
    os.makedirs(MODELS_DIR, exist_ok=True)
    print(f"模型目录: {MODELS_DIR}\n")
    
    # 下载模型
    success = 0
    failed = 0
    
    for name, url in MODEL_URLS.items():
        dest = os.path.join(MODELS_DIR, f"{name}.pth")
        
        # 检查是否已存在
        if os.path.exists(dest):
            size = os.path.getsize(dest) / (1024 * 1024)  # MB
            print(f"✓ {name} 已存在 ({size:.1f} MB)\n")
            success += 1
            continue
        
        # 下载
        if download_file(url, dest):
            success += 1
        else:
            failed += 1
    
    # 汇总
    print("=" * 50)
    print(f"下载完成: {success} 个成功, {failed} 个失败")
    print("=" * 50)
    
    if failed > 0:
        print("\n提示: 如果下载失败，可以手动下载模型放到 models/ 目录:")
        for name, url in MODEL_URLS.items():
            print(f"  {name}: {url}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
