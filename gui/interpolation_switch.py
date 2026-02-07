"""
补帧开关控件
提供补帧功能的启用/禁用控制
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QSlider, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont


class InterpolationSwitch(QFrame):
    """
    补帧开关控件
    提供补帧功能的开关和简单配置
    """
    
    interpolation_changed = pyqtSignal(bool)  # 补帧开关状态改变
    target_fps_changed = pyqtSignal(int)     # 目标帧率改变
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_enabled = False
        self.source_fps = 24
        self.target_fps = 60
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI布局"""
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题行
        title_layout = QHBoxLayout()
        
        title = QLabel("🎬 补帧设置")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        title_layout.addWidget(title)
        
        title_layout.addStretch()
        
        # 开关
        self.enable_checkbox = QCheckBox("启用补帧")
        self.enable_checkbox.setChecked(False)
        self.enable_checkbox.stateChanged.connect(self.on_enable_changed)
        title_layout.addWidget(self.enable_checkbox)
        
        layout.addLayout(title_layout)
        
        # 说明文字
        self.desc_label = QLabel(
            "使用 RIFE 算法将视频帧率提升至 60fps\n"
            "• 24fps → 60fps (推荐)\n"
            "• 30fps → 60fps"
        )
        self.desc_label.setStyleSheet("color: #666666; font-size: 12px;")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)
        
        # 帧率显示
        self.fps_layout = QHBoxLayout()
        
        self.source_fps_label = QLabel("原始帧率: 24fps")
        self.source_fps_label.setStyleSheet("color: #2196F3;")
        self.fps_layout.addWidget(self.source_fps_label)
        
        self.fps_layout.addStretch()
        
        arrow = QLabel("➜")
        arrow.setStyleSheet("color: #999;")
        self.fps_layout.addWidget(arrow)
        
        self.fps_layout.addStretch()
        
        self.target_fps_label = QLabel("目标帧率: 60fps")
        self.target_fps_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.fps_layout.addWidget(self.target_fps_label)
        
        layout.addLayout(self.fps_layout)
        
        # 显存提示
        self.vram_label = QLabel("💾 额外显存占用: ~1GB")
        self.vram_label.setStyleSheet("color: #ff9800; font-size: 11px;")
        layout.addWidget(self.vram_label)
        
        # 初始状态
        self.set_enabled(False)
    
    def on_enable_changed(self, state):
        """开关状态改变"""
        self.is_enabled = (state == Qt.CheckState.Checked.value)
        self.set_enabled(self.is_enabled)
        self.interpolation_changed.emit(self.is_enabled)
    
    def set_enabled(self, enabled: bool):
        """设置补帧启用状态"""
        self.is_enabled = enabled
        self.enable_checkbox.setChecked(enabled)
        
        if enabled:
            self.desc_label.setStyleSheet("color: #333333; font-size: 12px;")
            self.vram_label.setStyleSheet("color: #ff9800; font-size: 11px;")
        else:
            self.desc_label.setStyleSheet("color: #999999; font-size: 12px;")
            self.vram_label.setStyleSheet("color: #cccccc; font-size: 11px;")
            self.source_fps_label.setStyleSheet("color: #999999;")
            self.target_fps_label.setStyleSheet("color: #999999;")
    
    def set_source_fps(self, fps: float):
        """设置原始帧率"""
        self.source_fps = fps
        self.source_fps_label.setText(f"原始帧率: {fps:.1f}fps")
        
        # 自动计算目标帧率
        if fps <= 25:
            self.target_fps = 60
        elif fps <= 30:
            self.target_fps = 60
        elif fps <= 50:
            self.target_fps = 60
        else:
            self.target_fps = int(fps)
        
        self.target_fps_label.setText(f"目标帧率: {self.target_fps}fps")
    
    def is_interpolation_enabled(self) -> bool:
        """获取补帧是否启用"""
        return self.is_enabled
    
    def get_target_fps(self) -> int:
        """获取目标帧率"""
        return self.target_fps if self.is_enabled else 0


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 创建补帧开关
    switch = InterpolationSwitch()
    switch.set_source_fps(24.0)
    
    # 连接信号
    def on_interpolation_changed(enabled):
        print(f"补帧 {'启用' if enabled else '禁用'}")
    
    switch.interpolation_changed.connect(on_interpolation_changed)
    
    switch.show()
    sys.exit(app.exec())
