import math

import pytest

import jitterbuf

def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False

def _b():
    b = jitterbuf.JitterBuffer(3)
    for i in range(4):
        b.push(i, bytes([i]))
    return b


def _in_order():
    b = _b()
    return [b.pop() for _ in range(4)] == [b"\x00", b"\x01", b"\x02", b"\x03"]


def _depth():
    return _b().depth() == 4


def _reorder():
    b = jitterbuf.JitterBuffer(3)
    b.push(2, b"c")
    b.push(1, b"b")
    return b.pop() == b"b"


def _gap():
    b = jitterbuf.JitterBuffer(3)
    b.push(0, b"a")
    b.push(2, b"c")
    first = b.pop()
    second = b.pop()
    return first == b"a" and second == b""


def _lost():
    b = jitterbuf.JitterBuffer(3)
    b.push(0, b"a")
    b.push(2, b"c")
    b.pop()
    b.pop()
    return b.lost() == 1


def _empty_pop():
    return jitterbuf.JitterBuffer(3).pop() == b""


def _dup():
    b = jitterbuf.JitterBuffer(3)
    b.push(1, b"a")
    b.push(1, b"b")
    return b.pop() == b"a"


def _bad_target():
    return _raises(lambda: jitterbuf.JitterBuffer(0))


def _bad_seq():
    return _raises(lambda: jitterbuf.JitterBuffer(3).push(-1, b"x"))


def _type():
    return isinstance(_b().pop(), bytes)


def _det():
    a = _b()
    c = _b()
    return [a.pop() for _ in range(3)] == [c.pop() for _ in range(3)]


def _many():
    return len([_b().pop() for _ in range(4)]) == 4


def _payload():
    return _b().pop() == b"\x00"


def _empty_depth():
    return jitterbuf.JitterBuffer(5).depth() == 0


def _lost_zero():
    b = jitterbuf.JitterBuffer(3)
    b.push(0, b"a")
    b.pop()
    return b.lost() == 0

CASES = [("in_order", "_in_order"), ("depth", "_depth"), ("reorder", "_reorder"), ("gap", "_gap"), ("lost", "_lost"), ("empty_pop", "_empty_pop"), ("dup", "_dup"), ("bad_target", "_bad_target"), ("bad_seq", "_bad_seq"), ("type", "_type"), ("det", "_det"), ("many", "_many"), ("payload", "_payload"), ("empty_depth", "_empty_depth"), ("lost_zero", "_lost_zero")]


@pytest.mark.parametrize("name,check", CASES, ids=[c[0] for c in CASES])
def test_spec(name, check):
    assert globals()[check]() is True
