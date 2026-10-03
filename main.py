import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import threading
import time
import csv
import json
import os
import bisect
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from nwt_driver import NWTInstrument, SweepWorker

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NWT4000 上位机 (Python版)")
        self.geometry("1100x850") 
        
        self.current_x_data = []
        self.current_y_data = []
        self.bg_x_data = []
        self.bg_y_data = []
        
        self.config_filepath = "nwt_settings.json"
        
        # 多条曲线存储
        self.saved_traces = {} # {trace_key: {'x': x, 'y': y, 'line': line, 'color': color}}
        self.trace_vars = {}
        self.trace_chks = {}

        self.colors = ['#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        self.plot_font_family = "Microsoft YaHei"
        self.plot_label_size = 12
        self.plot_tick_size = 10
        self.font_family_options = [
            "Microsoft YaHei",
            "SimHei",
            "SimSun",
            "Arial",
            "Times New Roman",
            "Calibri",
            "Consolas",
        ]
        
        self.create_widgets()
        self.inst = NWTInstrument(log_callback=self.log_message)
        self.sweep_thread = None
        self.detect_thread = None
        self.refresh_ports()
        
        # 尝试加载上次的设置缓存
        self.load_config()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.log_message("程序已启动，等待连接设备...")
        
        # 启动后自动连接
        self.after(500, self.auto_connect)

    def auto_connect(self):
        if self.cb_ports.get():
            self.log_message(f"自动尝试连接 {self.cb_ports.get()} ...")
            self.toggle_connection()

    def load_config(self):
        if os.path.exists(self.config_filepath):
            try:
                with open(self.config_filepath, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                if "port" in config and config["port"] in self.cb_ports["values"]:
                    self.cb_ports.current(self.cb_ports["values"].index(config["port"]))
                if "baud" in config:
                    self.entry_baud.delete(0, tk.END)
                    self.entry_baud.insert(0, config["baud"])
                if "model" in config and config["model"] in self.cb_model["values"]:
                    self.cb_model.current(self.cb_model["values"].index(config["model"]))
                    
                if "start_f" in config:
                    self.entry_start.delete(0, tk.END)
                    self.entry_start.insert(0, config["start_f"])
                if "stop_f" in config:
                    self.entry_stop.delete(0, tk.END)
                    self.entry_stop.insert(0, config["stop_f"])
                if "steps" in config:
                    self.entry_steps.delete(0, tk.END)
                    self.entry_steps.insert(0, config["steps"])
                if "y_offset" in config:
                    self.entry_y_offset.delete(0, tk.END)
                    self.entry_y_offset.insert(0, config["y_offset"])
                if "y_scale" in config:
                    self.entry_y_scale.delete(0, tk.END)
                    self.entry_y_scale.insert(0, config["y_scale"])

                self.plot_font_family = config.get("plot_font_family", self.plot_font_family)
                self.plot_label_size = int(config.get("plot_label_size", self.plot_label_size))
                self.plot_tick_size = int(config.get("plot_tick_size", self.plot_tick_size))
                if hasattr(self, "cb_plot_font"):
                    if self.plot_font_family not in self.font_family_options:
                        self.font_family_options.append(self.plot_font_family)
                        self.cb_plot_font["values"] = self.font_family_options
                    self.cb_plot_font.set(self.plot_font_family)
                    self.entry_label_font_size.delete(0, tk.END)
                    self.entry_label_font_size.insert(0, str(self.plot_label_size))
                    self.entry_tick_font_size.delete(0, tk.END)
                    self.entry_tick_font_size.insert(0, str(self.plot_tick_size))
                    self.apply_plot_style(redraw=False)
                    
                if "use_bg" in config:
                    self.use_bg_var.set(config["use_bg"])
                if "use_smooth" in config:
                    self.use_smooth_var.set(config["use_smooth"])
                if "bg_x_data" in config:
                    self.bg_x_data = config.get("bg_x_data", [])
                if "bg_y_data" in config:
                    self.bg_y_data = config.get("bg_y_data", [])
                    
                if "geometry" in config:
                    self.geometry(config["geometry"])
                if "window_state" in config and config["window_state"] == "zoomed":
                    self.state('zoomed')
                    
                if "subplots" in config:
                    self.fig.subplots_adjust(**config["subplots"])
                    
                self.log_message("已加载上次的参数设置。")
            except Exception as e:
                self.log_message(f"加载缓存配置失败: {e}")

    def save_config(self):
        try:
            config = {
                "port": self.cb_ports.get(),
                "baud": self.entry_baud.get(),
                "model": self.cb_model.get(),
                "start_f": self.entry_start.get(),
                "stop_f": self.entry_stop.get(),
                "steps": self.entry_steps.get(),
                "y_offset": self.entry_y_offset.get(),
                "y_scale": self.entry_y_scale.get(),
                "plot_font_family": self.plot_font_family,
                "plot_label_size": self.plot_label_size,
                "plot_tick_size": self.plot_tick_size,
                "use_bg": self.use_bg_var.get(),
                "use_smooth": self.use_smooth_var.get(),
                "bg_x_data": self.bg_x_data,
                "bg_y_data": self.bg_y_data,
                "geometry": self.geometry(),
                "window_state": self.state(),
                "subplots": {
                    "left": self.fig.subplotpars.left,
                    "bottom": self.fig.subplotpars.bottom,
                    "right": self.fig.subplotpars.right,
                    "top": self.fig.subplotpars.top
                }
            }
            with open(self.config_filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def reset_all_settings(self):
        if messagebox.askyesno("确认重置", "确定要清除所有缓存并恢复初始默认设置吗？\n(这将会清除您的配置并重置界面)"):
            if os.path.exists(self.config_filepath):
                try: os.remove(self.config_filepath)
                except: pass
            
            # 恢复UI数据
            self.entry_start.delete(0, tk.END)
            self.entry_start.insert(0, "1000000")
            self.entry_stop.delete(0, tk.END)
            self.entry_stop.insert(0, "30000000")
            self.entry_steps.delete(0, tk.END)
            self.entry_steps.insert(0, "500")
            self.entry_y_offset.delete(0, tk.END)
            self.entry_y_offset.insert(0, "-250.0")
            self.entry_y_scale.delete(0, tk.END)
            self.entry_y_scale.insert(0, "0.7")

            self.plot_font_family = "Microsoft YaHei"
            self.plot_label_size = 12
            self.plot_tick_size = 10
            self.cb_plot_font.set(self.plot_font_family)
            self.entry_label_font_size.delete(0, tk.END)
            self.entry_label_font_size.insert(0, str(self.plot_label_size))
            self.entry_tick_font_size.delete(0, tk.END)
            self.entry_tick_font_size.insert(0, str(self.plot_tick_size))
            
            self.use_bg_var.set(False)
            self.use_smooth_var.set(False)
            self.bg_x_data = []
            self.bg_y_data = []
            self.clear_all_traces()
            
            # 图表复位
            if self.state() == "zoomed": 
                self.state("normal")
            self.geometry("1100x850")
            self.fig.subplots_adjust(left=0.125, bottom=0.11, right=0.9, top=0.88)
            self.apply_plot_style(redraw=False)
            self.canvas.draw_idle()
            
            self.log_message("所有设置和缓存已重置完毕！")

    def toggle_com_panel(self):
        if self.com_panel_visible:
            self.lf_com.pack_forget()
            self.btn_toggle_com.config(text="展开通信设置 ▼")
            self.com_panel_visible = False
        else:
            self.lf_com.pack(fill=tk.X, pady=2, after=self.btn_toggle_com)
            self.btn_toggle_com.config(text="收起通信设置 ▲")
            self.com_panel_visible = True

    def smooth_data(self, data, window_size=5):
        if len(data) < window_size:
            return data
        smoothed = []
        for i in range(len(data)):
            start = max(0, i - window_size // 2)
            end = min(len(data), i + window_size // 2 + 1)
            smoothed.append(sum(data[start:end]) / (end - start))
        return smoothed

    def log_message(self, message):
        def _append():
            timestamp = time.strftime("[%H:%M:%S] ", time.localtime())
            self.txt_log.config(state=tk.NORMAL)
            self.txt_log.insert(tk.END, timestamp + message + "\n")
            self.txt_log.see(tk.END)
            self.txt_log.config(state=tk.DISABLED)
        self.after(0, _append)

    def create_menu_bar(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="导出当前扫描 CSV", command=self.export_csv)
        file_menu.add_command(label="导出实验数据 CSV", command=self.export_experiment_csv)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.on_close)
        menubar.add_cascade(label="文件", menu=file_menu)

        device_menu = tk.Menu(menubar, tearoff=0)
        device_menu.add_command(label="刷新端口", command=self.refresh_ports)
        device_menu.add_command(label="连接/断开设备", command=self.toggle_connection)
        device_menu.add_command(label="一键排错探测", command=self.start_auto_detect)
        menubar.add_cascade(label="设备", menu=device_menu)

        scan_menu = tk.Menu(menubar, tearoff=0)
        scan_menu.add_checkbutton(label="连续扫描", variable=self.continuous_var)
        scan_menu.add_command(label="开始扫描", command=self.start_sweep)
        scan_menu.add_command(label="停止扫描", command=self.stop_sweep)
        menubar.add_cascade(label="扫描", menu=scan_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_checkbutton(label="显示当前扫描曲线", variable=self.show_scan_var, command=self.replot_data)
        view_menu.add_checkbutton(label="扣除底噪", variable=self.use_bg_var, command=self.replot_data)
        view_menu.add_checkbutton(label="平滑曲线", variable=self.use_smooth_var, command=self.replot_data)
        menubar.add_cascade(label="视图", menu=view_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="保存当前为参考底噪", command=self.save_as_background)
        tools_menu.add_command(label="固定当前曲线", command=self.save_trace_to_plot)
        tools_menu.add_command(label="清除所有固定曲线", command=self.clear_all_traces)
        tools_menu.add_separator()
        tools_menu.add_command(label="重置参数与缓存", command=self.reset_all_settings)
        menubar.add_cascade(label="工具", menu=tools_menu)

        self.config(menu=menubar)

    def create_widgets(self):
        self.continuous_var = tk.BooleanVar(value=True)
        self.use_bg_var = tk.BooleanVar()
        self.use_smooth_var = tk.BooleanVar()
        self.show_scan_var = tk.BooleanVar(value=True)

        top_controls = ttk.Notebook(self)
        top_controls.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(6, 4))

        tab_comm = tk.Frame(top_controls, padx=8, pady=6)
        tab_scan = tk.Frame(top_controls, padx=8, pady=6)
        tab_analysis = tk.Frame(top_controls, padx=8, pady=6)
        tab_style = tk.Frame(top_controls, padx=8, pady=6)
        top_controls.add(tab_comm, text="通信")
        top_controls.add(tab_scan, text="扫描")
        top_controls.add(tab_analysis, text="分析")
        top_controls.add(tab_style, text="图表")

        tk.Label(tab_comm, text="端口").grid(row=0, column=0, sticky="w")
        self.cb_ports = ttk.Combobox(tab_comm, width=12)
        self.cb_ports.grid(row=1, column=0, padx=(0, 8))
        tk.Button(tab_comm, text="刷新端口", command=self.refresh_ports).grid(row=1, column=1, padx=(0, 12))

        tk.Label(tab_comm, text="波特率").grid(row=0, column=2, sticky="w")
        self.entry_baud = tk.Entry(tab_comm, width=10)
        self.entry_baud.insert(0, "57600")
        self.entry_baud.grid(row=1, column=2, padx=(0, 8))

        tk.Label(tab_comm, text="设备型号").grid(row=0, column=3, sticky="w")
        self.cb_model = ttk.Combobox(tab_comm, values=["NWT150/500/1000", "NWT3000/4000/6000 (x10)"], state="readonly", width=26)
        self.cb_model.current(1)
        self.cb_model.grid(row=1, column=3, padx=(0, 8))

        self.btn_connect = tk.Button(tab_comm, text="打开串口", command=self.toggle_connection, bg="#dddddd", width=12)
        self.btn_connect.grid(row=1, column=4, padx=(0, 8))
        self.btn_detect = tk.Button(tab_comm, text="一键排错探测", command=self.start_auto_detect, width=12)
        self.btn_detect.grid(row=1, column=5)

        tk.Label(tab_scan, text="起始频率(Hz)").grid(row=0, column=0, sticky="w")
        self.entry_start = tk.Entry(tab_scan, width=14)
        self.entry_start.insert(0, "1000000")
        self.entry_start.bind("<Return>", self.on_freq_entry_return)
        self.entry_start.bind("<FocusOut>", self.on_freq_entry_return)
        self.entry_start.grid(row=1, column=0, padx=(0, 8))

        tk.Label(tab_scan, text="终止频率(Hz)").grid(row=0, column=1, sticky="w")
        self.entry_stop = tk.Entry(tab_scan, width=14)
        self.entry_stop.insert(0, "30000000")
        self.entry_stop.bind("<Return>", self.on_freq_entry_return)
        self.entry_stop.bind("<FocusOut>", self.on_freq_entry_return)
        self.entry_stop.grid(row=1, column=1, padx=(0, 8))

        tk.Label(tab_scan, text="点数").grid(row=0, column=2, sticky="w")
        self.entry_steps = tk.Entry(tab_scan, width=8)
        self.entry_steps.insert(0, "500")
        self.entry_steps.grid(row=1, column=2, padx=(0, 8))

        tk.Label(tab_scan, text="系数(dB/ADC)").grid(row=0, column=3, sticky="w")
        self.entry_y_scale = tk.Entry(tab_scan, width=8)
        self.entry_y_scale.insert(0, "0.7")
        self.entry_y_scale.grid(row=1, column=3, padx=(0, 8))

        tk.Label(tab_scan, text="补偿(dBm)").grid(row=0, column=4, sticky="w")
        self.entry_y_offset = tk.Entry(tab_scan, width=8)
        self.entry_y_offset.insert(0, "-250.0")
        self.entry_y_offset.grid(row=1, column=4, padx=(0, 8))

        self.chk_cont = tk.Checkbutton(tab_scan, text="连续扫描", variable=self.continuous_var)
        self.chk_cont.grid(row=1, column=5, padx=(0, 8))

        self.btn_start = tk.Button(tab_scan, text="开始扫描", command=self.start_sweep, bg="green", fg="white", font=("Arial", 11, "bold"), state=tk.DISABLED)
        self.btn_start.grid(row=1, column=6, padx=(0, 6))
        self.btn_stop = tk.Button(tab_scan, text="停止", command=self.stop_sweep, bg="red", fg="white", state=tk.DISABLED)
        self.btn_stop.grid(row=1, column=7, padx=(0, 6))

        self.progress = ttk.Progressbar(tab_scan, orient=tk.HORIZONTAL, length=240, mode="determinate")
        self.progress.grid(row=2, column=0, columnspan=8, sticky="we", pady=(8, 0))

        self.btn_save_trace = tk.Button(tab_analysis, text="固定当前曲线", command=self.save_trace_to_plot, bg="#d9ead3")
        self.btn_save_trace.grid(row=0, column=0, padx=(0, 8), pady=2)
        self.btn_clear_traces = tk.Button(tab_analysis, text="清除所有固定曲线", command=self.clear_all_traces)
        self.btn_clear_traces.grid(row=0, column=1, padx=(0, 8), pady=2)
        self.btn_save_bg = tk.Button(tab_analysis, text="保存当前为参考底噪", command=self.save_as_background)
        self.btn_save_bg.grid(row=0, column=2, padx=(0, 8), pady=2)
        self.btn_export_csv = tk.Button(tab_analysis, text="导出CSV数据", command=self.export_csv)
        self.btn_export_csv.grid(row=0, column=3, padx=(0, 8), pady=2)
        self.btn_import_csv = tk.Button(tab_analysis, text="导入CSV到绘图板", command=self.import_csv)
        self.btn_import_csv.grid(row=0, column=4, padx=(0, 8), pady=2)
        self.btn_reset_cache = tk.Button(tab_analysis, text="重置参数与缓存", command=self.reset_all_settings, bg="#fce5cd")
        self.btn_reset_cache.grid(row=0, column=5, padx=(0, 8), pady=2)

        self.chk_use_bg = tk.Checkbutton(tab_analysis, text="扣除底噪", variable=self.use_bg_var, command=self.replot_data)
        self.chk_use_bg.grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.chk_smooth = tk.Checkbutton(tab_analysis, text="平滑曲线", variable=self.use_smooth_var, command=self.replot_data)
        self.chk_smooth.grid(row=1, column=1, sticky="w", padx=(0, 8))
        self.chk_show_scan = tk.Checkbutton(tab_analysis, text="显示当前扫描曲线", variable=self.show_scan_var, command=self.replot_data)
        self.chk_show_scan.grid(row=1, column=2, sticky="w", padx=(0, 8))

        tk.Label(tab_style, text="字体").grid(row=0, column=0, sticky="w")
        self.cb_plot_font = ttk.Combobox(tab_style, values=self.font_family_options, state="readonly", width=18)
        self.cb_plot_font.set(self.plot_font_family)
        self.cb_plot_font.grid(row=1, column=0, padx=(0, 10))
        self.cb_plot_font.bind("<<ComboboxSelected>>", self.apply_plot_style)

        tk.Label(tab_style, text="轴标题字号").grid(row=0, column=1, sticky="w")
        self.entry_label_font_size = tk.Entry(tab_style, width=6)
        self.entry_label_font_size.insert(0, str(self.plot_label_size))
        self.entry_label_font_size.grid(row=1, column=1, padx=(0, 10))

        tk.Label(tab_style, text="刻度字号").grid(row=0, column=2, sticky="w")
        self.entry_tick_font_size = tk.Entry(tab_style, width=6)
        self.entry_tick_font_size.insert(0, str(self.plot_tick_size))
        self.entry_tick_font_size.grid(row=1, column=2, padx=(0, 10))

        self.entry_label_font_size.bind("<Return>", self.apply_plot_style)
        self.entry_label_font_size.bind("<FocusOut>", self.apply_plot_style)
        self.entry_tick_font_size.bind("<Return>", self.apply_plot_style)
        self.entry_tick_font_size.bind("<FocusOut>", self.apply_plot_style)
        tk.Button(tab_style, text="应用字体设置", command=self.apply_plot_style).grid(row=1, column=3, padx=(0, 10))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        self.tab_plot = tk.Frame(self.notebook, bg="white")
        self.tab_record = tk.Frame(self.notebook, bg="#f9f9f9")
        self.tab_log = tk.Frame(self.notebook, bg="#f9f9f9")

        self.notebook.add(self.tab_plot, text="扫频图表视图")
        self.notebook.add(self.tab_record, text="实验数据记录")
        self.notebook.add(self.tab_log, text="运行日志")
        
        # === 扫频图表视图 ===
        self.fig = Figure(figsize=(6, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("")
        self.ax.set_xlabel("Frequency (MHz)")
        self.ax.set_ylabel("Amplitude (dBm)")
        self.ax.grid(True)
        self.apply_plot_style(redraw=False)
        
        self.line, = self.ax.plot([], [], "b-", linewidth=1.2)
        self.min_point_marker, = self.ax.plot([], [], "ro", markersize=8, label="Lowest Point")
        self.cursor_marker, = self.ax.plot([], [], "gx", markersize=10, mew=2)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.tab_plot)
        self.canvas.draw()
        
        self.canvas.mpl_connect("button_press_event", self.on_plot_click)
        
        toolbar = NavigationToolbar2Tk(self.canvas, self.tab_plot)
        toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.trace_manager_frame = tk.Frame(self.tab_plot, bg="white")
        self.trace_manager_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)

        status_frame = tk.Frame(self.tab_plot, bg="#f5f5f5")
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.lbl_resonance = tk.Label(status_frame, text="等待扫描...", font=("Arial", 11, "bold"), fg="#1f497d", bg="#f5f5f5", pady=4)
        self.lbl_resonance.pack(side=tk.LEFT, padx=8)
        self.lbl_cursor = tk.Label(status_frame, text="点击图表任意位置取点", font=("Arial", 9), fg="gray", bg="#f5f5f5")
        self.lbl_cursor.pack(side=tk.RIGHT, padx=8)

        # === 实验记录视图 ===
        top_bar = tk.Frame(self.tab_record, pady=10, padx=10, bg="#f9f9f9")
        top_bar.pack(fill=tk.X)

        tk.Label(top_bar, text="实验名称:", bg="#f9f9f9").pack(side=tk.LEFT)
        self.entry_exp_name = tk.Entry(top_bar, width=20)
        self.entry_exp_name.insert(0, "未命名实验")
        self.entry_exp_name.pack(side=tk.LEFT, padx=5)

        self.btn_start_exp = tk.Button(top_bar, text="开始记录", command=self.toggle_experiment, bg="#d9ead3")
        self.btn_start_exp.pack(side=tk.LEFT, padx=10)

        self.btn_next_group = tk.Button(top_bar, text="进入下一组", command=self.next_group, state=tk.DISABLED)
        self.btn_next_group.pack(side=tk.LEFT, padx=5)

        self.lbl_exp_status = tk.Label(top_bar, text="尚未开始", fg="gray", bg="#f9f9f9")
        self.lbl_exp_status.pack(side=tk.LEFT, padx=10)

        self.btn_export_exp = tk.Button(top_bar, text="导出实验数据(CSV)", command=self.export_experiment_csv)
        self.btn_export_exp.pack(side=tk.RIGHT, padx=5)

        columns = ("Group", "Scan", "ResonanceFreq", "ValleyAmp", "QFactor", "InvQFactor")
        self.tree_exp = ttk.Treeview(self.tab_record, columns=columns, show="headings", height=20)
        self.tree_exp.heading("Group", text="分组 (Group)")
        self.tree_exp.heading("Scan", text="扫描序号 (Scan#)")
        self.tree_exp.heading("ResonanceFreq", text="谐振频率 (MHz)")
        self.tree_exp.heading("ValleyAmp", text="谷点幅度 (dB/dBm)")
        self.tree_exp.heading("QFactor", text="Q值")
        self.tree_exp.heading("InvQFactor", text="1/Q值")

        self.tree_exp.column("Group", width=80, anchor=tk.CENTER)
        self.tree_exp.column("Scan", width=80, anchor=tk.CENTER)
        self.tree_exp.column("ResonanceFreq", width=120, anchor=tk.CENTER)
        self.tree_exp.column("ValleyAmp", width=120, anchor=tk.CENTER)
        self.tree_exp.column("QFactor", width=100, anchor=tk.CENTER)
        self.tree_exp.column("InvQFactor", width=100, anchor=tk.CENTER)
        
        self.tree_exp.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.txt_log = tk.Text(self.tab_log, height=8, state=tk.DISABLED, font=("Consolas", 9))
        self.txt_log.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.create_menu_bar()

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [p.device for p in ports]
        self.cb_ports["values"] = port_list
        if "COM6" in port_list:
            self.cb_ports.current(port_list.index("COM6"))
        elif port_list:
            self.cb_ports.current(0)

    def on_freq_entry_return(self, event=None):
        entry = getattr(event, "widget", event) if hasattr(event, "widget") else event
        if not entry: return
        try: raw_text = entry.get().strip().lower()
        except tk.TclError: return 
        if not raw_text: return

        multiplier = 1
        num_part = raw_text
        for suffix, mult in zip(['k', 'm', 'g'], [1e3, 1e6, 1e9]):
            if raw_text.endswith(suffix):
                multiplier = mult
                num_part = raw_text[:-1]
                break
        
        try:
            hz_val = int(float(num_part) * multiplier)
            if str(hz_val) != entry.get():
                entry.delete(0, tk.END)
                entry.insert(0, str(hz_val))
        except ValueError: pass

    def toggle_connection(self):
        if not self.inst.is_connected:
            self.inst.multiplier = 10 if "x10" in self.cb_model.get() else 1
            port = self.cb_ports.get()
            try: baud = int(self.entry_baud.get())
            except ValueError: messagebox.showerror("错误", "波特率必须是整数"); return
            if not port: return

            success, msg = self.inst.connect(port, baud)
            if success:
                self.btn_connect.config(text="关闭串口", bg="#ffcccc")
                self.btn_start.config(state=tk.NORMAL)
            else: messagebox.showerror("连接失败", msg)
        else:
            self.stop_sweep()
            self.inst.disconnect()
            self.btn_connect.config(text="打开串口", bg="#dddddd")
            self.btn_start.config(state=tk.DISABLED)

    def save_as_background(self):
        if not self.current_x_data or not self.current_y_data:
            messagebox.showwarning("提示", "请先完成一次扫频以取得数据。")
            return
        self.bg_x_data = list(self.current_x_data)
        self.bg_y_data = list(self.current_y_data)
        self.log_message(f"已保存 {len(self.bg_y_data)} 个点作为参考底噪！")
        messagebox.showinfo("成功", "已保存底噪参考。现在勾选【扣除底噪】即可呈现干净的相对增益特征。")

    def save_trace_to_plot(self):
        if not self.current_x_data or not self.current_y_data:
            messagebox.showwarning("提示", "当前没有可以固定的曲线数据。")
            return
            
        p_y = self._apply_plot_options(self.current_y_data, self.current_x_data)

        if getattr(self, 'is_experimenting', False):
            trace_key = f"Group {self.current_group}"
            label_text = f"实验 {self.current_group}"
        else:
            if not hasattr(self, 'manual_trace_count'):
                self.manual_trace_count = 0
            self.manual_trace_count += 1
            trace_key = f"Manual {self.manual_trace_count}"
            label_text = f"临时固留 {self.manual_trace_count}"

        if trace_key in self.saved_traces:
            old_trace = self.saved_traces[trace_key]
            try:
                if 'line' in old_trace and old_trace['line'] in self.ax.lines:
                    old_trace['line'].remove()
            except Exception:
                pass
            color = old_trace['color']
            self.log_message(f"已更新覆盖 {trace_key} 的固定图像！")
        else:
            color = self.colors[len(self.saved_traces) % len(self.colors)]
            var = tk.BooleanVar(value=True)
            self.trace_vars[trace_key] = var
            chk = tk.Checkbutton(self.trace_manager_frame, text=label_text, variable=var, 
                                 command=self.update_traces_visibility, fg=color, bg="white", font=("Arial", 9, "bold"))
            chk.pack(side=tk.LEFT, padx=5)
            self.trace_chks[trace_key] = chk
            self.log_message(f"固定了新图层：{trace_key}")
            
        # 画在图上
        line, = self.ax.plot(self.current_x_data, p_y, color=color, linewidth=1.5, linestyle='--', alpha=0.9)
        self.saved_traces[trace_key] = {
            'x': list(self.current_x_data),
            'y': list(p_y),
            'line': line,
            'color': color
        }
        
        # 强制更新一下 canvas
        self.canvas.draw_idle()

    def update_traces_visibility(self):
        for key, trace in self.saved_traces.items():
            if key in self.trace_vars and 'line' in trace and trace['line'] in self.ax.lines:
                trace['line'].set_visible(self.trace_vars[key].get())
        self.canvas.draw_idle()

    def clear_all_traces(self):
        for trace in self.saved_traces.values():
            try:
                if 'line' in trace and trace['line'] in self.ax.lines:
                    trace['line'].remove()
            except Exception:
                pass
        self.saved_traces.clear()
        
        if hasattr(self, 'trace_chks'):
            for chk in self.trace_chks.values():
                chk.destroy()
            self.trace_chks.clear()
        
        if hasattr(self, 'trace_vars'):
            self.trace_vars.clear()
        
        if hasattr(self, 'manual_trace_count'):
            self.manual_trace_count = 0
            
        self.canvas.draw_idle()
        self.log_message("已清除所有固定波形！")

    def export_csv(self):
        if not self.current_x_data: return
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV 文件", "*.csv")])
        if not filepath: return
        try:
            self._write_scan_csv(filepath, self.current_x_data, self.current_y_data)
            self.log_message(f"数据导出成功: {filepath}")
        except Exception as e: messagebox.showerror("错误", str(e))

    def import_csv(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filepath:
            return

        try:
            x_data = []
            y_data = []
            with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                    reader = csv.reader(f, dialect)
                except csv.Error:
                    reader = csv.reader(f)

                for row in reader:
                    if len(row) < 2:
                        continue
                    try:
                        x = float(str(row[0]).strip())
                        y = float(str(row[1]).strip())
                    except ValueError:
                        # Skip header/invalid rows.
                        continue
                    x_data.append(x)
                    y_data.append(y)

            if len(x_data) < 2:
                raise ValueError("CSV has fewer than 2 valid data points.")

            self.current_x_data = x_data
            self.current_y_data = y_data
            self.cursor_marker.set_data([], [])
            self.lbl_cursor.config(text="Click chart to inspect point", fg="gray")
            self.update_plot_data(self.current_x_data, self.current_y_data)
            self.log_message(f"CSV imported: {filepath} ({len(x_data)} points)")
        except Exception as e:
            messagebox.showerror("Import failed", str(e))

    def on_plot_click(self, event):
        if event.inaxes != self.ax or not self.current_x_data: return
        cx, cy = event.xdata, event.ydata
        idx = min(range(len(self.current_x_data)), key=lambda i: abs(self.current_x_data[i] - cx))
        ax = self.current_x_data[idx]
        ay = self.current_y_data[idx]
        bg_aligned = self._get_aligned_bg_for_x(self.current_x_data)
        if self.use_bg_var.get() and bg_aligned and idx < len(bg_aligned):
            ay -= bg_aligned[idx]
            
        self.cursor_marker.set_data([ax], [ay])
        self.lbl_cursor.config(text=f"选点: {ax:.3f} MHz, {ay:.2f} dB", fg="#006400")
        self.canvas.draw_idle()

    def replot_data(self):
        self.ax.set_ylabel("Relative Magnitude (dB)" if self.use_bg_var.get() else "Amplitude (dBm)")
        if self.current_x_data:
            self.update_plot_data(self.current_x_data, self.current_y_data)

    def apply_plot_style(self, event=None, redraw=True):
        if not hasattr(self, "ax"):
            return

        try:
            label_size = int(self.entry_label_font_size.get())
            tick_size = int(self.entry_tick_font_size.get())
            if label_size <= 0 or tick_size <= 0:
                raise ValueError
            self.plot_label_size = label_size
            self.plot_tick_size = tick_size
        except ValueError:
            self.log_message("字体字号无效，需为正整数")
            return

        self.plot_font_family = self.cb_plot_font.get().strip() or self.plot_font_family

        self.ax.xaxis.label.set_fontname(self.plot_font_family)
        self.ax.yaxis.label.set_fontname(self.plot_font_family)
        self.ax.xaxis.label.set_fontsize(self.plot_label_size)
        self.ax.yaxis.label.set_fontsize(self.plot_label_size)
        self.ax.title.set_fontname(self.plot_font_family)
        self.ax.title.set_fontsize(self.plot_label_size)
        self.ax.set_title("")

        for tick_label in self.ax.get_xticklabels() + self.ax.get_yticklabels():
            tick_label.set_fontname(self.plot_font_family)
            tick_label.set_fontsize(self.plot_tick_size)

        if redraw:
            self.canvas.draw_idle()

    def _get_aligned_bg_for_x(self, x_data):
        if not x_data or not self.bg_y_data:
            return None

        # Backward compatibility: old cache may only contain bg_y_data.
        if not self.bg_x_data:
            if len(self.bg_y_data) == len(x_data):
                return list(self.bg_y_data)
            if len(self.bg_y_data) >= 2:
                n_src = len(self.bg_y_data) - 1
                n_dst = len(x_data) - 1
                if n_dst <= 0:
                    return [self.bg_y_data[0]]
                aligned = []
                for i in range(len(x_data)):
                    pos = (i * n_src) / n_dst
                    left = int(pos)
                    right = min(left + 1, n_src)
                    ratio = pos - left
                    y1 = self.bg_y_data[left]
                    y2 = self.bg_y_data[right]
                    aligned.append(y1 + ratio * (y2 - y1))
                return aligned
            return None

        if len(self.bg_x_data) != len(self.bg_y_data):
            return None

        bg_x = self.bg_x_data
        bg_y = self.bg_y_data
        if len(bg_x) >= 2 and bg_x[0] > bg_x[-1]:
            bg_x = list(reversed(bg_x))
            bg_y = list(reversed(bg_y))

        if len(bg_x) == len(x_data) and all(
            abs(bx - x) < 1e-12 for bx, x in zip(bg_x, x_data)
        ):
            return list(bg_y)

        # Interpolate background onto target x-axis.
        if len(bg_x) == 1:
            return [bg_y[0] for _ in x_data]

        aligned = []
        for x in x_data:
            if x <= bg_x[0]:
                aligned.append(bg_y[0])
                continue
            if x >= bg_x[-1]:
                aligned.append(bg_y[-1])
                continue

            right = bisect.bisect_left(bg_x, x)
            left = right - 1
            x1, x2 = bg_x[left], bg_x[right]
            y1, y2 = bg_y[left], bg_y[right]
            if x2 == x1:
                aligned.append(y1)
            else:
                ratio = (x - x1) / (x2 - x1)
                aligned.append(y1 + ratio * (y2 - y1))
        return aligned

    def _apply_plot_options(self, y_data, x_data=None):
        processed_y = list(y_data)
        target_x = x_data if x_data is not None else self.current_x_data
        bg_aligned = self._get_aligned_bg_for_x(target_x)
        if self.use_bg_var.get() and bg_aligned and len(bg_aligned) == len(processed_y):
            processed_y = [y - bg for y, bg in zip(y_data, bg_aligned)]
        if self.use_smooth_var.get():
            processed_y = self.smooth_data(processed_y, window_size=5)
        return processed_y

    def _read_sweep_params(self):
        try:
            return (
                int(self.entry_start.get()),
                int(self.entry_stop.get()),
                int(self.entry_steps.get()),
                float(self.entry_y_offset.get()),
                float(self.entry_y_scale.get()),
            )
        except ValueError:
            messagebox.showerror("错误", "参数格式错误")
            return None

    def _build_sweep_worker(self, params, quiet_log=False):
        start_f, stop_f, steps, y_offset, y_scale = params
        return SweepWorker(
            self.inst,
            start_f,
            stop_f,
            steps,
            y_offset,
            y_scale,
            data_callback=self._handle_sweep_data,
            progress_callback=self.update_progress,
            finished_callback=self.on_sweep_finished,
            log_callback=(lambda _m: None) if quiet_log else self.log_message
        )

    def _write_scan_csv(self, filepath, x_data, y_data):
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Frequency(MHz)", "Amplitude(dBm)"])
            for x, y in zip(x_data, y_data):
                w.writerow([f"{x:.6f}", f"{y:.2f}"])

    def start_sweep(self):
        self.on_freq_entry_return(self.entry_start)
        self.on_freq_entry_return(self.entry_stop)

        params = self._read_sweep_params()
        if not params:
            return

        if not self.inst.is_connected:
            return

        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.progress["value"] = 0
        self.lbl_resonance.config(text="扫描中...", fg="gray")
        
        self.interrupted_sweep = False
        self.is_continuous_running = self.continuous_var.get()
        self.continuous_session_min_y = float('inf')
        self.continuous_session_min_x = 0
        
        self.ax.clear()
        self.ax.set_title("")
        self.ax.set_xlabel("Frequency (MHz)")
        self.ax.set_ylabel("Relative Magnitude (dB)" if self.use_bg_var.get() else "Amplitude (dBm)")
        
        if self.use_bg_var.get():
            self.ax.set_ylim(-50, 10)
            self.ax.axhline(0, color="black", linewidth=1, linestyle="--")
        else:
            self.ax.set_ylim(-80, 10)
            self.ax.set_yticks(range(-80, 11, 10))
            
        self.ax.grid(True, which="major", linestyle="-", linewidth=0.8, color="gray")
        self.apply_plot_style(redraw=False)
        
        # 恢复保存的对比曲线
        for trace_key, trace in self.saved_traces.items():
            if trace_key not in self.trace_vars:
                continue
            line, = self.ax.plot(trace['x'], trace['y'], color=trace['color'], linewidth=1.2, linestyle='--', alpha=0.8)
            trace['line'] = line
            line.set_visible(self.trace_vars[trace_key].get())

        self.line, = self.ax.plot([], [], "b-", linewidth=1.2)
        self.min_point_marker, = self.ax.plot([], [], "ro", markersize=7)
        self.cursor_marker, = self.ax.plot([], [], "gx", markersize=9)
        self.canvas.draw()

        self.sweep_thread = self._build_sweep_worker(params)
        self.sweep_thread.start()

    def stop_sweep(self):
        self.is_continuous_running = False
        self.interrupted_sweep = True
        if self.sweep_thread and getattr(self.sweep_thread, 'is_alive', lambda: False)():
            self.sweep_thread.stop()

    def calculate_q_factor(self, x_data, y_data, min_idx):
        if not x_data or not y_data or min_idx < 0 or min_idx >= len(y_data):
            return 0.0
            
        min_y = y_data[min_idx]
        target_y = min_y + 3.0
        
        f_L = None
        for i in range(min_idx, 0, -1):
            if y_data[i] <= target_y <= y_data[i-1]:
                ratio = (target_y - y_data[i]) / (y_data[i-1] - y_data[i]) if y_data[i-1] != y_data[i] else 0
                f_L = x_data[i] - ratio * (x_data[i] - x_data[i-1])
                break
                
        f_R = None
        for i in range(min_idx, len(y_data)-1):
            if y_data[i] <= target_y <= y_data[i+1]:
                ratio = (target_y - y_data[i]) / (y_data[i+1] - y_data[i]) if y_data[i+1] != y_data[i] else 0
                f_R = x_data[i] + ratio * (x_data[i+1] - x_data[i])
                break
                
        if f_L is not None and f_R is not None:
            bw = f_R - f_L
            if bw > 0:
                return x_data[min_idx] / bw
        return 0.0

    def update_plot_data(self, x_data, y_data):
        p_y = self._apply_plot_options(y_data, x_data)

        self.line.set_xdata(x_data)
        self.line.set_ydata(p_y)
        
        # 控制当前扫描曲线及最低点标记的显示状态
        show_scan = getattr(self, 'show_scan_var', None) is None or self.show_scan_var.get()
        self.line.set_visible(show_scan)

        if len(x_data) > 1:
            self.ax.set_xlim(min(x_data), max(x_data))
            
            # 动态扩展Y轴边界
            min_y, max_y = min(p_y), max(p_y)
            curr_ymin, curr_ymax = self.ax.get_ylim()
            if min_y < curr_ymin or max_y > curr_ymax:
                self.ax.set_ylim(min(curr_ymin, min_y - 5), max(curr_ymax, max_y + 5))

            midx = min(range(len(p_y)), key=p_y.__getitem__)
            mx, my = x_data[midx], p_y[midx]
            self.min_point_marker.set_data([mx], [my])
            self.min_point_marker.set_visible(show_scan)
            
            q_val = self.calculate_q_factor(x_data, p_y, midx)
            q_str = f"{q_val:.1f}" if q_val > 0 else "N/A"
            inv_q_str = f"{1.0/q_val:.4f}" if q_val > 0 else "N/A"
            self.lbl_resonance.config(text=f"★ 谐振频率: {mx:.3f} MHz\n谷点幅度: {my:.2f} dB, Q值: {q_str}, 1/Q: {inv_q_str}", fg="#c00000")

        self.apply_plot_style(redraw=False)
        self.canvas.draw_idle()

    def _handle_sweep_data(self, x_data, y_data):
        # 放到主线程中执行，防止后台线程直接操作GUI导致更新延迟、卡顿或偶尔崩溃而疯狂重试
        self.after(0, lambda: self._process_sweep_data_ui(x_data, y_data))

    def _process_sweep_data_ui(self, x_data, y_data):
        self.current_x_data = x_data
        self.current_y_data = y_data
        
        self.update_plot_data(x_data, y_data)

        if getattr(self, 'is_experimenting', False) and len(x_data) > 1 and not getattr(self, 'interrupted_sweep', False):
            p_y = self._apply_plot_options(y_data, x_data)

            midx = min(range(len(p_y)), key=p_y.__getitem__)
            mx, my = x_data[midx], p_y[midx]
            q_val = self.calculate_q_factor(x_data, p_y, midx)

            if getattr(self, 'is_continuous_running', False):
                if my < getattr(self, 'continuous_session_min_y', float('inf')):
                    self.continuous_session_min_y = my
                    self.continuous_session_min_x = mx
                    self.record_sweep_result(mx, my, q_val)
            else:
                self.record_sweep_result(mx, my, q_val)

    def update_progress(self, percent):
        self.after(0, lambda: self.progress.configure(value=percent))

    def on_sweep_finished(self):
        # 如果还在连续扫描状态，并且没有手动停止
        if getattr(self, 'is_continuous_running', False):
            # 增加充分的延迟(由0改为500ms)，确保收到完整信息且UI渲染完成后再发起下一次，避免不断狂发请求
            self.after(500, self._restart_sweep_worker)
        else:
            self.after(0, lambda: [self.btn_start.config(state=tk.NORMAL), self.btn_stop.config(state=tk.DISABLED)])
            # 新增：如果是实验中且停止了扫描，自动固定并保存曲线
            if getattr(self, 'is_experimenting', False):
                self.after(100, self.auto_fix_and_save)

    def auto_fix_and_save(self):
        if not self.current_x_data or not self.current_y_data:
            return
            
        # 1. 自动固定当前曲线
        self.save_trace_to_plot()
        
        # 2. 自动保存扫描数据(CSV)并按照要求命名
        exp_name = self.entry_exp_name.get().strip() or "未命名实验"
        group_str = f"组别{self.current_group}"
        # 删除时间戳，确保同一组实验的文件被不断覆盖
        filename = f"{exp_name}_{group_str}.csv"
        filepath = os.path.join(os.getcwd(), filename)
        
        try:
            self._write_scan_csv(filepath, self.current_x_data, self.current_y_data)
            self.log_message(f"已自动保存/更新数据至: {filename}")
        except Exception as e:
            self.log_message(f"自动保存数据失败: {e}")
            
    def _restart_sweep_worker(self):
        # 若在延迟期间被停止了，就放弃重启
        if not getattr(self, 'is_continuous_running', False):
            self.on_sweep_finished()
            return
            
        try:
            params = self._read_sweep_params()
            if not params:
                self.stop_sweep()
                return

            # 不再传递log_callback以避免日志疯狂刷屏
            self.sweep_thread = self._build_sweep_worker(params, quiet_log=True)
            self.sweep_thread.start()
        except Exception:
            self.stop_sweep()

    def start_auto_detect(self):
        if not self.cb_ports.get(): return
        self.btn_detect.config(state=tk.DISABLED, text="探测中...")
        if self.inst.is_connected: self.toggle_connection()
        self.detect_thread = threading.Thread(target=self._auto_detect_worker, args=(self.cb_ports.get(),))
        self.detect_thread.daemon = True
        self.detect_thread.start()

    def _auto_detect_worker(self, port):
        found = None
        for baud in [57600, 115200, 38400, 9600]:
            try:
                ser = serial.Serial(port, baud, timeout=0.1)
                ser.write(b"\x8fv"); time.sleep(0.05)
                if ser.read(100): found = baud
                ser.close()
                if found: break
            except: pass
        self.after(0, lambda: self._report_detect(found))

    def _report_detect(self, found):
        self.btn_detect.config(state=tk.NORMAL, text="一键排错探测")
        if found:
            self.entry_baud.delete(0, tk.END); self.entry_baud.insert(0, str(found))
            messagebox.showinfo("成功", f"找到设备，波特率 {found}")
        else: messagebox.showwarning("失败", "未找到设备响应。")

    def on_close(self):
        self.save_config()
        self.stop_sweep()
        self.inst.disconnect()
        self.destroy()

    # ================= 实验记录平台逻辑 =================
    def toggle_experiment(self):
        if not hasattr(self, 'is_experimenting'):
            self.is_experimenting = False
            
        if not self.is_experimenting:
            self.is_experimenting = True
            self.current_group = 1
            self.scan_count_in_group = 0
            self.experiment_data = [] 
            for item in self.tree_exp.get_children():
                self.tree_exp.delete(item)
            
            self.btn_start_exp.config(text="结束实验", bg="#f4cccc")
            self.btn_next_group.config(state=tk.NORMAL)
            self.lbl_exp_status.config(text=f"记录中 (组 1)", fg="blue")
            self.entry_exp_name.config(state=tk.DISABLED)
            
            # 自动切换到记录选项卡看到清空动作
            self.notebook.select(self.tab_record)
        else:
            if not messagebox.askyesno("确认操作", "确定要结束当前实验吗？\n如果尚未导出综合数据，请先导出。"):
                return
            self.is_experimenting = False
            self.btn_start_exp.config(text="开始实验", bg="#d9ead3")
            self.btn_next_group.config(state=tk.DISABLED)
            self.lbl_exp_status.config(text="实验已结束", fg="green")
            self.entry_exp_name.config(state=tk.NORMAL)

    def next_group(self):
        if getattr(self, 'is_experimenting', False):
            self.current_group += 1
            self.scan_count_in_group = 0
            self.lbl_exp_status.config(text=f"记录中 (组 {self.current_group})", fg="blue")
            self.log_message(f"--- 实验记录进入第{self.current_group}组 ---")

    def record_sweep_result(self, res_x, res_y, res_q=0.0):
        if getattr(self, 'is_experimenting', False):
            self.scan_count_in_group += 1
            q_str = f"{res_q:.1f}" if res_q > 0 else "N/A"
            inv_q_str = f"{1.0/res_q:.6f}" if res_q > 0 else "N/A"
            self.tree_exp.insert("", "end", values=(
                f"Group {self.current_group}",
                self.scan_count_in_group,
                f"{res_x:.4f}",
                f"{res_y:.2f}",
                q_str,
                inv_q_str
            ))
            self.experiment_data.append({
                "Group": self.current_group,
                "Scan": self.scan_count_in_group,
                "ResonanceFreq_MHz": res_x,
                "Amplitude": res_y,
                "QFactor": res_q,
                "InvQFactor": 1.0/res_q if res_q > 0 else 0.0
            })
            
    def export_experiment_csv(self):
        if not hasattr(self, 'experiment_data') or not self.experiment_data:
            messagebox.showwarning("提示", "当前没有实验数据可以导出。")
            return
            
        exp_name = self.entry_exp_name.get()
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv", 
            initialfile=f"{exp_name}_结果.csv",
            filetypes=[("CSV 文件", "*.csv")]
        )
        if not filepath: return
        try:
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["Group", "Scan Number", "Resonance Frequency (MHz)", "Amplitude(dB)", "Q Factor", "1/Q Factor"])
                for row in self.experiment_data:
                    q_val = row.get("QFactor", 0)
                    q_str = f"{q_val:.1f}" if q_val > 0 else "N/A"
                    inv_q_val = row.get("InvQFactor", 0)
                    inv_q_str = f"{inv_q_val:.6f}" if inv_q_val > 0 else "N/A"
                    w.writerow([row["Group"], row["Scan"], f"{row['ResonanceFreq_MHz']:.6f}", f"{row['Amplitude']:.2f}", q_str, inv_q_str])
            self.log_message(f"实验数据已导出至 {filepath}")
            messagebox.showinfo("导出成功", "实验数据已成功保存为CSV表格。")
        except Exception as e: 
            messagebox.showerror("错误", str(e))

if __name__ == "__main__":
    app = App()
    app.mainloop()


