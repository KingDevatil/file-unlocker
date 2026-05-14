"""
打包脚本 - 使用 PyInstaller 生成单文件 exe
运行时零依赖，仅需在构建时安装 PyInstaller
"""

import subprocess
import sys
import os


def build():
    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "FileLockDetector",
        "--clean",
        "--noconfirm",
        "main.py"
    ]
    print("执行打包命令：")
    print(" ".join(args))
    subprocess.run(args, check=True)
    print(f"\n打包完成，输出路径：{os.path.abspath('dist/FileLockDetector.exe')}")


if __name__ == "__main__":
    build()
