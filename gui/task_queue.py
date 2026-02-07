"""
任务队列组件
提供批量任务管理、暂停/继续/取消、错误处理功能
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass, asdict

from PyQt6.QtWidgets import (
    QListWidget, QListWidgetItem, QWidget,
    QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QMessageBox, QFileDialog, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread

from core.video_worker import VideoWorker
from config.settings import Settings
from config.presets import PresetLevel

logger = logging.getLogger(__name__)


@dataclass
class TaskInfo:
    """任务信息数据类"""
    file_path: str
    status: str = "等待中"  # 等待中/处理中/暂停/完成/失败
    progress: int = 0
    error_message: str = ""
    output_path: str = ""
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    preset: str = "standard"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TaskInfo':
        """从字典创建"""
        return cls(**data)


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
    """
    增强版任务队列列表
    支持批量导入、暂停/继续、状态持久化、错误处理
    """

    task_started = pyqtSignal(str)           # file_path
    task_finished = pyqtSignal(str, bool, str) # file_path, success, message
    all_finished = pyqtSignal()               # 所有任务完成
    progress_updated = pyqtSignal(int, int)     # current, total 总进度
    status_changed = pyqtSignal(str, str)      # file_path, status
    error_occurred = pyqtSignal(str, str)      # file_path, error_message

    def __init__(self, parent=None, state_file: str = "task_queue_state.json"):
        super().__init__(parent)
        self.tasks: Dict[str, tuple] = {}              # file_path -> (item, widget, info)
        self.pending_tasks: List[str] = []            # 待处理任务列表
        self.failed_tasks: List[str] = []              # 失败任务列表
        self.completed_tasks: List[str] = []           # 已完成任务列表
        self.current_worker: Optional[VideoWorker] = None
        self.is_processing = False
        self.is_paused = False
        self.current_preset = "standard"
        self.current_preset_level = PresetLevel.STANDARD
        self.enable_interpolate = False
        self.output_dir = None
        self.state_file = state_file
        self.error_handler: Optional[Callable] = None
        
        # 统计信息
        self.stats = {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "processing": 0,
            "pending": 0
        }

        self.setup_ui()
        self.setup_context_menu()
        self.load_state()

    def setup_ui(self):
        """设置UI样式"""
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
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def setup_context_menu(self):
        """设置右键菜单"""
        self.context_menu = QMenu(self)
        
        self.action_remove = self.context_menu.addAction("🗑 移除任务")
        self.action_remove.triggered.connect(self.remove_selected_task)
        
        self.action_retry = self.context_menu.addAction("🔄 重试")
        self.action_retry.triggered.connect(self.retry_selected_task)
        
        self.context_menu.addSeparator()
        
        self.action_clear_completed = self.context_menu.addAction("✨ 清除已完成")
        self.action_clear_completed.triggered.connect(self.clear_completed)
        
        self.action_clear_all = self.context_menu.addAction("🗑 清除所有")
        self.action_clear_all.triggered.connect(self.clear_all_tasks)
    
    def show_context_menu(self, position):
        """显示右键菜单"""
        if self.currentItem():
            self.context_menu.exec(self.mapToGlobal(position))
    
    def remove_selected_task(self):
        """移除选中的任务"""
        current = self.currentItem()
        if current:
            for file_path, (item, widget, info) in self.tasks.items():
                if item == current:
                    self.remove_task(file_path)
                    break
    
    def retry_selected_task(self):
        """重试选中的失败任务"""
        current = self.currentItem()
        if current:
            for file_path, (item, widget, info) in self.tasks.items():
                if item == current and info.status == "失败":
                    info.status = "等待中"
                    info.progress = 0
                    info.error_message = ""
                    widget.set_status("等待中")
                    widget.set_progress(0)
                    if file_path not in self.pending_tasks:
                        self.pending_tasks.append(file_path)
                    if file_path in self.failed_tasks:
                        self.failed_tasks.remove(file_path)
                    self.update_stats()
                    break
    
    def load_state(self):
        """加载队列状态"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                
                # 恢复任务
                for task_data in state.get("tasks", []):
                    info = TaskInfo.from_dict(task_data)
                    if os.path.exists(info.file_path) and info.status not in ["完成", "失败"]:
                        self._restore_task(info)
                
                logger.info(f"已恢复 {len(self.pending_tasks)} 个未完成任务")
        except Exception as e:
            logger.warning(f"加载队列状态失败: {e}")
    
    def save_state(self):
        """保存队列状态"""
        try:
            state = {
                "save_time": datetime.now().isoformat(),
                "tasks": [
                    info.to_dict() for _, _, info in self.tasks.values()
                ]
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存队列状态失败: {e}")

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
            logger.warning(f"任务已存在: {file_path}")
            return False
        
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return False
        
        # 获取输出路径
        output_path = self._get_output_path(file_path)
        
        # 创建任务信息
        info = TaskInfo(
            file_path=file_path,
            output_path=output_path,
            preset=self.current_preset
        )
        
        item = QListWidgetItem()
        widget = TaskItemWidget(file_path)
        widget.btn_remove.clicked.connect(lambda: self.remove_task(file_path))

        item.setSizeHint(widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, widget)

        self.tasks[file_path] = (item, widget, info)
        self.pending_tasks.append(file_path)
        self.stats["total"] += 1
        self.stats["pending"] += 1
        
        logger.info(f"添加任务: {os.path.basename(file_path)}")
        return True
    
    def _restore_task(self, info: TaskInfo):
        """恢复任务"""
        if not os.path.exists(info.file_path):
            return
        
        item = QListWidgetItem()
        widget = TaskItemWidget(info.file_path)
        widget.btn_remove.clicked.connect(lambda: self.remove_task(info.file_path))
        widget.set_status(info.status)
        widget.set_progress(info.progress)

        item.setSizeHint(widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, widget)

        self.tasks[info.file_path] = (item, widget, info)
        
        if info.status in ["等待中", "暂停"]:
            self.pending_tasks.append(info.file_path)
            self.stats["pending"] += 1
        elif info.status == "完成":
            self.completed_tasks.append(info.file_path)
            self.stats["completed"] += 1
        elif info.status == "失败":
            self.failed_tasks.append(info.file_path)
            self.stats["failed"] += 1
        
        self.stats["total"] += 1
    
    def _get_output_path(self, input_path: str) -> str:
        """生成输出路径"""
        if self.output_dir:
            return os.path.join(
                self.output_dir,
                Settings.get_output_path(input_path, self.current_preset)
            )
        return Settings.get_output_path(input_path, self.current_preset)
    
    def add_tasks_batch(self, file_paths: List[str]) -> int:
        """批量添加任务"""
        success_count = 0
        for file_path in file_paths:
            if self.add_task(file_path):
                success_count += 1
        
        logger.info(f"批量添加完成: {success_count}/{len(file_paths)} 个任务")
        return success_count
    
    def add_folder(self, folder_path: str, extensions: Optional[List[str]] = None) -> int:
        """
        添加文件夹中的所有视频文件
        
        Args:
            folder_path: 文件夹路径
            extensions: 视频扩展名列表，默认支持常见格式
            
        Returns:
            int: 添加的任务数量
        """
        if extensions is None:
            extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']
        
        extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' 
                     for ext in extensions]
        
        added_count = 0
        folder = Path(folder_path)
        
        if not folder.exists():
            logger.error(f"文件夹不存在: {folder_path}")
            return 0
        
        # 递归查找所有视频文件
        for ext in extensions:
            for video_file in folder.rglob(f"*{ext}"):
                if self.add_task(str(video_file)):
                    added_count += 1
        
        logger.info(f"从文件夹添加 {added_count} 个任务: {folder_path}")
        return added_count
    
    def update_stats(self):
        """更新统计信息"""
        self.stats = {
            "total": len(self.tasks),
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks),
            "processing": 1 if self.is_processing and self.current_worker else 0,
            "pending": len(self.pending_tasks)
        }

    def remove_task(self, file_path: str):
        """移除任务"""
        if file_path not in self.tasks:
            return

        # 如果正在处理这个任务，先停止
        if self.current_worker and self.current_worker.input_path == file_path:
            self.current_worker.stop()
            self.current_worker = None

        # 从各列表移除
        if file_path in self.pending_tasks:
            self.pending_tasks.remove(file_path)
        if file_path in self.failed_tasks:
            self.failed_tasks.remove(file_path)
        if file_path in self.completed_tasks:
            self.completed_tasks.remove(file_path)

        item, _, _ = self.tasks[file_path]
        row = self.row(item)
        self.takeItem(row)
        del self.tasks[file_path]
        
        self.update_stats()
        self.save_state()
    
    def clear_all_tasks(self):
        """清除所有任务"""
        # 停止当前任务
        if self.current_worker:
            self.current_worker.stop()
            self.current_worker = None
        
        self.is_processing = False
        self.pending_tasks.clear()
        self.failed_tasks.clear()
        self.completed_tasks.clear()
        
        # 清空列表
        self.clear()
        self.tasks.clear()
        
        self.stats = {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "processing": 0,
            "pending": 0
        }
        
        self.save_state()
        logger.info("已清除所有任务")

    def update_progress(self, file_path: str, progress: int):
        """更新进度"""
        if file_path in self.tasks:
            _, widget, info = self.tasks[file_path]
            widget.set_progress(progress)
            info.progress = progress
            self.status_changed.emit(file_path, info.status)

    def set_task_status(self, file_path: str, status: str):
        """设置任务状态"""
        if file_path in self.tasks:
            _, widget, info = self.tasks[file_path]
            widget.set_status(status)
            info.status = status
            self.status_changed.emit(file_path, status)

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
        
        # 更新任务信息
        if file_path in self.tasks:
            _, widget, info = self.tasks[file_path]
            info.end_time = datetime.now().isoformat()
            
            if success:
                self.set_task_status(file_path, "完成")
                self.completed_tasks.append(file_path)
                logger.info(f"任务完成: {os.path.basename(file_path)}")
            else:
                self.set_task_status(file_path, "失败")
                info.error_message = message
                self.failed_tasks.append(file_path)
                self.error_occurred.emit(file_path, message)
                logger.error(f"任务失败: {os.path.basename(file_path)} - {message}")
        
        self.task_finished.emit(file_path, success, message)
        self.update_stats()
        self.save_state()

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
        if self.current_worker:
            return self.current_worker.input_path == file_path
        return False

    def clear_completed(self):
        """清除已完成的任务"""
        to_remove = []
        for file_path, (item, widget, info) in self.tasks.items():
            status = widget.lbl_status.text()
            if status in ["完成", "失败"]:
                to_remove.append(file_path)

        for file_path in to_remove:
            self.remove_task(file_path)
        
        logger.info(f"已清除 {len(to_remove)} 个已完成任务")
