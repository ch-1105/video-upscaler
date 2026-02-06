"""
环境检测模块
检查 FFmpeg、CUDA、模型等依赖
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Tuple, List, Optional


class EnvironmentChecker:
    """环境检测器"""

    def __init__(self):
        self.ffmpeg_path = None
        self.ffprobe_path = None
        self.cuda_available = False
        self.cuda_version = None
        self.python_version = sys.version_info
        self.missing_deps = []

    def check_all(self) -> dict:
        """运行所有检查"""
        return {
            "ffmpeg": self.check_ffmpeg(),
            "cuda": self.check_cuda(),
            "python": self.check_python(),
            "models": self.check_models(),
            "pytorch": self.check_pytorch(),
        }

    def check_ffmpeg(self) -> bool:
        """检查 FFmpeg 是否可用"""
        # 先检查系统 PATH
        ffmpeg_path = shutil.which("ffmpeg")
        ffprobe_path = shutil.which("ffprobe")

        if ffmpeg_path and ffprobe_path:
            # 验证版本
            try:
                result = subprocess.run(
                    [ffmpeg_path, "-version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    version_line = result.stdout.split('\n')[0]
                    self.ffmpeg_path = ffmpeg_path
                    self.ffprobe_path = ffprobe_path
                    return True
            except Exception:
                pass

        # 检查常见安装位置
        common_paths = [
            "/usr/bin",
            "/usr/local/bin",
            "/opt/ffmpeg/bin",
            os.path.expanduser("~/.local/bin"),
        ]

        for path in common_paths:
            ffmpeg = os.path.join(path, "ffmpeg")
            ffprobe = os.path.join(path, "ffprobe")
            if os.path.exists(ffmpeg) and os.path.exists(ffprobe):
                self.ffmpeg_path = ffmpeg
                self.ffprobe_path = ffprobe
                return True

        self.missing_deps.append({
            "name": "FFmpeg",
            "install_guide": self._get_ffmpeg_install_guide()
        })
        return False

    def check_cuda(self) -> bool:
        """检查 CUDA 是否可用"""
        try:
            # 检查 nvidia-smi
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.cuda_available = True
                # 获取 CUDA 版本
                version_result = subprocess.run(
                    ["nvcc", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if version_result.returncode == 0:
                    for line in version_result.stdout.split('\n'):
                        if "release" in line:
                            self.cuda_version = line.split("release")[-1].split(",")[0].strip()
                return True
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # 也通过 torch 检查
        try:
            import torch
            if torch.cuda.is_available():
                self.cuda_available = True
                self.cuda_version = torch.version.cuda
                return True
        except ImportError:
            pass

        self.missing_deps.append({
            "name": "CUDA",
            "optional": True,
            "install_guide": "CUDA 可选，没有会回退到 CPU 处理（较慢）"
        })
        return False

    def check_python(self) -> bool:
        """检查 Python 版本"""
        return self.python_version >= (3, 9)

    def check_models(self) -> dict:
        """检查模型文件是否存在"""
        models_dir = Path(__file__).parent.parent / "models"
        user_models = Path.home() / ".video-upscaler" / "models"

        required_models = {
            "RealESRGAN_x4plus.pth": [models_dir, user_models],
            "RealESRGAN_x2plus.pth": [models_dir, user_models],
        }

        status = {}
        for model_name, search_paths in required_models.items():
            found = False
            for path in search_paths:
                if (path / model_name).exists():
                    found = True
                    break
            status[model_name] = found

        return status

    def check_pytorch(self) -> bool:
        """检查 PyTorch 是否安装"""
        try:
            import torch
            import torchvision
            return True
        except ImportError:
            self.missing_deps.append({
                "name": "PyTorch",
                "install_guide": "pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121"
            })
            return False

    def get_ffmpeg_path(self) -> Tuple[Optional[str], Optional[str]]:
        """获取 FFmpeg 路径"""
        return self.ffmpeg_path, self.ffprobe_path

    def _get_ffmpeg_install_guide(self) -> str:
        """获取 FFmpeg 安装指南"""
        if sys.platform == "linux":
            return "sudo apt install ffmpeg 或 sudo yum install ffmpeg"
        elif sys.platform == "darwin":
            return "brew install ffmpeg"
        elif sys.platform == "win32":
            return "1. 下载 https://www.gyan.dev/ffmpeg/builds/\n2. 解压并添加到系统 PATH"
        return "请访问 https://ffmpeg.org/download.html"

    def get_summary(self) -> str:
        """获取检测摘要"""
        lines = ["=" * 50, "环境检测", "=" * 50]

        # FFmpeg
        if self.ffmpeg_path:
            lines.append(f"✓ FFmpeg: {self.ffmpeg_path}")
        else:
            lines.append("✗ FFmpeg: 未找到")

        # CUDA
        if self.cuda_available:
            lines.append(f"✓ CUDA: {self.cuda_version or '可用'}")
        else:
            lines.append("⚠ CUDA: 未检测到（将使用 CPU）")

        # PyTorch
        try:
            import torch
            lines.append(f"✓ PyTorch: {torch.__version__}")
            if torch.cuda.is_available():
                lines.append(f"  GPU: {torch.cuda.get_device_name(0)}")
        except ImportError:
            lines.append("✗ PyTorch: 未安装")

        # Python
        lines.append(f"✓ Python: {sys.version.split()[0]}")

        # Models
        model_status = self.check_models()
        found = sum(1 for v in model_status.values() if v)
        lines.append(f"ℹ 模型: {found}/{len(model_status)} 已下载")

        lines.append("=" * 50)

        if self.missing_deps:
            lines.append("\n缺失依赖:")
            for dep in self.missing_deps:
                optional = "(可选)" if dep.get("optional") else "(必需)"
                lines.append(f"\n{dep['name']} {optional}")
                lines.append(f"安装: {dep['install_guide']}")

        return "\n".join(lines)


def check_environment() -> EnvironmentChecker:
    """快速检查环境"""
    checker = EnvironmentChecker()
    checker.check_all()
    return checker


if __name__ == "__main__":
    checker = check_environment()
    print(checker.get_summary())
