"""
预览组件
显示原图和超分后的对比
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

class PreviewWidget(QWidget):
    """预览组件"""
    
    frame_selected = pyqtSignal(int)  # 选中帧号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 顶部标签
        title = QLabel("预览 (原图 / 超分后)")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # 左右对比区域
        compare_layout = QHBoxLayout()
        
        # 原图
        self.original_label = QLabel("原图")
        self.original_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.original_label.setMinimumSize(400, 300)
        self.original_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)
        compare_layout.addWidget(self.original_label)
        
        # 超分结果
        self.result_label = QLabel("超分结果")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setMinimumSize(400, 300)
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)
        compare_layout.addWidget(self.result_label)
        
        layout.addLayout(compare_layout)
        
        # 帧选择滑块
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("帧:"))
        
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setMinimum(1)
        self.frame_slider.setMaximum(1)
        self.frame_slider.setValue(1)
        self.frame_slider.setEnabled(False)
        self.frame_slider.valueChanged.connect(self._on_frame_changed)
        slider_layout.addWidget(self.frame_slider, 1)
        
        self.frame_label = QLabel("1 / 1")
        slider_layout.addWidget(self.frame_label)
        
        layout.addLayout(slider_layout)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        self.btn_compare = QPushButton("同步对比")
        self.btn_compare.setCheckable(True)
        self.btn_compare.setChecked(True)
        
        self.btn_fullscreen = QPushButton("全屏预览")
        
        btn_layout.addWidget(self.btn_compare)
        btn_layout.addWidget(self.btn_fullscreen)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
    
    def set_video(self, original_frame: str = None, total_frames: int = 1):
        """设置预览视频"""
        self.frame_slider.setMaximum(total_frames)
        self.frame_slider.setValue(1)
        self.frame_label.setText(f"1 / {total_frames}")
        
        if total_frames > 1:
            self.frame_slider.setEnabled(True)
    
    def set_frames(self, current: int, total: int):
        """更新帧计数"""
        self.frame_slider.setMaximum(total)
        self.frame_label.setText(f"{current} / {total}")
    
    def _on_frame_changed(self, value: int):
        """帧改变"""
        self.frame_label.setText(f"{value} / {self.frame_slider.maximum()}")
        self.frame_selected.emit(value)
    
    def clear(self):
        """清空预览"""
        self.original_label.setText("原图")
        self.result_label.setText("超分结果")
        self.frame_slider.setMaximum(1)
        self.frame_slider.setValue(1)
        self.frame_slider.setEnabled(False)
