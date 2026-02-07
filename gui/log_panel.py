"""
日志显示面板
提供实时日志输出、日志级别区分、错误提示功能
"""

import logging
import sys
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QComboBox, QLabel, QFrame, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QTextCursor, QColor, QFont, QTextCharFormat


class LogLevel:
    """日志级别定义"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    
    COLORS = {
        DEBUG: "#9e9e9e",      # 灰色
        INFO: "#2196f3",       # 蓝色
        WARNING: "#ff9800",    # 橙色
        ERROR: "#f44336",      # 红色
        CRITICAL: "#9c27b0"    # 紫色
    }


class QtLogHandler(logging.Handler):
    """
    自定义日志处理器
    将 Python logging 输出重定向到 Qt 界面
    """
    
    new_log = pyqtSignal(str, str)  # (消息, 级别)
    
    def __init__(self, parent=None):
        super().__init__()
        self.setLevel(logging.DEBUG)
        
    def emit(self, record):
        """处理日志记录"""
        try:
            msg = self.format(record)
            level = record.levelname
            self.new_log.emit(msg, level)
        except Exception:
            self.handleError(record)


class LogPanel(QFrame):
    """
    日志显示面板
    支持实时日志显示、级别筛选、日志导出
    """
    
    log_clicked = pyqtSignal(str, str)  # 点击日志项信号
    
    def __init__(self, parent=None, max_lines: int = 1000):
        super().__init__(parent)
        self.max_lines = max_lines
        self.log_buffer = []  # 日志缓冲区
        self.current_filter = "ALL"  # 当前筛选级别
        self.auto_scroll = True
        
        self.setup_ui()
        self.setup_logger()
    
    def setup_ui(self):
        """设置UI布局"""
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(200)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 标题栏
        title_layout = QHBoxLayout()
        
        title_label = QLabel("📋 处理日志")
        title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 级别筛选下拉框
        filter_label = QLabel("筛选:")
        title_layout.addWidget(filter_label)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "调试", "信息", "警告", "错误", "严重"])
        self.filter_combo.setCurrentIndex(1)  # 默认选择"信息"
        self.filter_combo.currentIndexChanged.connect(self.on_filter_changed)
        title_layout.addWidget(self.filter_combo)
        
        title_layout.addSpacing(10)
        
        # 自动滚动复选框（使用按钮代替）
        self.scroll_btn = QPushButton("⬇ 自动滚动")
        self.scroll_btn.setCheckable(True)
        self.scroll_btn.setChecked(True)
        self.scroll_btn.clicked.connect(self.toggle_auto_scroll)
        title_layout.addWidget(self.scroll_btn)
        
        layout.addLayout(title_layout)
        
        # 日志文本区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.log_text)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        self.clear_btn = QPushButton("🗑 清空")
        self.clear_btn.setToolTip("清空所有日志")
        self.clear_btn.clicked.connect(self.clear_logs)
        toolbar_layout.addWidget(self.clear_btn)
        
        self.export_btn = QPushButton("💾 导出")
        self.export_btn.setToolTip("导出日志到文件")
        self.export_btn.clicked.connect(self.export_logs)
        toolbar_layout.addWidget(self.export_btn)
        
        toolbar_layout.addStretch()
        
        # 日志计数
        self.count_label = QLabel("日志: 0 条")
        toolbar_layout.addWidget(self.count_label)
        
        layout.addLayout(toolbar_layout)
    
    def setup_logger(self):
        """设置日志处理器"""
        self.log_handler = QtLogHandler(self)
        self.log_handler.new_log.connect(self.append_log)
        
        # 设置格式化
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        )
        self.log_handler.setFormatter(formatter)
    
    def append_log(self, message: str, level: str):
        """
        追加日志到显示区域
        
        Args:
            message: 日志消息
            level: 日志级别
        """
        # 保存到缓冲区
        self.log_buffer.append((message, level))
        
        # 检查筛选条件
        if not self.should_show_log(level):
            return
        
        # 获取颜色
        color = LogLevel.COLORS.get(level, "#d4d4d4")
        
        # 移动光标到末尾
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # 设置文本格式
        char_format = QTextCharFormat()
        char_format.setForeground(QColor(color))
        
        # 插入带格式的文本
        cursor.setCharFormat(char_format)
        cursor.insertText(message + "\n")
        
        # 限制行数
        if self.log_text.document().lineCount() > self.max_lines:
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
        
        # 自动滚动
        if self.auto_scroll:
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
        
        # 更新计数
        self.update_count()
    
    def should_show_log(self, level: str) -> bool:
        """检查日志是否应该显示（根据筛选条件）"""
        level_map = {
            "ALL": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "DEBUG": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "INFO": ["INFO", "WARNING", "ERROR", "CRITICAL"],
            "WARNING": ["WARNING", "ERROR", "CRITICAL"],
            "ERROR": ["ERROR", "CRITICAL"],
            "CRITICAL": ["CRITICAL"]
        }
        
        filter_levels = level_map.get(self.current_filter, level_map["ALL"])
        return level in filter_levels
    
    def on_filter_changed(self, index: int):
        """筛选条件改变"""
        filter_map = {
            0: "ALL",    # 全部
            1: "INFO",   # 信息
            2: "WARNING", # 警告
            3: "ERROR",   # 错误
            4: "CRITICAL" # 严重
        }
        self.current_filter = filter_map.get(index, "ALL")
        self.refresh_display()
    
    def refresh_display(self):
        """刷新日志显示（根据筛选条件）"""
        self.log_text.clear()
        
        for message, level in self.log_buffer:
            if self.should_show_log(level):
                color = LogLevel.COLORS.get(level, "#d4d4d4")
                cursor = self.log_text.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                
                char_format = QTextCharFormat()
                char_format.setForeground(QColor(color))
                cursor.setCharFormat(char_format)
                cursor.insertText(message + "\n")
        
        if self.auto_scroll:
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
    
    def toggle_auto_scroll(self):
        """切换自动滚动状态"""
        self.auto_scroll = self.scroll_btn.isChecked()
        self.scroll_btn.setText("⬇ 自动滚动" if self.auto_scroll else "⏸ 暂停滚动")
    
    def clear_logs(self):
        """清空日志"""
        self.log_buffer.clear()
        self.log_text.clear()
        self.update_count()
    
    def export_logs(self):
        """导出日志到文件"""
        from PyQt6.QtWidgets import QFileDialog
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "导出日志",
            f"video_upscaler_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    for message, level in self.log_buffer:
                        f.write(f"{message}\n")
                self.append_log(f"✓ 日志已导出到: {filename}", "INFO")
            except Exception as e:
                self.append_log(f"✗ 导出失败: {e}", "ERROR")
    
    def update_count(self):
        """更新日志计数"""
        visible_count = sum(1 for _, level in self.log_buffer 
                          if self.should_show_log(level))
        total_count = len(self.log_buffer)
        self.count_label.setText(f"日志: {visible_count}/{total_count} 条")
    
    def get_handler(self) -> QtLogHandler:
        """获取日志处理器（用于添加到logger）"""
        return self.log_handler
    
    def log(self, message: str, level: str = "INFO"):
        """手动添加日志"""
        self.append_log(message, level)
    
    def info(self, message: str):
        """添加信息日志"""
        self.log(message, "INFO")
    
    def warning(self, message: str):
        """添加警告日志"""
        self.log(message, "WARNING")
    
    def error(self, message: str):
        """添加错误日志"""
        self.log(message, "ERROR")
    
    def debug(self, message: str):
        """添加调试日志"""
        self.log(message, "DEBUG")


class LogManager:
    """
    日志管理器
    管理全局日志配置
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if LogManager._initialized:
            return
        
        LogManager._initialized = True
        self.logger = logging.getLogger("VideoUpscaler")
        self.logger.setLevel(logging.DEBUG)
        self.handlers = []
    
    def setup_file_logging(self, log_file: str = "video_upscaler.log"):
        """设置文件日志"""
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.handlers.append(file_handler)
    
    def add_gui_handler(self, gui_handler: QtLogHandler):
        """添加GUI日志处理器"""
        self.logger.addHandler(gui_handler)
        self.handlers.append(gui_handler)
    
    def get_logger(self) -> logging.Logger:
        """获取日志器"""
        return self.logger
    
    def info(self, message: str):
        """记录信息"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """记录警告"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """记录错误"""
        self.logger.error(message)
    
    def debug(self, message: str):
        """记录调试"""
        self.logger.debug(message)


# 全局日志管理器实例
log_manager = LogManager()


def get_logger() -> logging.Logger:
    """获取全局日志器"""
    return log_manager.get_logger()


if __name__ == "__main__":
    import sys
    import random
    import time
    
    app = QApplication(sys.argv)
    
    # 创建日志面板
    panel = LogPanel()
    panel.setWindowTitle("日志面板测试")
    panel.resize(800, 500)
    
    # 添加GUI处理器到日志管理器
    log_manager.add_gui_handler(panel.get_handler())
    log_manager.setup_file_logging()
    
    panel.show()
    
    # 测试日志输出
    levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    messages = [
        "开始处理视频",
        "提取帧序列",
        "应用超分模型",
        "编码输出视频",
        "处理完成",
        "检测到CUDA可用",
        "显存使用: 3.2GB/6GB",
        "FFmpeg命令执行成功",
        "警告: 显存紧张",
        "错误: 文件不存在"
    ]
    
    def add_test_log():
        level = random.choice(levels)
        message = random.choice(messages)
        log_manager.get_logger().log(
            getattr(logging, level),
            f"[{level}] {message} #{random.randint(1, 100)}"
        )
    
    # 定时器模拟实时日志
    timer = QTimer(panel)
    timer.timeout.connect(add_test_log)
    timer.start(500)  # 每500ms添加一条日志
    
    # 手动添加一些初始日志
    log_manager.info("=" * 50)
    log_manager.info("视频超分工具已启动")
    log_manager.info("版本: 0.2.0")
    log_manager.info("=" * 50)
    
    sys.exit(app.exec())
