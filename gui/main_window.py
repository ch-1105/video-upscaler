"""
主窗口
"""
import os
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QProgressBar,
    QListWidget, QFileDialog, QMessageBox, QGroupBox,
    QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from .task_queue import TaskQueueWidget
from .preview_widget import PreviewWidget


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Upscaler - 视频高清修复")
        self.setMinimumSize(1000, 700)

        self.setup_ui()
        self.setup_styles()
        self.setup_connections()
    
    def setup_ui(self):
        """设置UI"""
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QHBoxLayout(central)
        layout.setSpacing(20)
        
        # 左侧：控制和队列
        left_panel = self.create_left_panel()
        layout.addWidget(left_panel, 2)
        
        # 右侧：预览
        self.preview = PreviewWidget()
        layout.addWidget(self.preview, 3)
    
    def create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(15)
        
        # 拖放区域
        drop_zone = self.create_drop_zone()
        layout.addWidget(drop_zone)
        
        # 预设选择
        preset_group = self.create_preset_group()
        layout.addWidget(preset_group)
        
        # 任务队列
        self.task_queue = TaskQueueWidget()
        layout.addWidget(self.task_queue, 1)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("开始处理")
        self.btn_start.setObjectName("primary")
        self.btn_start.clicked.connect(self.on_start)
        
        self.btn_pause = QPushButton("暂停")
        self.btn_pause.clicked.connect(self.on_pause)
        self.btn_pause.setEnabled(False)
        
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_pause)
        
        layout.addLayout(btn_layout)
        
        # 总进度
        self.total_progress = QProgressBar()
        self.total_progress.setTextVisible(True)
        layout.addWidget(self.total_progress)
        
        return panel
    
    def create_drop_zone(self) -> QGroupBox:
        """创建拖放区域"""
        group = QGroupBox("导入视频")
        layout = QVBoxLayout(group)
        
        self.drop_label = QLabel("拖放视频文件到这里\n或点击选择文件")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setMinimumHeight(100)
        self.drop_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #666;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        self.drop_label.mousePressEvent = lambda e: self.on_select_files()
        
        # 启用拖放
        self.drop_label.setAcceptDrops(True)
        self.drop_label.dragEnterEvent = self.on_drag_enter
        self.drop_label.dropEvent = self.on_drop
        
        layout.addWidget(self.drop_label)
        
        return group
    
    def create_preset_group(self) -> QGroupBox:
        """创建预设选择组"""
        group = QGroupBox("输出设置")
        layout = QVBoxLayout(group)
        
        # 预设档位
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("画质档位:"))
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["流畅 (720p/1080p)", "标准 (1080p60)", "高清 (4K60)"])
        preset_layout.addWidget(self.preset_combo)
        
        layout.addLayout(preset_layout)
        
        # 补帧选项
        self.interpolate_check = QCheckBox("启用补帧 (24fps → 60fps)")
        self.interpolate_check.setChecked(True)
        layout.addWidget(self.interpolate_check)
        
        # 输出目录
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出目录:"))
        
        self.output_path = QLabel("默认: 视频同目录")
        self.output_path.setStyleSheet("color: #666;")
        output_layout.addWidget(self.output_path, 1)
        
        btn_output = QPushButton("选择...")
        btn_output.clicked.connect(self.on_select_output)
        output_layout.addWidget(btn_output)
        
        layout.addLayout(output_layout)
        
        return group
    
    def setup_styles(self):
        """设置样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QPushButton {
                padding: 10px 20px;
                border: 1px solid #ccc;
                border-radius: 6px;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QPushButton#primary {
                background-color: #2196F3;
                color: white;
                border: none;
            }
            QPushButton#primary:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
    
    def on_drag_enter(self, event: QDragEnterEvent):
        """拖放进入"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def on_drop(self, event: QDropEvent):
        """拖放释放"""
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        self.add_videos(files)
    
    def on_select_files(self):
        """选择文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频", "",
            "视频文件 (*.mp4 *.mkv *.avi *.mov *.wmv);;所有文件 (*)"
        )
        if files:
            self.add_videos(files)
    
    def add_videos(self, files: list):
        """添加视频到队列"""
        for f in files:
            self.task_queue.add_task(f)
        self.drop_label.setText(f"已添加 {self.task_queue.count()} 个视频\n点击添加更多")
    
    def setup_connections(self):
        """连接信号"""
        # 队列信号
        self.task_queue.task_started.connect(self.on_task_started)
        self.task_queue.task_finished.connect(self.on_task_finished)
        self.task_queue.all_finished.connect(self.on_all_finished)
        self.task_queue.progress_updated.connect(self.on_progress_updated)

        # 预设改变
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)

        # 补帧选项改变
        self.interpolate_check.stateChanged.connect(self.on_interpolate_changed)

    def on_preset_changed(self, index: int):
        """预设改变"""
        presets = ["流畅", "标准", "高清"]
        if 0 <= index < len(presets):
            self.task_queue.set_preset(presets[index])

    def on_interpolate_changed(self, state: int):
        """补帧选项改变"""
        self.task_queue.set_interpolate(bool(state))

    def on_task_started(self, file_path: str):
        """任务开始"""
        self.preview.set_video(total_frames=100)  # 预估

    def on_task_finished(self, file_path: str, success: bool):
        """任务完成"""
        pass

    def on_all_finished(self):
        """所有任务完成"""
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.total_progress.setValue(100)
        QMessageBox.information(self, "完成", "所有视频处理完成！")

    def on_progress_updated(self, current: int, total: int):
        """总进度更新"""
        self.total_progress.setValue(int(current / total * 100))

    def on_select_output(self):
        """选择输出目录"""
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_path.setText(path)
            self.task_queue.set_output_dir(path)

    def on_start(self):
        """开始处理"""
        if self.task_queue.count() == 0:
            QMessageBox.warning(self, "提示", "请先添加视频文件")
            return

        # 更新设置
        self.on_preset_changed(self.preset_combo.currentIndex())
        self.on_interpolate_changed(self.interpolate_check.checkState().value)

        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.total_progress.setValue(0)
        self.task_queue.start_processing()

    def on_pause(self):
        """暂停"""
        self.task_queue.pause_processing()
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
