"""
TDD: 测试 detector.py 的真实文件占用场景
创建一个子进程打开文件并保持锁定，然后检测
"""

import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.detector import detect_file_lock
from core.terminator import terminate_process


class TestDetectRealFileLock(unittest.TestCase):

    def test_detects_locked_file(self):
        """
        创建一个子进程以独占模式打开文件并保持锁定，
        然后检测该文件应返回占用进程信息。
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"locked content")
            tmp_path = f.name

        # 启动一个子进程，以独占写模式打开文件并保持
        lock_script = (
            "import time\n"
            f"f = open({repr(tmp_path)}, 'r+')\n"  # r+ 模式会打开文件并持有句柄
            "time.sleep(60)\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", lock_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            # 等待子进程稳定打开文件
            time.sleep(0.8)

            result = detect_file_lock(tmp_path)

            # 应该至少检测到一个进程
            self.assertTrue(len(result) > 0, f"未检测到占用进程，结果：{result}")

            # 验证返回的数据结构
            for info in result:
                self.assertIn("name", info)
                self.assertIn("pid", info)
                self.assertIn("path", info)
                self.assertIsInstance(info["pid"], int)
                self.assertGreater(info["pid"], 0)

            # PID 中应包含我们的子进程
            pids = [info["pid"] for info in result]
            self.assertIn(proc.pid, pids)

        finally:
            # 清理：强制终止并等待子进程完全退出
            terminate_process(proc.pid)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            proc.stdout.close()
            proc.stderr.close()
            time.sleep(0.2)
            try:
                os.unlink(tmp_path)
            except PermissionError:
                pass  # 子进程可能还没完全释放


if __name__ == "__main__":
    unittest.main()
