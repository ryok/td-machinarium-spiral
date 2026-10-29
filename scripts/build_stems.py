"""
build_stems.py
==============
7本の輪を、曲の7本のステムに1本ずつ割り当てる（build_spiral → build_audio の後に実行）。
帯域分割の音反応（build_audio）と違い、渦がそのまま曲のミックスになる: パートが鳴り始めると
その輪が現れ、ブレイクでドラムが抜けると下の輪が消えて声と filter の輪だけが残る。

  msp_stemin_<name> (Audio File In ×7) ─► 平均で1ch ─► 名前を付けて merge ─► RMS
     ─► ÷ 曲全体の p95（tools/stem_levels.py で測る）─► msp_stem（速い）/ msp_stem_hold（鳴っているか）

  - 輪の順（下から）は spiral_geo.py の STEM_ORDER。寒色の輪は vox
  - 回転の速さ（中域）・ほつれ（高域）・にじみ（低域）は build_audio の全体ミックスのまま
  - 正規化は 6秒平均の自動ゲインを使わない。ブレイクで無音のパートを持ち上げてしまうため、
    曲全体で決まる固定の基準（p95）で割る

実行:
  uv run --with numpy --with soundfile tools/stem_levels.py <stems_dir> --json reference/stem_levels_<song>.json
  P='/path/to/td-machinarium-spiral/scripts/build_stems.py'
  g=dict(globals()); g['__file__']=P; exec(open(P).read(), g)
  g['build_stems'](stems_dir='/path/to/stems', levels='/path/to/stem_levels.json')

録画（build_recorder の start）は msp_aud_in と msp_stemin_* をまとめて頭に戻す。
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import td_build as tb  # noqa: E402

STEMS = ('kick', 'bass', 'groove', 'vox', 'filter', 'hits', 'hats')
HOLD_FALL = 1.5        # 鳴り止んでから輪が消えるまでの秒数（Lag の下り）
X0, Y0 = -600, -1000


def build_stems(path='/project1', stems_dir=None, levels=None):
    p = tb.get_parent(path)
    tb.require(p, 'msp_geo', 'msp_aud_in', hint='build_spiral.py → build_audio.py(audio_file=...)')
    with open(levels) as f:
        p95 = json.load(f)['p95']

    merge = tb.ensure(p, 'msp_stem_merge', 'mergeCHOP', X0 + 480, Y0)
    for i, name in enumerate(STEMS):
        y = Y0 + 300 - i * 100
        src = tb.ensure(p, f'msp_stemin_{name}', 'audiofileinCHOP', X0, y, pars={
            'file': os.path.join(stems_dir, f'{name}.wav'), 'play': True, 'repeat': 'on'})
        mono = tb.ensure(p, f'msp_stemmono_{name}', 'mathCHOP', X0 + 160, y,
                         pars={'chanop': 'avg'}, inputs=[src.name])
        tb.ensure(p, f'msp_stemren_{name}', 'renameCHOP', X0 + 320, y,
                  pars={'renamefrom': '*', 'renameto': name}, inputs=[mono.name])
        merge.inputConnectors[i].connect(p.op(f'msp_stemren_{name}'))

    norm = [p95[s] for s in STEMS]
    nodes = {
        'msp_stem_rms': dict(type='analyzeCHOP', x=X0 + 640, y=Y0, pars={'function': 'rmspower'}),
        'msp_stem_norm': dict(type='expressionCHOP', x=X0 + 800, y=Y0, pars={
            'expr0expr': ('expr', f"min(1.5, me.inputVal / {norm}[me.chanIndex]) "
                                  "if me.inputVal == me.inputVal else 0")}),
        'msp_stem_lag': dict(type='lagCHOP', x=X0 + 960, y=Y0, pars={'lag1': 0.02, 'lag2': 0.12}),
        'msp_stem': dict(type='nullCHOP', x=X0 + 1120, y=Y0, pars={}),
        'msp_stem_hold': dict(type='lagCHOP', x=X0 + 1120, y=Y0 - 120, pars={
            'lag1': 0.05, 'lag2': HOLD_FALL}),
    }
    wires = {
        'msp_stem_rms': [(0, 'msp_stem_merge')],
        'msp_stem_norm': [(0, 'msp_stem_rms')],
        'msp_stem_lag': [(0, 'msp_stem_norm')],
        'msp_stem': [(0, 'msp_stem_lag')],
        'msp_stem_hold': [(0, 'msp_stem_norm')],
    }
    made = tb.build_nodes(p, nodes, wires)
    print('[build_stems] done:', ', '.join(STEMS))
    return made['msp_stem']


if __name__ == '__main__':
    build_stems()
