"""
build_audio.py
==============
build_spiral.py で組んだ渦を音に反応させる（build_spiral の後に実行）。

  msp_aud_in (デバイス or ファイル) ─► 帯域 low/mid/high ─► msp_aud（速い） / msp_aud_slow（6秒平均）
  msp_drive (Constant CHOP): t / low / mid / high を Script SOP と Level TOP が読む

対応づけ（Script SOP 側は spiral_geo.py の onCook）:
  - 低域 → 下の大きい輪ほど強く、弧が開き先頭が明るくなる（キックで輪が伸びる）
  - 高域 → 上の小さい輪ほど強く同じ反応。加えて三角形のほつれが外へ広がる
  - 中域 → 回転の速さ。msp_drive の t は「1 + 中域」を Speed CHOP で積分した時刻
           （absTime に係数を掛けると、係数が変わった瞬間に位置が飛ぶ）
  - 低域 → 大きいブラーの明るさ（にじみが拍で膨らむ）

各帯域は「今の値 ÷ (直近6秒平均×2 + 下駄)」の自動ゲインで 0〜1.5 にそろえる（td-artwork-vj と同じ）。
🚨 Audio Spectrum の frequencylog は 0、Trim は relative='abs'。既定のままだと低中高がほぼ同じ値になる。

実行:
  P='/Users/ryookada/work/td-machinarium-spiral/scripts/build_audio.py'
  g=dict(globals()); g['__file__']=P; exec(open(P).read(), g); g['build_audio']()
  ファイルで試すときは g['build_audio'](audio_file='/path/to/song.mp3')
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import td_build as tb  # noqa: E402

AGC_SEC = 6.0
BAND_FLOOR = {'low': 0.01, 'mid': 0.01, 'high': 0.003}
MID_SPEED = 0.8          # 中域 1.0 で回転が 1.8 倍速
GLOW_BASE, GLOW_LOW = 1.7, 0.5
X0, Y0 = -600, -500


def _ch(node, ch):
    """node の ch を読む式。node やチャンネルが無ければ 0（1つの欠けで式全体が tdError にならない）"""
    return (f"(op('{node}')['{ch}'] if op('{node}') is not None "
            f"and op('{node}')['{ch}'] is not None else 0)")


def _band(ch):
    return (f"min(1.5, max(0, {_ch('msp_aud', ch)} / "
            f"(2 * {_ch('msp_aud_slow', ch)} + {BAND_FLOOR[ch]})))")


NODES = {
    'msp_aud_mono': dict(type='mathCHOP', x=X0 + 160, y=Y0, pars={'chanop': 'avg'}),
    'msp_aud_spec': dict(type='audiospectrumCHOP', x=X0 + 320, y=Y0, pars={'frequencylog': 0}),
    'msp_band_low': dict(type='trimCHOP', x=X0 + 480, y=Y0 + 80, pars={
        'relative': 'abs', 'start': 2, 'end': 120}),
    'msp_band_mid': dict(type='trimCHOP', x=X0 + 480, y=Y0, pars={
        'relative': 'abs', 'start': 120, 'end': 900}),
    'msp_band_high': dict(type='trimCHOP', x=X0 + 480, y=Y0 - 80, pars={
        'relative': 'abs', 'start': 900, 'end': 4000}),
    'msp_an_low': dict(type='analyzeCHOP', x=X0 + 640, y=Y0 + 80, pars={'function': 'average'}),
    'msp_an_mid': dict(type='analyzeCHOP', x=X0 + 640, y=Y0, pars={'function': 'average'}),
    'msp_an_high': dict(type='analyzeCHOP', x=X0 + 640, y=Y0 - 80, pars={'function': 'average'}),
    'msp_ren_low': dict(type='renameCHOP', x=X0 + 800, y=Y0 + 80, pars={'renamefrom': '*', 'renameto': 'low'}),
    'msp_ren_mid': dict(type='renameCHOP', x=X0 + 800, y=Y0, pars={'renamefrom': '*', 'renameto': 'mid'}),
    'msp_ren_high': dict(type='renameCHOP', x=X0 + 800, y=Y0 - 80, pars={'renamefrom': '*', 'renameto': 'high'}),
    'msp_aud_merge': dict(type='mergeCHOP', x=X0 + 960, y=Y0, pars={}),
    # 曲の差し替え時に混ざる NaN を Lag の手前で消す（td-artwork-vj で実機確認）
    'msp_aud_clean': dict(type='expressionCHOP', x=X0 + 1120, y=Y0, pars={
        'expr0expr': ('expr', "me.inputVal if me.inputVal == me.inputVal and abs(me.inputVal) < 1e6 else 0")}),
    'msp_aud_lag': dict(type='lagCHOP', x=X0 + 1280, y=Y0, pars={'lag1': 0.02, 'lag2': 0.15}),
    'msp_aud': dict(type='nullCHOP', x=X0 + 1440, y=Y0, pars={}),
    'msp_aud_slow': dict(type='lagCHOP', x=X0 + 1440, y=Y0 - 120, pars={'lag1': AGC_SEC, 'lag2': AGC_SEC}),
    'msp_time_rate': dict(type='constantCHOP', x=X0 + 1600, y=Y0 + 120, pars={
        'name0': 't', 'value0': ('expr', f"1 + {MID_SPEED} * {_band('mid')}")}),
    'msp_time': dict(type='speedCHOP', x=X0 + 1760, y=Y0 + 120, pars={}),
    'msp_drive': dict(type='constantCHOP', x=X0 + 1920, y=Y0, pars={
        'name0': 't', 'value0': ('expr', _ch('msp_time', 't')),
        'name1': 'low', 'value1': ('expr', _band('low')),
        'name2': 'mid', 'value2': ('expr', _band('mid')),
        'name3': 'high', 'value3': ('expr', _band('high'))}),
}
WIRES = {
    'msp_aud_spec': [(0, 'msp_aud_mono')],
    'msp_band_low': [(0, 'msp_aud_spec')], 'msp_band_mid': [(0, 'msp_aud_spec')],
    'msp_band_high': [(0, 'msp_aud_spec')],
    'msp_an_low': [(0, 'msp_band_low')], 'msp_an_mid': [(0, 'msp_band_mid')],
    'msp_an_high': [(0, 'msp_band_high')],
    'msp_ren_low': [(0, 'msp_an_low')], 'msp_ren_mid': [(0, 'msp_an_mid')],
    'msp_ren_high': [(0, 'msp_an_high')],
    'msp_aud_merge': [(0, 'msp_ren_low'), (1, 'msp_ren_mid'), (2, 'msp_ren_high')],
    'msp_aud_clean': [(0, 'msp_aud_merge')],
    'msp_aud_lag': [(0, 'msp_aud_clean')],
    'msp_aud': [(0, 'msp_aud_lag')],
    'msp_aud_slow': [(0, 'msp_aud_clean')],
    'msp_time': [(0, 'msp_time_rate')],
}


def build_audio(path='/project1', audio_file=None, device=None):
    """audio_file を渡せばファイル再生（ループ）、無ければ Audio Device In。
    device はデバイスIDの文字列（例 'BlackHole2ch_UID'）。None なら既定の入力。"""
    p = tb.get_parent(path)
    tb.require(p, 'msp_geo', 'msp_lvl_l', hint='build_spiral.py')
    if audio_file:
        src = tb.ensure(p, 'msp_aud_in', 'audiofileinCHOP', X0, Y0,
                        pars={'file': audio_file, 'play': True, 'repeat': 'on'})
    else:
        src = tb.ensure(p, 'msp_aud_in', 'audiodeviceinCHOP', X0, Y0)
        if device:
            tb.set_pars(src, {'device': device})
    made = tb.build_nodes(p, NODES, WIRES)
    made['msp_aud_mono'].inputConnectors[0].connect(src)

    # にじみを低域で膨らませる
    p.op('msp_lvl_l').par.brightness1.expr = f"{GLOW_BASE} + {GLOW_LOW} * {_ch('msp_drive', 'low')}"
    print('[build_audio] done: source =', src.OPType, audio_file or device or 'default device')
    return made['msp_drive']


if __name__ == '__main__':
    build_audio()
