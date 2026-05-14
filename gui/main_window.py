"""
主界面模块 - tkinter + 文件拖拽支持
零第三方依赖
"""

import os
import sys
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# 确保 core / utils 在路径中
_script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from core.detector import detect_file_lock
from core.terminator import terminate_process
from utils.filewalk import scan_folder_for_locks


# --- 拖拽支持 (通过 ctypes 绑定 WM_DROPFILES) ---
import ctypes
from ctypes import wintypes

_shell32 = ctypes.windll.shell32
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

DragQueryFileW = _shell32.DragQueryFileW
DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
DragQueryFileW.restype = wintypes.UINT

DragFinish = _shell32.DragFinish
DragFinish.argtypes = [wintypes.HANDLE]
DragFinish.restype = None

WM_DROPFILES = 0x0233
GWL_WNDPROC = -4

CallWindowProcW = _user32.CallWindowProcW
CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
CallWindowProcW.restype = ctypes.c_long

# 64 位兼容：使用 SetWindowLongPtrW / GetWindowLongPtrW（在 32 位上回退到 SetWindowLongW）
# c_void_p 在 64 位为 8 字节、32 位为 4 字节，与 LONG_PTR 大小一致，
# 且是指针类型，满足 ctypes.cast() 要求。
_WPARAM_PTR = ctypes.c_void_p
if hasattr(_user32, 'SetWindowLongPtrW'):
    _SetWindowLong = _user32.SetWindowLongPtrW
    _GetWindowLong = _user32.GetWindowLongPtrW
else:
    _SetWindowLong = _user32.SetWindowLongW
    _GetWindowLong = _user32.GetWindowLongW
_SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, _WPARAM_PTR]
_SetWindowLong.restype = _WPARAM_PTR
_GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
_GetWindowLong.restype = _WPARAM_PTR


