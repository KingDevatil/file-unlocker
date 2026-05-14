"""
TDD: 测试 detector.py 的文件占用检测行为
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.detector import detect_file_lock, get_process_image_path


class TestDetectFileLock(unittest.TestCase):

    def test_nonexistent_file_returns_empty(self):
        """检测不存在的文件应返回空列表"""
        result = detect_file_lock(r"C:\ThisFileDoesNotExist_12345.txt")
        self.assertEqual(result, [])

    def test_unoccupied_file_returns_empty(self):
        """检测未被占用的临时文件应返回空列表"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test")
            tmp_path = f.name
        try:
            result = detect_file_lock(tmp_path)
            self.assertEqual(result, [])
        finally:
            os.unlink(tmp_path)

    def test_get_process_image_path_self(self):
        """获取当前进程的路径应返回非空字符串"""
        import os as _os
        pid = _os.getpid()
        path = get_process_image_path(pid)
        self.assertIsInstance(path, str)
        self.assertTrue(len(path) > 0)
        self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
