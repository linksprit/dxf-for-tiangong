# -*- coding: utf-8 -*-
"""
柜柜DXF转天工DXF - GUI版 v8.0
基于云熙模板，将异形板材DXF转换为六视图展开图
柜柜板件dxf导入天工7.9.2
"""

import sys
import os
import glob
import base64
import tempfile

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox,
                             QGroupBox, QTextEdit, QDoubleSpinBox, QStatusBar, QRadioButton,
                             QButtonGroup)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

# 兼容PyInstaller打包路径
if hasattr(sys, '_MEIPASS'):
    sys.path.insert(0, sys._MEIPASS)

# 导入内置模板
HAS_BUILTIN_TEMPLATE = False
DEFAULT_TEMPLATE_BASE64 = ""
try:
    from template_data import DEFAULT_TEMPLATE_BASE64
    HAS_BUILTIN_TEMPLATE = True
except ImportError:
    pass

# 导入核心转换模块
from dxf_converter_core import convert_single, GAP

VERSION = "8.0.0"


class ConvertWorker(QThread):
    """后台转换线程"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)  # current, total
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, mode, source_path, template_path, output_dir, thickness, source_layer, template_name=None):
        super().__init__()
        self.mode = mode  # 'file' or 'folder'
        self.source_path = source_path
        self.template_path = template_path
        self.template_name = template_name or os.path.basename(template_path)
        self.output_dir = output_dir
        self.thickness = thickness
        self.source_layer = source_layer
    
    def log(self, msg):
        self.log_signal.emit(msg)
    
    def run(self):
        try:
            # 确保输出目录存在
            os.makedirs(self.output_dir, exist_ok=True)
            
            if self.mode == 'file':
                # 单文件转换
                self.log(f"源文件: {os.path.basename(self.source_path)}")
                self.log(f"模板文件: {self.template_name}")
                self.log(f"板材厚度: {self.thickness}mm")
                self.log(f"视图间距: {GAP}mm")
                self.log("")
                
                base_name = os.path.splitext(os.path.basename(self.source_path))[0]
                output_name = base_name + "zh.dxf"
                output_path = os.path.join(self.output_dir, output_name)
                
                self.log("[转换中] 正在处理...")
                success, msg = convert_single(
                    self.source_path, self.template_path, output_path,
                    self.thickness, self.source_layer, base_name
                )
                
                if success:
                    self.log(f"✅ 完成! 输出: {output_name}")
                    self.log(f"   {msg}")
                    self.finished_signal.emit(True, output_path)
                else:
                    self.log(f"❌ {msg}")
                    self.finished_signal.emit(False, msg)
            
            elif self.mode == 'folder':
                # 批量转换
                dxf_files = glob.glob(os.path.join(self.source_path, "*.dxf"))
                # 排除已经是zh结尾的
                dxf_files = [f for f in dxf_files if not os.path.basename(f).endswith("zh.dxf")]
                
                total = len(dxf_files)
                if total == 0:
                    self.log("❌ 未找到DXF文件")
                    self.finished_signal.emit(False, "源文件夹中没有DXF文件")
                    return
                
                # 输出目录：源文件夹同级的 zh+文件夹名
                source_parent = os.path.dirname(self.source_path)
                source_folder_name = os.path.basename(self.source_path)
                batch_output_dir = os.path.join(source_parent, "zh" + source_folder_name)
                os.makedirs(batch_output_dir, exist_ok=True)
                
                self.log(f"找到 {total} 个DXF文件待转换")
                self.log(f"源文件夹: {self.source_path}")
                self.log(f"输出目录: {batch_output_dir}")
                self.log(f"模板文件: {self.template_name}")
                self.log(f"板材厚度: {self.thickness}mm")
                self.log("")
                
                success_count = 0
                fail_count = 0
                
                for idx, dxf_file in enumerate(dxf_files, 1):
                    base_name = os.path.splitext(os.path.basename(dxf_file))[0]
                    output_name = base_name + "zh.dxf"
                    output_path = os.path.join(batch_output_dir, output_name)
                    
                    self.progress_signal.emit(idx, total)
                    self.log(f"[{idx}/{total}] {os.path.basename(dxf_file)} ...",)
                    
                    success, msg = convert_single(
                        dxf_file, self.template_path, output_path,
                        self.thickness, self.source_layer, base_name
                    )
                    
                    if success:
                        success_count += 1
                        self.log(f"    ✅ {output_name}")
                    else:
                        fail_count += 1
                        self.log(f"    ❌ 失败: {msg.split(chr(10))[0]}")
                
                self.log("")
                self.log(f"=" * 50)
                self.log(f"批量转换完成: 成功 {success_count} 个, 失败 {fail_count} 个")
                self.log(f"输出目录: {batch_output_dir}")
                
                if success_count > 0:
                    self.finished_signal.emit(True, f"成功 {success_count} 个，失败 {fail_count} 个\n输出目录: {batch_output_dir}")
                else:
                    self.finished_signal.emit(False, f"全部失败，共 {total} 个文件")
        
        except Exception as e:
            import traceback
            self.log(f"\n❌ 错误: {e}")
            self.log(traceback.format_exc())
            self.finished_signal.emit(False, str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("柜柜DXF转天工DXF")
        self.setMinimumSize(700, 640)
        self.resize(700, 640)
        
        self.worker = None
        self._build_ui()
        self._auto_fill_template()
    
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(18, 15, 18, 15)
        main_layout.setSpacing(12)
        
        # 标题
        title = QLabel("柜柜DXF转天工DXF")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        # 副标题1
        subtitle1 = QLabel("基于云熙模板，将异形板材DXF转换为六视图展开图")
        subtitle1.setStyleSheet("color: #555;")
        subtitle1.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(subtitle1)
        
        # 副标题2
        subtitle2 = QLabel("柜柜板件DXF导入天工7.9.2")
        subtitle2.setStyleSheet("color: #888; font-size: 12px;")
        subtitle2.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(subtitle2)
        
        # 源文件/文件夹选择区
        source_group = QGroupBox(" 1. 选择源文件或源文件夹 ")
        source_layout = QVBoxLayout(source_group)
        
        # 单选按钮
        radio_layout = QHBoxLayout()
        self.radio_file = QRadioButton("单文件")
        self.radio_folder = QRadioButton("文件夹（批量）")
        self.radio_file.setChecked(True)
        radio_layout.addWidget(self.radio_file)
        radio_layout.addWidget(self.radio_folder)
        radio_layout.addStretch()
        source_layout.addLayout(radio_layout)
        
        # 路径输入
        path_layout = QHBoxLayout()
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("选择源DXF文件...")
        path_layout.addWidget(self.source_edit, 1)
        self.btn_browse_source = QPushButton("浏览...")
        self.btn_browse_source.setFixedWidth(80)
        self.btn_browse_source.clicked.connect(self._browse_source)
        path_layout.addWidget(self.btn_browse_source)
        source_layout.addLayout(path_layout)
        
        main_layout.addWidget(source_group)
        
        # 模板文件
        template_group = QGroupBox(" 2. 模板文件（可选，内置默认云熙模板） ")
        template_layout = QHBoxLayout(template_group)
        template_layout.addWidget(QLabel("模板文件:"), 0)
        self.template_edit = QLineEdit()
        self.template_edit.setPlaceholderText("留空使用内置默认模板")
        template_layout.addWidget(self.template_edit, 1)
        btn_template = QPushButton("浏览...")
        btn_template.setFixedWidth(80)
        btn_template.clicked.connect(self._browse_template)
        template_layout.addWidget(btn_template)
        main_layout.addWidget(template_group)
        
        # 导出文件夹
        output_group = QGroupBox(" 3. 导出文件夹 ")
        output_layout = QVBoxLayout(output_group)
        
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("导出到:"), 0)
        self.output_edit = QLineEdit()
        # 默认桌面
        default_desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        self.output_edit.setText(default_desktop)
        output_row.addWidget(self.output_edit, 1)
        btn_output = QPushButton("浏览...")
        btn_output.setFixedWidth(80)
        btn_output.clicked.connect(self._browse_output)
        output_row.addWidget(btn_output)
        output_layout.addLayout(output_row)
        
        self.output_hint = QLabel("提示：单文件模式有效；文件夹模式自动输出到源文件夹同级的「zh+文件夹名」目录")
        self.output_hint.setStyleSheet("color: gray; font-size: 11px;")
        output_layout.addWidget(self.output_hint)
        
        main_layout.addWidget(output_group)
        
        # 参数设置区
        param_group = QGroupBox(" 参数设置 ")
        param_layout = QHBoxLayout(param_group)
        
        param_layout.addWidget(QLabel("主视图图层:"))
        self.layer_edit = QLineEdit("0")
        self.layer_edit.setFixedWidth(60)
        param_layout.addWidget(self.layer_edit)
        
        param_layout.addStretch()
        
        info_label = QLabel("保留所有实体：孔位、拉槽、LWPOLYLINE弧线等")
        info_label.setStyleSheet("color: #2a8; font-size: 11px;")
        param_layout.addWidget(info_label)
        
        main_layout.addWidget(param_group)
        
        # 转换按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.start_btn = QPushButton("开始转换")
        self.start_btn.setMinimumWidth(160)
        self.start_btn.setMinimumHeight(40)
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self.start_btn.setFont(font)
        self.start_btn.clicked.connect(self._start_convert)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)
        
        # 日志区
        log_group = QGroupBox(" 处理日志 ")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_group, 1)
        
        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage(f"就绪  v{VERSION}")
        
        # 连接单选按钮
        self.radio_file.toggled.connect(self._on_mode_changed)
    
    def _auto_fill_template(self):
        """自动填充模板文件路径"""
        exe_dir = os.path.dirname(sys.argv[0]) if hasattr(sys, 'frozen') else os.getcwd()
        candidates = [
            os.path.join(exe_dir, "云熙.dxf"),
            os.path.join(os.getcwd(), "云熙.dxf"),
        ]
        for c in candidates:
            if os.path.exists(c):
                self.template_edit.setText(c)
                break
    
    def _resolve_template(self, template_input):
        """解析模板路径优先级：
        1. 用户手动选择的模板文件
        2. 程序同目录下的 云熙.dxf
        3. 内置默认模板
        """
        # 1. 用户选的
        if template_input and os.path.exists(template_input):
            return template_input, os.path.basename(template_input)
        
        # 2. 同目录的云熙.dxf
        exe_dir = os.path.dirname(sys.argv[0]) if hasattr(sys, 'frozen') else os.getcwd()
        candidates = [
            os.path.join(exe_dir, "云熙.dxf"),
            os.path.join(os.getcwd(), "云熙.dxf"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c, "云熙.dxf"
        
        # 3. 内置默认模板
        if HAS_BUILTIN_TEMPLATE and DEFAULT_TEMPLATE_BASE64:
            try:
                tmp_dir = tempfile.gettempdir()
                tmp_path = os.path.join(tmp_dir, "yungxi_default_template.dxf")
                data = base64.b64decode(DEFAULT_TEMPLATE_BASE64)
                with open(tmp_path, 'wb') as f:
                    f.write(data)
                return tmp_path, "内置默认模板（云熙）"
            except Exception:
                pass
        
        return None, None
    
    def _on_mode_changed(self):
        is_file = self.radio_file.isChecked()
        if is_file:
            self.source_edit.setPlaceholderText("选择源DXF文件...")
            self.output_edit.setEnabled(True)
        else:
            self.source_edit.setPlaceholderText("选择包含DXF文件的文件夹...")
            self.output_edit.setEnabled(False)
    
    def _browse_source(self):
        if self.radio_file.isChecked():
            path, _ = QFileDialog.getOpenFileName(
                self, "选择源DXF文件", "",
                "DXF文件 (*.dxf);;所有文件 (*.*)"
            )
            if path:
                self.source_edit.setText(path)
        else:
            path = QFileDialog.getExistingDirectory(
                self, "选择源文件夹", ""
            )
            if path:
                self.source_edit.setText(path)
    
    def _browse_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择模板DXF文件", "",
            "DXF文件 (*.dxf);;所有文件 (*.*)"
        )
        if path:
            self.template_edit.setText(path)
    
    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择导出文件夹", self.output_edit.text()
        )
        if path:
            self.output_edit.setText(path)
    
    def _log(self, message):
        self.log_text.append(message)
    
    def _progress(self, current, total):
        self.statusBar.showMessage(f"正在转换... {current}/{total}")
    
    def _start_convert(self):
        if self.worker and self.worker.isRunning():
            return
        
        source = self.source_edit.text().strip()
        template_input = self.template_edit.text().strip()
        output_dir = self.output_edit.text().strip()
        
        if not source:
            QMessageBox.warning(self, "提示", "请选择源文件或源文件夹")
            return
        
        is_file_mode = self.radio_file.isChecked()
        
        if is_file_mode:
            if not os.path.exists(source):
                QMessageBox.critical(self, "错误", f"源文件不存在:\n{source}")
                return
            if not source.lower().endswith('.dxf'):
                QMessageBox.warning(self, "提示", "请选择DXF文件")
                return
        else:
            if not os.path.isdir(source):
                QMessageBox.critical(self, "错误", f"源文件夹不存在:\n{source}")
                return
        
        # 解析模板路径
        template_path, template_name = self._resolve_template(template_input)
        if not template_path:
            QMessageBox.critical(
                self, "错误",
                "未找到模板文件！\n\n"
                "请选择模板DXF文件，或将 云熙.dxf 放在程序同目录下。"
            )
            return
        
        if not output_dir:
            QMessageBox.warning(self, "提示", "请设置导出文件夹")
            return
        
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法创建输出目录:\n{e}")
            return
        
        source_layer = self.layer_edit.text().strip() or "0"
        thickness = 18.0  # 固定厚度，从图形尺寸中体现
        
        # 清空日志
        self.log_text.clear()
        
        self.start_btn.setEnabled(False)
        self.start_btn.setText("转换中...")
        self.statusBar.showMessage("正在转换...")
        
        # 启动后台线程
        mode = 'file' if is_file_mode else 'folder'
        self.worker = ConvertWorker(mode, source, template_path, output_dir, thickness, source_layer, template_name)
        self.worker.log_signal.connect(self._log)
        self.worker.progress_signal.connect(self._progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()
    
    def _on_finished(self, success, message):
        self.start_btn.setEnabled(True)
        self.start_btn.setText("开始转换")
        
        if success:
            self.statusBar.showMessage("转换完成")
            QMessageBox.information(self, "完成", f"转换成功！\n\n{message}")
        else:
            self.statusBar.showMessage("转换失败")
            QMessageBox.critical(self, "错误", f"转换失败:\n{message}")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
