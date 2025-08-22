import sys
import os
import csv
import math
import shutil
from datetime import datetime
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont, ImageOps
import exifread
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QFileDialog, QListWidget, QSplitter, 
    QTabWidget, QTextEdit, QAction, QMenuBar, QToolBar, QStatusBar,
    QMessageBox, QInputDialog, QProgressDialog, QColorDialog,
    QComboBox, QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox,
    QCheckBox, QGridLayout, QListWidgetItem, QMenu, QTreeWidget,
    QTreeWidgetItem, QDockWidget, QSlider, QScrollArea, QFrame, 
    QLineEdit, QRadioButton, QButtonGroup, QDialog
)
from PyQt5.QtGui import (
    QPixmap, QImage, QIcon, QPainter, QColor, QTransform, QFont,
    QStandardItemModel, QStandardItem, QCursor, QPixmapCache, QKeySequence
)
from PyQt5.QtCore import Qt, QSize, QPoint, QUrl, QThread, pyqtSignal, QTimer, QDateTime
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog

# 在文件开头添加这个函数来替代 imghdr.what()
def get_image_format(file_path):
    """获取图片格式，替代 imghdr.what()"""
    try:
        with Image.open(file_path) as img:
            return img.format
    except:
        # 如果无法用PIL打开，尝试通过文件扩展名判断
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.jpg', '.jpeg']:
            return 'JPEG'
        elif ext == '.png':
            return 'PNG'
        elif ext == '.bmp':
            return 'BMP'
        elif ext == '.gif':
            return 'GIF'
        elif ext == '.tiff':
            return 'TIFF'
        elif ext == '.webp':
            return 'WEBP'
        else:
            return 'JPEG'  # 默认值
class ThumbnailGenerator(QThread):
    """后台生成缩略图的线程"""
    thumbnail_generated = pyqtSignal(str, QPixmap)  # 路径和缩略图
    finished = pyqtSignal()
    
    def __init__(self, paths):
        super().__init__()
        self.paths = paths
        self.running = True
        
    def run(self):
        for path in self.paths:
            if not self.running:
                break
                
            try:
                # 尝试从缓存读取
                cache_key = f"thumb_{path}"
                cached_pixmap = QPixmapCache.find(cache_key)
                if cached_pixmap and not cached_pixmap.isNull():
                    self.thumbnail_generated.emit(path, cached_pixmap)
                    continue
                
                # 生成新的缩略图
                with Image.open(path) as img:
                    # 计算缩略图尺寸（保持比例）
                    max_size = 120
                    w, h = img.size
                    ratio = min(max_size / w, max_size / h)
                    new_size = (int(w * ratio), int(h * ratio))
                    
                    # 转换为QPixmap
                    img.thumbnail(new_size)
                    if img.mode == 'RGBA':
                        q_image = QImage(img.tobytes(), img.width, img.height, 
                                       img.width * 4, QImage.Format_RGBA8888)
                    else:
                        rgb_img = img.convert('RGB')
                        q_image = QImage(rgb_img.tobytes(), rgb_img.width, rgb_img.height, 
                                       rgb_img.width * 3, QImage.Format_RGB888)
                    
                    pixmap = QPixmap.fromImage(q_image)
                    
                    # 缓存缩略图
                    QPixmapCache.insert(cache_key, pixmap)
                    
                    self.thumbnail_generated.emit(path, pixmap)
            except Exception as e:
                print(f"生成缩略图出错 {path}: {e}")
        
        self.finished.emit()
    
    def stop(self):
        self.running = False
        self.wait()

class BatchProcessor(QThread):
    """批量处理图片的线程"""
    progress_updated = pyqtSignal(int)
    finished = pyqtSignal(bool, str)  # 成功标志和消息
    
    def __init__(self, files, operations, output_dir, overwrite=False):
        super().__init__()
        self.files = files
        self.operations = operations  # 要执行的操作列表
        self.output_dir = output_dir
        self.overwrite = overwrite
        self.running = True
        
    def run(self):
        try:
            total = len(self.files)
            success_count = 0
            
            for i, file_path in enumerate(self.files):
                if not self.running:
                    break
                    
                try:
                    # 处理单个文件
                    self.process_file(file_path)
                    success_count += 1
                except Exception as e:
                    print(f"处理文件 {file_path} 出错: {e}")
                
                # 更新进度
                self.progress_updated.emit(int((i + 1) / total * 100))
            
            if self.running:
                msg = f"批量处理完成: {success_count}/{total} 个文件成功"
                self.finished.emit(True, msg)
            else:
                self.finished.emit(False, "批量处理已取消")
                
        except Exception as e:
            self.finished.emit(False, f"批量处理出错: {str(e)}")
    
    def process_file(self, file_path):
        """处理单个文件"""
        # 获取输出路径
        file_name = os.path.basename(file_path)
        output_path = os.path.join(self.output_dir, file_name)
        
        # 检查是否已存在
        if os.path.exists(output_path) and not self.overwrite:
            # 生成新文件名
            base, ext = os.path.splitext(file_name)
            counter = 1
            while True:
                new_name = f"{base}_{counter}{ext}"
                output_path = os.path.join(self.output_dir, new_name)
                if not os.path.exists(output_path):
                    break
                counter += 1
        
        # 打开原始图片
        with Image.open(file_path) as img:
            processed_img = img.copy()
            
            # 应用所有操作
            for op in self.operations:
                op_type = op["type"]
                
                if op_type == "resize":
                    width = op.get("width", processed_img.width)
                    height = op.get("height", processed_img.height)
                    processed_img = processed_img.resize((width, height), Image.LANCZOS)
                    
                elif op_type == "rotate":
                    angle = op.get("angle", 0)
                    if angle != 0:
                        processed_img = processed_img.rotate(angle, expand=True)
                        
                elif op_type == "convert":
                    format = op.get("format", "JPEG")
                    # 这里只是记录格式，保存时使用
                    
                elif op_type == "brightness":
                    factor = op.get("factor", 1.0)
                    if factor != 1.0:
                        enhancer = ImageEnhance.Brightness(processed_img)
                        processed_img = enhancer.enhance(factor)
                        
                elif op_type == "contrast":
                    factor = op.get("factor", 1.0)
                    if factor != 1.0:
                        enhancer = ImageEnhance.Contrast(processed_img)
                        processed_img = enhancer.enhance(factor)
                        
                elif op_type == "grayscale":
                    if processed_img.mode != 'L':
                        processed_img = processed_img.convert('L')
            
            # 保存处理后的图片
            format = op.get("format", get_image_format(file_path)).upper()
            if format == "JPG":
                format = "JPEG"
                
            processed_img.save(output_path, format)
    
    def stop(self):
        self.running = False
        self.wait()

class CoordinatesExporter(QThread):
    """导出经纬度坐标的线程"""
    progress_updated = pyqtSignal(int)
    finished = pyqtSignal(bool, str)  # 成功标志和消息
    
    def __init__(self, files):
        super().__init__()
        self.files = files
        self.running = True
        
    def run(self):
        try:
            total = len(self.files)
            success_count = 0
            coordinates_data = []
            
            for i, file_path in enumerate(self.files):
                if not self.running:
                    break
                    
                try:
                    # 提取经纬度
                    lat, lon = self.extract_coordinates(file_path)
                    if lat is not None and lon is not None:
                        file_name = os.path.basename(file_path)
                        coordinates_data.append((file_path, file_name, lat, lon))
                        success_count += 1
                except Exception as e:
                    print(f"提取经纬度出错 {file_path}: {e}")
                
                # 更新进度
                self.progress_updated.emit(int((i + 1) / total * 100))
            
            if self.running:
                # 让用户选择保存位置
                save_path, _ = QFileDialog.getSaveFileName(
                    None, "保存坐标数据", 
                    os.path.join(os.path.dirname(self.files[0]), "coordinates.csv"), 
                    "CSV文件 (*.csv);;所有文件 (*)"
                )
                
                if save_path:
                    try:
                        with open(save_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(['文件路径', '文件名', '纬度', '经度', 'Google地图链接'])
                            
                            for file_path, file_name, lat, lon in coordinates_data:
                                map_link = f"https://www.google.com/maps?q={lat},{lon}"
                                writer.writerow([file_path, file_name, lat, lon, map_link])
                        
                        msg = f"成功导出 {success_count}/{total} 张图片的坐标数据"
                        self.finished.emit(True, msg)
                    except Exception as e:
                        self.finished.emit(False, f"保存坐标数据失败: {str(e)}")
                else:
                    self.finished.emit(False, "导出已取消")
            else:
                self.finished.emit(False, "导出已取消")
                
        except Exception as e:
            self.finished.emit(False, f"导出坐标数据出错: {str(e)}")
    
    def extract_coordinates(self, file_path):
        """从图片中提取经纬度"""
        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
                
                # 检查是否有经纬度数据
                if 'GPS GPSLatitude' not in tags or 'GPS GPSLongitude' not in tags:
                    return None, None
                
                # 获取纬度
                lat = tags['GPS GPSLatitude']
                lat_ref = tags.get('GPS GPSLatitudeRef', 'N')
                
                # 获取经度
                lon = tags['GPS GPSLongitude']
                lon_ref = tags.get('GPS GPSLongitudeRef', 'E')
                
                # 解析纬度
                def parse_dms(dms):
                    """解析度分秒值"""
                    d = float(dms.values[0].num) / dms.values[0].den
                    m = float(dms.values[1].num) / dms.values[1].den
                    s = float(dms.values[2].num) / dms.values[2].den
                    return d + m/60 + s/3600
                
                latitude = parse_dms(lat)
                if lat_ref.values[0] == 'S':
                    latitude = -latitude
                    
                # 解析经度
                longitude = parse_dms(lon)
                if lon_ref.values[0] == 'W':
                    longitude = -longitude
                    
                return round(latitude, 6), round(longitude, 6)
            
        except Exception as e:
            print(f"提取经纬度出错 {file_path}: {e}")
            return None, None
    
    def stop(self):
        self.running = False
        self.wait()

class BatchProcessDialog(QDialog):
    """批量处理对话框"""
    def __init__(self, parent, files):
        super().__init__(parent)
        self.setWindowTitle("批量处理图片")
        self.resize(500, 400)
        self.files = files
        self.operations = []
        
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # 操作选择区域
        op_group = QGroupBox("选择操作")
        op_layout = QVBoxLayout()
        
        # 调整大小
        self.resize_check = QCheckBox("调整大小")
        self.resize_check.stateChanged.connect(self.toggle_resize_options)
        resize_box = QWidget()
        resize_layout = QHBoxLayout(resize_box)
        resize_layout.addWidget(QLabel("宽度:"))
        self.resize_width = QSpinBox()
        self.resize_width.setRange(1, 10000)
        self.resize_width.setValue(800)
        resize_layout.addWidget(self.resize_width)
        resize_layout.addWidget(QLabel("高度:"))
        self.resize_height = QSpinBox()
        self.resize_height.setRange(1, 10000)
        self.resize_height.setValue(600)
        resize_layout.addWidget(self.resize_height)
        self.keep_ratio = QCheckBox("保持比例")
        self.keep_ratio.setChecked(True)
        resize_layout.addWidget(self.keep_ratio)
        resize_box.setEnabled(False)
        
        # 旋转
        self.rotate_check = QCheckBox("旋转")
        self.rotate_check.stateChanged.connect(self.toggle_rotate_options)
        rotate_box = QWidget()
        rotate_layout = QHBoxLayout(rotate_box)
        rotate_layout.addWidget(QLabel("角度:"))
        self.rotate_angle = QSpinBox()
        self.rotate_angle.setRange(-360, 360)
        self.rotate_angle.setValue(90)
        rotate_layout.addWidget(self.rotate_angle)
        rotate_box.setEnabled(False)
        
        # 转换格式
        self.convert_check = QCheckBox("转换格式")
        self.convert_check.stateChanged.connect(self.toggle_convert_options)
        convert_box = QWidget()
        convert_layout = QHBoxLayout(convert_box)
        convert_layout.addWidget(QLabel("目标格式:"))
        self.convert_format = QComboBox()
        self.convert_format.addItems(["JPEG", "PNG", "BMP", "TIFF"])
        convert_layout.addWidget(self.convert_format)
        convert_box.setEnabled(False)
        
        # 调整亮度
        self.brightness_check = QCheckBox("调整亮度")
        self.brightness_check.stateChanged.connect(self.toggle_brightness_options)
        brightness_box = QWidget()
        brightness_layout = QHBoxLayout(brightness_box)
        brightness_layout.addWidget(QLabel("亮度:"))
        self.brightness_factor = QDoubleSpinBox()
        self.brightness_factor.setRange(0.1, 3.0)
        self.brightness_factor.setValue(1.0)
        self.brightness_factor.setSingleStep(0.1)
        brightness_layout.addWidget(self.brightness_factor)
        brightness_box.setEnabled(False)
        
        # 调整对比度
        self.contrast_check = QCheckBox("调整对比度")
        self.contrast_check.stateChanged.connect(self.toggle_contrast_options)
        contrast_box = QWidget()
        contrast_layout = QHBoxLayout(contrast_box)
        contrast_layout.addWidget(QLabel("对比度:"))
        self.contrast_factor = QDoubleSpinBox()
        self.contrast_factor.setRange(0.1, 3.0)
        self.contrast_factor.setValue(1.0)
        self.contrast_factor.setSingleStep(0.1)
        contrast_layout.addWidget(self.contrast_factor)
        contrast_box.setEnabled(False)
        
        # 转为黑白
        self.grayscale_check = QCheckBox("转为黑白图片")
        
        # 添加到布局
        op_layout.addWidget(self.resize_check)
        op_layout.addWidget(resize_box)
        op_layout.addWidget(self.rotate_check)
        op_layout.addWidget(rotate_box)
        op_layout.addWidget(self.convert_check)
        op_layout.addWidget(convert_box)
        op_layout.addWidget(self.brightness_check)
        op_layout.addWidget(brightness_box)
        op_layout.addWidget(self.contrast_check)
        op_layout.addWidget(contrast_box)
        op_layout.addWidget(self.grayscale_check)
        op_layout.addStretch()
        
        op_group.setLayout(op_layout)
        layout.addWidget(op_group)
        
        # 输出设置
        output_group = QGroupBox("输出设置")
        output_layout = QFormLayout()
        
        self.output_dir = QLineEdit()
        self.output_dir.setText(os.path.join(os.getcwd(), "processed"))
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_output_dir)
        
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.output_dir)
        dir_layout.addWidget(browse_btn)
        
        self.overwrite = QCheckBox("覆盖已存在的文件")
        self.overwrite.setChecked(False)
        
        output_layout.addRow("输出文件夹:", dir_layout)
        output_layout.addRow(self.overwrite)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        self.process_btn = QPushButton("开始处理")
        self.process_btn.clicked.connect(self.process)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.process_btn)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def toggle_resize_options(self, state):
        self.resize_width.setEnabled(state)
        self.resize_height.setEnabled(state)
        self.keep_ratio.setEnabled(state)
    
    def toggle_rotate_options(self, state):
        self.rotate_angle.setEnabled(state)
    
    def toggle_convert_options(self, state):
        self.convert_format.setEnabled(state)
    
    def toggle_brightness_options(self, state):
        self.brightness_factor.setEnabled(state)
    
    def toggle_contrast_options(self, state):
        self.contrast_factor.setEnabled(state)
    
    def browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出文件夹", os.getcwd())
        if dir_path:
            self.output_dir.setText(dir_path)
    
    def process(self):
        # 收集操作
        self.operations = []
        
        if self.resize_check.isChecked():
            self.operations.append({
                "type": "resize",
                "width": self.resize_width.value(),
                "height": self.resize_height.value()
            })
        
        if self.rotate_check.isChecked():
            self.operations.append({
                "type": "rotate",
                "angle": self.rotate_angle.value()
            })
        
        if self.convert_check.isChecked():
            self.operations.append({
                "type": "convert",
                "format": self.convert_format.currentText()
            })
        
        if self.brightness_check.isChecked():
            self.operations.append({
                "type": "brightness",
                "factor": self.brightness_factor.value()
            })
        
        if self.contrast_check.isChecked():
            self.operations.append({
                "type": "contrast",
                "factor": self.contrast_factor.value()
            })
        
        if self.grayscale_check.isChecked():
            self.operations.append({
                "type": "grayscale"
            })
        
        if not self.operations:
            QMessageBox.warning(self, "警告", "请至少选择一项操作")
            return
        
        # 检查输出目录
        output_dir = self.output_dir.text()
        if not output_dir:
            QMessageBox.warning(self, "警告", "请指定输出文件夹")
            return
            
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法创建输出文件夹: {str(e)}")
                return
        
        # 创建进度对话框
        self.progress_dialog = QProgressDialog("正在处理...", "取消", 0, 100, self)
        self.progress_dialog.setWindowTitle("批量处理")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        
        # 创建并启动处理器
        self.processor = BatchProcessor(
            self.files, 
            self.operations, 
            output_dir,
            self.overwrite.isChecked()
        )
        self.processor.progress_updated.connect(self.progress_dialog.setValue)
        self.processor.finished.connect(self.on_process_finished)
        self.progress_dialog.canceled.connect(self.processor.stop)
        
        self.process_btn.setEnabled(False)
        self.processor.start()
    
    def on_process_finished(self, success, message):
        self.progress_dialog.close()
        self.process_btn.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "完成", message)
            self.accept()
        else:
            QMessageBox.warning(self, "提示", message)

class ImageViewerEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 初始化变量
        self.current_dir = os.path.expanduser("~")
        self.current_image_path = None
        self.original_image = None  # PIL Image对象
        self.edited_image = None   # 编辑后的PIL Image对象
        self.image_history = []    # 用于撤销操作
        self.history_index = -1    # 当前历史位置
        self.EXIF_data = {}        # 存储EXIF信息
        self.thumbnail_thread = None  # 缩略图生成线程
        self.zoom_factor = 1.0     # 缩放因子
        self.thumbnail_view_mode = 0  # 0:列表, 1:网格, 2:详细
        self.image_files = []      # 当前文件夹中的图片文件列表
        self.all_image_files = []  # 所有图片文件（用于搜索）
        self.search_query = ""     # 当前搜索查询
        
        self.initUI()
        
    def initUI(self):
        # 设置窗口
        self.setWindowTitle('疯狂植物人图片查看与编辑软件')
        self.setGeometry(100, 100, 1400, 900)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # 创建主分割器
        main_splitter = QSplitter(Qt.Horizontal)
        
        # 创建左侧面板（文件夹和文件浏览）
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # 文件夹树和文件列表切换
        view_mode_layout = QHBoxLayout()
        self.list_mode_btn = QPushButton("列表视图")
        self.list_mode_btn.setCheckable(True)
        self.list_mode_btn.setChecked(True)
        self.list_mode_btn.clicked.connect(lambda: self.set_thumbnail_view_mode(0))
        
        self.grid_mode_btn = QPushButton("网格视图")
        self.grid_mode_btn.setCheckable(True)
        self.grid_mode_btn.clicked.connect(lambda: self.set_thumbnail_view_mode(1))
        
        self.details_mode_btn = QPushButton("详细视图")
        self.details_mode_btn.setCheckable(True)
        self.details_mode_btn.clicked.connect(lambda: self.set_thumbnail_view_mode(2))
        
        view_mode_group = QButtonGroup()
        view_mode_group.addButton(self.list_mode_btn, 0)
        view_mode_group.addButton(self.grid_mode_btn, 1)
        view_mode_group.addButton(self.details_mode_btn, 2)
        
        view_mode_layout.addWidget(self.list_mode_btn)
        view_mode_layout.addWidget(self.grid_mode_btn)
        view_mode_layout.addWidget(self.details_mode_btn)
        left_layout.addLayout(view_mode_layout)
        
        # 添加搜索框和查找按钮
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索图片或文件夹...")
        self.search_input.textChanged.connect(self.search_images)
        self.search_input.returnPressed.connect(self.search_images)
        
        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self.search_images)
        
        self.clear_search_btn = QPushButton("清除")
        self.clear_search_btn.clicked.connect(self.clear_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)
        search_layout.addWidget(self.clear_search_btn)
        left_layout.addLayout(search_layout)
        
        # 添加文件夹查找按钮
        folder_search_layout = QHBoxLayout()
        
        self.folder_search_input = QLineEdit()
        self.folder_search_input.setPlaceholderText("输入文件夹路径...")
        
        self.browse_folder_btn = QPushButton("浏览...")
        self.browse_folder_btn.clicked.connect(self.browse_folder)
        
        folder_search_layout.addWidget(self.folder_search_input)
        folder_search_layout.addWidget(self.browse_folder_btn)
        left_layout.addLayout(folder_search_layout)
        
        # 文件夹树
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderLabel("文件夹")
        self.folder_tree.itemClicked.connect(self.on_folder_clicked)
        self.populate_folder_tree()
        
        # 文件列表（缩略图视图）
        self.file_scroll_area = QScrollArea()
        self.file_scroll_area.setWidgetResizable(True)
        
        self.file_container = QWidget()
        self.file_container_layout = QVBoxLayout(self.file_container)
        self.file_scroll_area.setWidget(self.file_container)
        
        # 左侧分割器
        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.addWidget(self.folder_tree)
        left_splitter.addWidget(self.file_scroll_area)
        left_splitter.setSizes([200, 600])
        
        left_layout.addWidget(left_splitter)
        left_panel.setMinimumWidth(250)
        left_panel.setMaximumWidth(400)
        
        main_splitter.addWidget(left_panel)
        
        # 右侧主内容区
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 图片导航栏
        nav_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("上一张")
        self.prev_btn.clicked.connect(self.load_previous_image)
        self.next_btn = QPushButton("下一张")
        self.next_btn.clicked.connect(self.load_next_image)
        
        self.image_index_label = QLabel("")
        
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.next_btn)
        nav_layout.addWidget(self.image_index_label)
        nav_layout.addStretch()
        
        # 缩放控制
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("缩放:"))
        
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setMaximumWidth(30)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        
        self.zoom_level = QLabel("100%")
        
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setMaximumWidth(30)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        
        self.zoom_fit_btn = QPushButton("适应窗口")
        self.zoom_fit_btn.clicked.connect(self.zoom_fit)
        
        self.zoom_actual_btn = QPushButton("实际大小")
        self.zoom_actual_btn.clicked.connect(self.zoom_actual)
        
        zoom_layout.addWidget(self.zoom_out_btn)
        zoom_layout.addWidget(self.zoom_level)
        zoom_layout.addWidget(self.zoom_in_btn)
        zoom_layout.addWidget(self.zoom_fit_btn)
        zoom_layout.addWidget(self.zoom_actual_btn)
        
        nav_layout.addLayout(zoom_layout)
        right_layout.addLayout(nav_layout)
        
        # 图片显示区域
        self.image_scroll_area = QScrollArea()
        self.image_scroll_area.setWidgetResizable(True)
        self.image_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.image_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.image_container = QWidget()
        self.image_label = QLabel('请打开一张图片')
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(600, 400)  # 增加最小尺寸
        self.image_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        
        container_layout = QVBoxLayout(self.image_container)
        container_layout.addWidget(self.image_label, alignment=Qt.AlignCenter)
        self.image_scroll_area.setWidget(self.image_container)
        
        # 标签页控件
        self.tabs = QTabWidget()
        self.tabs.setMinimumHeight(200)  # 设置标签页最小高度
        
        # 信息标签页
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.tabs.addTab(self.info_text, "图片信息")
        
        # 编辑标签页
        self.edit_panel = self.create_edit_panel()
        self.tabs.addTab(self.edit_panel, "图片编辑")
        
        # EXIF标签页
        self.exif_text = QTextEdit()
        self.exif_text.setReadOnly(True)
        self.tabs.addTab(self.exif_text, "EXIF信息")
        
        # 元数据标签页
        self.metadata_tree = QTreeWidget()
        self.metadata_tree.setHeaderLabel("元数据")
        self.tabs.addTab(self.metadata_tree, "元数据")
        
        # 创建垂直分割器，允许用户调整图片预览和标签页的大小
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(self.image_scroll_area)
        right_splitter.addWidget(self.tabs)
        right_splitter.setSizes([600, 300])  # 初始比例：图片区域占2/3，标签页占1/3
        
        # 设置分割器手柄样式
        right_splitter.setHandleWidth(6)
        right_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #cccccc;
                height: 6px;
            }
            QSplitter::handle:hover {
                background: #aaaaaa;
            }
        """)
        
        right_layout.addWidget(right_splitter, 1)  # 添加分割器到布局，并设置拉伸因子为1
        
        main_splitter.addWidget(right_panel)
        
        # 设置分割器比例，使右侧面板占据更多空间
        main_splitter.setSizes([300, 1100])
        main_layout.addWidget(main_splitter)
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建工具栏
        self.create_tool_bar()
        
        # 创建状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        # 添加底部状态栏信息
        self.file_info_label = QLabel("")
        self.statusBar.addPermanentWidget(self.file_info_label)
        
        # 初始化快捷键
        self.init_shortcuts()
    
    def init_shortcuts(self):
        """初始化快捷键"""
        # 方向键导航图片
        self.image_label.setFocusPolicy(Qt.StrongFocus)
        
    def set_thumbnail_view_mode(self, mode):
        """设置缩略图视图模式"""
        self.thumbnail_view_mode = mode
        # 刷新文件列表
        current_folder = self.get_current_folder()
        if current_folder and os.path.isdir(current_folder):
            self.load_folder_images(current_folder)
    
    def get_current_folder(self):
        """获取当前选中的文件夹"""
        selected_items = self.folder_tree.selectedItems()
        if selected_items:
            return selected_items[0].data(0, Qt.UserRole)
        return None
    
    def populate_folder_tree(self):
        """填充文件夹树"""
        # 清空现有内容
        self.folder_tree.clear()
        
        # 添加计算机根目录
        computer_item = QTreeWidgetItem(["计算机"])
        computer_item.setData(0, Qt.UserRole, "")
        self.folder_tree.addTopLevelItem(computer_item)
        
        # 添加常用目录
        favorite_item = QTreeWidgetItem(["常用文件夹"])
        self.folder_tree.addTopLevelItem(favorite_item)
        
        # 添加桌面
        desktop_path = os.path.expanduser("~/Desktop")
        if os.path.exists(desktop_path):
            desktop_item = QTreeWidgetItem(["桌面"])
            desktop_item.setData(0, Qt.UserRole, desktop_path)
            favorite_item.addChild(desktop_item)
        
        # 添加图片文件夹
        pictures_path = os.path.expanduser("~/Pictures")
        if os.path.exists(pictures_path):
            pictures_item = QTreeWidgetItem(["图片"])
            pictures_item.setData(0, Qt.UserRole, pictures_path)
            favorite_item.addChild(pictures_item)
        
        # 添加磁盘驱动器（Windows）
        if sys.platform.startswith('win'):
            import ctypes
            import string
            from ctypes import wintypes
            
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            
            def get_drives():
                drives = []
                bitmask = kernel32.GetLogicalDrives()
                for letter in string.ascii_uppercase:
                    if bitmask & 1:
                        drives.append(f"{letter}:\\")
                    bitmask >>= 1
                return drives
            
            for drive in get_drives():
                drive_item = QTreeWidgetItem([drive])
                drive_item.setData(0, Qt.UserRole, drive)
                computer_item.addChild(drive_item)
        else:
            # Linux/Mac
            for root in ['/', os.path.expanduser("~")]:
                item = QTreeWidgetItem([root])
                item.setData(0, Qt.UserRole, root)
                computer_item.addChild(item)
        
        # 展开常用文件夹
        favorite_item.setExpanded(True)
    
    def on_folder_clicked(self, item, column):
        """文件夹被点击时加载图片"""
        folder_path = item.data(0, Qt.UserRole)
        if folder_path and os.path.isdir(folder_path):
            self.load_folder_images(folder_path)
    
    def load_folder_images(self, folder_path):
        """加载文件夹中的图片"""
        # 停止当前的缩略图生成线程
        if self.thumbnail_thread and self.thumbnail_thread.isRunning():
            self.thumbnail_thread.stop()
        
        # 清空现有内容
        for i in reversed(range(self.file_container.layout().count())):
            widget = self.file_container.layout().itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 获取文件夹中的图片文件
        image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')
        self.image_files = []
        
        try:
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_path) and file_name.lower().endswith(image_extensions):
                    self.image_files.append(file_path)
            
            # 根据文件名排序
            self.image_files.sort()
            
            # 更新状态
            self.statusBar.showMessage(f"在 {folder_path} 中找到 {len(self.image_files)} 张图片")
            
            # 根据视图模式显示文件
            if self.thumbnail_view_mode == 0:  # 列表视图
                self.show_list_view()
            elif self.thumbnail_view_mode == 1:  # 网格视图
                self.show_grid_view()
            else:  # 详细视图
                self.show_details_view()
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法加载文件夹: {str(e)}")
    
    def show_list_view(self):
        """显示列表视图"""
        # 创建列表
        list_widget = QListWidget()
        list_widget.setViewMode(QListWidget.IconMode)
        list_widget.setIconSize(QSize(80, 80))
        list_widget.setResizeMode(QListWidget.Adjust)
        list_widget.itemDoubleClicked.connect(self.on_list_item_double_clicked)
        
        self.file_container.layout().addWidget(list_widget)
        
        # 启动后台线程生成缩略图
        self.thumbnail_thread = ThumbnailGenerator(self.image_files)
        self.thumbnail_thread.thumbnail_generated.connect(
            lambda path, pixmap: self.add_list_item(list_widget, path, pixmap)
        )
        self.thumbnail_thread.start()
    
    def add_list_item(self, list_widget, path, pixmap):
        """添加列表项"""
        item = QListWidgetItem(QIcon(pixmap), os.path.basename(path))
        item.setData(Qt.UserRole, path)
        list_widget.addItem(item)
        
        # 如果是当前选中的图片，高亮显示
        if path == self.current_image_path:
            item.setSelected(True)
    
    def show_grid_view(self):
        """显示网格视图"""
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        
        # 创建一个容器部件来容纳网格
        grid_widget = QWidget()
        grid_widget.setLayout(grid_layout)
        self.file_container.layout().addWidget(grid_widget)
        
        # 记录位置
        self.grid_positions = {}
        
        # 启动后台线程生成缩略图
        self.thumbnail_thread = ThumbnailGenerator(self.image_files)
        self.thumbnail_thread.thumbnail_generated.connect(
            lambda path, pixmap: self.add_grid_item(grid_layout, path, pixmap)
        )
        self.thumbnail_thread.start()
    
    def add_grid_item(self, grid_layout, path, pixmap):
        """添加网格项"""
        # 找到文件索引
        try:
            index = self.image_files.index(path)
        except ValueError:
            return
            
        # 计算位置（每行4个）
        row = index // 4
        col = index % 4
        
        # 创建缩略图按钮
        btn = QPushButton()
        btn.setIcon(QIcon(pixmap))
        btn.setIconSize(QSize(120, 120))
        btn.setText(os.path.basename(path))
        btn.setToolTip(path)
        btn.setMinimumHeight(150)
        btn.setMaximumWidth(140)
        btn.setStyleSheet("text-align: center; padding: 5px;")
        btn.clicked.connect(lambda checked, p=path: self.load_image(p))
        
        # 如果是当前图片，高亮显示
        if path == self.current_image_path:
            btn.setStyleSheet("background-color: #cce5ff; text-align: center; padding: 5px;")
        
        grid_layout.addWidget(btn, row, col)
        self.grid_positions[path] = (row, col)
    
    def show_details_view(self):
        """显示详细视图"""
        # 创建详细信息树
        details_tree = QTreeWidget()
        details_tree.setColumnCount(4)
        details_tree.setHeaderLabels(["文件名", "尺寸", "修改日期", "大小"])
        details_tree.setSortingEnabled(True)
        details_tree.itemDoubleClicked.connect(self.on_details_item_double_clicked)
        
        self.file_container.layout().addWidget(details_tree)
        
        # 先添加所有项目（占位）
        self.details_items = {}
        for path in self.image_files:
            item = QTreeWidgetItem([
                os.path.basename(path),
                "",  # 尺寸稍后填充
                "",  # 日期稍后填充
                ""   # 大小稍后填充
            ])
            item.setData(0, Qt.UserRole, path)
            details_tree.addTopLevelItem(item)
            self.details_items[path] = item
            
            # 获取基本文件信息
            try:
                # 文件大小
                file_size = os.path.getsize(path)
                if file_size < 1024:
                    size_str = f"{file_size} B"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size / 1024:.1f} KB"
                else:
                    size_str = f"{file_size / (1024 * 1024):.1f} MB"
                item.setText(3, size_str)
                
                # 修改日期
                mtime = os.path.getmtime(path)
                date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                item.setText(2, date_str)
                
            except Exception as e:
                print(f"获取文件信息出错 {path}: {e}")
        
        # 启动后台线程生成缩略图和获取图片信息
        self.thumbnail_thread = ThumbnailGenerator(self.image_files)
        self.thumbnail_thread.thumbnail_generated.connect(
            lambda path, pixmap: self.update_details_item(path)
        )
        self.thumbnail_thread.start()
    
    def update_details_item(self, path):
        """更新详细视图项目信息"""
        if path not in self.details_items:
            return
            
        item = self.details_items[path]
        
        try:
            # 获取图片尺寸
            with Image.open(path) as img:
                item.setText(1, f"{img.width} x {img.height}")
                
            # 如果是当前图片，高亮显示
            if path == self.current_image_path:
                for col in range(4):
                    item.setBackground(col, QColor(204, 229, 255))
                
        except Exception as e:
            print(f"更新详细信息出错 {path}: {e}")
    
    def on_list_item_double_clicked(self, item):
        """列表项双击事件"""
        path = item.data(Qt.UserRole)
        if path:
            self.load_image(path)
    
    def on_details_item_double_clicked(self, item, column):
        """详细视图项双击事件"""
        path = item.data(0, Qt.UserRole)
        if path:
            self.load_image(path)
    
    def create_menu_bar(self):
        # 文件菜单
        file_menu = self.menuBar().addMenu('文件')
        
        # 打开图片动作
        open_action = QAction('打开图片', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_image)
        file_menu.addAction(open_action)
        
        # 打开文件夹动作
        open_dir_action = QAction('打开文件夹', self)
        open_dir_action.setShortcut('Ctrl+D')
        open_dir_action.triggered.connect(self.open_directory)
        file_menu.addAction(open_dir_action)
        
        file_menu.addSeparator()
        
        # 保存图片动作
        save_action = QAction('保存图片', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_image)
        file_menu.addAction(save_action)
        
        # 另存为动作
        save_as_action = QAction('另存为', self)
        save_as_action.setShortcut('Ctrl+Shift+S')
        save_as_action.triggered.connect(self.save_image_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        # 导出EXIF动作
        export_exif_action = QAction('导出EXIF信息', self)
        export_exif_action.triggered.connect(self.export_exif_to_csv)
        file_menu.addAction(export_exif_action)
        
        # 导出经纬度坐标
        export_coords_action = QAction('导出经纬度坐标', self)
        export_coords_action.triggered.connect(self.export_coordinates)
        file_menu.addAction(export_coords_action)
        
        # 批量处理
        batch_action = QAction('批量处理', self)
        batch_action.triggered.connect(self.batch_process)
        file_menu.addAction(batch_action)
        
        file_menu.addSeparator()
        
        # 打印动作
        print_action = QAction('打印', self)
        print_action.setShortcut('Ctrl+P')
        print_action.triggered.connect(self.print_image)
        file_menu.addAction(print_action)
        
        file_menu.addSeparator()
        
        # 退出动作
        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = self.menuBar().addMenu('编辑')
        
        # 撤销动作
        undo_action = QAction('撤销', self)
        undo_action.setShortcut('Ctrl+Z')
        undo_action.triggered.connect(self.undo_edit)
        edit_menu.addAction(undo_action)
        
        edit_menu.addSeparator()
        
        # 剪切、复制、粘贴（对于图片文件操作）
        cut_action = QAction('剪切', self)
        cut_action.setShortcut('Ctrl+X')
        cut_action.triggered.connect(self.cut_image)
        edit_menu.addAction(cut_action)
        
        copy_action = QAction('复制', self)
        copy_action.setShortcut('Ctrl+C')
        copy_action.triggered.connect(self.copy_image)
        edit_menu.addAction(copy_action)
        
        paste_action = QAction('粘贴', self)
        paste_action.setShortcut('Ctrl+V')
        paste_action.triggered.connect(self.paste_image)
        edit_menu.addAction(paste_action)
        
        edit_menu.addSeparator()
        
        # 重命名
        rename_action = QAction('重命名', self)
        rename_action.setShortcut('F2')
        rename_action.triggered.connect(self.rename_image)
        edit_menu.addAction(rename_action)
        
        # 删除
        delete_action = QAction('删除', self)
        delete_action.setShortcut('Delete')
        delete_action.triggered.connect(self.delete_image)
        edit_menu.addAction(delete_action)
        
        edit_menu.addSeparator()
        
        # 旋转动作
        rotate_left_action = QAction('向左旋转', self)
        rotate_left_action.setShortcut('Ctrl+L')
        rotate_left_action.triggered.connect(lambda: self.rotate_image(-90))
        edit_menu.addAction(rotate_left_action)
        
        rotate_right_action = QAction('向右旋转', self)
        rotate_right_action.setShortcut('Ctrl+R')
        rotate_right_action.triggered.connect(lambda: self.rotate_image(90))
        edit_menu.addAction(rotate_right_action)
        
        # 查看菜单
        view_menu = self.menuBar().addMenu('查看')
        
        # 视图模式
        list_view_action = QAction('列表视图', self)
        list_view_action.setCheckable(True)
        list_view_action.setChecked(True)
        list_view_action.triggered.connect(lambda: self.set_thumbnail_view_mode(0))
        view_menu.addAction(list_view_action)
        
        grid_view_action = QAction('网格视图', self)
        grid_view_action.setCheckable(True)
        grid_view_action.triggered.connect(lambda: self.set_thumbnail_view_mode(1))
        view_menu.addAction(grid_view_action)
        
        details_view_action = QAction('详细视图', self)
        details_view_action.setCheckable(True)
        details_view_action.triggered.connect(lambda: self.set_thumbnail_view_mode(2))
        view_menu.addAction(details_view_action)
        
        view_menu.addSeparator()
        
        # 全屏
        fullscreen_action = QAction('全屏', self)
        fullscreen_action.setShortcut('F11')
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        # 工具菜单
        tools_menu = self.menuBar().addMenu('工具')
        
        # 批量重命名
        batch_rename_action = QAction('批量重命名', self)
        batch_rename_action.triggered.connect(self.batch_rename)
        tools_menu.addAction(batch_rename_action)
        
        # 批量导出坐标
        batch_export_coords_action = QAction('批量导出经纬度坐标', self)
        batch_export_coords_action.triggered.connect(self.batch_export_coordinates)
        tools_menu.addAction(batch_export_coords_action)
        
        # 幻灯片
        slideshow_action = QAction('幻灯片', self)
        slideshow_action.setShortcut('F5')
        slideshow_action.triggered.connect(self.start_slideshow)
        tools_menu.addAction(slideshow_action)
        
        # 帮助菜单
        help_menu = self.menuBar().addMenu('帮助')
        
        # 关于动作
        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_tool_bar(self):
        toolbar = QToolBar('工具')
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # 打开图片
        open_action = QAction(QIcon.fromTheme('document-open'), '打开图片', self)
        open_action.triggered.connect(self.open_image)
        toolbar.addAction(open_action)
        
        # 保存图片
        save_action = QAction(QIcon.fromTheme('document-save'), '保存图片', self)
        save_action.triggered.connect(self.save_image)
        toolbar.addAction(save_action)
        
        toolbar.addSeparator()
        
        # 旋转
        rotate_left_action = QAction(QIcon.fromTheme('object-rotate-left'), '向左旋转', self)
        rotate_left_action.triggered.connect(lambda: self.rotate_image(-90))
        toolbar.addAction(rotate_left_action)
        
        rotate_right_action = QAction(QIcon.fromTheme('object-rotate-right'), '向右旋转', self)
        rotate_right_action.triggered.connect(lambda: self.rotate_image(90))
        toolbar.addAction(rotate_right_action)
        
        toolbar.addSeparator()
        
        # 翻转
        flip_horizontal_action = QAction('水平翻转', self)
        flip_horizontal_action.triggered.connect(self.flip_image_horizontal)
        toolbar.addAction(flip_horizontal_action)
        
        flip_vertical_action = QAction('垂直翻转', self)
        flip_vertical_action.triggered.connect(self.flip_image_vertical)
        toolbar.addAction(flip_vertical_action)
        
        toolbar.addSeparator()
        
        # 常用编辑
        crop_action = QAction(QIcon.fromTheme('transform-crop'), '裁剪', self)
        crop_action.triggered.connect(self.crop_image)
        toolbar.addAction(crop_action)
        
        resize_action = QAction('调整大小', self)
        resize_action.triggered.connect(self.show_resize_dialog)
        toolbar.addAction(resize_action)
        
        toolbar.addSeparator()
        
        # 幻灯片
        slideshow_action = QAction(QIcon.fromTheme('media-playback-start'), '幻灯片', self)
        slideshow_action.triggered.connect(self.start_slideshow)
        toolbar.addAction(slideshow_action)
        
        # 导出坐标
        export_coords_action = QAction(QIcon.fromTheme('mark-location'), '导出坐标', self)
        export_coords_action.triggered.connect(self.export_coordinates)
        toolbar.addAction(export_coords_action)
    
    def create_edit_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 基本编辑工具
        basic_group = QGroupBox("基本编辑")
        basic_layout = QGridLayout()
        
        # 旋转控制
        rotate_label = QLabel("旋转角度:")
        self.rotate_angle = QSpinBox()
        self.rotate_angle.setRange(-180, 180)
        self.rotate_angle.setValue(0)
        rotate_btn = QPushButton("应用旋转")
        rotate_btn.clicked.connect(lambda: self.rotate_image(self.rotate_angle.value()))
        
        basic_layout.addWidget(rotate_label, 0, 0)
        basic_layout.addWidget(self.rotate_angle, 0, 1)
        basic_layout.addWidget(rotate_btn, 0, 2)
        
        # 缩放控制
        scale_label = QLabel("缩放比例:")
        self.scale_factor = QDoubleSpinBox()
        self.scale_factor.setRange(0.1, 5.0)
        self.scale_factor.setValue(1.0)
        self.scale_factor.setSingleStep(0.1)
        scale_btn = QPushButton("应用缩放")
        scale_btn.clicked.connect(lambda: self.scale_image(self.scale_factor.value()))
        
        basic_layout.addWidget(scale_label, 1, 0)
        basic_layout.addWidget(self.scale_factor, 1, 1)
        basic_layout.addWidget(scale_btn, 1, 2)
        
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)
        
        # 尺寸调整
        resize_group = QGroupBox("调整尺寸")
        resize_layout = QGridLayout()
        
        resize_width_label = QLabel("宽度:")
        self.resize_width = QSpinBox()
        self.resize_width.setRange(1, 10000)
        
        resize_height_label = QLabel("高度:")
        self.resize_height = QSpinBox()
        self.resize_height.setRange(1, 10000)
        
        self.keep_aspect_ratio = QCheckBox("保持比例")
        self.keep_aspect_ratio.setChecked(True)
        self.keep_aspect_ratio.stateChanged.connect(self.update_resize_dimensions)
        
        resize_btn = QPushButton("应用尺寸调整")
        resize_btn.clicked.connect(self.resize_image)
        
        resize_layout.addWidget(resize_width_label, 0, 0)
        resize_layout.addWidget(self.resize_width, 0, 1)
        resize_layout.addWidget(resize_height_label, 1, 0)
        resize_layout.addWidget(self.resize_height, 1, 1)
        resize_layout.addWidget(self.keep_aspect_ratio, 2, 0)
        resize_layout.addWidget(resize_btn, 2, 1)
        
        resize_group.setLayout(resize_layout)
        layout.addWidget(resize_group)
        
        # 色彩调整
        color_group = QGroupBox("色彩调整")
        color_layout = QGridLayout()
        
        # 亮度
        brightness_label = QLabel("亮度:")
        self.brightness_factor = QDoubleSpinBox()
        self.brightness_factor.setRange(0.1, 3.0)
        self.brightness_factor.setValue(1.0)
        self.brightness_factor.setSingleStep(0.1)
        
        # 对比度
        contrast_label = QLabel("对比度:")
        self.contrast_factor = QDoubleSpinBox()
        self.contrast_factor.setRange(0.1, 3.0)
        self.contrast_factor.setValue(1.0)
        self.contrast_factor.setSingleStep(0.1)
        
        # 饱和度
        saturation_label = QLabel("饱和度:")
        self.saturation_factor = QDoubleSpinBox()
        self.saturation_factor.setRange(0.0, 3.0)
        self.saturation_factor.setValue(1.0)
        self.saturation_factor.setSingleStep(0.1)
        
        # 色调
        hue_label = QLabel("色调:")
        self.hue_factor = QDoubleSpinBox()
        self.hue_factor.setRange(-0.5, 0.5)
        self.hue_factor.setValue(0.0)
        self.hue_factor.setSingleStep(0.05)
        
        # 应用按钮
        apply_color_btn = QPushButton("应用色彩调整")
        apply_color_btn.clicked.connect(self.adjust_color)
        
        color_layout.addWidget(brightness_label, 0, 0)
        color_layout.addWidget(self.brightness_factor, 0, 1)
        color_layout.addWidget(contrast_label, 1, 0)
        color_layout.addWidget(self.contrast_factor, 1, 1)
        color_layout.addWidget(saturation_label, 2, 0)
        color_layout.addWidget(self.saturation_factor, 2, 1)
        color_layout.addWidget(hue_label, 3, 0)
        color_layout.addWidget(self.hue_factor, 3, 1)
        color_layout.addWidget(apply_color_btn, 4, 0, 1, 2)
        
        color_group.setLayout(color_layout)
        layout.addWidget(color_group)
        
        # 滤镜效果
        filter_group = QGroupBox("滤镜效果")
        filter_layout = QHBoxLayout()
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["无", "黑白", "模糊", "锐化", "边缘检测", "浮雕", "反色", "怀旧"])
        
        apply_filter_btn = QPushButton("应用滤镜")
        apply_filter_btn.clicked.connect(self.apply_filter)
        
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addWidget(apply_filter_btn)
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        # 其他编辑功能
        other_group = QGroupBox("其他编辑")
        other_layout = QHBoxLayout()
        
        flip_h_btn = QPushButton("水平翻转")
        flip_h_btn.clicked.connect(self.flip_image_horizontal)
        
        flip_v_btn = QPushButton("垂直翻转")
        flip_v_btn.clicked.connect(self.flip_image_vertical)
        
        crop_btn = QPushButton("裁剪图片")
        crop_btn.clicked.connect(self.crop_image)
        
        reset_btn = QPushButton("重置编辑")
        reset_btn.clicked.connect(self.reset_edits)
        
        other_layout.addWidget(flip_h_btn)
        other_layout.addWidget(flip_v_btn)
        other_layout.addWidget(crop_btn)
        other_layout.addWidget(reset_btn)
        other_group.setLayout(other_layout)
        layout.addWidget(other_group)
        
        # 添加文字水印
        watermark_group = QGroupBox("添加水印")
        watermark_layout = QFormLayout()
        
        self.watermark_input = QTextEdit()
        self.watermark_input.setMaximumHeight(60)
        self.watermark_input.setPlaceholderText("输入水印文字")
        
        self.watermark_size = QSpinBox()
        self.watermark_size.setRange(8, 72)
        self.watermark_size.setValue(24)
        
        self.watermark_opacity = QDoubleSpinBox()
        self.watermark_opacity.setRange(0.1, 1.0)
        self.watermark_opacity.setValue(0.5)
        
        self.watermark_color_btn = QPushButton("选择颜色")
        self.watermark_color_btn.clicked.connect(self.choose_watermark_color)
        self.watermark_color = (255, 255, 255)  # 默认白色
        
        self.watermark_position = QComboBox()
        self.watermark_position.addItems(["右下角", "左下角", "右上角", "左上角", "中心"])
        
        add_watermark_btn = QPushButton("添加水印")
        add_watermark_btn.clicked.connect(self.add_watermark)
        
        watermark_layout.addRow("水印文字:", self.watermark_input)
        watermark_layout.addRow("字体大小:", self.watermark_size)
        watermark_layout.addRow("透明度:", self.watermark_opacity)
        watermark_layout.addRow("文字颜色:", self.watermark_color_btn)
        watermark_layout.addRow("位置:", self.watermark_position)
        watermark_layout.addRow(add_watermark_btn)
        
        watermark_group.setLayout(watermark_layout)
        layout.addWidget(watermark_group)
        
        # 填充剩余空间
        layout.addStretch()
        
        return panel
    
    def update_resize_dimensions(self):
        """当宽度或高度变化时，保持比例更新另一个值"""
        if not self.keep_aspect_ratio.isChecked() or self.original_image is None:
            return
            
        # 只在用户输入时更新，避免循环更新
        sender = self.sender()
        if sender == self.resize_width:
            new_width = self.resize_width.value()
            ratio = new_width / self.original_image.width
            new_height = int(self.original_image.height * ratio)
            self.resize_height.setValue(new_height)
        elif sender == self.resize_height:
            new_height = self.resize_height.value()
            ratio = new_height / self.original_image.height
            new_width = int(self.original_image.width * ratio)
            self.resize_width.setValue(new_width)
    
    def show_resize_dialog(self):
        """显示调整大小对话框"""
        if self.original_image is None:
            return
            
        # 设置当前尺寸
        self.resize_width.setValue(self.original_image.width)
        self.resize_height.setValue(self.original_image.height)
        
        # 切换到编辑标签页
        self.tabs.setCurrentIndex(1)
    
    def resize_image(self):
        """调整图片尺寸"""
        if self.edited_image is None:
            return
            
        new_width = self.resize_width.value()
        new_height = self.resize_height.value()
        
        if new_width <= 0 or new_height <= 0:
            QMessageBox.warning(self, "警告", "尺寸必须为正数")
            return
            
        if new_width == self.edited_image.width and new_height == self.edited_image.height:
            return  # 尺寸未变化，无需处理
            
        # 保存当前状态用于撤销
        self.save_history_state()
        
        # 调整尺寸
        self.edited_image = self.edited_image.resize((new_width, new_height), Image.LANCZOS)
        self.update_image_display()
        self.statusBar.showMessage(f"图片尺寸已调整为 {new_width} x {new_height}")
    
    def choose_watermark_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.watermark_color = (color.red(), color.green(), color.blue())
    
    def add_watermark(self):
        if self.edited_image is None:
            return
            
        text = self.watermark_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "警告", "请输入水印文字")
            return
            
        # 保存当前状态用于撤销
        self.save_history_state()
        
        # 创建水印
        watermark_img = self.edited_image.copy()
        draw = ImageDraw.Draw(watermark_img)
        
        # 尝试加载字体，如无法加载则使用默认字体
        try:
            font = ImageFont.truetype("arial.ttf", self.watermark_size.value())
        except:
            try:
                font = ImageFont.load_default()
            except:
                QMessageBox.warning(self, "警告", "无法加载字体，无法添加水印")
                return
        
        # 获取图片尺寸和文字尺寸
        width, height = watermark_img.size
        text_width, text_height = draw.textsize(text, font=font)
        
        # 根据选择的位置计算文字位置
        position = self.watermark_position.currentIndex()
        margin = 10
        
        if position == 0:  # 右下角
            x = width - text_width - margin
            y = height - text_height - margin
        elif position == 1:  # 左下角
            x = margin
            y = height - text_height - margin
        elif position == 2:  # 右上角
            x = width - text_width - margin
            y = margin
        elif position == 3:  # 左上角
            x = margin
            y = margin
        else:  # 中心
            x = (width - text_width) // 2
            y = (height - text_height) // 2
        
        # 添加半透明文字
        alpha = int(self.watermark_opacity.value() * 255)
        if watermark_img.mode in ('RGBA', 'LA'):
            overlay = Image.new('RGBA', watermark_img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)
            draw.text((x, y), text, font=font, fill=(*self.watermark_color, alpha))
            watermark_img = Image.alpha_composite(watermark_img, overlay)
        else:
            # 对于非透明图片，创建一个带有透明度的图层
            watermark_img = watermark_img.convert('RGBA')
            overlay = Image.new('RGBA', watermark_img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)
            draw.text((x, y), text, font=font, fill=(*self.watermark_color, alpha))
            watermark_img = Image.alpha_composite(watermark_img, overlay)
            # 转换回原来的模式
            watermark_img = watermark_img.convert(self.original_image.mode)
        
        self.edited_image = watermark_img
        self.update_image_display()
        self.statusBar.showMessage(f"已添加水印: {text}")
    
    def open_image(self):
        """打开单张图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", self.current_dir, 
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp);;所有文件 (*)"
        )
        
        if file_path:
            self.current_dir = os.path.dirname(file_path)
            self.load_image(file_path)
            
            # 在文件夹树中选中对应的文件夹
            self.select_folder_in_tree(self.current_dir)
    
    def select_folder_in_tree(self, folder_path):
        """在文件夹树中选中指定的文件夹"""
        # 递归查找文件夹项
        def find_folder_item(item, path):
            if item.data(0, Qt.UserRole) == path:
                return item
            for i in range(item.childCount()):
                child = item.child(i)
                result = find_folder_item(child, path)
                if result:
                    return result
            return None
        
        # 从根节点开始查找
        for i in range(self.folder_tree.topLevelItemCount()):
            top_item = self.folder_tree.topLevelItem(i)
            found_item = find_folder_item(top_item, folder_path)
            if found_item:
                self.folder_tree.setCurrentItem(found_item)
                self.folder_tree.scrollToItem(found_item)
                found_item.setExpanded(True)
                return
    def browse_folder(self):
        """浏览并选择文件夹"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹", self.current_dir)
        if folder_path:
            self.folder_search_input.setText(folder_path)
            self.load_folder_images(folder_path)
            self.select_folder_in_tree(folder_path)
    
    def search_images(self):
        """搜索图片"""
        self.search_query = self.search_input.text().strip().lower()
        
        if not self.search_query:
            # 如果没有搜索查询，显示所有图片
            self.image_files = self.all_image_files.copy()
        else:
            # 过滤匹配搜索查询的图片
            self.image_files = [
                path for path in self.all_image_files
                if self.search_query in os.path.basename(path).lower()
            ]
        
        # 更新文件列表显示
        self.update_file_list_view()
    
    def clear_search(self):
        """清除搜索"""
        self.search_input.clear()
        self.search_query = ""
        self.image_files = self.all_image_files.copy()
        self.update_file_list_view()
    
    def load_folder_images(self, folder_path):
        """加载文件夹中的图片"""
        # 停止当前的缩略图生成线程
        if self.thumbnail_thread and self.thumbnail_thread.isRunning():
            self.thumbnail_thread.stop()
        
        # 清空现有内容
        self.clear_file_container()
        
        # 获取文件夹中的图片文件
        image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')
        self.all_image_files = []
        
        try:
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_path) and file_name.lower().endswith(image_extensions):
                    self.all_image_files.append(file_path)
            
            # 根据文件名排序
            self.all_image_files.sort()
            
            # 应用当前搜索查询
            if self.search_query:
                self.image_files = [
                    path for path in self.all_image_files
                    if self.search_query in os.path.basename(path).lower()
                ]
            else:
                self.image_files = self.all_image_files.copy()
            
            # 更新状态
            self.statusBar.showMessage(f"在 {folder_path} 中找到 {len(self.all_image_files)} 张图片")
            
            # 根据视图模式显示文件
            self.update_file_list_view()
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法加载文件夹: {str(e)}")
    
    def clear_file_container(self):
        """清空文件容器内容"""
        # 清空现有内容
        while self.file_container_layout.count():
            child = self.file_container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def update_file_list_view(self):
        """更新文件列表视图"""
        self.clear_file_container()
        
        if self.thumbnail_view_mode == 0:  # 列表视图
            self.show_list_view()
        elif self.thumbnail_view_mode == 1:  # 网格视图
            self.show_grid_view()
        else:  # 详细视图
            self.show_details_view()
    
    def show_list_view(self):
        """显示列表视图"""
        # 创建列表
        list_widget = QListWidget()
        list_widget.setViewMode(QListWidget.IconMode)
        list_widget.setIconSize(QSize(80, 80))
        list_widget.setResizeMode(QListWidget.Adjust)
        list_widget.itemDoubleClicked.connect(self.on_list_item_double_clicked)
        
        self.file_container_layout.addWidget(list_widget)
        
        # 启动后台线程生成缩略图
        self.thumbnail_thread = ThumbnailGenerator(self.image_files)
        self.thumbnail_thread.thumbnail_generated.connect(
            lambda path, pixmap: self.add_list_item(list_widget, path, pixmap)
        )
        self.thumbnail_thread.start()
    
    def show_grid_view(self):
        """显示网格视图"""
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        
        # 创建一个容器部件来容纳网格
        grid_widget = QWidget()
        grid_widget.setLayout(grid_layout)
        self.file_container_layout.addWidget(grid_widget)
        
        # 记录位置
        self.grid_positions = {}
        
        # 启动后台线程生成缩略图
        self.thumbnail_thread = ThumbnailGenerator(self.image_files)
        self.thumbnail_thread.thumbnail_generated.connect(
            lambda path, pixmap: self.add_grid_item(grid_layout, path, pixmap)
        )
        self.thumbnail_thread.start()
    
    def show_details_view(self):
        """显示详细视图"""
        # 创建详细信息树
        details_tree = QTreeWidget()
        details_tree.setColumnCount(4)
        details_tree.setHeaderLabels(["文件名", "尺寸", "修改日期", "大小"])
        details_tree.setSortingEnabled(True)
        details_tree.itemDoubleClicked.connect(self.on_details_item_double_clicked)
        
        self.file_container_layout.addWidget(details_tree)
        
        # 先添加所有项目（占位）
        self.details_items = {}
        for path in self.image_files:
            item = QTreeWidgetItem([
                os.path.basename(path),
                "",  # 尺寸稍后填充
                "",  # 日期稍后填充
                ""   # 大小稍后填充
            ])
            item.setData(0, Qt.UserRole, path)
            details_tree.addTopLevelItem(item)
            self.details_items[path] = item
            
            # 获取基本文件信息
            try:
                # 文件大小
                file_size = os.path.getsize(path)
                if file_size < 1024:
                    size_str = f"{file_size} B"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size / 1024:.1f} KB"
                else:
                    size_str = f"{file_size / (1024 * 1024):.1f} MB"
                item.setText(3, size_str)
                
                # 修改日期
                mtime = os.path.getmtime(path)
                date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                item.setText(2, date_str)
                
            except Exception as e:
                print(f"获取文件信息出错 {path}: {e}")
        
        # 启动后台线程生成缩略图和获取图片信息
        self.thumbnail_thread = ThumbnailGenerator(self.image_files)
        self.thumbnail_thread.thumbnail_generated.connect(
            lambda path, pixmap: self.update_details_item(path)
        )
        self.thumbnail_thread.start()    
    def open_directory(self):
        """打开文件夹并显示图片列表"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择文件夹", self.current_dir)
        
        if dir_path:
            self.current_dir = dir_path
            self.load_folder_images(dir_path)
            self.select_folder_in_tree(dir_path)
    
    def load_image(self, file_path):
        """加载图片并显示"""
        try:
            # 打开图片
            self.original_image = Image.open(file_path)
            self.edited_image = self.original_image.copy()
            
            # 重置历史记录
            self.image_history = []
            self.history_index = -1
            self.save_history_state()
            
            # 更新调整尺寸控件
            self.resize_width.setValue(self.original_image.width)
            self.resize_height.setValue(self.original_image.height)
            
            # 更新显示
            self.current_image_path = file_path
            self.zoom_factor = 1.0
            self.update_image_display()
            self.update_image_info()
            self.extract_exif_data()
            self.populate_metadata_tree()
            
            # 更新导航信息
            self.update_navigation_info()
            
            # 更新状态栏
            file_name = os.path.basename(file_path)
            self.statusBar.showMessage(f"已打开: {file_name}")
            self.file_info_label.setText(f"{self.original_image.width} x {self.original_image.height} px | {self.get_file_size_str(file_path)}")
            
            # 自动调整图片大小以适应窗口
            self.zoom_fit()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开图片: {str(e)}")
            self.statusBar.showMessage("打开图片失败")
    
    def get_file_size_str(self, file_path):
        """获取文件大小的字符串表示"""
        try:
            file_size = os.path.getsize(file_path)
            if file_size < 1024:
                return f"{file_size} B"
            elif file_size < 1024 * 1024:
                return f"{file_size / 1024:.1f} KB"
            else:
                return f"{file_size / (1024 * 1024):.1f} MB"
        except:
            return "未知大小"
    
    def update_navigation_info(self):
        """更新导航信息（上一张/下一张）"""
        if not self.image_files or self.current_image_path not in self.image_files:
            self.image_index_label.setText("")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return
            
        current_index = self.image_files.index(self.current_image_path)
        total = len(self.image_files)
        self.image_index_label.setText(f"{current_index + 1} / {total}")
        
        self.prev_btn.setEnabled(current_index > 0)
        self.next_btn.setEnabled(current_index < total - 1)
    
    def load_previous_image(self):
        """加载上一张图片"""
        if not self.image_files or self.current_image_path not in self.image_files:
            return
            
        current_index = self.image_files.index(self.current_image_path)
        if current_index > 0:
            self.load_image(self.image_files[current_index - 1])
    
    def load_next_image(self):
        """加载下一张图片"""
        if not self.image_files or self.current_image_path not in self.image_files:
            return
            
        current_index = self.image_files.index(self.current_image_path)
        if current_index < len(self.image_files) - 1:
            self.load_image(self.image_files[current_index + 1])
    
    def update_image_display(self):
        """更新图片显示"""
        if self.edited_image is None:
            return
            
        # 将PIL Image转换为QPixmap
        try:
            # 处理不同模式的图像
            if self.edited_image.mode == 'RGBA':
                q_image = QImage(self.edited_image.tobytes(), self.edited_image.width, 
                                self.edited_image.height, self.edited_image.width * 4, 
                                QImage.Format_RGBA8888)
            elif self.edited_image.mode == 'L':  # 灰度图
                q_image = QImage(self.edited_image.tobytes(), self.edited_image.width, 
                                self.edited_image.height, self.edited_image.width, 
                                QImage.Format_Grayscale8)
            else:  # RGB等其他模式
                rgb_image = self.edited_image.convert('RGB')
                q_image = QImage(rgb_image.tobytes(), rgb_image.width, 
                                rgb_image.height, rgb_image.width * 3, 
                                QImage.Format_RGB888)
            
            pixmap = QPixmap.fromImage(q_image)
            
            # 应用缩放
            scaled_pixmap = pixmap.scaled(
                int(pixmap.width() * self.zoom_factor),
                int(pixmap.height() * self.zoom_factor),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            self.image_label.setPixmap(scaled_pixmap)
            self.zoom_level.setText(f"{int(self.zoom_factor * 100)}%")
            
            # 调整容器大小以适应图片
            self.image_container.setMinimumSize(scaled_pixmap.size())
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法显示图片: {str(e)}")
    
    def zoom_in(self):
        """放大图片"""
        if self.edited_image is None:
            return
            
        self.zoom_factor *= 1.2
        if self.zoom_factor > 10.0:  # 最大放大10倍
            self.zoom_factor = 10.0
            
        self.update_image_display()
    
    def zoom_out(self):
        """缩小图片"""
        if self.edited_image is None:
            return
            
        self.zoom_factor /= 1.2
        if self.zoom_factor < 0.1:  # 最小缩小到10%
            self.zoom_factor = 0.1
            
        self.update_image_display()
    
    def zoom_fit(self):
        """调整图片大小以适应窗口"""
        if self.edited_image is None:
            return
            
        # 获取显示区域大小
        view_width = self.image_scroll_area.viewport().width()
        view_height = self.image_scroll_area.viewport().height()
        
        # 计算缩放比例
        img_width, img_height = self.edited_image.size
        ratio = min(view_width / img_width, view_height / img_height)
        
        self.zoom_factor = ratio
        self.update_image_display()
    
    def zoom_actual(self):
        """实际大小显示"""
        if self.edited_image is None:
            return
            
        self.zoom_factor = 1.0
        self.update_image_display()
    
    def toggle_fullscreen(self):
        """切换全屏模式"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
        elif event.key() == Qt.Key_Left:
            self.load_previous_image()
        elif event.key() == Qt.Key_Right:
            self.load_next_image()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            self.zoom_in()
        elif event.key() == Qt.Key_Minus:
            self.zoom_out()
        elif event.key() == Qt.Key_0:
            self.zoom_actual()
        elif hasattr(self, 'slideshow_dialog') and self.slideshow_dialog.isVisible():
            if event.key() == Qt.Key_Escape:
                self.stop_slideshow()
            elif event.key() == Qt.Key_Left:
                self.prev_slide()
            elif event.key() == Qt.Key_Right:
                self.next_slide()
            elif event.key() == Qt.Key_Space:
                self.toggle_play_pause()
            elif event.key() == Qt.Key_P:
                self.toggle_play_pause()
        else:
            super().keyPressEvent(event)
    
    def update_image_info(self):
        """更新图片基本信息"""
        if self.original_image is None:
            self.info_text.clear()
            return
            
        info = f"图片信息:\n\n"
        info += f"文件名: {os.path.basename(self.current_image_path)}\n"
        info += f"路径: {self.current_image_path}\n"
        info += f"格式: {self.original_image.format}\n"
        info += f"尺寸: {self.original_image.width} x {self.original_image.height} 像素\n"
        info += f"模式: {self.original_image.mode}\n"
        
        # 获取文件大小
        try:
            file_size = os.path.getsize(self.current_image_path)
            if file_size < 1024:
                info += f"文件大小: {file_size} 字节\n"
            elif file_size < 1024 * 1024:
                info += f"文件大小: {file_size / 1024:.2f} KB\n"
            else:
                info += f"文件大小: {file_size / (1024 * 1024):.2f} MB\n"
        except:
            pass
        
        # 添加修改时间
        try:
            modify_time = os.path.getmtime(self.current_image_path)
            info += f"修改时间: {datetime.fromtimestamp(modify_time)}\n"
        except:
            pass
        
        # 添加创建时间
        try:
            create_time = os.path.getctime(self.current_image_path)
            info += f"创建时间: {datetime.fromtimestamp(create_time)}\n"
        except:
            pass
        
        # 添加经纬度信息
        latitude, longitude = self.get_coordinates()
        if latitude is not None and longitude is not None:
            info += f"\n经纬度: {latitude}, {longitude}\n"
            info += f"Google地图: https://www.google.com/maps?q={latitude},{longitude}\n"
        
        self.info_text.setText(info)
    
    def extract_exif_data(self):
        """提取并显示EXIF信息"""
        self.EXIF_data = {}
        
        if self.current_image_path is None:
            self.exif_text.clear()
            return
            
        try:
            with open(self.current_image_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
                
                if not tags:
                    self.exif_text.setText("该图片不包含EXIF信息")
                    return
                
                exif_info = "EXIF信息:\n\n"
                
                for tag in tags:
                    tag_name = tag.split(':')[-1]
                    tag_value = str(tags[tag])
                    self.EXIF_data[tag_name] = tag_value
                    exif_info += f"{tag_name}: {tag_value}\n"
                
                # 提取经纬度信息（如果存在）
                latitude, longitude = self.get_coordinates()
                if latitude and longitude:
                    exif_info += f"\n经纬度: {latitude}, {longitude}\n"
                    exif_info += f"Google地图: https://www.google.com/maps?q={latitude},{longitude}\n"
                
                self.exif_text.setText(exif_info)
                
        except Exception as e:
            self.exif_text.setText(f"提取EXIF信息时出错: {str(e)}")
    
    def populate_metadata_tree(self):
        """填充元数据树"""
        self.metadata_tree.clear()
        
        if self.current_image_path is None:
            return
            
        # 文件系统信息
        file_system_item = QTreeWidgetItem(["文件系统信息"])
        
        try:
            # 文件名
            item = QTreeWidgetItem(["文件名", os.path.basename(self.current_image_path)])
            file_system_item.addChild(item)
            
            # 文件路径
            item = QTreeWidgetItem(["路径", self.current_image_path])
            file_system_item.addChild(item)
            
            # 文件大小
            file_size = os.path.getsize(self.current_image_path)
            if file_size < 1024:
                size_str = f"{file_size} 字节"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.2f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.2f} MB"
            item = QTreeWidgetItem(["大小", size_str])
            file_system_item.addChild(item)
            
            # 创建时间
            create_time = os.path.getctime(self.current_image_path)
            item = QTreeWidgetItem(["创建时间", datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M:%S")])
            file_system_item.addChild(item)
            
            # 修改时间
            modify_time = os.path.getmtime(self.current_image_path)
            item = QTreeWidgetItem(["修改时间", datetime.fromtimestamp(modify_time).strftime("%Y-%m-%d %H:%M:%S")])
            file_system_item.addChild(item)
            
        except Exception as e:
            item = QTreeWidgetItem(["错误", str(e)])
            file_system_item.addChild(item)
        
        self.metadata_tree.addTopLevelItem(file_system_item)
        
        # 图片信息
        image_info_item = QTreeWidgetItem(["图片信息"])
        
        if self.original_image:
            item = QTreeWidgetItem(["格式", self.original_image.format])
            image_info_item.addChild(item)
            
            item = QTreeWidgetItem(["尺寸", f"{self.original_image.width} x {self.original_image.height} 像素"])
            image_info_item.addChild(item)
            
            item = QTreeWidgetItem(["色彩模式", self.original_image.mode])
            image_info_item.addChild(item)
        
        self.metadata_tree.addTopLevelItem(image_info_item)
        
        # EXIF信息
        exif_item = QTreeWidgetItem(["EXIF信息"])
        
        if self.EXIF_data:
            for key, value in self.EXIF_data.items():
                item = QTreeWidgetItem([key, value])
                exif_item.addChild(item)
                
            # 经纬度
            latitude, longitude = self.get_coordinates()
            if latitude and longitude:
                item = QTreeWidgetItem(["经纬度", f"{latitude}, {longitude}"])
                exif_item.addChild(item)
                item = QTreeWidgetItem(["Google地图", f"https://www.google.com/maps?q={latitude},{longitude}"])
                exif_item.addChild(item)
        else:
            item = QTreeWidgetItem(["信息", "无EXIF数据"])
            exif_item.addChild(item)
        
        self.metadata_tree.addTopLevelItem(exif_item)
        
        # 展开所有项
        self.metadata_tree.expandAll()
    
    def get_coordinates(self):
        """从EXIF数据中提取经纬度坐标"""
        try:
            # 检查是否有经纬度数据
            if 'GPS GPSLatitude' not in self.EXIF_data or 'GPS GPSLongitude' not in self.EXIF_data:
                return None, None
                
            # 获取纬度
            lat = self.EXIF_data['GPS GPSLatitude']
            lat_ref = self.EXIF_data.get('GPS GPSLatitudeRef', 'N')
            
            # 获取经度
            lon = self.EXIF_data['GPS GPSLongitude']
            lon_ref = self.EXIF_data.get('GPS GPSLongitudeRef', 'E')
            
            # 解析纬度
            def parse_dms(dms_str):
                """解析度分秒字符串"""
                parts = dms_str.strip('[]').split(',')
                d = float(parts[0].split('/')[0]) / float(parts[0].split('/')[1])
                m = float(parts[1].split('/')[0]) / float(parts[1].split('/')[1])
                s = float(parts[2].split('/')[0]) / float(parts[2].split('/')[1])
                return d + m/60 + s/3600
            
            latitude = parse_dms(lat)
            if lat_ref == 'S':
                latitude = -latitude
                
            # 解析经度
            longitude = parse_dms(lon)
            if lon_ref == 'W':
                longitude = -longitude
                
            return round(latitude, 6), round(longitude, 6)
            
        except Exception as e:
            print(f"解析经纬度时出错: {e}")
            return None, None
    
    def export_exif_to_csv(self):
        """将EXIF信息导出为CSV文件"""
        if not self.EXIF_data:
            QMessageBox.information(self, "提示", "没有可导出的EXIF信息")
            return
            
        # 获取保存路径
        default_filename = f"{os.path.splitext(os.path.basename(self.current_image_path))[0]}_exif.csv"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存EXIF信息", 
            os.path.join(self.current_dir, default_filename), 
            "CSV文件 (*.csv);;所有文件 (*)"
        )
        
        if not save_path:
            return
            
        try:
            with open(save_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['属性', '值'])
                
                for key, value in self.EXIF_data.items():
                    writer.writerow([key, value])
                
                # 添加经纬度（如果存在）
                latitude, longitude = self.get_coordinates()
                if latitude and longitude:
                    writer.writerow(['Latitude', latitude])
                    writer.writerow(['Longitude', longitude])
                    writer.writerow(['Google Maps URL', f"https://www.google.com/maps?q={latitude},{longitude}"])
            
            self.statusBar.showMessage(f"EXIF信息已导出到: {save_path}")
            QMessageBox.information(self, "成功", f"EXIF信息已成功导出到:\n{save_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出EXIF信息失败: {str(e)}")
    
    def export_coordinates(self):
        """导出当前图片的经纬度坐标"""
        if self.current_image_path is None:
            QMessageBox.information(self, "提示", "请先打开一张图片")
            return
            
        latitude, longitude = self.get_coordinates()
        if latitude is None or longitude is None:
            QMessageBox.information(self, "提示", "该图片不包含经纬度信息")
            return
            
        # 获取保存路径
        default_filename = f"{os.path.splitext(os.path.basename(self.current_image_path))[0]}_coordinates.csv"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存坐标信息", 
            os.path.join(self.current_dir, default_filename), 
            "CSV文件 (*.csv);;所有文件 (*)"
        )
        
        if not save_path:
            return
            
        try:
            with open(save_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['文件路径', '纬度', '经度', 'Google地图链接'])
                map_link = f"https://www.google.com/maps?q={latitude},{longitude}"
                writer.writerow([self.current_image_path, latitude, longitude, map_link])
            
            self.statusBar.showMessage(f"坐标信息已导出到: {save_path}")
            QMessageBox.information(self, "成功", f"经纬度坐标已成功导出到:\n{save_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出坐标信息失败: {str(e)}")
    
    def batch_export_coordinates(self):
        """批量导出当前文件夹中所有图片的经纬度坐标"""
        if not self.image_files:
            QMessageBox.information(self, "提示", "没有可导出的图片")
            return
            
        # 创建进度对话框
        progress_dialog = QProgressDialog("正在提取坐标...", "取消", 0, 100, self)
        progress_dialog.setWindowTitle("批量导出坐标")
        progress_dialog.setWindowModality(Qt.WindowModal)
        
        # 创建并启动导出器
        self.coordinates_exporter = CoordinatesExporter(self.image_files)
        self.coordinates_exporter.progress_updated.connect(progress_dialog.setValue)
        self.coordinates_exporter.finished.connect(lambda success, msg: self.on_coordinates_exported(success, msg, progress_dialog))
        progress_dialog.canceled.connect(self.coordinates_exporter.stop)
        
        self.coordinates_exporter.start()
    
    def on_coordinates_exported(self, success, message, progress_dialog):
        progress_dialog.close()
        
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.warning(self, "提示", message)
    
    def save_history_state(self):
        """保存当前编辑状态到历史记录"""
        if self.edited_image is None:
            return
            
        # 移除当前位置之后的历史记录
        if self.history_index < len(self.image_history) - 1:
            self.image_history = self.image_history[:self.history_index + 1]
            
        # 保存当前状态
        self.image_history.append(self.edited_image.copy())
        self.history_index = len(self.image_history) - 1
        
        # 限制历史记录长度，防止内存占用过大
        if len(self.image_history) > 20:
            self.image_history.pop(0)
            self.history_index -= 1
    
    def undo_edit(self):
        """撤销上一步编辑"""
        if self.history_index > 0:
            self.history_index -= 1
            self.edited_image = self.image_history[self.history_index].copy()
            self.update_image_display()
            self.statusBar.showMessage("已撤销上一步操作")
        else:
            self.statusBar.showMessage("没有可撤销的操作")
    
    def rotate_image(self, angle):
        """旋转图片"""
        if self.edited_image is None or angle == 0:
            return
            
        # 保存当前状态用于撤销
        self.save_history_state()
        
        # 旋转图片
        self.edited_image = self.edited_image.rotate(angle, expand=True)
        self.update_image_display()
        self.statusBar.showMessage(f"图片已旋转 {angle} 度")
    
    def flip_image_horizontal(self):
        """水平翻转图片"""
        if self.edited_image is None:
            return
            
        # 保存当前状态用于撤销
        self.save_history_state()
        
        # 水平翻转
        self.edited_image = self.edited_image.transpose(Image.FLIP_LEFT_RIGHT)
        self.update_image_display()
        self.statusBar.showMessage("图片已水平翻转")
    
    def flip_image_vertical(self):
        """垂直翻转图片"""
        if self.edited_image is None:
            return
            
        # 保存当前状态用于撤销
        self.save_history_state()
        
        # 垂直翻转
        self.edited_image = self.edited_image.transpose(Image.FLIP_TOP_BOTTOM)
        self.update_image_display()
        self.statusBar.showMessage("图片已垂直翻转")
    
    def scale_image(self, factor):
        """缩放图片"""
        if self.edited_image is None or factor <= 0 or factor == 1.0:
            return
            
        # 保存当前状态用于撤销
        self.save_history_state()
        
        # 计算新尺寸
        new_width = int(self.edited_image.width * factor)
        new_height = int(self.edited_image.height * factor)
        
        # 缩放图片
        self.edited_image = self.edited_image.resize((new_width, new_height), Image.LANCZOS)
        self.update_image_display()
        self.statusBar.showMessage(f"图片已缩放 {factor:.1f} 倍")
    
    def adjust_color(self):
        """调整图片亮度、对比度和饱和度"""
        if self.edited_image is None:
            return
            
        # 保存当前状态用于撤销
        self.save_history_state()
        
        # 调整亮度
        brightness = self.brightness_factor.value()
        if brightness != 1.0:
            enhancer = ImageEnhance.Brightness(self.edited_image)
            self.edited_image = enhancer.enhance(brightness)
        
        # 调整对比度
        contrast = self.contrast_factor.value()
        if contrast != 1.0:
            enhancer = ImageEnhance.Contrast(self.edited_image)
            self.edited_image = enhancer.enhance(contrast)
        
        # 调整饱和度
        saturation = self.saturation_factor.value()
        if saturation != 1.0:
            enhancer = ImageEnhance.Color(self.edited_image)
            self.edited_image = enhancer.enhance(saturation)
        
        # 调整色调
        hue = self.hue_factor.value()
        if hue != 0.0:
            # 转换为HSV颜色空间调整色调
            if self.edited_image.mode != 'RGB':
                rgb_img = self.edited_image.convert('RGB')
            else:
                rgb_img = self.edited_image.copy()
                
            hsv_img = rgb_img.convert('HSV')
            h, s, v = hsv_img.split()
            
            # 调整色调通道
            h_np = np.array(h, dtype=np.uint8)
            h_np = (h_np + int(hue * 255)) % 256
            new_h = Image.fromarray(h_np.astype(np.uint8))
            
            # 合并通道并转换回RGB
            new_hsv = Image.merge('HSV', (new_h, s, v))
            self.edited_image = new_hsv.convert('RGB')
            
            # 如果原图不是RGB模式，转换回去
            if self.original_image.mode != 'RGB':
                self.edited_image = self.edited_image.convert(self.original_image.mode)
        
        self.update_image_display()
        self.statusBar.showMessage("图片色彩已调整")
    
    def apply_filter(self):
        """应用滤镜效果"""
        if self.edited_image is None:
            return
            
        filter_type = self.filter_combo.currentText()
        if filter_type == "无":
            return
            
        # 保存当前状态用于撤销
        self.save_history_state()
        
        if filter_type == "黑白":
            self.edited_image = self.edited_image.convert('L')
        elif filter_type == "模糊":
            self.edited_image = self.edited_image.filter(ImageFilter.BLUR)
        elif filter_type == "锐化":
            self.edited_image = self.edited_image.filter(ImageFilter.SHARPEN)
        elif filter_type == "边缘检测":
            self.edited_image = self.edited_image.filter(ImageFilter.FIND_EDGES)
        elif filter_type == "浮雕":
            self.edited_image = self.edited_image.filter(ImageFilter.EMBOSS)
        elif filter_type == "反色":
            self.edited_image = ImageOps.invert(self.edited_image.convert('RGB')).convert(self.edited_image.mode)
        elif filter_type == "怀旧":
            # 简单的怀旧效果
            if self.edited_image.mode != 'RGB':
                rgb_img = self.edited_image.convert('RGB')
            else:
                rgb_img = self.edited_image.copy()
                
            width, height = rgb_img.size
            pixels = rgb_img.load()
            
            for i in range(width):
                for j in range(height):
                    r, g, b = pixels[i, j]
                    # 怀旧色调算法
                    new_r = int(0.393 * r + 0.769 * g + 0.189 * b)
                    new_g = int(0.349 * r + 0.686 * g + 0.168 * b)
                    new_b = int(0.272 * r + 0.534 * g + 0.131 * b)
                    
                    # 确保值在0-255范围内
                    new_r = min(255, new_r)
                    new_g = min(255, new_g)
                    new_b = min(255, new_b)
                    
                    pixels[i, j] = (new_r, new_g, new_b)
            
            self.edited_image = rgb_img
            # 如果原图不是RGB模式，转换回去
            if self.original_image.mode != 'RGB':
                self.edited_image = self.edited_image.convert(self.original_image.mode)
        
        self.update_image_display()
        self.statusBar.showMessage(f"已应用 {filter_type} 滤镜")
    
    def crop_image(self):
        """裁剪图片"""
        if self.edited_image is None:
            return
            
        # 让用户输入裁剪区域的百分比
        try:
            left, ok1 = QInputDialog.getDouble(self, "裁剪设置", "左侧百分比 (0-100):", 0, 0, 100)
            if not ok1:
                return
                
            top, ok2 = QInputDialog.getDouble(self, "裁剪设置", "顶部百分比 (0-100):", 0, 0, 100)
            if not ok2:
                return
                
            right, ok3 = QInputDialog.getDouble(self, "裁剪设置", "右侧百分比 (0-100):", 100, 0, 100)
            if not ok3 or right <= left:
                return
                
            bottom, ok4 = QInputDialog.getDouble(self, "裁剪设置", "底部百分比 (0-100):", 100, 0, 100)
            if not ok4 or bottom <= top:
                return
                
            # 转换为像素坐标
            width, height = self.edited_image.size
            left_pixel = int(width * left / 100)
            top_pixel = int(height * top / 100)
            right_pixel = int(width * right / 100)
            bottom_pixel = int(height * bottom / 100)
            
            # 保存当前状态用于撤销
            self.save_history_state()
            
            # 裁剪图片
            self.edited_image = self.edited_image.crop((left_pixel, top_pixel, right_pixel, bottom_pixel))
            self.update_image_display()
            self.statusBar.showMessage(f"图片已裁剪，新尺寸: {self.edited_image.width} x {self.edited_image.height}")
            
            # 更新调整尺寸控件
            self.resize_width.setValue(self.edited_image.width)
            self.resize_height.setValue(self.edited_image.height)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"裁剪图片失败: {str(e)}")
    
    def reset_edits(self):
        """重置所有编辑，恢复原始图片"""
        if self.original_image is not None:
            # 保存当前状态用于撤销
            self.save_history_state()
            
            self.edited_image = self.original_image.copy()
            self.update_image_display()
            
            # 更新调整尺寸控件
            self.resize_width.setValue(self.edited_image.width)
            self.resize_height.setValue(self.edited_image.height)
            
            self.statusBar.showMessage("已重置所有编辑")
    
    def save_image(self):
        """保存图片（覆盖原图）"""
        if self.current_image_path is None or self.edited_image is None:
            return
            
        # 询问确认
        reply = QMessageBox.question(
            self, "确认保存", 
            f"确定要覆盖原始图片 '{os.path.basename(self.current_image_path)}' 吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        try:
            # 保存图片，保持原始格式
            self.edited_image.save(self.current_image_path)
            self.statusBar.showMessage(f"图片已保存: {os.path.basename(self.current_image_path)}")
            
            # 更新原始图片引用
            self.original_image = self.edited_image.copy()
            
            # 重置历史记录
            self.image_history = []
            self.history_index = -1
            self.save_history_state()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存图片失败: {str(e)}")
    
    def save_image_as(self):
        """另存为新图片"""
        if self.edited_image is None:
            return
            
        # 获取原始文件格式
        original_ext = os.path.splitext(self.current_image_path)[1].lower() if self.current_image_path else '.png'
        
        # 默认文件名
        default_filename = f"{os.path.splitext(os.path.basename(self.current_image_path))[0]}_edited{original_ext}" if self.current_image_path else "edited_image.png"
        
        # 获取保存路径
        save_path, _ = QFileDialog.getSaveFileName(
            self, "另存为", 
            os.path.join(self.current_dir, default_filename), 
            "PNG图片 (*.png);;JPEG图片 (*.jpg *.jpeg);;BMP图片 (*.bmp);;TIFF图片 (*.tiff);;WebP图片 (*.webp);;所有文件 (*)"
        )
        
        if not save_path:
            return
            
        try:
            # 确定保存格式
            save_ext = os.path.splitext(save_path)[1].lower()
            format = 'PNG'
            if save_ext in ('.jpg', '.jpeg'):
                format = 'JPEG'
            elif save_ext == '.bmp':
                format = 'BMP'
            elif save_ext == '.tiff':
                format = 'TIFF'
            elif save_ext == '.webp':
                format = 'WebP'
            
            # 保存图片
            self.edited_image.save(save_path, format)
            
            # 更新当前路径
            self.current_image_path = save_path
            self.original_image = self.edited_image.copy()
            
            # 重置历史记录
            self.image_history = []
            self.history_index = -1
            self.save_history_state()
            
            # 更新信息
            self.update_image_info()
            self.populate_metadata_tree()
            
            # 刷新文件列表
            current_folder = os.path.dirname(save_path)
            if current_folder == os.path.dirname(self.image_files[0]) if self.image_files else False:
                self.load_folder_images(current_folder)
                
            self.statusBar.showMessage(f"图片已保存: {os.path.basename(save_path)}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存图片失败: {str(e)}")
    
    def print_image(self):
        """打印图片"""
        if self.edited_image is None:
            return
            
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)
        
        if dialog.exec_() == QPrintDialog.Accepted:
            # 将PIL Image转换为QImage
            if self.edited_image.mode == 'RGBA':
                q_image = QImage(self.edited_image.tobytes(), self.edited_image.width, 
                                self.edited_image.height, self.edited_image.width * 4, 
                                QImage.Format_RGBA8888)
            else:
                rgb_image = self.edited_image.convert('RGB')
                q_image = QImage(rgb_image.tobytes(), rgb_image.width, 
                                rgb_image.height, rgb_image.width * 3, 
                                QImage.Format_RGB888)
            
            # 绘制图片到打印机
            painter = QPainter(printer)
            rect = painter.viewport()
            size = q_image.size()
            size.scale(rect.size(), Qt.KeepAspectRatio)
            painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
            painter.setWindow(q_image.rect())
            painter.drawImage(0, 0, q_image)
            painter.end()
            
            self.statusBar.showMessage("图片打印完成")
    
    def cut_image(self):
        """剪切图片文件"""
        if not self.current_image_path:
            return
            
        # 保存到剪贴板
        clipboard = QApplication.clipboard()
        mime_data = QApplication.clipboard().mimeData()
        mime_data.setUrls([QUrl.fromLocalFile(self.current_image_path)])
        mime_data.setText("cut:" + self.current_image_path)  # 标记为剪切操作
        clipboard.setMimeData(mime_data)
        
        self.statusBar.showMessage(f"已剪切: {os.path.basename(self.current_image_path)}")
    
    def copy_image(self):
        """复制图片文件"""
        if not self.current_image_path:
            return
            
        # 保存到剪贴板
        clipboard = QApplication.clipboard()
        mime_data = QApplication.clipboard().mimeData()
        mime_data.setUrls([QUrl.fromLocalFile(self.current_image_path)])
        mime_data.setText("copy:" + self.current_image_path)  # 标记为复制操作
        clipboard.setMimeData(mime_data)
        
        self.statusBar.showMessage(f"已复制: {os.path.basename(self.current_image_path)}")
    
    def paste_image(self):
        """粘贴图片文件"""
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        if not mime_data or not mime_data.hasUrls():
            return
            
        # 获取当前文件夹
        current_folder = self.get_current_folder() or self.current_dir
        
        for url in mime_data.urls():
            if url.isLocalFile():
                source_path = url.toLocalFile()
                
                # 检查是否是图片文件
                if not source_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')):
                    continue
                
                # 确定操作类型（剪切或复制）
                is_cut = False
                if mime_data.hasText() and mime_data.text().startswith("cut:"):
                    is_cut = True
                
                # 目标路径
                file_name = os.path.basename(source_path)
                dest_path = os.path.join(current_folder, file_name)
                
                # 检查文件是否已存在
                counter = 1
                while os.path.exists(dest_path):
                    base, ext = os.path.splitext(file_name)
                    dest_path = os.path.join(current_folder, f"{base}_{counter}{ext}")
                    counter += 1
                
                try:
                    if is_cut:
                        # 剪切（移动）文件
                        shutil.move(source_path, dest_path)
                        self.statusBar.showMessage(f"已移动: {file_name} 到 {current_folder}")
                    else:
                        # 复制文件
                        shutil.copy2(source_path, dest_path)
                        self.statusBar.showMessage(f"已复制: {file_name} 到 {current_folder}")
                        
                    # 刷新文件列表
                    self.load_folder_images(current_folder)
                    
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"操作失败: {str(e)}")
    
    def rename_image(self):
        """重命名图片文件"""
        if not self.current_image_path:
            return
            
        current_name = os.path.basename(self.current_image_path)
        new_name, ok = QInputDialog.getText(self, "重命名", "请输入新文件名:", text=current_name)
        
        if ok and new_name and new_name != current_name:
            # 确保扩展名保持一致
            base, ext = os.path.splitext(current_name)
            new_base, new_ext = os.path.splitext(new_name)
            if not new_ext:
                new_name = new_base + ext
            
            new_path = os.path.join(os.path.dirname(self.current_image_path), new_name)
            
            try:
                os.rename(self.current_image_path, new_path)
                self.current_image_path = new_path
                self.update_image_info()
                self.populate_metadata_tree()
                
                # 刷新文件列表
                current_folder = os.path.dirname(new_path)
                self.load_folder_images(current_folder)
                
                self.statusBar.showMessage(f"已重命名为: {new_name}")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"重命名失败: {str(e)}")
    
    def delete_image(self):
        """删除图片文件"""
        if not self.current_image_path:
            return
            
        file_name = os.path.basename(self.current_image_path)
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除 '{file_name}' 吗？\n此操作无法撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                os.remove(self.current_image_path)
                self.statusBar.showMessage(f"已删除: {file_name}")
                
                # 刷新文件列表
                current_folder = os.path.dirname(self.current_image_path)
                self.load_folder_images(current_folder)
                
                # 清除当前图片显示
                self.current_image_path = None
                self.original_image = None
                self.edited_image = None
                self.image_history = []
                self.history_index = -1
                self.EXIF_data = {}
                
                self.image_label.setText('请打开一张图片')
                self.info_text.clear()
                self.exif_text.clear()
                self.metadata_tree.clear()
                self.update_navigation_info()
                self.file_info_label.setText("")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败: {str(e)}")
    
    def batch_process(self):
        """批量处理图片"""
        if not self.image_files:
            QMessageBox.information(self, "提示", "没有可处理的图片")
            return
            
        # 显示批量处理对话框
        dialog = BatchProcessDialog(self, self.image_files)
        if dialog.exec_():
            # 处理完成后刷新文件列表
            current_folder = self.get_current_folder()
            if current_folder:
                self.load_folder_images(current_folder)
    
    def batch_rename(self):
        """批量重命名图片"""
        if not self.image_files or len(self.image_files) < 1:
            QMessageBox.information(self, "提示", "没有可重命名的图片")
            return
            
        # 创建批量重命名对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("批量重命名")
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # 命名模式
        pattern_group = QGroupBox("命名模式")
        pattern_layout = QVBoxLayout()
        
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("输入前缀")
        self.prefix_input.setText("image_")
        
        counter_layout = QHBoxLayout()
        counter_layout.addWidget(QLabel("起始编号:"))
        self.start_number = QSpinBox()
        self.start_number.setRange(1, 1000)
        self.start_number.setValue(1)
        counter_layout.addWidget(self.start_number)
        
        counter_layout.addWidget(QLabel("位数:"))
        self.number_digits = QSpinBox()
        self.number_digits.setRange(1, 6)
        self.number_digits.setValue(3)
        counter_layout.addWidget(self.number_digits)
        
        pattern_layout.addWidget(QLabel("前缀:"))
        pattern_layout.addWidget(self.prefix_input)
        pattern_layout.addLayout(counter_layout)
        
        preview_label = QLabel("预览:")
        self.preview_text = QLabel("image_001.jpg")
        pattern_layout.addWidget(preview_label)
        pattern_layout.addWidget(self.preview_text)
        
        # 更新预览
        def update_preview():
            prefix = self.prefix_input.text()
            start = self.start_number.value()
            digits = self.number_digits.value()
            if self.image_files:
                ext = os.path.splitext(self.image_files[0])[1]
                self.preview_text.setText(f"{prefix}{str(start).zfill(digits)}{ext}")
        
        self.prefix_input.textChanged.connect(update_preview)
        self.start_number.valueChanged.connect(update_preview)
        self.number_digits.valueChanged.connect(update_preview)
        
        pattern_group.setLayout(pattern_layout)
        layout.addWidget(pattern_group)
        
        # 选项
        options_group = QGroupBox("选项")
        options_layout = QVBoxLayout()
        
        self.keep_original_ext = QCheckBox("保持原始扩展名")
        self.keep_original_ext.setChecked(True)
        
        self.replace_existing = QCheckBox("替换已存在的文件")
        self.replace_existing.setChecked(False)
        
        options_layout.addWidget(self.keep_original_ext)
        options_layout.addWidget(self.replace_existing)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        if dialog.exec_():
            # 执行批量重命名
            prefix = self.prefix_input.text()
            start = self.start_number.value()
            digits = self.number_digits.value()
            replace = self.replace_existing.isChecked()
            
            success_count = 0
            error_count = 0
            errors = []
            
            folder = os.path.dirname(self.image_files[0])
            
            for i, file_path in enumerate(self.image_files):
                try:
                    # 获取文件扩展名
                    if self.keep_original_ext:
                        ext = os.path.splitext(file_path)[1]
                    else:
                        ext = os.path.splitext(file_path)[1].lower()
                    
                    # 生成新文件名
                    new_name = f"{prefix}{str(start + i).zfill(digits)}{ext}"
                    new_path = os.path.join(folder, new_name)
                    
                    # 检查是否已存在
                    if os.path.exists(new_path) and not replace:
                        error_count += 1
                        errors.append(f"文件已存在: {new_name}")
                        continue
                    
                    # 重命名
                    os.rename(file_path, new_path)
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    errors.append(f"重命名 {os.path.basename(file_path)} 失败: {str(e)}")
            
            # 显示结果
            msg = f"批量重命名完成:\n成功: {success_count}\n失败: {error_count}"
            if errors:
                msg += "\n\n错误详情:\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    msg += f"\n... 还有 {len(errors) - 5} 个错误"
            
            QMessageBox.information(self, "完成", msg)
            
            # 刷新文件列表
            self.load_folder_images(folder)
    
    def start_slideshow(self):
        """开始幻灯片播放"""
        if not self.image_files or len(self.image_files) < 1:
            QMessageBox.information(self, "提示", "没有可播放的图片")
            return
            
        # 创建幻灯片对话框
        self.slideshow_dialog = QDialog(self, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.slideshow_dialog.setWindowTitle("幻灯片")
        self.slideshow_dialog.setGeometry(0, 0, QApplication.desktop().width(), QApplication.desktop().height())
        self.slideshow_dialog.setStyleSheet("background-color: black;")
        
        layout = QVBoxLayout(self.slideshow_dialog)
        
        self.slide_label = QLabel()
        self.slide_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.slide_label, 1)  # 图片区域占据主要空间
        
        # 控制按钮区域
        control_layout = QHBoxLayout()
        control_layout.setAlignment(Qt.AlignCenter)
        
        # 添加控制按钮
        self.prev_btn_slide = QPushButton("◀")
        self.prev_btn_slide.setFixedSize(50, 50)
        self.prev_btn_slide.setStyleSheet("font-size: 20px; background-color: rgba(0,0,0,100); color: white; border-radius: 25px;")
        self.prev_btn_slide.clicked.connect(self.prev_slide)
        
        self.play_pause_btn = QPushButton("⏸")
        self.play_pause_btn.setFixedSize(50, 50)
        self.play_pause_btn.setStyleSheet("font-size: 20px; background-color: rgba(0,0,0,100); color: white; border-radius: 25px;")
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        
        self.next_btn_slide = QPushButton("▶")
        self.next_btn_slide.setFixedSize(50, 50)
        self.next_btn_slide.setStyleSheet("font-size: 20px; background-color: rgba(0,0,0,100); color: white; border-radius: 25px;")
        self.next_btn_slide.clicked.connect(self.next_slide)
        
        self.exit_btn = QPushButton("✕")
        self.exit_btn.setFixedSize(50, 50)
        self.exit_btn.setStyleSheet("font-size: 20px; background-color: rgba(0,0,0,100); color: white; border-radius: 25px;")
        self.exit_btn.clicked.connect(self.stop_slideshow)
        
        control_layout.addWidget(self.prev_btn_slide)
        control_layout.addWidget(self.play_pause_btn)
        control_layout.addWidget(self.next_btn_slide)
        control_layout.addWidget(self.exit_btn)
        
        # 状态栏
        status_layout = QHBoxLayout()
        self.slide_info = QLabel()
        self.slide_info.setStyleSheet("color: white; font-size: 14px;")
        status_layout.addWidget(self.slide_info, 1)
        
        self.slide_progress = QLabel()
        self.slide_progress.setStyleSheet("color: white; font-size: 14px;")
        self.slide_progress.setAlignment(Qt.AlignRight)
        status_layout.addWidget(self.slide_progress, 1)
        
        # 添加控制栏和状态栏到主布局
        layout.addLayout(status_layout)
        layout.addLayout(control_layout)
        
        # 幻灯片控制
        self.slide_index = 0
        if self.current_image_path in self.image_files:
            self.slide_index = self.image_files.index(self.current_image_path)
        
        self.slide_timer = QTimer()
        self.slide_timer.setInterval(3000)  # 3秒切换一张
        self.slide_timer.timeout.connect(self.next_slide)
        self.is_playing = True
        
        # 显示第一张
        self.show_slide(self.slide_index)
        self.slide_timer.start()
        
        # 显示对话框
        self.slideshow_dialog.showFullScreen()

    def show_slide(self, index):
        """显示指定索引的幻灯片"""
        if index < 0:
            index = len(self.image_files) - 1
        elif index >= len(self.image_files):
            index = 0
            
        self.slide_index = index
        file_path = self.image_files[index]
        try:
            # 打开图片并适应屏幕
            screen_width = self.slideshow_dialog.width()
            screen_height = self.slideshow_dialog.height() - 100  # 减去控制栏高度
            
            with Image.open(file_path) as img:
                # 计算缩放比例
                w, h = img.size
                ratio = min(screen_width / w, screen_height / h) * 0.95  # 留5%边距
                new_size = (int(w * ratio), int(h * ratio))
                
                # 转换为QPixmap
                img.thumbnail(new_size)
                if img.mode == 'RGBA':
                    q_image = QImage(img.tobytes(), img.width, img.height, 
                                   img.width * 4, QImage.Format_RGBA8888)
                else:
                    rgb_img = img.convert('RGB')
                    q_image = QImage(rgb_img.tobytes(), rgb_img.width, rgb_img.height, 
                                   rgb_img.width * 3, QImage.Format_RGB888)
                
                pixmap = QPixmap.fromImage(q_image)
                self.slide_label.setPixmap(pixmap)
                
                # 更新信息
                file_name = os.path.basename(file_path)
                self.slide_info.setText(f"{file_name} ({img.width}x{img.height})")
                self.slide_progress.setText(f"{index + 1}/{len(self.image_files)}")
                
        except Exception as e:
            print(f"显示幻灯片出错 {file_path}: {e}")
            self.slide_info.setText(f"无法显示: {os.path.basename(file_path)}")

    def next_slide(self):
        """显示下一张幻灯片"""
        self.show_slide(self.slide_index + 1)

    def prev_slide(self):
        """显示上一张幻灯片"""
        self.show_slide(self.slide_index - 1)

    def toggle_play_pause(self):
        """切换播放/暂停状态"""
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.slide_timer.start()
            self.play_pause_btn.setText("⏸")
        else:
            self.slide_timer.stop()
            self.play_pause_btn.setText("▶")

    def stop_slideshow(self):
        """停止幻灯片播放"""
        self.slide_timer.stop()
        self.slideshow_dialog.close()
    
    def show_about(self):
        """显示关于对话框"""
        about_text = """
        <h2>疯狂植物人图片查看与编辑软件</h2>
        <p>版本 1.0</p>
        <p>基于 PyQt5 和 PIL 开发的图片浏览器</p>
        <p>功能特点：</p>
        <ul>
            <li>支持多种图片格式：JPG, PNG, BMP, GIF, TIFF, WebP</li>
            <li>图片编辑功能：旋转、缩放、裁剪、色彩调整</li>
            <li>批量处理：重命名、格式转换、尺寸调整</li>
            <li>EXIF信息查看与导出</li>
            <li>经纬度坐标导出功能</li>
            <li>幻灯片播放功能</li>
        </ul>
        <p>© 2025 疯狂植物人图片查看与编辑软件</p>
        """
        QMessageBox.about(self, "关于", about_text)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ImageViewerEditor()
    viewer.show()
    sys.exit(app.exec_())