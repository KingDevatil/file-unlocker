"""
批量文件夹扫描工具 - 使用 os.walk，纯标准库
"""

import os
import threading
import queue


def scan_folder_for_locks(folder_path: str, result_queue: queue.Queue, stop_event: threading.Event):
    """
    在后台线程中递归扫描文件夹内所有文件，并将每个文件路径放入队列。
    调用方负责自行检测占用（通常结合 core.detector）。
    本函数仅负责枚举文件路径，避免阻塞 GUI。
    """
    if not os.path.exists(folder_path):
        result_queue.put(("error", f"路径不存在: {folder_path}"))
        result_queue.put(("done", None))
        return
    if not os.path.isdir(folder_path):
        result_queue.put(("error", f"不是文件夹: {folder_path}"))
        result_queue.put(("done", None))
        return

    try:
        for root, _dirs, files in os.walk(folder_path):
            if stop_event.is_set():
                break
            for filename in files:
                if stop_event.is_set():
                    break
                full_path = os.path.join(root, filename)
                result_queue.put(("file", full_path))
    except Exception as e:
        result_queue.put(("error", str(e)))
    finally:
        result_queue.put(("done", None))
