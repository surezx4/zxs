import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os
import datetime

class WetlandCalculator:
    def __init__(self, root):
        self.root = root
        self.root.title("小微湿地计算软件MIcroWET v1.0")
        self.root.geometry("1200x800")
        
        # 初始化数据（包含hydraulic_time）
        self.data = {
            "wetland_type": "河流型",
            "area": 1000.0,
            "depth_avg": 1.5,
            "porosity": 30.0,
            "rainfall": 50.0,
            "initial_water_level": 0.5,
            "design_water_level": 1.2,
            "influent_conc": 50.0,
            "effluent_conc": 10.0,
            "flow_rate": 10.0,
            "hydraulic_time": 3.0,  # 水力停留时间参数
            "annual_temp": 15.0,
            "annual_humidity": 60.0,
            "evap_coeff": 0.7,
            "wind_coeff": 1.2,
            "ref_evap": 800.0,
            "vegetation_coverage": 80.0,
            "biomass_density": 2.5,
            "soil_carbon": 2.0,
            "soil_bulk_density": 1.3,
            "soil_depth": 0.3
        }
        
        self.create_widgets()
        
    def create_widgets(self):
        # 标签页布局（同增强版）
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 1. 数据输入页
        frame_input = ttk.Frame(notebook)
        notebook.add(frame_input, text="数据输入")
        self.setup_input_frame(frame_input)
        
        # 2. 结果展示页（同增强版）
        frame_result = ttk.Frame(notebook)
        notebook.add(frame_result, text="结果展示")
        self.setup_result_frame(frame_result)
        
        # 3. 数据管理页（同增强版）
        frame_data = ttk.Frame(notebook)
        notebook.add(frame_data, text="数据管理")
        self.setup_data_frame(frame_data)
        
    def setup_input_frame(self, frame):
        # 第一行：湿地基础参数（同增强版）
        frame_base = ttk.LabelFrame(frame, text="湿地基础参数")
        frame_base.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        ttk.Label(frame_base, text="湿地类型：").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.wetland_type = ttk.Combobox(frame_base, values=["河流型", "湖泊型", "沼泽型"], width=15)
        self.wetland_type.current(0)
        self.wetland_type.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(frame_base, text="面积（㎡）：").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.area = ttk.Entry(frame_base, width=15)
        self.area.insert(0, "1000.0")
        self.area.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(frame_base, text="平均深度（m）：").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.depth_avg = ttk.Entry(frame_base, width=15)
        self.depth_avg.insert(0, "1.5")
        self.depth_avg.grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(frame_base, text="土壤孔隙率（%）：").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.porosity = ttk.Entry(frame_base, width=15)
        self.porosity.insert(0, "30.0")
        self.porosity.grid(row=3, column=1, padx=5, pady=5)
        
        # 第一行：水文与水质参数（增加hydraulic_time输入框）
        frame_hydro = ttk.LabelFrame(frame, text="水文与水质参数")
        frame_hydro.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        ttk.Label(frame_hydro, text="降雨量（mm）：").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.rainfall = ttk.Entry(frame_hydro, width=15)
        self.rainfall.insert(0, "50.0")
        self.rainfall.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(frame_hydro, text="初期水位（m）：").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.initial_water_level = ttk.Entry(frame_hydro, width=15)
        self.initial_water_level.insert(0, "0.5")
        self.initial_water_level.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(frame_hydro, text="设计水位（m）：").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.design_water_level = ttk.Entry(frame_hydro, width=15)
        self.design_water_level.insert(0, "1.2")
        self.design_water_level.grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(frame_hydro, text="进水污染物浓度（mg/L）：").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.influent_conc = ttk.Entry(frame_hydro, width=15)
        self.influent_conc.insert(0, "50.0")
        self.influent_conc.grid(row=3, column=1, padx=5, pady=5)
        
        ttk.Label(frame_hydro, text="出水污染物浓度（mg/L）：").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.effluent_conc = ttk.Entry(frame_hydro, width=15)
        self.effluent_conc.insert(0, "10.0")
        self.effluent_conc.grid(row=4, column=1, padx=5, pady=5)
        
        ttk.Label(frame_hydro, text="流量（m³/d）：").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.flow_rate = ttk.Entry(frame_hydro, width=15)
        self.flow_rate.insert(0, "10.0")
        self.flow_rate.grid(row=5, column=1, padx=5, pady=5)
        
        # 新增：水力停留时间输入框（修复缺失的属性定义）
        ttk.Label(frame_hydro, text="水力停留时间（d）：").grid(row=6, column=0, padx=5, pady=5, sticky="w")
        self.hydraulic_time = ttk.Entry(frame_hydro, width=15)
        self.hydraulic_time.insert(0, "3.0")
        self.hydraulic_time.grid(row=6, column=1, padx=5, pady=5)
        
        # 第二行：气候调节参数（同增强版）
        frame_climate = ttk.LabelFrame(frame, text="气候调节参数")
        frame_climate.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        ttk.Label(frame_climate, text="年均气温（℃）：").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.annual_temp = ttk.Entry(frame_climate, width=15)
        self.annual_temp.insert(0, "15.0")
        self.annual_temp.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(frame_climate, text="年均相对湿度（%）：").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.annual_humidity = ttk.Entry(frame_climate, width=15)
        self.annual_humidity.insert(0, "60.0")
        self.annual_humidity.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(frame_climate, text="水面蒸发系数：").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.evap_coeff = ttk.Entry(frame_climate, width=15)
        self.evap_coeff.insert(0, "0.7")
        self.evap_coeff.grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(frame_climate, text="风速修正系数：").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.wind_coeff = ttk.Entry(frame_climate, width=15)
        self.wind_coeff.insert(0, "1.2")
        self.wind_coeff.grid(row=3, column=1, padx=5, pady=5)
        
        ttk.Label(frame_climate, text="参考蒸发量（mm）：").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.ref_evap = ttk.Entry(frame_climate, width=15)
        self.ref_evap.insert(0, "800.0")
        self.ref_evap.grid(row=4, column=1, padx=5, pady=5)
        
        # 第二行：固碳增汇参数（同增强版）
        frame_carbon = ttk.LabelFrame(frame, text="固碳增汇参数")
        frame_carbon.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
        
        ttk.Label(frame_carbon, text="植被覆盖率（%）：").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.vegetation_coverage = ttk.Entry(frame_carbon, width=15)
        self.vegetation_coverage.insert(0, "80.0")
        self.vegetation_coverage.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(frame_carbon, text="植被生物量密度（kg/㎡）：").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.biomass_density = ttk.Entry(frame_carbon, width=15)
        self.biomass_density.insert(0, "2.5")
        self.biomass_density.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(frame_carbon, text="土壤有机碳含量（%）：").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.soil_carbon = ttk.Entry(frame_carbon, width=15)
        self.soil_carbon.insert(0, "2.0")
        self.soil_carbon.grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(frame_carbon, text="土壤容重（g/cm³）：").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.soil_bulk_density = ttk.Entry(frame_carbon, width=15)
        self.soil_bulk_density.insert(0, "1.3")
        self.soil_bulk_density.grid(row=3, column=1, padx=5, pady=5)
        
        ttk.Label(frame_carbon, text="土壤采样深度（m）：").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.soil_depth = ttk.Entry(frame_carbon, width=15)
        self.soil_depth.insert(0, "0.3")
        self.soil_depth.grid(row=4, column=1, padx=5, pady=5)
        
        # 计算按钮（同增强版）
        btn_calc = ttk.Button(frame, text="开始计算", command=self.calculate)
        btn_calc.grid(row=2, column=0, columnspan=2, pady=20)
        
        # 权重设置（同增强版）
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        
    def setup_result_frame(self, frame):
        # 结果文本展示（同增强版）
        self.result_text = tk.Text(frame, height=12, width=100)
        self.result_text.pack(padx=10, pady=10, fill="x")
        
        # 图表展示（2x2布局）（同增强版）
        self.fig, self.ax = plt.subplots(2, 2, figsize=(10, 8))
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.get_tk_widget().pack(padx=10, pady=10, fill="both", expand=True)
        
    def setup_data_frame(self, frame):
        # 数据管理页内容（同增强版）
        ttk.Label(frame, text="历史计算记录：").pack(padx=10, pady=10, anchor="w")
        
        self.record_listbox = tk.Listbox(frame, width=100, height=20)
        self.record_listbox.pack(padx=10, pady=5, fill="both", expand=True)
        
        frame_btn = ttk.Frame(frame)
        frame_btn.pack(pady=10)
        
        btn_save = ttk.Button(frame_btn, text="保存当前结果", command=self.save_result)
        btn_save.grid(row=0, column=0, padx=10)
        
        btn_load = ttk.Button(frame_btn, text="加载历史记录", command=self.load_record)
        btn_load.grid(row=0, column=1, padx=10)
        
    def calculate(self):
        try:
            # 获取输入数据（补充hydraulic_time的获取）
            self.data["wetland_type"] = self.wetland_type.get()
            self.data["area"] = float(self.area.get())
            self.data["depth_avg"] = float(self.depth_avg.get())
            self.data["porosity"] = float(self.porosity.get()) / 100  # 转换为小数
            self.data["rainfall"] = float(self.rainfall.get())
            self.data["initial_water_level"] = float(self.initial_water_level.get())
            self.data["design_water_level"] = float(self.design_water_level.get())
            self.data["influent_conc"] = float(self.influent_conc.get())
            self.data["effluent_conc"] = float(self.effluent_conc.get())
            self.data["flow_rate"] = float(self.flow_rate.get())
            self.data["hydraulic_time"] = float(self.hydraulic_time.get())  # 新增：获取水力停留时间
            self.data["annual_temp"] = float(self.annual_temp.get())
            self.data["annual_humidity"] = float(self.annual_humidity.get())
            self.data["evap_coeff"] = float(self.evap_coeff.get())
            self.data["wind_coeff"] = float(self.wind_coeff.get())
            self.data["ref_evap"] = float(self.ref_evap.get())
            self.data["vegetation_coverage"] = float(self.vegetation_coverage.get()) / 100  # 转换为小数
            self.data["biomass_density"] = float(self.biomass_density.get())
            self.data["soil_carbon"] = float(self.soil_carbon.get()) / 100  # 转换为小数
            self.data["soil_bulk_density"] = float(self.soil_bulk_density.get())
            self.data["soil_depth"] = float(self.soil_depth.get())
            
            # 计算逻辑（同增强版，此处略）
            storage = self.data["area"] * (self.data["design_water_level"] - self.data["initial_water_level"]) * self.data["porosity"]
            removal_efficiency = (self.data["influent_conc"] - self.data["effluent_conc"]) / self.data["influent_conc"] * 100
            pollutant_removal = self.data["flow_rate"] * self.data["hydraulic_time"] * (self.data["influent_conc"] - self.data["effluent_conc"]) * 1e-6
            avg_evap = 0.001 * self.data["evap_coeff"] * (0.478 + 0.725 * self.data["wind_coeff"]) * self.data["ref_evap"]
            annual_evaporation = self.data["area"] * avg_evap
            cooling_effect = 0.02 * annual_evaporation / self.data["area"]
            vegetation_carbon = self.data["area"] * self.data["vegetation_coverage"] * self.data["biomass_density"] * 0.5
            soil_carbon = self.data["area"] * self.data["soil_depth"] * self.data["soil_bulk_density"] * 1000 * self.data["soil_carbon"] * 0.58
            total_carbon = vegetation_carbon + soil_carbon
            
            # 结果展示（同增强版，此处略）
            result_str = f"===== 计算结果 =====\n"
            result_str += f"湿地类型：{self.data['wetland_type']}\n"
            result_str += f"调蓄量：{storage:.2f} m³\n"
            result_str += f"污染物去除效率：{removal_efficiency:.2f}%，污染物去除量：{pollutant_removal:.2f} kg\n"
            result_str += f"年蒸发量：{annual_evaporation:.2f} m³，降温效应：{cooling_effect:.2f} ℃\n"
            result_str += f"植被年固碳量：{vegetation_carbon:.2f} kg，土壤固碳量：{soil_carbon:.2f} kg，总固碳量：{total_carbon:.2f} kg\n"
            
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, result_str)
            
            # 图表绘制（同增强版，此处略）
            self.ax[0,0].clear()
            self.ax[0,0].bar(["调蓄量"], [storage], color="skyblue")
            self.ax[0,0].set_ylabel("调蓄量（m³）")
            self.ax[0,0].set_title("湿地调蓄能力")
            
            self.ax[0,1].clear()
            self.ax[0,1].bar(["进水浓度", "出水浓度"], [self.data["influent_conc"], self.data["effluent_conc"]], color=["orange", "green"])
            self.ax[0,1].set_ylabel("浓度（mg/L）")
            self.ax[0,1].set_title("污染物浓度对比")
            
            self.ax[1,0].clear()
            self.ax[1,0].pie([vegetation_carbon, soil_carbon], labels=["植被固碳", "土壤固碳"], autopct='%1.1f%%', colors=["lightgreen", "brown"])
            self.ax[1,0].set_title("固碳组成占比")
            
            self.ax[1,1].clear()
            self.ax[1,1].bar(["年蒸发量（×10³）", "降温效应"], [annual_evaporation/1000, cooling_effect], color=["lightblue", "purple"])
            self.ax[1,1].set_title("气候调节能力")
            
            self.fig.tight_layout()
            self.canvas.draw()
            
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            self.record_listbox.insert(tk.END, f"{current_time} - {self.data['wetland_type']} 湿地计算记录")
            
        except ValueError as e:
            messagebox.showerror("输入错误", f"请输入有效的数值：{str(e)}")
        except Exception as e:
            messagebox.showerror("计算错误", f"计算过程出错：{str(e)}")
            
    def save_result(self):
        # 数据保存逻辑（同增强版，此处略）
        if not self.result_text.get(1.0, tk.END).strip():
            messagebox.showwarning("警告", "请先完成计算再保存结果")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"计算时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(self.result_text.get(1.0, tk.END))
            messagebox.showinfo("成功", f"结果已保存至：{file_path}")
            
    def load_record(self):
        # 加载记录逻辑（同增强版，此处略）
        selected = self.record_listbox.curselection()
        if not selected:
            messagebox.showwarning("警告", "请选择要加载的记录")
            return
        messagebox.showinfo("提示", "此处可扩展为加载选中记录的详细数据")

if __name__ == "__main__":
    root = tk.Tk()
    app = WetlandCalculator(root)
    root.mainloop()