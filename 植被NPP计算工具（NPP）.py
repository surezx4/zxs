
import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
import rasterio
import pandas as pd

class NPPCalculator:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("植被NPP计算工具 v1.0")
    
    # 必须先初始化params再调用setup_ui
        self.params = {
        'Emax': 0.39,
        'Topt': 20,
        'W': 0.5
    }
    
        self.setup_ui()


    def setup_ui(self):
        # 数据输入区域
        input_frame = tk.LabelFrame(self.window, text="数据输入")
        input_frame.pack(padx=10, pady=5, fill="x")
        
        tk.Button(input_frame, text="导入Landsat数据", command=self.load_landsat).grid(row=0, column=0, padx=5)
        tk.Button(input_frame, text="导入温度数据", command=self.load_temp).grid(row=0, column=1, padx=5)
        tk.Button(input_frame, text="导入参数文件", command=self.load_params).grid(row=0, column=2, padx=5)

        # 参数设置区域
        param_frame = tk.LabelFrame(self.window, text="模型参数")
        param_frame.pack(padx=10, pady=5, fill="x")
        
        self.create_param_entry(param_frame, "Emax (gC/MJ):", 0, self.params['Emax'])
        self.create_param_entry(param_frame, "Topt (℃):", 1, self.params['Topt'])
        self.create_param_entry(param_frame, "W:", 2, self.params['W'])

        # 计算按钮
        tk.Button(self.window, text="计算NPP", command=self.calculate_npp, 
                 bg="#4CAF50", fg="white").pack(pady=10)

        # 结果显示
        self.result_text = tk.Text(self.window, height=10)
        self.result_text.pack(padx=10, pady=5, fill="both")

    def create_param_entry(self, frame, label, row, default):
        tk.Label(frame, text=label).grid(row=row, column=0, sticky="e")
        entry = tk.Entry(frame)
        entry.insert(0, str(default))
        entry.grid(row=row, column=1)
        setattr(self, label.split()[0].lower(), entry)

    def load_landsat(self):
        filepath = filedialog.askopenfilename(title="选择Landsat数据文件",
                                            filetypes=[("GeoTIFF", "*.tif")])
        if filepath:
            self.landsat_data = rasterio.open(filepath).read(1)
            self.show_message(f"已加载Landsat数据: {filepath}")

    def load_temp(self):
        filepath = filedialog.askopenfilename(title="选择温度数据文件",
                                            filetypes=[("CSV", "*.csv")])
        if filepath:
            self.temp_data = pd.read_csv(filepath).values
            self.show_message(f"已加载温度数据: {filepath}")

    def load_params(self):
        filepath = filedialog.askopenfilename(title="选择参数文件",
                                            filetypes=[("JSON", "*.json")])
        if filepath:
            import json
            with open(filepath) as f:
                self.params.update(json.load(f))
            self.show_message(f"已加载参数文件: {filepath}")

    def calculate_npp(self):
        try:
            # 获取用户输入的参数
            Emax = float(self.emax.get())
            Topt = float(self.topt.get())
            W = float(self.w.get())
            
            # 计算温度胁迫因子T
            T = np.exp(-0.5 * ((self.temp_data - Topt) / 5)**2)  # 温度胁迫公式
            
            # 计算APAR (简化处理)
            APAR = self.landsat_data * 0.48  # 假设Landsat数据已转换为PAR
            
            # 计算NPP = APAR × E = APAR × (T × W × Emax)
            NPP = APAR * (T * W * Emax)
            
            # 显示结果
            self.show_message(f"计算完成!\n平均NPP: {np.mean(NPP):.2f} gC/m²/year")
            
            # 保存结果
            self.save_result(NPP)
            
        except Exception as e:
            messagebox.showerror("错误", f"计算失败: {str(e)}")

    def save_result(self, npp):
        filepath = filedialog.asksaveasfilename(title="保存NPP结果",
                                              defaultextension=".tif",
                                              filetypes=[("GeoTIFF", "*.tif")])
        if filepath:
            with rasterio.open(filepath, 'w', 
                             driver='GTiff',
                             height=npp.shape[0],
                             width=npp.shape[1],
                             count=1,
                             dtype=npp.dtype) as dst:
                dst.write(npp, 1)
            self.show_message(f"结果已保存至: {filepath}")

    def show_message(self, msg):
        self.result_text.insert("end", msg + "\n\n")
        self.result_text.see("end")

    def run(self):
        self.window.mainloop()

if __name__ == "__main__":
    app = NPPCalculator()
    app.run()
