# File Unlocker — 文件占用检测与解除工具

一款基于 Windows Restart Manager API 的轻量级文件占用检测与解除工具。使用纯标准库（`ctypes` + `tkinter`）实现，**运行时零第三方依赖**，仅构建时需要 `PyInstaller`。

## 功能特性

- **文件占用检测**：通过 Windows Restart Manager API 精确识别占用目标文件的进程（名称、PID、可执行文件路径）。
- **文件夹批量扫描**：支持递归扫描整个文件夹，后台线程枚举文件并逐一检测占用情况。
- **进程终止**：可一键终止选中进程，先尝试发送 `WM_CLOSE` 优雅关闭，超时后强制 `TerminateProcess`。
- **文件拖拽**：支持将文件或文件夹直接拖拽到程序窗口进行检测。
- **单文件打包**：通过 PyInstaller 可打包为独立 `.exe`，方便分发。

## 项目结构

```
file-unlocker/
├── main.py                 # 入口文件
├── build.py                # PyInstaller 打包脚本
├── requirements.txt        # 构建依赖
├── core/
│   ├── detector.py         # 占用检测（RestartManager API）
│   └── terminator.py       # 进程终止（kernel32/user32）
├── gui/
│   └── main_window.py      # tkinter 主界面 + 拖拽支持
├── utils/
│   └── filewalk.py         # 文件夹递归扫描
└── tests/                  # 测试代码
```

## 运行方式

### 源码直接运行

```bash
python main.py
```

无需安装任何第三方库，仅需 Python 3.x（Windows 环境）。

### 打包为可执行文件

```bash
pip install -r requirements.txt
python build.py
```

打包完成后，可执行文件位于 `dist/FileLockDetector.exe`。

## 使用说明

1. 启动程序后，点击「选择文件」或「选择文件夹」，也可以直接将文件/文件夹拖拽到窗口。
2. 程序会列出占用目标文件的进程信息（进程名、PID、路径）。
3. 在列表中选中目标行，点击「解除占用（终止选中）」即可终止对应进程。
4. 点击「刷新检测」可重新检测当前列表中的文件。

## 系统要求

- Windows 7 或更高版本
- Python 3.7+（如直接运行源码）

## 技术细节

- **占用检测**：使用 `ctypes` 调用 `Rstrtmgr.dll` 的 Restart Manager 会话 API（`RmStartSession` / `RmRegisterResources` / `RmGetList`）。
- **进程终止**：先通过 `EnumWindows` + `PostMessageW` 发送 `WM_CLOSE`，若未退出则调用 `TerminateProcess`。
- **文件拖拽**：子类化 tkinter 窗口过程（`SetWindowLongPtr`），处理 `WM_DROPFILES` 消息。

## License

MIT License
