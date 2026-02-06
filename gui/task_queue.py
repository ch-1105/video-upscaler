"""
任务队列组件
"""
import os
from PyQt6.QtWidgets import (
    QListWidget, QListWidgetItem, QWidget,
    QHBoxLayout, QLabel, QProgressBar, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread


class TaskItemWidget(QWidget):
    """单个任务项控件"""
    
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 文件名
        self.lbl_name = QLabel(self.filename)
        self.lbl_name.setFixedWidth(200)
        layout.addWidget(self.lbl_name)
        
        # 状态
        self.lbl_status = QLabel("等待中")
        self.lbl_status.setStyleSheet("color: #999;")
        layout.addWidget(self.lbl_status)
        
        # 进度条
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setValue(0)
        layout.addWidget(self.progress, 1)
        
        # 删除按钮
        self.btn_remove = QPushButton("×")
        self.btn_remove.setFixedSize(24, 24)
        self.btn_remove.setStyleSheet("""
            QPushButton {
                border: none;
                color: #999;
                font-size: 16px;
            }
            QPushButton:hover {
                color: #f44336;
            }
        """)
        layout.addWidget(self.btn_remove)
    
    def set_status(self, status: str):
        """设置状态"""
        self.lbl_status.setText(status)
        colors = {
            "等待中": "#999",
            "处理中": "#2196F3",
            "完成": "#4CAF50",
            "失败": "#f44336"
        }
        self.lbl_status.setStyleSheet(f"color: {colors.get(status, '#999')};")
    
    def set_progress(self, value: int):
        """设置进度"""
        self.progress.setValue(value)


class TaskQueueWidget(QListWidget):
    """任务队列列表"""
    
    task_started = pyqtSignal(str)  # file_path
    task_finished = pyqtSignal(str, bool)  # file_path, success
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks = {}  # file_path -> TaskItemWidget
        self.setup_ui()
    
    def setup_ui(self):
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: white;
            }
            QListWidget::item {
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)
    
    def add_task(self, file_path: str):
        """添加任务"""
        if file_path in self.tasks:
            return
        
        item = QListWidgetItem()
        widget = TaskItemWidget(file_path)
        widget.btn_remove.clicked.connect(lambda: self.remove_task(file_path))
        
        item.setSizeHint(widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, widget)
        
        self.tasks[file_path] = (item, widget)
    
    def remove_task(self, file_path: str):
        """移除任务"""
        if file_path not in self.tasks:
            return
        
        item, _ = self.tasks[file_path]
        row = self.row(item)
        self.takeItem(row)
        del self.tasks[file_path]
    
    def update_progress(self, file_path: str, progress: int):
        """更新进度"""
        if file_path in self.tasks:
            _, widget = self.tasks[file_path]
            widget.set_progress(progress)
    
    def set_task_status(self, file_path: str, status: str):
        """设置任务状态"""
        if file_path in self.tasks:
            _, widget = self.tasks[file_path]
            widget.set_status(status)
    
    def start_processing(self):
        """开始处理队列"""
        # TODO: 启动处理线程
        pass
    
    def pause_processing(self):
        """暂停处理"""
        # TODO: 暂停处理
        pass
    
    def get_pending_tasks(self) -> list:
        """获取待处理任务"""
        return list(self.tasks.keys())
