"""
档位选择器控件
提供流畅/标准/高清三档预设选择界面
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QButtonGroup,
    QRadioButton, QLabel, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from config.presets import PresetLevel, PresetConfig, get_preset_config, list_presets, check_vram_compatibility


class PresetCard(QFrame):
    """
    预设档位卡片
    显示档位信息和选择状态
    """
    
    def __init__(self, preset_level: PresetLevel, parent=None):
        super().__init__(parent)
        self.preset_level = preset_level
        self.config = get_preset_config(preset_level)
        self.is_selected = False
        
        self.setup_ui()
        self.set_selected(False)
    
    def setup_ui(self):
        """设置UI布局"""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setLineWidth(2)
        self.setMinimumWidth(180)
        self.setMinimumHeight(120)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 档位名称
        self.name_label = QLabel(self.config.name)
        self.name_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)
        
        # 分辨率
        resolution_text = self.config.target_resolution or "自动"
        self.resolution_label = QLabel(f"📺 {resolution_text}")
        self.resolution_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.resolution_label)
        
        # 帧率
        fps_text = f"{self.config.target_fps}fps" if self.config.target_fps else "原帧率"
        self.fps_label = QLabel(f"🎬 {fps_text}")
        self.fps_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.fps_label)
        
        # 显存需求
        self.vram_label = QLabel(f"💾 ~{self.config.vram_required_gb:.1f}GB 显存")
        self.vram_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.vram_label)
        
        # 设置工具提示
        tooltip = f"""
<b>{self.config.name}</b><br>
{self.config.description}<br><br>
<b>配置详情:</b><br>
• 超分倍数: {self.config.scale_factor}x<br>
• 编码预设: {self.config.encoder_preset}<br>
• 编码质量: CRF {self.config.encoder_quality}<br>
• 补帧: {'启用' if self.config.use_interpolation else '禁用'}
        """
        self.setToolTip(tooltip.strip())
    
    def set_selected(self, selected: bool):
        """设置选中状态"""
        self.is_selected = selected
        if selected:
            self.setStyleSheet("""
                QFrame {
                    background-color: #e3f2fd;
                    border: 2px solid #1976d2;
                    border-radius: 8px;
                }
            """)
            self.name_label.setStyleSheet("color: #1976d2;")
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: white;
                    border: 2px solid #cccccc;
                    border-radius: 8px;
                }
                QFrame:hover {
                    border: 2px solid #1976d2;
                    background-color: #f5f5f5;
                }
            """)
            self.name_label.setStyleSheet("color: #333333;")
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent().select_preset(self.preset_level)


class PresetSelector(QWidget):
    """
    档位选择器主控件
    包含三个档位卡片和显存检测
    """
    
    preset_changed = pyqtSignal(PresetLevel)  # 档位改变信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_preset = PresetLevel.STANDARD
        self.cards = {}
        self.available_vram = 0.0
        
        self.setup_ui()
        self.update_vram_info()
    
    def setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("处理档位")
        title_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # 档位卡片容器
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(15)
        
        for level in [PresetLevel.FAST, PresetLevel.STANDARD, PresetLevel.HIGH]:
            card = PresetCard(level, self)
            self.cards[level] = card
            cards_layout.addWidget(card)
        
        layout.addLayout(cards_layout)
        
        # 显存状态标签
        self.vram_status_label = QLabel()
        self.vram_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.vram_status_label)
        
        # 说明文字
        desc_label = QLabel("💡 点击卡片选择处理档位，自动检测显存兼容性")
        desc_label.setStyleSheet("color: #666666; font-size: 12px;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)
        
        # 初始选中标准档
        self.select_preset(PresetLevel.STANDARD)
    
    def select_preset(self, level: PresetLevel):
        """选择档位"""
        self.current_preset = level
        
        # 更新卡片状态
        for preset_level, card in self.cards.items():
            card.set_selected(preset_level == level)
        
        # 检查显存兼容性
        self.update_vram_status()
        
        # 发送信号
        self.preset_changed.emit(level)
    
    def set_available_vram(self, vram_gb: float):
        """设置可用显存（用于显存检测）"""
        self.available_vram = vram_gb
        self.update_vram_status()
    
    def update_vram_status(self):
        """更新显存状态显示"""
        if self.available_vram <= 0:
            self.vram_status_label.setText("💻 显存检测中...")
            self.vram_status_label.setStyleSheet("color: #666666;")
            return
        
        compatible, message = check_vram_compatibility(
            self.available_vram, 
            self.current_preset
        )
        
        self.vram_status_label.setText(message)
        
        if "✓" in message:
            self.vram_status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        elif "⚠" in message:
            self.vram_status_label.setStyleSheet("color: #ff9800; font-weight: bold;")
        else:
            self.vram_status_label.setStyleSheet("color: #f44336; font-weight: bold;")
    
    def update_vram_info(self):
        """更新显存信息（尝试自动检测）"""
        try:
            import torch
            if torch.cuda.is_available():
                total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                self.set_available_vram(total_vram)
            else:
                self.vram_status_label.setText("⚠ 未检测到CUDA显卡")
                self.vram_status_label.setStyleSheet("color: #ff9800;")
        except Exception:
            self.vram_status_label.setText("ℹ 显存信息待检测")
            self.vram_status_label.setStyleSheet("color: #666666;")
    
    def get_current_preset(self) -> PresetConfig:
        """获取当前选中的预设配置"""
        return get_preset_config(self.current_preset)
    
    def get_current_preset_level(self) -> PresetLevel:
        """获取当前选中的档位"""
        return self.current_preset


# 兼容旧代码的别名
PresetSelectorWidget = PresetSelector


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    selector = PresetSelector()
    selector.set_available_vram(6.0)  # 模拟6GB显存
    
    # 连接信号测试
    def on_preset_changed(level):
        config = get_preset_config(level)
        print(f"选择档位: {config.name}")
    
    selector.preset_changed.connect(on_preset_changed)
    
    selector.show()
    sys.exit(app.exec())
