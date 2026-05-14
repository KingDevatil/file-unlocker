"""
进程终止模块 - 使用 ctypes 调用 kernel32 / user32
零第三方依赖
"""

import ctypes
from ctypes import wintypes

_kernel32 = ctypes.WinDLL("kernel32.dll")
_user32 = ctypes.WinDLL("user32.dll")

# 类型
DWORD = wintypes.DWORD
BOOL = wintypes.BOOL
HANDLE = wintypes.HANDLE
HWND = wintypes.HWND
UINT = wintypes.UINT
LPARAM = wintypes.LPARAM

# 常量
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_INFORMATION = 0x0400
STILL_ACTIVE = 259
WM_CLOSE = 0x0010

# OpenProcess
OpenProcess = _kernel32.OpenProcess
OpenProcess.argtypes = [DWORD, BOOL, DWORD]
OpenProcess.restype = HANDLE

# TerminateProcess
TerminateProcess = _kernel32.TerminateProcess
TerminateProcess.argtypes = [HANDLE, UINT]
TerminateProcess.restype = BOOL

# GetExitCodeProcess
GetExitCodeProcess = _kernel32.GetExitCodeProcess
GetExitCodeProcess.argtypes = [HANDLE, ctypes.POINTER(DWORD)]
GetExitCodeProcess.restype = BOOL

# WaitForSingleObject
WaitForSingleObject = _kernel32.WaitForSingleObject
WaitForSingleObject.argtypes = [HANDLE, DWORD]
WaitForSingleObject.restype = DWORD

# CloseHandle
CloseHandle = _kernel32.CloseHandle
CloseHandle.argtypes = [HANDLE]
CloseHandle.restype = BOOL

# EnumWindows / PostMessageW
EnumWindows = _user32.EnumWindows
EnumWindows.argtypes = [ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM), LPARAM]
EnumWindows.restype = BOOL

PostMessageW = _user32.PostMessageW
PostMessageW.argtypes = [HWND, UINT, wintypes.WPARAM, LPARAM]
PostMessageW.restype = BOOL

GetWindowThreadProcessId = _user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(DWORD)]
GetWindowThreadProcessId.restype = DWORD

INFINITE = 0xFFFFFFFF


def terminate_process(pid: int, timeout_ms: int = 3000) -> bool:
    """
    终止指定 PID 的进程。
    先尝试优雅关闭（发送 WM_CLOSE 到其顶层窗口），失败后强制 TerminateProcess。
    """
    # 1. 尝试发送 WM_CLOSE
    _try_send_wm_close(pid)

    # 2. 强制终止
    h_process = OpenProcess(PROCESS_TERMINATE | PROCESS_QUERY_INFORMATION, False, pid)
    if not h_process:
        return False

    try:
        if TerminateProcess(h_process, 1):
            WaitForSingleObject(h_process, timeout_ms)
            exit_code = DWORD(0)
            if GetExitCodeProcess(h_process, ctypes.byref(exit_code)):
                return exit_code.value != STILL_ACTIVE
            return True
        return False
    finally:
        CloseHandle(h_process)


def _try_send_wm_close(pid: int):
    """向目标进程的所有顶层窗口发送 WM_CLOSE"""
    target_hwnds = []

    @ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)
    def enum_callback(hwnd, _lparam):
        dw_pid = DWORD(0)
        GetWindowThreadProcessId(hwnd, ctypes.byref(dw_pid))
        if dw_pid.value == pid:
            target_hwnds.append(hwnd)
        return True

    try:
        EnumWindows(enum_callback, 0)
    except Exception:
        pass

    for hwnd in target_hwnds:
        try:
            PostMessageW(hwnd, WM_CLOSE, 0, 0)
        except Exception:
            pass
