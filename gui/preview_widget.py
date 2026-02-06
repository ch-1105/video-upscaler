"""
预览组件
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage
import cv2
import numpy as np


class PreviewWidget(QWidget):
    """预览组件 - 原图 vs 超分 对比"""
    
    def __init__(self):
        super().__init__()
        self.current_frame = None
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 标签
        self.title_label = QLabel("预览")
        layout.addWidget(self.title_label)
        
        # 原图预览
        self.original_label = QLabel("原图")
        self.original_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.original_label.setMinimumSize(400, 225)
        self.original_label.setStyleSheet("background-color: #222; color: white;")
        layout.addWidget(self.original_label)
        
        # 处理结果预览
        self.result_label = QLabel("处理后")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setMinimumSize(400, 225)
        self.result_label.setStyleSheet("background-color: #222; color: white;")
        layout.addWidget(self.result_label)
        
        # 控制
        controls = QHBoxLayout()
        
        self.btn_compare = QPushButton("对比模式: 左右")
        self.btn_compare.clicked.connect(self.toggle_compare)
        controls.addWidget(self.btn_compare)
        
        controls.addWidget(QLabel("缩放:"))
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["100%", "125%", "150%", "200%"])
        controls.addWidget(self.zoom_combo)
        
        layout.addLayout(controls)
    
    def toggle_compare(self):
        """切换对比模式"""
        # TODO: 实现多种对比模式
        pass
    
    def show_frame(self, frame: np.ndarray, is_original: bool = True):
        """显示帧"""
        if frame is None:
            return
        
        # 转换为QImage
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 缩放适应显示区域
        max_w, max_h = 400, 225
        scale = min(max_w / w, max_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        
        resized = cv2.resize(rgb, (new_w, new_h))
        
        # 创建QPixmap
        bytes_per_line = 3 * new_w
        q_img = QImage(resized.data, new_w, new_h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        
        # 显示
        label = self.original_label if is_original else self.result_label
        label.setPixmap(pixmap)
    
    def clear(self):
        """清空预览"""
        self.original_label.setText("原图")
        self.result_label.setText("处理后")
        self.original_label.setPixmap(QPixmap())
        self.result_label.setPixmap(QPixmap())
