"""jitterbuf 核心 API（初始未实现）。"""


class JitterBuffer:
    def __init__(self, target):
        """按目标延迟构造"""
        raise NotImplementedError

    def push(self, seq, payload):
        """入队"""
        raise NotImplementedError

    def pop(self):
        """出队一帧"""
        raise NotImplementedError

    def depth(self):
        """当前深度"""
        raise NotImplementedError

    def lost(self):
        """丢包数"""
        raise NotImplementedError
