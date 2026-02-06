"""
任务队列组件
"""
import os
from PyQt6.QtWidgets import (
    QListWidget, QListWidgetItem, QWidget,
    QHBoxLayout, QLabel, QProgressBar, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal

from core.video_worker import VideoWorker
from config.settings import Settings


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
            "暂停": "#FF9800",
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
    all_finished = pyqtSignal()  # 所有任务完成
    progress_updated = pyqtSignal(int, int)  # current, total 总进度

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks = {}  # file_path -> TaskItemWidget
        self.pending_tasks = []  # 待处理任务列表
        self.current_worker = None  # 当前工作线程
        self.is_processing = False
        self.is_paused = False
        self.current_preset = "标准"
        self.enable_interpolate = False
        self.output_dir = None

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

    def set_preset(self, preset: str):
        """设置处理预设"""
        self.current_preset = preset

    def set_interpolate(self, enabled: bool):
        """设置是否启用补帧"""
        self.enable_interpolate = enabled

    def set_output_dir(self, output_dir: str):
        """设置输出目录"""
        self.output_dir = output_dir

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
        self.pending_tasks.append(file_path)

    def remove_task(self, file_path: str):
        """移除任务"""
        if file_path not in self.tasks:
            return

        # 如果正在处理这个任务，先停止
        if self.current_worker and self.current_worker.input_path == file_path:
            self.current_worker.stop()
            self.current_worker = None

        # 从待处理列表移除
        if file_path in self.pending_tasks:
            self.pending_tasks.remove(file_path)

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
        if not self.pending_tasks:
            return

        self.is_processing = True
        self.is_paused = False
        self._process_next()

    def pause_processing(self):
        """暂停处理"""
        self.is_paused = True
        if self.current_worker:
            self.current_worker.stop()

    def _process_next(self):
        """处理下一个任务"""
        if self.is_paused:
            return

        if not self.pending_tasks:
            self.is_processing = False
            self.all_finished.emit()
            return

        # 获取下一个任务
        file_path = self.pending_tasks[0]
        self.set_task_status(file_path, "处理中")

        # 生成输出路径
        if self.output_dir:
            output_path = os.path.join(
                self.output_dir,
                Settings.get_output_path(file_path, self.current_preset)
            )
        else:
            output_path = Settings.get_output_path(file_path, self.current_preset)

        # 创建处理线程
        self.current_worker = VideoWorker(
            input_path=file_path,
            output_path=output_path,
            preset=self.current_preset,
            enable_interpolate=self.enable_interpolate
        )

        # 连接信号
        self.current_worker.progress.connect(
            lambda current, total: self._on_progress(file_path, current, total)
        )
        self.current_worker.status.connect(
            lambda status: self._on_status(file_path, status)
        )
        self.current_worker.frame_progress.connect(
            lambda current, total: self._on_frame_progress(file_path, current, total)
        )
        self.current_worker.finished.connect(
            lambda success, msg: self._on_finished(file_path, success, msg)
        )

        # 启动
        self.task_started.emit(file_path)
        self.current_worker.start()

    def _on_progress(self, file_path: str, current: int, total: int):
        """进度更新"""
        self.update_progress(file_path, int(current / total * 100))

        # 计算总进度
        total_tasks = len(self.tasks)
        completed = total_tasks - len(self.pending_tasks)
        if total > 0:
            total_progress = int((completed + current / total) / total_tasks * 100)
        else:
            total_progress = int(completed / total_tasks * 100)
        self.progress_updated.emit(total_progress, 100)

    def _on_status(self, file_path: str, status: str):
        """状态更新"""
        if self.is_paused:
            self.set_task_status(file_path, "暂停")
        else:
            self.set_task_status(file_path, status)

    def _on_frame_progress(self, file_path: str, current: int, total: int):
        """帧进度更新（用于预览）"""
        pass  # 可以连接到预览组件

    def _on_finished(self, file_path: str, success: bool, message: str):
        """任务完成"""
        if file_path in self.pending_tasks:
            self.pending_tasks.remove(file_path)

        if success:
            self.set_task_status(file_path, "完成")
        else:
            self.set_task_status(file_path, "失败")

        self.task_finished.emit(file_path, success)

        # 清理
        self.current_worker = None

        # 继续下一个
        if not self.is_paused:
            self._process_next()

    def get_pending_tasks(self) -> list:
        """获取待处理任务"""
        return list(self.pending_tasks)

    def is_task_processing(self, file_path: str) -> bool:
        """检查任务是否正在处理"""
        return self.current_worker and self.current_worker.input_path == file_path

    def clear_completed(self):
        """清除已完成的任务"""
        to_remove = []
        for file_path, (item, widget) in self.tasks.items():
            status = widget.lbl_status.text()
            if status in ["完成", "失败"]:
                to_remove.append(file_path)

        for file_path in to_remove:
            self.remove_task(file_path)
