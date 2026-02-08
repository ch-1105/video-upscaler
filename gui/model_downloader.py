"""
模型下载器对话框
支持GUI进度显示和自动下载
"""
import os
import sys
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QPushButton, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject

# 导入下载功能
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.download_models import MODELS, get_models_dir, download_file, check_sha256


class DownloadSignals(QObject):
    """下载信号"""
    progress = pyqtSignal(str, int, int)  # 模型名, 当前MB, 总MB
    status = pyqtSignal(str)  # 状态消息
    finished = pyqtSignal(bool, str)  # 成功/失败, 消息
    model_complete = pyqtSignal(str, bool)  # 模型名, 成功


class ModelDownloaderDialog(QDialog):
    """模型下载对话框"""
    
    def __init__(self, parent=None, auto_download=True):
        super().__init__(parent)
        self.setWindowTitle("下载模型")
        self.setMinimumSize(500, 400)
        self.setModal(True)
        
        self.signals = DownloadSignals()
        self.download_thread = None
        self.is_downloading = False
        self.models_to_download = []
        self.current_model_index = 0
        
        self.setup_ui()
        
        # 连接信号
        self.signals.progress.connect(self.on_progress)
        self.signals.status.connect(self.on_status)
        self.signals.finished.connect(self.on_finished)
        self.signals.model_complete.connect(self.on_model_complete)
        
        # 自动开始下载
        if auto_download:
            self.start_download()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("正在下载AI模型")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 说明
        desc = QLabel(
            "首次使用需要下载超分模型文件（约100MB）\n"
            "这些文件将被保存在本地，供后续使用"
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #666;")
        layout.addWidget(desc)
        
        # 当前模型
        self.model_label = QLabel("准备下载...")
        self.model_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.model_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 日志输出
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.on_cancel)
        btn_layout.addWidget(self.btn_cancel)
        
        self.btn_retry = QPushButton("重试")
        self.btn_retry.clicked.connect(self.start_download)
        self.btn_retry.setVisible(False)
        btn_layout.addWidget(self.btn_retry)
        
        self.btn_close = QPushButton("完成")
        self.btn_close.clicked.connect(self.accept)
        self.btn_close.setVisible(False)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 20px;
            }
        """)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)
    
    def start_download(self):
        """开始下载"""
        # 检查需要下载的模型
        self.models_to_download = self.get_missing_models()
        
        if not self.models_to_download:
            self.signals.finished.emit(True, "所有模型已存在")
            return
        
        self.current_model_index = 0
        self.is_downloading = True
        self.btn_retry.setVisible(False)
        self.btn_close.setVisible(False)
        self.log_text.clear()
        
        # 启动下载线程
        self.download_thread = threading.Thread(target=self.download_worker)
        self.download_thread.daemon = True
        self.download_thread.start()
    
    def get_missing_models(self):
        """获取需要下载的模型列表"""
        models_dir = get_models_dir()
        missing = []
        
        for name, info in MODELS.items():
            dest_path = models_dir / info["filename"]
            if not dest_path.exists():
                missing.append(name)
            elif info["hash"] and not check_sha256(str(dest_path), info["hash"]):
                self.log_text.append(f"模型 {name} 校验失败，将重新下载")
                missing.append(name)
        
        return missing
    
    def download_worker(self):
        """下载工作线程"""
        models_dir = get_models_dir()
        os.makedirs(models_dir, exist_ok=True)
        
        total_models = len(self.models_to_download)
        success_count = 0
        
        for i, name in enumerate(self.models_to_download):
            if not self.is_downloading:
                break
            
            self.current_model_index = i
            info = MODELS[name]
            dest_path = models_dir / info["filename"]
            
            self.signals.status.emit(f"正在下载 {name} ({i+1}/{total_models})...")
            
            try:
                # 使用带进度回调的下载
                self.download_with_progress(info["url"], str(dest_path), name, info["size_mb"])
                
                # 验证
                if info["hash"] and not check_sha256(str(dest_path), info["hash"]):
                    raise Exception("文件校验失败")
                
                self.signals.model_complete.emit(name, True)
                success_count += 1
                
            except Exception as e:
                self.signals.model_complete.emit(name, False)
                self.signals.status.emit(f"下载 {name} 失败: {e}")
                if dest_path.exists():
                    os.remove(dest_path)
        
        # 完成
        if success_count == total_models:
            self.signals.finished.emit(True, f"成功下载 {success_count} 个模型")
        else:
            self.signals.finished.emit(False, f"成功 {success_count}/{total_models} 个模型")
    
    def download_with_progress(self, url, dest, name, total_mb):
        """带进度回调的下载"""
        import urllib.request
        
        class ProgressCallback:
            def __init__(self, dialog, total):
                self.dialog = dialog
                self.total = total
                self.last_percent = -1
            
            def __call__(self, block_num, block_size, total_size):
                downloaded = block_num * block_size / 1024 / 1024
                percent = int(downloaded / self.total * 100) if self.total > 0 else 0
                if percent != self.last_percent:
                    self.dialog.signals.progress.emit(name, int(downloaded), self.total)
                    self.last_percent = percent
        
        urllib.request.urlretrieve(url, dest, ProgressCallback(self, total_mb))
    
    def on_progress(self, name, current_mb, total_mb):
        """更新进度"""
        self.model_label.setText(f"下载 {name} ({self.current_model_index+1}/{len(self.models_to_download)})")
        percent = int(current_mb / total_mb * 100) if total_mb > 0 else 0
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{current_mb}MB / {total_mb}MB ({percent}%)")
    
    def on_status(self, message):
        """更新状态"""
        self.log_text.append(message)
    
    def on_model_complete(self, name, success):
        """单个模型完成"""
        if success:
            self.log_text.append(f"✓ {name} 下载完成")
        else:
            self.log_text.append(f"✗ {name} 下载失败")
    
    def on_finished(self, success, message):
        """全部完成"""
        self.is_downloading = False
        self.model_label.setText(message)
        self.progress_bar.setValue(100 if success else 0)
        
        if success:
            self.btn_cancel.setVisible(False)
            self.btn_close.setVisible(True)
            self.btn_retry.setVisible(False)
        else:
            self.btn_retry.setVisible(True)
            QMessageBox.warning(self, "下载失败", message)
    
    def on_cancel(self):
        """取消下载"""
        self.is_downloading = False
        self.reject()
    
    @staticmethod
    def check_and_download(parent=None, silent=False):
        """检查并下载模型（静态方法）"""
        models_dir = get_models_dir()
        missing = []
        
        for name, info in MODELS.items():
            dest_path = models_dir / info["filename"]
            if not dest_path.exists():
                missing.append(name)
        
        if not missing:
            return True
        
        if silent:
            # 静默模式，直接返回False
            return False
        
        # 显示下载对话框
        dialog = ModelDownloaderDialog(parent, auto_download=True)
        return dialog.exec() == QDialog.DialogCode.Accepted


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    result = ModelDownloaderDialog.check_and_download()
    print(f"Download result: {result}")
    sys.exit(0 if result else 1)
