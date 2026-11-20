"""实时语音抖动缓冲实现。

设计要点：
* 按序号（扩展为绝对序号，支持 16 位回绕）重排；
* 播放指针之前缺失的帧以空字节 ``b""`` 补偿，并计入 ``lost()``；
* 缓存深度上限为 ``target + 1``（当前待播帧 + target 帧前瞻延迟），
  超出时丢弃最旧的帧，保证缓冲区不会越过目标延迟；
* 空缓冲 ``pop()`` 返回 ``b""``，不抛异常；
* 所有公开方法由同一把锁保护，push/pop 可并发调用。
"""

from __future__ import annotations

import heapq
import threading


class JitterBuffer:
    """定长目标延迟抖动缓冲。"""

    def __init__(self, target):
        if isinstance(target, bool) or not isinstance(target, int) or target <= 0:
            raise ValueError("target 必须是正整数")
        self._target = target
        self._capacity = target + 1
        self._buf = {}  # 扩展序号 -> payload
        self._heap = []  # 扩展序号小顶堆，用于快速取出最旧帧
        self._next = None  # 下一个应出队的扩展序号
        self._newest = None  # 已接收的最大扩展序号
        self._mod = 1 << 16  # 当前序号回绕模数（16 位，必要时扩展）
        self._lost = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # 内部辅助（调用方必须持锁）
    # ------------------------------------------------------------------ #
    def _extend(self, seq: int) -> int:
        """把原始序号映射为单调递增的绝对序号，处理回绕。"""
        mod = self._mod
        while seq >= mod:
            mod <<= 16
        self._mod = mod
        if self._newest is None:
            return seq
        delta = (seq - (self._newest % mod)) % mod
        if delta >= mod >> 1:  # 落在“过去”半区
            delta -= mod
        return self._newest + delta

    def _clean_heap(self) -> None:
        heap = self._heap
        buf = self._buf
        while heap and heap[0] not in buf:
            heapq.heappop(heap)

    def _oldest(self):
        self._clean_heap()
        if not self._heap and self._buf:
            self._heap = list(self._buf)
            heapq.heapify(self._heap)
            self._clean_heap()
        return self._heap[0] if self._heap else None

    # ------------------------------------------------------------------ #
    # 公开 API
    # ------------------------------------------------------------------ #
    def push(self, seq, payload):
        """按序号入队；重复帧保留先到者，迟到帧直接丢弃。"""
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            raise ValueError("seq 必须是非负整数")
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise TypeError("payload 必须是 bytes-like 对象")
        if not isinstance(payload, bytes):
            payload = bytes(payload)

        with self._lock:
            ext = self._extend(seq)

            # 已经出队过的帧（迟到帧）或重复帧：丢弃，不改变缓冲状态。
            if self._next is not None and ext < self._next:
                return
            if ext in self._buf:
                return

            if len(self._buf) >= self._capacity:
                oldest = self._oldest()
                # 新帧比整个缓冲区都旧：同样视为迟到帧丢弃。
                if oldest is None or ext <= oldest:
                    return
                # 丢弃最旧帧，给新帧让位，确保深度不超过 target + 1。
                heapq.heappop(self._heap)
                del self._buf[oldest]
                if self._next is None:
                    # 播放尚未开始，被丢弃的帧不会被 pop 访问到，直接计丢。
                    self._lost += 1

            self._buf[ext] = payload
            heapq.heappush(self._heap, ext)
            if self._newest is None or ext > self._newest:
                self._newest = ext

    def pop(self):
        """出队一帧；缺失帧返回 ``b""``，缓冲为空时也返回 ``b""``。"""
        with self._lock:
            while self._buf:
                oldest = self._oldest()
                if oldest is None:  # 理论不可达：dict 非空则堆必非空
                    break
                if self._next is None:
                    self._next = oldest
                if self._next < oldest:
                    # 序号缺口：插入一帧静音补偿。
                    self._next += 1
                    self._lost += 1
                    return b""
                if self._next == oldest:
                    heapq.heappop(self._heap)
                    payload = self._buf.pop(oldest)
                    self._next = oldest + 1
                    return payload
                # self._next > oldest：过旧残留帧，丢弃后继续。
                heapq.heappop(self._heap)
                del self._buf[oldest]
            return b""

    def depth(self):
        """当前缓冲的帧数。"""
        with self._lock:
            return len(self._buf)

    def lost(self):
        """累计丢包（含缺口补偿与因超目标延迟被丢弃的帧）。"""
        with self._lock:
            return self._lost


__all__ = ["JitterBuffer"]
