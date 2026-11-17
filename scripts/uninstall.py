#!/usr/bin/env python3
"""卸载本安装器管理的 thread-status 内容，保留用户改动。"""

import sys

sys.dont_write_bytecode = True

from _installation import main


if __name__ == "__main__":
    raise SystemExit(main("uninstall"))
