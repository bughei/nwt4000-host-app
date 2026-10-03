import serial
import serial.tools.list_ports
import threading
import time

# ==========================================
# 1. 仪器通信控制类 (负责与硬件交互)
# ==========================================
class NWTInstrument:
    """
    负责处理与 NWT 扫频仪的底层串口通信。
    遵循 NWT 标准协议。
    如果是 NWT3000/4000/6000 等，其控制字往往有倍率（multiplier），也就是将频率除以倍率后发送。
    """
    def __init__(self, log_callback=None):
        self.ser = None
        self.is_connected = False
        self.log = log_callback if log_callback else lambda msg: None
        self.multiplier = 10  # NWT4000/6000 系列必须固定为10倍率！

    def connect(self, port, baudrate=57600):
        """连接串口"""
        self.log(f"尝试连接串口: {port}, 波特率: {baudrate}...")
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=1.0,  # 读超时，防止卡死
                write_timeout=1.0
            )
            self.is_connected = True
            self.log(f"串口 {port} 连接成功")
            return True, "连接成功"
        except Exception as e:
            self.is_connected = False
            self.log(f"串口连接失败: {str(e)}")
            return False, str(e)

    def disconnect(self):
        """断开串口"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.log("串口已关闭")
        self.is_connected = False

    def set_frequency(self, freq_hz):
        """
        设置单点频率命令: 0x8F + 'f' + 9位频率字符 (含倍率处理)
        """
        if not self.is_connected:
            self.log("错误: 尝试发送频率但串口未连接")
            return
        
        cmd_val = int(freq_hz / self.multiplier)
        cmd_str = "f{:09d}".format(cmd_val)

        try:
            self.ser.write(b'\x8f' + cmd_str.encode('ascii'))
        except Exception as e:
            self.log(f"发送频率指令异常: {e}")
        
        time.sleep(0.005) 

    def read_signal_strength(self):
        """
        单点读取信号强度。
        经过抓包分析，目前暂留该接口。实际扫频应使用高速硬件扫频(x命令)。
        """
        if not self.is_connected:
            return 0

        try:
            self.ser.reset_input_buffer()
            self.ser.write(b'\x8fe') 
            raw_data = self.ser.readline()
            if raw_data:
                try:
                    str_val = raw_data.decode('ascii', errors='ignore').strip()
                    if not str_val:
                        return 0
                    return int(str_val)
                except ValueError:
                    return 0
            return 0
        except Exception as e:
            self.log(f"读取信号强度IO异常: {e}")
            return 0

    def start_hardware_sweep(self, start_f, stop_f, points):
        """
        发送硬件高速扫频指令 0x8F + 'x' + <9位起始频> + <8位步长> + <4位点数>
        注意在 NWT6000 (x10) 中：起始频率除以10，而步长不除以10。
        """
        if not self.is_connected:
            return False

        try:
            # 1. 计算参数
            start_val = min(int(start_f / self.multiplier), 999999999)
            
            if points > 1:
                # 重要修复：NWT6000硬件的起步频率和步进频率都会在下位机内部被乘以倍率（10倍）。
                # 因此发送给硬件之前，两者都必须除以 self.multiplier ，以保证协议命令长度和物理步长正确！
                step_val = int(((stop_f - start_f) / self.multiplier) / (points - 1))
                # 防越界保护：如果单步步长大于 99999999，会导致字符串超出8位，引发下位机解析乱码！
                if step_val > 99999999:
                    step_val = 99999999
            else:
                step_val = 0
            
            # 最高支持4位点数，协议限制
            points_val = points
            if points_val > 9999:
                points_val = 9999
                
            cmd_str = f"x{start_val:09d}{step_val:08d}{points_val:04d}"
            
            self.log(f"下发扫频指令: {cmd_str}")
            # 发送前确保硬件不在发送陈旧数据
            self.ser.write(b'\x8fv')
            time.sleep(0.05)
            self.ser.reset_input_buffer()
            # 发送带 \x8f 前缀的命令
            self.ser.write(b'\x8f' + cmd_str.encode('ascii'))
            return True
            
        except Exception as e:
            self.log(f"下发扫频异常: {e}")
            return False

# ==========================================
# 2. 扫频工作线程 (负责后台逻辑)
# ==========================================
class SweepWorker(threading.Thread):
    """
    后台线程，执行扫频循环，避免阻塞 GUI。
    """
    def __init__(self, instrument, start_f, stop_f, steps, y_offset, y_scale, data_callback, progress_callback, finished_callback, log_callback=None):
        super().__init__()
        self.instrument = instrument
        self.start_f = start_f
        self.stop_f = stop_f
        self.steps = steps
        self.y_offset = y_offset
        self.y_scale = y_scale
        
        # 回调函数，用于向 GUI 传递数据
        self.data_callback = data_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
        self.log = log_callback if log_callback else lambda msg: None
        
        self._running = True  # 控制线程停止的标志

    def stop(self):
        self.log("正在停止扫描...")
        self._running = False
        try:
            self.instrument.ser.write(b'\x8fv')
            time.sleep(0.1)
            self.instrument.ser.reset_input_buffer()
        except:
            pass

    def run(self):
        """线程主逻辑 - 使用硬件连续高速扫频特性"""
        try:
            self.log(f"启动扫描任务: {self.start_f}-{self.stop_f}Hz, {self.steps}点")
            
            # 下发硬件配置扫频指令
            success = self.instrument.start_hardware_sweep(self.start_f, self.stop_f, self.steps)
            if not success:
                self.log("硬件扫频指令发送失败")
                self.finished_callback()
                return

            x_data = [] # 频率轴
            y_data = [] # 幅度轴 (dBm)
            
            # 频率步进用于重构 x 轴
            if self.steps <= 1:
                step_freq = 0
            else:
                step_freq = (self.stop_f - self.start_f) / (self.steps - 1)
            
            expected_bytes = self.steps * 4  # NWT6000 returns 4 bytes per point (CH1, CH2)
            received_bytes = bytearray()
            
            self.log(f"等待硬件连续返回数据, 期待 {expected_bytes} 字节...")
            
            try:
                # 增加串口读取时的容错时间
                self.instrument.ser.timeout = 5.0
                
                while self._running and len(received_bytes) < expected_bytes:
                    chunk = self.instrument.ser.read(expected_bytes - len(received_bytes))
                    if chunk:
                        received_bytes.extend(chunk)
                        percent = int((len(received_bytes) / expected_bytes) * 100)
                        self.progress_callback(percent)
                    else:
                        self.log("读取数据超时！可能是点数过多或扫频时间长")
                        break
            except Exception as e:
                self.log(f"接收硬件数据流异常: {e}")
                
            # 恢复默认短超时
            self.instrument.ser.timeout = 1.0
            
            # 解析数据
            if len(received_bytes) > 0:
                self.log(f"实际接收数据字节数: {len(received_bytes)}")
                
                pts_received = len(received_bytes) // 4  # 4 bytes per point

                for i in range(pts_received):
                    current_f = self.start_f + i * step_freq
                    x_data.append(current_f / 1e6)

                    # NWT6000: Byte 0,1 are CH1 (Log detector we want). Byte 2,3 are CH2
                    low_byte = received_bytes[i*4]
                    high_byte = received_bytes[i*4 + 1]
                    adc_value = low_byte + (high_byte << 8)
                    
                    # 应用用户设置的补偿值，将没有校准过的ADC相对值推高到合适区间
                    dbm = (adc_value * self.y_scale) + self.y_offset
                    if i == 0 or i == pts_received-1: self.log(f'Debug ADC[i]: adc={adc_value}, dbm={dbm}')
                    y_data.append(dbm)
                    
                # 发送到 GUI 更新图表
                self.data_callback(x_data, y_data)
                
            self.log("扫描任务完毕")
            self.finished_callback()
        except Exception as _e:
            self.log(f"扫频线程发生未捕获致命错误: {_e}")
            self.finished_callback()
