"""
TDD: 测试 gui/main_window.py 的关键行为
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.main_window import MainWindow


class TestMainWindowInit(unittest.TestCase):

    def test_window_can_be_created_and_destroyed(self):
        """MainWindow 应能正常实例化并销毁，_setup_drag_drop 不崩溃"""
        app = MainWindow()
        # 验证核心组件已初始化
        self.assertIsNotNone(app.root)
        self.assertIsNotNone(app.tree)
        # 立即销毁，避免阻塞
        app.root.destroy()

    def test_drag_drop_callback_registered(self):
        """拖拽设置完成后，旧窗口过程应被保存"""
        app = MainWindow()
        # _setup_drag_drop 成功执行后会保存旧 wndproc
        self.assertIsNotNone(app._old_wndproc)
        app.root.destroy()


if __name__ == "__main__":
    unittest.main()
