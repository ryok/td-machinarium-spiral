"""
spiral_geo.py
=============
Script SOP（msp_geo/msp_sop）のコールバック本文。build_spiral.py が Text DAT に流し込む。

1つの Script SOP で次の4種類を毎フレーム作り直す（すべて XZ 平面の円を Y 方向に積む）:
  - ribbon : 各リングの明るい帯（閉ポリゴンの四角形列）。先頭ほど明るく、尾は暗い
  - zigzag : 帯の内側を往復する折れ線（暗い尾でも帯の「網目」が残る）
  - plexus : 帯の外側にほつれる三角形の網（開いた折れ線で描く）
  - guide  : 円錐状に下りる細い螺旋＋下の全周円

色は点属性 Cd に入れ、Constant MAT がそのまま掛け合わせる。1.0 を超える値は
16bit float の Render TOP でブルームの「芯」になる。
"""

import math
import random

N_RINGS = 7
WARM = (1.0, 0.72, 0.62)
COOL = (0.62, 0.6, 1.0)
COOL_RING = 3             # 1本だけ寒色にする（元動画の青紫のリング）


def _ring(i, t):
    """リング i の形状パラメータ（時刻 t で回転・開閉する）"""
    rng = random.Random(1000 + i)
    radius = 3.0 - i * 0.34
    y = i * 0.42
    width = rng.uniform(0.12, 0.30)
    speed = rng.uniform(0.18, 0.45) * (1 if i % 2 == 0 else -1)
    start = rng.uniform(0, 2 * math.pi) + t * speed
    sweep = math.pi * (0.95 + 0.6 * math.sin(t * rng.uniform(0.15, 0.35) + i * 1.7))
    gain = rng.uniform(0.5, 1.2) * (0.5 if i == COOL_RING else 1.0)
    col = COOL if i == COOL_RING else WARM
    return dict(radius=radius, y=y, width=width, start=start, sweep=sweep,
                gain=gain, col=col, dir=1 if speed > 0 else -1, seed=i)


def _xz(r, a, y):
    return (r * math.cos(a), y, r * math.sin(a))


def _scale(col, k):
    return (col[0] * k, col[1] * k, col[2] * k, 1.0)


def _poly(op, pts, cols, closed):
    poly = op.appendPoly(len(pts), closed=closed, addPoints=True)
    for k, (p, c) in enumerate(zip(pts, cols)):
        v = poly[k].point
        v.P = p
        v.Cd = c


def _ribbon(op, R, n=140):
    r0, r1, y = R['radius'], R['radius'] + R['width'], R['y']
    angs = [R['start'] + R['dir'] * R['sweep'] * k / (n - 1) for k in range(n)]
    # k=n-1 が進行方向の先頭。塗りは先頭付近だけにし、残りは網目で見せる
    # （塗りが長いと手前に来た帯がのっぺりした板になる）
    lum = [R['gain'] * 1.6 * (k / (n - 1)) ** 4.5 for k in range(n)]
    for k in range(n - 1):
        if lum[k + 1] < 0.01:
            continue
        a, b = angs[k], angs[k + 1]
        c0, c1 = _scale(R['col'], lum[k]), _scale(R['col'], lum[k + 1])
        _poly(op, [_xz(r0, a, y), _xz(r1, a, y), _xz(r1, b, y), _xz(r0, b, y)],
              [c0, c0, c1, c1], closed=True)
    # 帯の中の網目: 内縁・ゆらぐ中段・外縁の3列を往復して三角形を作る
    rng = random.Random(R['seed'] * 31)
    w = R['width']
    mid = [r0 + w * rng.uniform(0.25, 0.75) for _ in range(n)]
    net = [R['gain'] * (0.12 + 0.55 * k / (n - 1)) for k in range(n)]
    lo, hi = [], []
    for k in range(n):
        lo.append(_xz(r0 if k % 2 == 0 else mid[k], angs[k], y))
        hi.append(_xz(mid[k] if k % 2 == 0 else r1, angs[k], y))
    cols = [_scale(R['col'], v) for v in net]
    _poly(op, lo, cols, closed=False)
    _poly(op, hi, cols, closed=False)
    for r in (r0, r1):   # 縁の細い線
        _poly(op, [_xz(r, a, y) for a in angs], [_scale(R['col'], v * 0.8) for v in net],
              closed=False)
    return angs


def _plexus(op, R, angs, t):
    """帯の外縁からほつれる三角形。先頭寄りほど密・明るい"""
    rng = random.Random(R['seed'] * 77)
    r1, y = R['radius'] + R['width'], R['y']
    step = 3
    prev = None
    for k in range(0, len(angs), step):
        f = k / (len(angs) - 1)
        a = angs[k]
        wob = math.sin(t * 0.8 + k * 0.37 + R['seed'])
        dr = rng.uniform(0.03, 0.28) * (0.4 + f) + 0.03 * wob
        dy = rng.uniform(-0.15, 0.15) * (0.3 + f)
        edge = _xz(r1, a, y)
        out = _xz(r1 + dr, a + rng.uniform(-0.04, 0.04), y + dy)
        if prev is not None and rng.random() < 0.35 + 0.6 * f:
            c = _scale(R['col'], R['gain'] * (0.06 + 0.45 * f))
            pe, po = prev
            _poly(op, [pe, po, edge, pe], [c] * 4, closed=False)
            _poly(op, [po, out, edge], [c] * 3, closed=False)
        # ときどき長い迷い線
        if rng.random() < 0.06:
            far = _xz(r1 + dr * 3, a + rng.uniform(-0.3, 0.3), y + dy * 3)
            _poly(op, [out, far], [_scale(R['col'], 0.25)] * 2, closed=False)
        prev = (edge, out)


def _guides(op, t):
    c = _scale(WARM, 0.22)
    # 円錐状の螺旋（下の大きいリングから上の小さいリングへ）
    n = 600
    turns = N_RINGS - 0.5
    pts = []
    for k in range(n):
        f = k / (n - 1)
        a = 2 * math.pi * turns * f + t * 0.05
        pts.append(_xz(2.5 - 2.2 * f ** 0.9, a, -0.6 + 2.6 * f))
    _poly(op, pts, [c] * n, closed=False)
    # 下の全周円
    for j in range(3):
        r, y = 2.7 + j * 0.45, -0.7 - j * 0.35
        m = 160
        _poly(op, [_xz(r, 2 * math.pi * k / m, y) for k in range(m + 1)],
              [_scale(WARM, 0.15)] * (m + 1), closed=False)


def onCook(scriptOp):
    t = absTime.seconds * float(scriptOp.fetch('speed', 1.0))
    scriptOp.clear()
    scriptOp.pointAttribs.create('Cd')
    for i in range(N_RINGS):
        R = _ring(i, t)
        angs = _ribbon(scriptOp, R)
        _plexus(scriptOp, R, angs, t)
    _guides(scriptOp, t)
    return
