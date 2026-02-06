#!/usr/bin/env python3
"""
Video Upscaler - 视频高清修复工具
主入口
"""
import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.env_checker import check_environment
from gui.main_window import MainWindow


def check_environment_gui():
    """检查环境并在 GUI 中显示结果"""
    checker = check_environment()
    
    # 检查必要依赖
    has_ffmpeg = checker.ffmpeg_path is not None
    has_pytorch = checker.check_pytorch()
    
    if not has_ffmpeg:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("环境检查失败")
        msg.setText("未检测到 FFmpeg")
        msg.setInformativeText(
            "FFmpeg 是必需依赖，用于视频解帧和编码。\n\n"
            f"安装指南: {checker._get_ffmpeg_install_guide()}"
        )
        msg.exec()
        return False
    
    if not has_pytorch:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("环境检查失败")
        msg.setText("未检测到 PyTorch")
        msg.setInformativeText(
            "请安装 PyTorch: pip install torch torchvision"
        )
        msg.exec()
        return False
    
    # 检查模型
    model_status = checker.check_models()
    missing_models = [name for name, exists in model_status.items() if not exists]
    
    if missing_models:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("模型文件缺失")
        msg.setText(f"缺少 {len(missing_models)} 个模型文件")
        msg.setInformativeText(
            f"缺失: {', '.join(missing_models)}\n\n"
            "是否现在下载？"
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            # 运行模型下载脚本
            import subprocess
            result = subprocess.run(
                [sys.executable, "scripts/download_models.py"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                QMessageBox.critical(
                    None, "下载失败",
                    f"模型下载失败:\n{result.stderr}"
                )
                return False
    
    return True


def main():
    # 启用高分屏支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("Video Upscaler")
    app.setApplicationVersion("1.0.0")
    
    # 环境检查
    if not check_environment_gui():
        sys.exit(1)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