def _handle_drop_files(hwnd, wparam):
    """解析 WM_DROPFILES 的拖拽路径列表"""
    hdrop = wparam
    file_count = DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
    paths = []
    for i in range(file_count):
        length = DragQueryFileW(hdrop, i, None, 0)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            DragQueryFileW(hdrop, i, buf, length + 1)
            paths.append(buf.value)
    DragFinish(hdrop)
    return paths


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("文件占用检测工具")
        self.root.geometry("900x600")
        self.root.minsize(700, 450)

        # 全局变量
        self._scan_queue = queue.Queue()
        self._scan_stop_event = threading.Event()
        self._scan_thread = None
        self._pending_scan_paths = []

        # 存储当前选中的检测结果 {行id: filepath}
        self._row_file_map = {}

        self._build_ui()
        self._setup_drag_drop()
        self._start_queue_polling()

    def _build_ui(self):
        # 顶部区域：说明 + 按钮
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="拖拽文件或文件夹到下方区域，或点击按钮选择：").pack(side=tk.LEFT)

        ttk.Button(top_frame, text="选择文件", command=self._on_select_file).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(top_frame, text="选择文件夹", command=self._on_select_folder).pack(side=tk.RIGHT, padx=(5, 0))

        # 拖拽接收区
        self.drop_frame = tk.Frame(self.root, bg="#f0f4f8", highlightbackground="#4a90d9", highlightthickness=2)
        self.drop_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.drop_label = tk.Label(
            self.drop_frame,
            text="将文件或文件夹拖拽到此处",
            bg="#f0f4f8",
            fg="#4a90d9",
            font=("Microsoft YaHei", 14, "bold")
        )
        self.drop_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # 结果显示区域（Treeview）
        result_frame = ttk.Frame(self.root, padding=(10, 0))
        result_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(result_frame, text="占用进程列表：").pack(anchor=tk.W)

        columns = ("file", "name", "pid", "path")
        self.tree = ttk.Treeview(result_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("file", text="被占用文件")
        self.tree.heading("name", text="进程名")
        self.tree.heading("pid", text="PID")
        self.tree.heading("path", text="进程路径")
        self.tree.column("file", width=250)
        self.tree.column("name", width=150)
        self.tree.column("pid", width=80)
        self.tree.column("path", width=300)

        vsb = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 底部操作栏
        bottom_frame = ttk.Frame(self.root, padding=10)
        bottom_frame.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(bottom_frame, textvariable=self.status_var).pack(side=tk.LEFT)

        ttk.Button(bottom_frame, text="刷新检测", command=self._on_refresh).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(bottom_frame, text="解除占用（终止选中）", command=self._on_terminate_selected).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(bottom_frame, text="清空结果", command=self._on_clear).pack(side=tk.RIGHT, padx=(5, 0))

    def _setup_drag_drop(self):
        """通过 ctypes 子类化窗口过程以支持 WM_DROPFILES"""
        self._old_wndproc = None
        self._py_wndproc = None

        # 启用拖放
        _shell32.DragAcceptFiles(self.root.winfo_id(), True)

        # 创建新的窗口过程回调
        @ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        def new_wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_DROPFILES:
                paths = _handle_drop_files(hwnd, wparam)
                if paths:
                    self._handle_paths(paths)
                return 0
            return CallWindowProcW(self._old_wndproc, hwnd, msg, wparam, lparam)

        self._py_wndproc = new_wndproc
        self._old_wndproc = _GetWindowLong(self.root.winfo_id(), GWL_WNDPROC)
        _SetWindowLong(self.root.winfo_id(), GWL_WNDPROC, ctypes.cast(self._py_wndproc, _WPARAM_PTR).value)

    def _handle_paths(self, paths):
        """处理传入的路径列表（文件或文件夹）"""
        files = []
        folders = []
        for p in paths:
            if os.path.isfile(p):
                files.append(p)
            elif os.path.isdir(p):
                folders.append(p)

        if files:
            self._detect_files(files)

        if folders:
            # 批量扫描文件夹
            self._start_folder_scan(folders)

    def _detect_files(self, file_paths):
        """对单个/多个文件执行占用检测，并更新 UI"""
        self.status_var.set(f"正在检测 {len(file_paths)} 个文件...")
        self.root.update_idletasks()

        for fp in file_paths:
            procs = detect_file_lock(fp)
            if procs:
                for proc in procs:
                    iid = self.tree.insert("", tk.END, values=(fp, proc["name"], proc["pid"], proc["path"]))
                    self._row_file_map[iid] = fp
            else:
                # 未检测到占用，也插入一行提示
                iid = self.tree.insert("", tk.END, values=(fp, "(未检测到占用)", "", ""))
                self._row_file_map[iid] = fp

        self.status_var.set("检测完成")

    def _start_folder_scan(self, folders):
        """启动后台线程扫描文件夹"""
        # 取消之前的扫描
        if self._scan_thread and self._scan_thread.is_alive():
            self._scan_stop_event.set()
            self._scan_thread.join(timeout=1)

        self._scan_stop_event.clear()
        self._pending_scan_paths = folders
        self.status_var.set("正在扫描文件夹...")

        def worker():
            for folder in folders:
                if self._scan_stop_event.is_set():
                    break
                scan_folder_for_locks(folder, self._scan_queue, self._scan_stop_event)

        self._scan_thread = threading.Thread(target=worker, daemon=True)
        self._scan_thread.start()

    def _start_queue_polling(self):
        """定时轮询扫描队列，将后台发现的文件交给检测模块"""
        def poll():
            processed = 0
            try:
                while True:
                    item = self._scan_queue.get_nowait()
                    msg_type, data = item
                    if msg_type == "file":
                        # 检测单个文件
                        procs = detect_file_lock(data)
                        if procs:
                            for proc in procs:
                                iid = self.tree.insert("", tk.END, values=(data, proc["name"], proc["pid"], proc["path"]))
                                self._row_file_map[iid] = data
                        else:
                            iid = self.tree.insert("", tk.END, values=(data, "(未检测到占用)", "", ""))
                            self._row_file_map[iid] = data
                        processed += 1
                    elif msg_type == "error":
                        messagebox.showerror("扫描错误", f"扫描过程中出错：{data}")
                    elif msg_type == "done":
                        self.status_var.set("扫描完成")
            except queue.Empty:
                pass

            if processed > 0:
                self.status_var.set(f"已扫描并检测 {processed} 个文件")

            self.root.after(200, poll)

        self.root.after(200, poll)

    def _on_select_file(self):
        from tkinter import filedialog
        files = filedialog.askopenfilenames(title="选择要检测的文件")
        if files:
            self._handle_paths(list(files))

    def _on_select_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="选择要扫描的文件夹")
        if folder:
            self._handle_paths([folder])

    def _on_refresh(self):
        """重新检测当前列表中所有文件"""
        files = list(set(self._row_file_map.values()))
        self.tree.delete(*self.tree.get_children())
        self._row_file_map.clear()
        if files:
            self._detect_files(files)
        else:
            self.status_var.set("列表为空，无可刷新内容")

    def _on_terminate_selected(self):
        """终止选中行对应的进程"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选中要终止的进程行")
            return

        pids_to_kill = set()
        for iid in selected:
            vals = self.tree.item(iid, "values")
            if len(vals) >= 3 and str(vals[2]).isdigit():
                pids_to_kill.add(int(vals[2]))

        if not pids_to_kill:
            messagebox.showwarning("提示", "选中的行不包含可终止的进程")
            return

        answer = messagebox.askyesno(
            "确认",
            f"即将强制终止以下 PID 对应的进程：\n{', '.join(map(str, pids_to_kill))}\n\n是否继续？"
        )
        if not answer:
            return

        success = []
        failed = []
        for pid in pids_to_kill:
            if terminate_process(pid):
                success.append(pid)
            else:
                failed.append(pid)

        msg = ""
        if success:
            msg += f"成功终止：{success}\n"
        if failed:
            msg += f"终止失败：{failed}"
        messagebox.showinfo("结果", msg)

        # 自动刷新
        self._on_refresh()

    def _on_clear(self):
        self.tree.delete(*self.tree.get_children())
        self._row_file_map.clear()
        self.status_var.set("已清空")

    def run(self):
        self.root.mainloop()
