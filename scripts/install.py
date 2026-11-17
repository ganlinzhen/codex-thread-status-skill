#!/usr/bin/env python3
"""安装 thread-status 技能和全局触发规则。"""

import sys

sys.dont_write_bytecode = True

from _installation import main


if __name__ == "__main__":
    raise SystemExit(main("install"))
