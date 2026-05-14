"""
文件占用检测模块 - 使用 ctypes 调用 Restart Manager API
零第三方依赖
"""

import ctypes
import ctypes.wintypes
from ctypes import wintypes
import traceback
import os


# --- Windows API 类型与常量定义 ---

DWORD = wintypes.DWORD
WCHAR = wintypes.WCHAR
UINT = wintypes.UINT
UINT32 = ctypes.c_uint32
BOOL = wintypes.BOOL
HANDLE = wintypes.HANDLE
PWCHAR = ctypes.POINTER(WCHAR)
LPCWSTR = wintypes.LPCWSTR
LPWSTR = wintypes.LPWSTR

# Restart Manager 错误码
ERROR_SUCCESS = 0
ERROR_MORE_DATA = 234
CCH_RM_MAX_APP_NAME = 255
CCH_RM_MAX_SVC_NAME = 63
# CCH_RM_SESSION_KEY = 32 (定义于 restartmanager.h)，需额外 +1 容纳终止空字符
RM_SESSION_KEY_LEN = 32


class RM_UNIQUE_PROCESS(ctypes.Structure):
    _fields_ = [
        ("dwProcessId", DWORD),
        ("ProcessStartTime", ctypes.c_longlong),  # FILETIME
    ]


class RM_PROCESS_INFO(ctypes.Structure):
    _fields_ = [
        ("Process", RM_UNIQUE_PROCESS),
        ("strAppName", WCHAR * (CCH_RM_MAX_APP_NAME + 1)),
        ("strServiceShortName", WCHAR * (CCH_RM_MAX_SVC_NAME + 1)),
        ("ApplicationType", ctypes.c_int),  # RM_APP_TYPE
        ("AppStatus", DWORD),
        ("TSSessionId", DWORD),
        ("bRestartable", BOOL),
    ]


# 加载 Rstrtmgr.dll
_rstrtmgr = ctypes.WinDLL("Rstrtmgr.dll")

# RmStartSession
RmStartSession = _rstrtmgr.RmStartSession
RmStartSession.argtypes = [ctypes.POINTER(DWORD), DWORD, ctypes.c_wchar_p]
RmStartSession.restype = DWORD

# RmEndSession
RmEndSession = _rstrtmgr.RmEndSession
RmEndSession.argtypes = [DWORD]
RmEndSession.restype = DWORD

# RmRegisterResources
RmRegisterResources = _rstrtmgr.RmRegisterResources
RmRegisterResources.argtypes = [
    DWORD, UINT, ctypes.POINTER(LPCWSTR), UINT,
    ctypes.POINTER(RM_UNIQUE_PROCESS), UINT, ctypes.c_wchar_p
]
RmRegisterResources.restype = DWORD

# RmGetList
RmGetList = _rstrtmgr.RmGetList
RmGetList.argtypes = [
    DWORD, ctypes.POINTER(UINT), ctypes.POINTER(UINT),
    ctypes.POINTER(RM_PROCESS_INFO), ctypes.POINTER(DWORD)
]
RmGetList.restype = DWORD


# 进程路径查询辅助
_kernel32 = ctypes.WinDLL("kernel32.dll")

OpenProcess = _kernel32.OpenProcess
OpenProcess.argtypes = [DWORD, BOOL, DWORD]
OpenProcess.restype = HANDLE

CloseHandle = _kernel32.CloseHandle
CloseHandle.argtypes = [HANDLE]
CloseHandle.restype = BOOL

QueryFullProcessImageNameW = _kernel32.QueryFullProcessImageNameW
QueryFullProcessImageNameW.argtypes = [HANDLE, DWORD, LPWSTR, ctypes.POINTER(DWORD)]
QueryFullProcessImageNameW.restype = BOOL

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


def get_process_image_path(pid: int) -> str:
    """通过 PID 获取进程可执行文件完整路径"""
    h_process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h_process:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = DWORD(1024)
        if QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        CloseHandle(h_process)


def detect_file_lock(filepath: str):
    """
    检测单个文件的占用进程信息。
    返回: list[dict] 每个 dict 包含 name, pid, path
    """
    if not os.path.exists(filepath):
        return []

    session_handle = DWORD(0)
    session_key = ctypes.create_unicode_buffer(RM_SESSION_KEY_LEN + 1)

    ret = RmStartSession(ctypes.byref(session_handle), 0, session_key)
    if ret != ERROR_SUCCESS:
        return []

    try:
        file_path = os.path.abspath(filepath)
        p_path = LPCWSTR(file_path)

        ret = RmRegisterResources(session_handle, 1, ctypes.byref(p_path), 0, None, 0, None)
        if ret != ERROR_SUCCESS:
            return []

        proc_needed = UINT(0)
        proc_count = UINT(0)
        reboot_reasons = DWORD(0)

        ret = RmGetList(session_handle, ctypes.byref(proc_needed), ctypes.byref(proc_count), None, ctypes.byref(reboot_reasons))
        if ret == ERROR_MORE_DATA and proc_needed.value > 0:
            proc_info_array = (RM_PROCESS_INFO * proc_needed.value)()
            proc_count2 = UINT(proc_needed.value)
            ret = RmGetList(session_handle, ctypes.byref(proc_needed), ctypes.byref(proc_count2), proc_info_array, ctypes.byref(reboot_reasons))
            if ret != ERROR_SUCCESS:
                return []

            results = []
            for i in range(proc_count2.value):
                info = proc_info_array[i]
                pid = info.Process.dwProcessId
                name = info.strAppName
                path = get_process_image_path(pid)
                results.append({
                    "name": name,
                    "pid": pid,
                    "path": path,
                })
            return results
        return []
    except Exception:
        traceback.print_exc()
        return []
    finally:
        RmEndSession(session_handle)
