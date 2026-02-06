# Video Upscaler

Windows 视频高清修复工具，基于 Real-ESRGAN 和 RIFE，支持超分 + 帧率修复。

## 系统要求

- Windows 10/11
- NVIDIA 显卡（推荐 RTX 系列，支持 CUDA）
- Python 3.9+

## 功能特性

| 功能 | 说明 |
|------|------|
| **视频超分** | 480p/720p → 1080p/4K（Real-ESRGAN）|
| **帧率修复** | 24fps → 60fps（RIFE 补帧）|
| **批量处理** | 多视频队列处理 |
| **三档预设** | 流畅/标准/高清 |

## 三档输出预设

| 档位 | 分辨率 | 帧率 | 显存需求 | 处理速度 |
|------|--------|------|----------|----------|
| 流畅 | 720p/1080p | 原帧率 | ~2GB | 快 |
| 标准 | 1080p | 60fps | ~4GB | 中等 |
| 高清 | 4K | 60fps | ~6GB | 慢 |

## 安装

```bash
# 克隆仓库
git clone https://github.com/ch-1105/video-upscaler.git
cd video-upscaler

# 安装依赖
pip install -r requirements.txt

# 下载模型（自动下载脚本）
python scripts/download_models.py
```

## 使用

```bash
# 启动 GUI
python main.py
```

## 项目结构

```
video-upscaler/
├── main.py              # 入口
├── gui/                 # PyQt6 界面
├── core/                # 核心处理
├── models/              # AI 模型
└── scripts/             # 工具脚本
```

## License

GPL-3.0
