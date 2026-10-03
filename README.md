# NWT4000 上位机 (Python 版)

用于 NWT 系列扫频仪的桌面上位机，重点适配 NWT3000/4000/6000，支持串口通信、实时扫频绘图、谐振点分析、实验记录和 CSV 导入导出。

本次版本为 **v1.1.0**，更新内容见 [CHANGELOG.md](CHANGELOG.md)。

## 下载与运行

从 [v1.1.0 Release](https://github.com/bughei/nwt4000-host-app/releases/tag/v1.1.0) 下载：

- `NWT4000_monitoring.exe`：Windows 64 位单文件程序，无需安装 Python。
- `nwt4000-host-app-v1.1.0-win64.zip`：包含上述 EXE、说明、更新日志和构建信息。
- `SHA256SUMS.txt`：EXE 和 ZIP 的 SHA256 校验值。

双击 EXE 即可运行；ZIP 请先解压再运行。串口连接需要电脑已安装对应 USB-串口驱动。已在 Windows 11 64 位验证构建与程序启动；尚未完成 Windows 10 或连接实物仪器的复测。

核对下载文件：

```powershell
Get-FileHash .\NWT4000_monitoring.exe -Algorithm SHA256
```

将结果与 Release 的 `SHA256SUMS.txt` 比较。主分支已移除旧版 `dist/main.exe`，最新 EXE 请从 Release 下载。历史标签及其 Source code 压缩包仍可能包含旧版 `dist/main.exe`，它不代表最新程序。仓库内 `release/nwt4000-host-app-v1.0.0-win64.zip` 也是旧版产物；旧版仍可从 [v1.0.0 Release](https://github.com/bughei/nwt4000-host-app/releases/tag/v1.0.0) 获取。

## 主要功能

- 串口连接、刷新端口与自动探测。
- 实时扫频与连续扫描，支持 `k/m/g` 频率后缀，例如 `300m` 表示 300 MHz。
- 谐振谷点识别，显示谐振频率、Q 值和 1/Q。
- 固定多条曲线进行比较、参考底噪保存与扣除、滑动平均平滑。
- 扫频 CSV 导入导出、实验分组记录与实验汇总 CSV 导出。
- 扫描参数、图表样式和界面状态缓存。

## 使用说明

1. 在顶部“通信”页选择串口、波特率和设备型号，点击“打开串口”。无法连接时可使用“一键排错探测”。
2. 在“扫描”页设置起始频率、终止频率和点数。请确保终止频率大于起始频率，点数至少为 2，并使用仪器支持的频率范围。
3. 点击“开始扫描”；启用连续扫描后，可通过“停止扫描”结束。
4. 在“分析”页管理固定曲线、参考底噪、平滑和 CSV；也可从顶部“文件 / 设备 / 扫描 / 视图 / 工具”菜单执行相应操作。
5. 在“图表”页调整图表字体、坐标轴标签字号和刻度字号。此设置不改变菜单、按钮等界面文字的字号。
6. 下方“扫频图表视图 / 实验数据记录 / 运行日志”用于查看曲线、实验记录和日志；图表下方显示分析结果与取点信息。

## 源码运行

需要 Python 3.10+ 和 Tkinter。本次构建使用 Python 3.14.3，详细环境与校验值见 [BUILD_INFO.txt](BUILD_INFO.txt)。

```powershell
python -m pip install -r requirements.txt
python main.py
```

## 构建 Windows EXE

在 Windows 64 位环境的项目根目录执行：

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller==6.19.0
python -m PyInstaller --clean --noconfirm main.spec
Move-Item -LiteralPath .\dist\main.exe -Destination .\dist\NWT4000_monitoring.exe
```

`main.spec` 输出名称仍为 `main.exe`，发布时重命名为 `NWT4000_monitoring.exe`。构建前请自行保存已有构建产物。依赖允许较新版本，因此不同环境重新构建不保证产生相同的二进制校验值。

## 项目结构

- `main.py`：GUI、绘图、分析和实验记录。
- `nwt_driver.py`：串口协议与扫频线程。
- `main.spec`：PyInstaller 单文件、无控制台构建配置。
- `requirements.txt`：运行依赖。
- `CHANGELOG.md`：版本更新日志。
- `BUILD_INFO.txt`：v1.1.0 构建环境、源码和 EXE 校验值。
- `nwt_settings.json`：运行时在工作目录生成的本地配置，不纳入发布。

## 验证与已知限制

本次已完成语法、程序初始化、频率后缀、模拟谐振谷点 Q 计算、绘图和数据处理、CSV/配置、模拟串口协议，以及打包 EXE 启动和正常退出检查
串口被占用时请关闭占用程序并检查连接设置。遇到异常时，请通过 [Issues](https://github.com/bughei/nwt4000-host-app/issues) 提供软件版本、设备型号、扫描参数及运行日志，勿上传私密实验数据。
