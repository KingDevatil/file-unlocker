"""
TDD: 测试 terminator.py 的进程终止行为
"""

import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.terminator import terminate_process


class TestTerminateProcess(unittest.TestCase):

    def test_terminate_nonexistent_pid_returns_false(self):
        """终止不存在的 PID 应返回 False"""
        result = terminate_process(99999)
        self.assertFalse(result)

    def test_terminate_real_subprocess(self):
        """创建一个安全的子进程并终止它"""
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # 等待子进程稳定启动
        time.sleep(0.5)
        self.assertIsNone(proc.poll())

        result = terminate_process(proc.pid)
        # 给终止操作一点时间
        time.sleep(0.5)

        # 关闭管道避免 ResourceWarning
        proc.stdout.close()
        proc.stderr.close()

        self.assertTrue(result)
        self.assertIsNotNone(proc.poll())


if __name__ == "__main__":
    unittest.main()
