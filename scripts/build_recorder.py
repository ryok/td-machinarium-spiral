"""
build_recorder.py
=================
msp_out（720x1280）を曲の音と一緒に1本の動画に録る。build_spiral → build_audio(audio_file=...) の後に実行。

  msp_rec (Movie File Out TOP)  audiochop=msp_aud_in で音も焼き込む
  msp_rec_ctl (Execute DAT)     曲の長さが過ぎたら録画を止める

  録画: op('/project1/msp_rec_ctl').module.start(秒数)
        曲を頭に戻し、回転の時刻（msp_time）も 0 に戻してから録画を始める。
        録れたファイルは reference/take_raw.mov（gitignore）。
  SNS 用には ffmpeg で H.264 に変換する（README「録画」）。

Movie File Out はリアルタイムで書くので、TD が 30fps を割ると録画もコマ落ちする。
録画中は TD の他の作業をしない。
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import td_build as tb  # noqa: E402

OUT_FILE = os.path.join(os.path.dirname(HERE), 'reference', 'take_raw.mov')

CTL = '''
def start(dur):
    p = parent()
    # 曲と、build_stems のステム（msp_stemin_*）を同じフレームで頭に戻す
    for a in [op('msp_aud_in')] + p.findChildren(name='msp_stemin_*', depth=1):
        a.par.cuepoint = 0
        a.par.cuepulse.pulse()
        a.par.play = True
    op('msp_time').par.resetpulse.pulse()
    p.store('_rec', {'t0': absTime.seconds, 'dur': float(dur)})
    op('msp_rec').par.record = True

def stop():
    op('msp_rec').par.record = False
    parent().unstore('_rec')

def onFrameEnd(frame):
    r = parent().fetch('_rec', None, search=False)
    if r and absTime.seconds - r['t0'] >= r['dur']:
        stop()
    return
'''


def build_recorder(path='/project1', out_file=OUT_FILE):
    p = tb.get_parent(path)
    tb.require(p, 'msp_out', 'msp_aud_in', 'msp_time',
               hint='build_spiral.py → build_audio.py(audio_file=...)')
    tb.ensure(p, 'msp_rec', 'moviefileoutTOP', 1100, 0, inputs=['msp_out'], pars={
        'type': 'movie', 'videocodec': 'mpeg4', 'fps': 30, 'record': False,
        'audiochop': p.op('msp_aud_in').path, 'audiocodec': 'mp3', 'file': out_file})
    tb.ensure(p, 'msp_rec_ctl', 'executeDAT', 1100, -150, text=CTL,
              pars={'frameend': True, 'active': True})
    print(f"[build_recorder] -> {out_file}. 録画: op('{p.path}/msp_rec_ctl').module.start(秒数)")
    return p.op('msp_rec')


if __name__ == '__main__':
    build_recorder()
