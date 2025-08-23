import sys
import os
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QMessageBox, QTextEdit,
                             QTabWidget, QProgressBar, QSplitter, QSizePolicy, QComboBox,
                             QLineEdit, QCheckBox)
from PyQt5.QtGui import QPixmap, QImage, QPalette, QColor
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import networkx as nx
from Bio.Phylo.TreeConstruction import DistanceMatrix, DistanceTreeConstructor
from Bio import Phylo
from io import StringIO
import tempfile
import seaborn as sns

class TreeWorker(QThread):
    """后台线程用于构建系统发育树"""
    finished = pyqtSignal(object, str, str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, csv_path, method="nj", root_name="Root"):
        super().__init__()
        self.csv_path = csv_path
        self.method = method
        self.root_name = root_name

    def run(self):
        try:
            # 读取CSV文件
            self.progress.emit(10, "读取CSV文件...")
            df = pd.read_csv(self.csv_path, index_col=0)
            
            # 验证数据格式
            self.progress.emit(20, "验证数据格式...")
            if not self._validate_data(df):
                self.error.emit("CSV格式无效。请确保第一行和第一列为样本名称，矩阵对称且对角线为0")
                return
            
            # 创建距离矩阵
            self.progress.emit(30, "创建距离矩阵...")
            dist_matrix = df.values
            sample_ids = df.index.tolist()
            
            # 转换为BioPython的距离矩阵格式
            matrix_list = []
            for i in range(len(dist_matrix)):
                matrix_list.append(dist_matrix[i, :i+1].tolist())
            
            dm = DistanceMatrix(names=sample_ids, matrix=matrix_list)
            
            # 构建系统发育树
            self.progress.emit(60, f"使用{self.method}方法构建系统发育树...")
            constructor = DistanceTreeConstructor()
            
            if self.method == "nj":
                tree = constructor.nj(dm)
            else:  # UPGMA
                tree = constructor.upgma(dm)
            
            # 添加根节点名称
            if self.root_name and tree.rooted:
                tree.root.name = self.root_name
            
            # 生成Newick格式
            self.progress.emit(80, "生成Newick格式...")
            handle = StringIO()
            Phylo.write(tree, handle, "newick")
            newick_str = handle.getvalue()
            
            # 生成树结构文本
            self.progress.emit(90, "生成树结构文本...")
            tree_ascii = self._tree_to_ascii(tree)
            
            self.progress.emit(100, "完成!")
            self.finished.emit(tree, newick_str, tree_ascii)
            
        except Exception as e:
            self.error.emit(f"处理过程中发生错误: {str(e)}")

    def _validate_data(self, df):
        """验证距离矩阵格式是否正确"""
        # 检查是否为方阵
        if df.shape[0] != df.shape[1]:
            return False
        
        # 检查对角线是否为0
        for i in range(df.shape[0]):
            if not np.isclose(df.iloc[i, i], 0):
                return False
        
        # 检查对称性
        for i in range(df.shape[0]):
            for j in range(i+1, df.shape[1]):
                if not np.isclose(df.iloc[i, j], df.iloc[j, i]):
                    return False
        
        return True
    
    def _tree_to_ascii(self, tree):
        """将树转换为ASCII表示"""
        if len(tree.get_terminals()) > 15:
            return "树太大，无法显示ASCII表示。请查看可视化标签页。"
        
        # 使用BioPython的draw_ascii函数
        handle = StringIO()
        Phylo.draw_ascii(tree, file=handle)
        return handle.getvalue()


class PhylogeneticTreeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("系统发育树生成工具")
        self.setGeometry(100, 100, 1200, 800)
        self.tree = None
        self.init_ui()
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QPushButton {
                background-color: #4a86e8;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a76d8;
            }
            QPushButton:disabled {
                background-color: #a0a0a0;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-family: Consolas, monospace;
            }
            QLabel {
                font-size: 12px;
            }
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                text-align: center;
                background-color: #e0e0e0;
            }
            QProgressBar::chunk {
                background-color: #4a86e8;
                width: 10px;
            }
            QTabWidget::pane {
                border: 1px solid #ccc;
                border-radius: 4px;
                background: white;
            }
            QTabBar::tab {
                background: #e0e0e0;
                padding: 8px 16px;
                border: 1px solid #ccc;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 1px solid white;
            }
            QLineEdit, QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
        """)

    def init_ui(self):
        """初始化用户界面"""
        # 创建主部件和布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # 顶部控制面板
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)

        # 文件选择部分
        file_group = QWidget()
        file_layout = QVBoxLayout(file_group)
        file_layout.setContentsMargins(0, 0, 0, 0)
        
        file_label = QLabel("距离矩阵CSV文件:")
        self.file_path_label = QLabel("未选择文件")
        self.file_path_label.setStyleSheet("color: #666; font-style: italic;")
        browse_button = QPushButton("浏览...")
        browse_button.clicked.connect(self.browse_file)
        
        file_layout.addWidget(file_label)
        file_layout.addWidget(self.file_path_label)
        file_layout.addWidget(browse_button)
        
        # 方法选择部分
        method_group = QWidget()
        method_layout = QVBoxLayout(method_group)
        method_layout.setContentsMargins(0, 0, 0, 0)
        
        method_label = QLabel("构建方法:")
        self.method_combo = QComboBox()
        self.method_combo.addItems(["邻接法 (NJ)", "UPGMA"])
        self.method_combo.setCurrentIndex(0)
        
        method_layout.addWidget(method_label)
        method_layout.addWidget(self.method_combo)
        
        # 根节点设置
        root_group = QWidget()
        root_layout = QVBoxLayout(root_group)
        root_layout.setContentsMargins(0, 0, 0, 0)
        
        root_label = QLabel("根节点名称:")
        self.root_edit = QLineEdit("Root")
        
        root_layout.addWidget(root_label)
        root_layout.addWidget(self.root_edit)
        
        # 操作按钮
        self.generate_button = QPushButton("生成系统发育树")
        self.generate_button.clicked.connect(self.generate_tree)
        self.generate_button.setEnabled(False)
        
        self.save_button = QPushButton("保存结果")
        self.save_button.clicked.connect(self.save_results)
        self.save_button.setEnabled(False)
        
        # 添加到控制面板
        control_layout.addWidget(file_group, 1)
        control_layout.addWidget(method_group, 1)
        control_layout.addWidget(root_group, 1)
        control_layout.addStretch(1)
        control_layout.addWidget(self.generate_button)
        control_layout.addWidget(self.save_button)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("准备就绪")
        
        # 结果展示区域
        self.tab_widget = QTabWidget()
        
        # 树结构标签页
        self.tree_text = QTextEdit()
        self.tree_text.setReadOnly(True)
        self.tree_text.setPlaceholderText("树结构将在这里显示...")
        
        # Newick格式标签页
        self.newick_text = QTextEdit()
        self.newick_text.setReadOnly(True)
        self.newick_text.setPlaceholderText("Newick格式将在这里显示...")
        
        # 树可视化标签页 - 使用Matplotlib
        self.viz_tab = QWidget()
        viz_layout = QVBoxLayout(self.viz_tab)
        self.figure = plt.figure(figsize=(10, 8))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        viz_layout.addWidget(self.canvas)
        
        # 距离矩阵标签页
        self.matrix_tab = QWidget()
        matrix_layout = QVBoxLayout(self.matrix_tab)
        self.matrix_text = QTextEdit()
        self.matrix_text.setReadOnly(True)
        self.matrix_text.setPlaceholderText("距离矩阵将在这里显示...")
        matrix_layout.addWidget(self.matrix_text)
        
        # 添加标签页
        self.tab_widget.addTab(self.tree_text, "树结构")
        self.tab_widget.addTab(self.newick_text, "Newick格式")
        self.tab_widget.addTab(self.viz_tab, "树可视化")
        self.tab_widget.addTab(self.matrix_tab, "距离矩阵")
        
        # 添加到主布局
        main_layout.addWidget(control_panel)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.tab_widget, 1)
        
        # 状态栏
        self.statusBar().showMessage("就绪")

    def browse_file(self):
        """浏览并选择CSV文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择距离矩阵CSV文件", "", "CSV文件 (*.csv)"
        )
        
        if file_path:
            self.file_path = file_path
            self.file_path_label.setText(os.path.basename(file_path))
            self.file_path_label.setToolTip(file_path)
            self.generate_button.setEnabled(True)
            self.statusBar().showMessage(f"已选择文件: {file_path}")
            
            # 显示距离矩阵预览
            self.show_matrix_preview()

    def show_matrix_preview(self):
        """显示距离矩阵预览"""
        try:
            df = pd.read_csv(self.file_path, index_col=0)
            self.matrix_text.setPlainText(self._format_matrix(df))
        except Exception as e:
            self.matrix_text.setPlainText(f"无法加载距离矩阵: {str(e)}")

    def _format_matrix(self, df):
        """格式化距离矩阵为文本"""
        if len(df) > 20:
            return "矩阵太大，无法完整显示。请查看可视化标签页。"
        
        # 创建格式化文本
        text = "样本名称\t" + "\t".join(df.columns) + "\n"
        for i, row in df.iterrows():
            text += f"{i}\t" + "\t".join(f"{x:.4f}" for x in row.values) + "\n"
        return text

    def generate_tree(self):
        """生成系统发育树"""
        if not hasattr(self, 'file_path'):
            QMessageBox.warning(self, "警告", "请先选择CSV文件")
            return
        
        # 禁用按钮并重置UI
        self.generate_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.tree_text.clear()
        self.newick_text.clear()
        self.figure.clear()
        self.canvas.draw()
        
        # 获取构建方法
        method = "nj" if self.method_combo.currentIndex() == 0 else "upgma"
        root_name = self.root_edit.text().strip()
        
        # 创建并启动工作线程
        self.worker = TreeWorker(self.file_path, method, root_name)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_tree_generated)
        self.worker.error.connect(self.on_error)
        self.worker.start()
        
        self.statusBar().showMessage("正在构建系统发育树...")

    def update_progress(self, value, message):
        """更新进度条状态"""
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(f"{message} ({value}%)")

    def on_tree_generated(self, tree, newick_str, tree_ascii):
        """树生成完成后的处理"""
        self.tree = tree
        self.tree_text.setPlainText(tree_ascii)
        self.newick_text.setPlainText(newick_str)
        
        # 生成树的可视化
        self.generate_tree_visualization()
        
        # 启用按钮
        self.generate_button.setEnabled(True)
        self.save_button.setEnabled(True)
        
        self.statusBar().showMessage("系统发育树生成完成!")

    def generate_tree_visualization(self):
        """生成树的可视化图像"""
        try:
            # 创建热图可视化
            self.figure.clear()
            
            # 创建1x2的子图布局
            ax1 = self.figure.add_subplot(121)  # 树可视化
            ax2 = self.figure.add_subplot(122)  # 距离矩阵热图
            
            # 绘制系统发育树
            Phylo.draw(self.tree, axes=ax1, do_show=False)
            ax1.set_title("系统发育树", fontsize=12)
            
            # 读取距离矩阵数据
            df = pd.read_csv(self.file_path, index_col=0)
            
            # 绘制距离矩阵热图
            sns.heatmap(df, annot=True, fmt=".2f", cmap="viridis", 
                        cbar_kws={'label': '进化距离'}, ax=ax2)
            ax2.set_title("距离矩阵热图", fontsize=12)
            
            # 调整布局
            self.figure.tight_layout()
            
            # 刷新画布
            self.canvas.draw()
            
        except Exception as e:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, f"生成可视化时出错:\n{str(e)}", 
                    ha='center', va='center', fontsize=12)
            self.canvas.draw()

    def on_error(self, message):
        """处理错误信息"""
        QMessageBox.critical(self, "错误", message)
        self.progress_bar.setFormat("错误: " + message)
        self.generate_button.setEnabled(True)
        self.statusBar().showMessage("发生错误")

    def save_results(self):
        """保存生成的结果"""
        if not self.tree:
            QMessageBox.warning(self, "警告", "没有可保存的结果")
            return
        
        # 选择保存目录
        save_dir = QFileDialog.getExistingDirectory(
            self, "选择保存目录", ""
        )
        
        if not save_dir:
            return
        
        try:
            # 保存Newick文件
            newick_path = os.path.join(save_dir, "phylogenetic_tree.newick")
            Phylo.write(self.tree, newick_path, "newick")
            
            # 保存树结构文本
            text_path = os.path.join(save_dir, "tree_structure.txt")
            with open(text_path, "w") as f:
                f.write(self.tree_text.toPlainText())
            
            # 保存距离矩阵
            matrix_path = os.path.join(save_dir, "distance_matrix.csv")
            df = pd.read_csv(self.file_path, index_col=0)
            df.to_csv(matrix_path)
            
            # 保存可视化图像
            viz_path = os.path.join(save_dir, "tree_visualization.png")
            self.figure.savefig(viz_path, dpi=300, bbox_inches='tight')
            
            QMessageBox.information(self, "成功", f"结果已保存到:\n{save_dir}")
            self.statusBar().showMessage(f"结果已保存到: {save_dir}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存文件时出错: {str(e)}")

    def closeEvent(self, event):
        """关闭应用程序时的处理"""
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.terminate()
        event.accept()


if __name__ == "__main__":
    # 设置seaborn样式 - 替代matplotlib样式设置
    sns.set_style("whitegrid")
    
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle("Fusion")
    
    # 创建并显示主窗口
    window = PhylogeneticTreeApp()
    window.show()
    
    sys.exit(app.exec_())