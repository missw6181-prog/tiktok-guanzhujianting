import sys
from pathlib import Path


def get_project_root() -> Path:
    """开发模式为仓库根目录；PyInstaller 打包后为可执行文件所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
