"""
TDD: 测试 filewalk.py 的扫描行为
"""

import os
import queue
import tempfile
import threading
import unittest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.filewalk import scan_folder_for_locks


class TestScanFolderForLocks(unittest.TestCase):

    def _collect_results(self, folder, timeout=5.0):
        """辅助方法：运行扫描并收集所有队列消息"""
        q = queue.Queue()
        stop = threading.Event()
        t = threading.Thread(target=scan_folder_for_locks, args=(folder, q, stop))
        t.start()
        t.join(timeout=timeout)
        # 如果超时，设置 stop 以便线程退出
        if t.is_alive():
            stop.set()
            t.join(timeout=1.0)

        results = []
        while True:
            try:
                results.append(q.get_nowait())
            except queue.Empty:
                break
        return results

    def test_empty_folder_returns_done_only(self):
        """空文件夹应只返回 done 消息"""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = self._collect_results(tmpdir)
        types = [r[0] for r in results]
        self.assertIn("done", types)
        self.assertNotIn("file", types)
        self.assertEqual(len([t for t in types if t == "done"]), 1)

    def test_finds_files_in_flat_folder(self):
        """单层文件夹应正确枚举所有文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ("a.txt", "b.log", "c.dat"):
                open(os.path.join(tmpdir, name), "w").close()
            results = self._collect_results(tmpdir)

        files = [r[1] for r in results if r[0] == "file"]
        basenames = sorted([os.path.basename(f) for f in files])
        self.assertEqual(basenames, ["a.txt", "b.log", "c.dat"])

    def test_finds_files_recursively(self):
        """嵌套子文件夹应递归扫描"""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "sub1", "sub2"))
            open(os.path.join(tmpdir, "root.txt"), "w").close()
            open(os.path.join(tmpdir, "sub1", "mid.txt"), "w").close()
            open(os.path.join(tmpdir, "sub1", "sub2", "deep.txt"), "w").close()
            results = self._collect_results(tmpdir)

        files = [r[1] for r in results if r[0] == "file"]
        basenames = sorted([os.path.basename(f) for f in files])
        self.assertEqual(basenames, ["deep.txt", "mid.txt", "root.txt"])

    def test_stop_event_interrupts_scan(self):
        """设置 stop_event 应立即中断扫描"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建大量文件以便有时间中断
            for i in range(200):
                open(os.path.join(tmpdir, f"file{i:03d}.txt"), "w").close()

            q = queue.Queue()
            stop = threading.Event()
            t = threading.Thread(target=scan_folder_for_locks, args=(tmpdir, q, stop))
            t.start()
            # 尽早触发 stop
            stop.set()
            t.join(timeout=2.0)

            results = []
            while True:
                try:
                    results.append(q.get_nowait())
                except queue.Empty:
                    break

        file_count = len([r for r in results if r[0] == "file"])
        self.assertLess(file_count, 200)
        self.assertIn("done", [r[0] for r in results])

    def test_nonexistent_folder_returns_error(self):
        """不存在的文件夹应返回 error 消息"""
        bad_path = r"C:\ThisPathDoesNotExist_12345"
        results = self._collect_results(bad_path, timeout=2.0)
        types = [r[0] for r in results]
        self.assertIn("error", types)


if __name__ == "__main__":
    unittest.main()
