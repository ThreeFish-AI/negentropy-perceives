"""工具层计时工具函数。"""

import time


def elapsed_ms(start_time: float) -> int:
    """计算开始时间到当前的毫秒耗时。"""
    return int((time.time() - start_time) * 1000)
