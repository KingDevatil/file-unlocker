"""
TDD: 测试 gui/main_window.py 的关键行为
"""

import os
import sys
import tempfile
import threading
import time
import tkinter as tk
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.main_window import MainWindow


class TestMainWindowInit(unittest.TestCase):

    def test_window_can_be_created_and_destroyed(self):
        """MainWindow 应能正常实例化并销毁，_setup_drag_drop 不崩溃"""
        app = MainWindow()
        self.assertIsNotNone(app.root)
        self.assertIsNotNone(app.tree)
        app.root.destroy()

    def test_drag_drop_callback_registered(self):
        """拖拽设置完成后，旧窗口过程应被保存"""
        app = MainWindow()
        self.assertIsNotNone(app._old_wndproc)
        app.root.destroy()


class TestMainWindowAsync(unittest.TestCase):
    """验证耗时操作不会阻塞 GUI 主线程"""

    def _wait_for_updates(self, app, timeout_sec=2.0):
        """等待后台线程完成并触发 tkinter after 回调"""
        time.sleep(timeout_sec)
        app.root.update_idletasks()
        app.root.update()

    def test_detect_files_async_does_not_block(self):
        """_detect_files 应在后台线程执行，主线程立即返回"""
        app = MainWindow()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test")
            tmp_path = f.name

        try:
            start = time.time()
            app._detect_files([tmp_path])
            elapsed = time.time() - start

            # 主线程应立即返回（< 100ms）
            self.assertLess(elapsed, 0.1)

            # 等待后台线程完成并处理 UI 队列
            self._wait_for_updates(app, 2.0)

            # tree 中应出现结果
            children = app.tree.get_children()
            self.assertTrue(len(children) > 0)
        finally:
            app.root.destroy()
            os.unlink(tmp_path)

    def test_refresh_clears_and_redetects(self):
        """_on_refresh 应先清空 tree，再异步重新检测"""
        app = MainWindow()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test")
            tmp_path = f.name

        try:
            # 先添加一个模拟结果
            iid = app.tree.insert("", tk.END, values=(tmp_path, "mock", "1234", ""))
            app._row_file_map[iid] = tmp_path

            # 调用刷新
            app._on_refresh()

            # tree 应立即被清空（清空是同步的）
            self.assertEqual(len(app.tree.get_children()), 0)

            # 等待异步检测完成
            self._wait_for_updates(app, 2.0)

            # 应重新检测到结果
            children = app.tree.get_children()
            self.assertTrue(len(children) > 0)
        finally:
            app.root.destroy()
            os.unlink(tmp_path)

    def test_terminate_callback_shows_result(self):
        """_show_terminate_result 应正确接收后台线程的结果列表"""
        app = MainWindow()
        try:
            # 直接测试回调方法（不涉及真实进程终止）
            app._show_terminate_result(success=[9998], failed=[9999])

            # 刷新后 tree 被清空（因为 _row_file_map 原本为空）
            self.assertEqual(len(app.tree.get_children()), 0)
            self.assertEqual(app.status_var.get(), "列表为空，无可刷新内容")
        finally:
            app.root.destroy()


if __name__ == "__main__":
    unittest.main()
