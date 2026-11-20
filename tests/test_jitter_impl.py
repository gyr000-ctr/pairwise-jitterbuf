"""抖动缓冲的验收用例（-k jitter 选中）。"""

import threading
import time

import pytest

from jitterbuf import JitterBuffer


def test_jitter_reorders_by_seq():
    b = JitterBuffer(4)
    for seq in (3, 1, 4, 2, 0):
        b.push(seq, bytes([seq]))
    assert [b.pop() for _ in range(5)] == [bytes([i]) for i in range(5)]


def test_jitter_gap_inserts_silence_with_length():
    b = JitterBuffer(8)
    b.push(0, b"\x01\x02")
    b.push(4, b"\x09\x09")
    out = [b.pop() for _ in range(5)]
    assert out == [b"\x01\x02", b"", b"", b"", b"\x09\x09"]
    assert all(isinstance(f, bytes) for f in out)
    assert b.lost() == 3


def test_jitter_depth_bounded_by_target():
    b = JitterBuffer(3)
    for seq in range(100):
        b.push(seq, b"x")
        assert b.depth() <= 4  # 目标延迟 3 帧 + 当前待播帧
    assert b.depth() <= 4


def test_jitter_empty_pop_returns_empty():
    b = JitterBuffer(3)
    assert b.pop() == b""
    assert b.depth() == 0


def test_jitter_100k_under_one_second():
    b = JitterBuffer(64)
    start = time.perf_counter()
    for seq in range(100_000):
        b.push(seq, b"x" * 32)
    while b.depth():
        b.pop()
    assert time.perf_counter() - start < 1.0


def test_jitter_concurrent_push_pop():
    b = JitterBuffer(16)
    errors = []
    stop = threading.Event()

    def produce(base):
        try:
            for seq in range(base, base + 10_000):
                b.push(seq, b"p")
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    def consume():
        try:
            while not stop.is_set():
                b.pop()
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    consumers = [threading.Thread(target=consume) for _ in range(2)]
    producers = [threading.Thread(target=produce, args=(i * 10_000,)) for i in range(2)]
    for t in consumers + producers:
        t.start()
    for t in producers:
        t.join()
    stop.set()
    for t in consumers:
        t.join()
    assert errors == []
    assert b.depth() <= 17


@pytest.mark.parametrize("start", [0, 65_530])
def test_jitter_sequence_wraparound(start):
    b = JitterBuffer(4)
    seqs = [(start + i) % 65_536 for i in range(4)]
    for seq in seqs:
        b.push(seq, bytes([seq & 0xFF]))
    assert [b.pop() for _ in range(4)] == [bytes([s & 0xFF]) for s in seqs]


def test_jitter_large_payload_memory_bounded():
    b = JitterBuffer(2)
    frame = b"y" * (256 * 1024)
    for seq in range(50):
        b.push(seq, frame)
    assert b.depth() <= 3
    assert b.pop() == frame
