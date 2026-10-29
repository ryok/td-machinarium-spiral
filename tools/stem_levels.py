"""ステムごとの音量（RMS）を 30fps のフレーム単位で測り、正規化の基準（p95）を出す。

  uv run --with numpy --with soundfile tools/stem_levels.py <stems_dir> [--json out.json] [--csv out.csv]

TD 側の build_stems.py はこの p95 で割って 0〜1.5 にそろえる（6秒平均の自動ゲインは
ブレイクで無音のステムを持ち上げてしまうので、曲全体で決まる固定の基準を使う）。
"""
import argparse
import json
import pathlib

import numpy as np
import soundfile as sf

FPS = 30


def frame_rms(path, win_sec):
    x, sr = sf.read(path, always_2d=True)
    x = x.mean(axis=1)
    hop = sr // FPS
    win = int(sr * win_sec)
    n = len(x) // hop
    out = np.zeros(n)
    for k in range(n):
        seg = x[max(0, k * hop + hop - win):k * hop + hop]
        out[k] = np.sqrt(np.mean(seg ** 2)) if len(seg) else 0.0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stems_dir')
    ap.add_argument('--win', type=float, default=0.05)
    ap.add_argument('--json', help='{stem: p95} を書く（build_stems.py が読む）')
    ap.add_argument('--csv', help='フレームごとの RMS（同期の確認用）')
    a = ap.parse_args()
    rows = {}
    for f in sorted(pathlib.Path(a.stems_dir).glob('*.wav')):
        r = frame_rms(f, a.win)
        rows[f.stem] = r
        on = r > r.max() * 0.02
        print(f"{f.stem:7s} p95={np.percentile(r, 95):.4f} max={r.max():.4f} "
              f"on={on.mean() * 100:4.1f}%")
    if a.json:
        with open(a.json, 'w') as fp:
            json.dump({'fps': FPS, 'win': a.win,
                       'p95': {s: round(float(np.percentile(v, 95)), 5) for s, v in rows.items()}},
                      fp, indent=2)
    if a.csv:
        names = list(rows)
        n = min(len(v) for v in rows.values())
        with open(a.csv, 'w') as fp:
            fp.write('frame,' + ','.join(names) + '\n')
            for k in range(n):
                fp.write(f"{k}," + ','.join(f"{rows[s][k]:.5f}" for s in names) + '\n')


if __name__ == '__main__':
    main()
