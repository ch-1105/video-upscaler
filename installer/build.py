#!/usr/bin/env python3
"""
打包脚本 - 使用 PyInstaller 创建可执行文件
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path


def clean_build():
    """清理构建目录"""
    dirs_to_remove = ['build', 'dist']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            print(f"清理 {dir_name}/...")
            shutil.rmtree(dir_name)
    
    # 清理 __pycache__
    for root, dirs, files in os.walk('.'):
        for dir_name in dirs:
            if dir_name == '__pycache__':
                path = os.path.join(root, dir_name)
                print(f"清理 {path}...")
                shutil.rmtree(path)


def build_executable():
    """构建可执行文件"""
    print("=" * 60)
    print("开始打包 Video Upscaler")
    print("=" * 60)
    
    # PyInstaller 参数
    pyinstaller_args = [
        'pyinstaller',
        '--name=VideoUpscaler',
        '--onefile',  # 打包为单个文件
        '--windowed',  # Windows下不显示控制台
        '--noconfirm',  # 不询问确认
        '--clean',  # 清理临时文件
        
        # 图标
        '--icon=assets/icon.ico',
        
        # 隐藏导入
        '--hidden-import=PyQt6.sip',
        '--hidden-import=PyQt6.QtCore',
        '--hidden-import=PyQt6.QtGui',
        '--hidden-import=PyQt6.QtWidgets',
        '--hidden-import=realesrgan',
        '--hidden-import=torch',
        '--hidden-import=cv2',
        '--hidden-import=numpy',
        '--hidden-import=PIL',
        
        # 数据文件
        '--add-data=config:config',
        '--add-data=gui:gui',
        '--add-data=core:core',
        '--add-data=scripts:scripts',
        
        # 排除不必要的模块以减小体积
        '--exclude-module=matplotlib',
        '--exclude-module=scipy',
        '--exclude-module=pandas',
        '--exclude-module=IPython',
        '--exclude-module=jupyter',
        '--exclude-module=notebook',
        '--exclude-module=pytest',
        '--exclude-module=tkinter',
        
        # 优化
        '--strip',  # 去除符号表
        
        # 主入口
        'main.py'
    ]
    
    print(f"运行命令: {' '.join(pyinstaller_args)}")
    result = subprocess.run(pyinstaller_args)
    
    if result.returncode != 0:
        print("✗ 打包失败!")
        return False
    
    print("\n✓ 可执行文件创建成功!")
    print(f"输出目录: {os.path.abspath('dist')}")
    return True


def create_directory_structure():
    """创建额外的目录结构"""
    print("\n创建目录结构...")
    
    dist_dir = Path('dist')
    
    # 创建必要的子目录
    dirs = [
        dist_dir / 'models',
        dist_dir / 'temp',
        dist_dir / 'logs',
    ]
    
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  创建: {dir_path}")


def copy_additional_files():
    """复制额外文件"""
    print("\n复制额外文件...")
    
    files_to_copy = [
        ('README.md', 'dist/README.txt'),
        ('LICENSE', 'dist/LICENSE.txt'),
    ]
    
    for src, dst in files_to_copy:
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  复制: {src} -> {dst}")


def create_batch_files():
    """创建批处理文件"""
    print("\n创建启动脚本...")
    
    # Windows启动脚本
    batch_content = '''@echo off
title Video Upscaler
cd /d "%~dp0"
start VideoUpscaler.exe
'''
    
    with open('dist/启动程序.bat', 'w', encoding='utf-8') as f:
        f.write(batch_content)
    print("  创建: dist/启动程序.bat")


def check_requirements():
    """检查打包依赖"""
    print("检查打包依赖...")
    
    try:
        import PyInstaller
        print(f"  ✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  ✗ PyInstaller 未安装")
        print("  请运行: pip install pyinstaller")
        return False
    
    return True


def get_file_size(file_path):
    """获取文件大小"""
    size = os.path.getsize(file_path)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def print_summary():
    """打印打包摘要"""
    print("\n" + "=" * 60)
    print("打包完成!")
    print("=" * 60)
    
    dist_dir = Path('dist')
    exe_path = dist_dir / 'VideoUpscaler.exe'
    
    if exe_path.exists():
        print(f"\n可执行文件: {exe_path}")
        print(f"文件大小: {get_file_size(exe_path)}")
    
    print(f"\n输出目录: {dist_dir.absolute()}")
    print("\n下一步:")
    print("  1. 运行: python installer/build.py (创建安装程序)")
    print("  2. 或使用 Inno Setup 编译 installer/setup.iss")


def main():
    """主函数"""
    # 切换到项目根目录
    os.chdir(Path(__file__).parent.parent)
    
    # 检查依赖
    if not check_requirements():
        sys.exit(1)
    
    # 清理旧的构建
    clean_build()
    
    # 构建
    if not build_executable():
        sys.exit(1)
    
    # 创建目录结构
    create_directory_structure()
    
    # 复制额外文件
    copy_additional_files()
    
    # 创建批处理文件
    create_batch_files()
    
    # 打印摘要
    print_summary()
    
    print("\n✓ 所有任务完成!")


if __name__ == "__main__":
    main()
