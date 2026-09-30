# -*- coding: utf-8 -*-
# python -m heart_protocol.benchmark  (避免 runner 被包导入引发的重复执行警告)
from .runner import main

if __name__ == "__main__":
    main()
