"""
build_spiral.py
===============
r/TouchDesigner「Audiovisual - a Tribute to Machinarium」(Yasiin_Miim) の見た目を
/project1 に組む（音反応なし・時間駆動のみ。音は build_audio.py で後から足す）。

  msp_geo_cb (Text DAT: spiral_geo.py) ─► msp_geo/msp_sop (Script SOP) ─► msp_mat (Constant MAT)
  msp_cam ─► msp_render (720x1280, 16bit float)
              ├─ msp_blur_s ─ msp_lvl_s ┐
              ├─ msp_blur_l ─ msp_lvl_l ┼─► msp_glow (add) ─► msp_bgadd (+背景) ─► msp_tone
              └───────────────────────┘
  msp_txt0..2 (でたらめ文字の HUD) ─► msp_hud (over) ─► msp_out
  msp_tick (Execute DAT): 毎フレーム Script SOP を cook、数フレームごとに HUD の文字を入れ替え

実行（TD の HTTP exec / Textport）:
  P='/Users/ryookada/work/td-machinarium-spiral/scripts/build_spiral.py'
  g=dict(globals()); g['__file__']=P; exec(open(P).read(), g); g['build_spiral']()
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import td_build as tb  # noqa: E402

RES = (720, 1280)
PREFIX = 'msp_'
CAM_A = '(absTime.seconds*0.06 + 0.5*math.sin(absTime.seconds*0.045))'
CAM_D = '(3.7 + 0.7*math.sin(absTime.seconds*0.11))'

TICK = '''
import random
CH = 'abcdefghijklmnopqrstuvwxyz'

def _gib(n):
    return ''.join(random.choice(CH) if random.random() > 0.35 else
                   random.choice(' *\\u00b7') for _ in range(n))

def onFrameStart(frame):
    op('msp_geo/msp_sop').cook(force=True)
    if frame % 4 == 0:
        for i, rows in enumerate(((7, 9), (12, 8, 6, 2), (5, 3, 6))):
            t = op('msp_txt%d' % i)
            if t is not None:
                t.par.text = '\\n'.join(_gib(n) for n in rows)
    return
'''


def build_spiral(path='/project1'):
    p = tb.get_parent(path)
    for c in [c for c in p.children if c.name.startswith(PREFIX)]:
        c.destroy()
    p.store('speed', 1.0)

    with open(os.path.join(HERE, 'spiral_geo.py')) as f:
        tb.ensure(p, 'msp_geo_cb', 'textDAT', -600, 200, text=f.read())

    tb.ensure(p, 'msp_mat', 'constantMAT', -600, 0)
    mat = p.op('msp_mat')
    for pn, pv in (('colorr', 1.0), ('colorg', 1.0), ('colorb', 1.0),
                   ('blending', True), ('srcblend', 'one'), ('destblend', 'one'),
                   ('depthtest', False), ('depthwriting', False)):
        tb.set_pars(mat, {pn: pv})

    geo = tb.ensure(p, 'msp_geo', 'geometryCOMP', -400, 200,
                    pars={'material': mat.path})
    for c in list(geo.children):
        c.destroy()
    sop = geo.create(tb.td.scriptSOP, 'msp_sop')
    sop.par.callbacks = p.op('msp_geo_cb').path
    sop.render = True
    sop.display = True

    tgt = tb.ensure(p, 'msp_target', 'nullCOMP', -400, 0, pars={'ty': 0.3})
    tb.ensure(p, 'msp_cam', 'cameraCOMP', -400, -200, pars={
        # 回転角に緩い揺らぎ（速度変化）、距離と高さに寄り引き
        'tx': ('expr', CAM_D + '*math.sin(' + CAM_A + ')'),
        'ty': ('expr', '3.7 + 0.6*math.sin(absTime.seconds*0.07 + 1.0)'),
        'tz': ('expr', CAM_D + '*math.cos(' + CAM_A + ')'),
        'lookat': tgt.path,
        'fov': 70,
    })

    tb.ensure(p, 'msp_render', 'renderTOP', -200, 0, res=RES, pars={
        'camera': p.op('msp_cam').path, 'geometry': geo.path, 'lights': '',
        'format': 'rgba16float',
    })
    tb.ensure(p, 'msp_blur_s', 'blurTOP', 0, 100, pars={'size': 6, 'format': 'rgba16float'},
              inputs=['msp_render'])
    tb.ensure(p, 'msp_blur_l', 'blurTOP', 0, -100, pars={'size': 90, 'format': 'rgba16float'},
              inputs=['msp_render'])
    tb.ensure(p, 'msp_lvl_s', 'levelTOP', 150, 100, pars={'brightness1': 1.2},
              inputs=['msp_blur_s'])
    tb.ensure(p, 'msp_lvl_l', 'levelTOP', 150, -100, pars={'brightness1': 2.0},
              inputs=['msp_blur_l'])
    tb.ensure(p, 'msp_glow', 'compositeTOP', 300, 0, pars={'operand': 'add'},
              inputs=['msp_render', 'msp_lvl_s', 'msp_lvl_l'])

    tb.ensure(p, 'msp_bg', 'constantTOP', 300, -200, res=RES,
              pars={'colorr': 0.055, 'colorg': 0.04, 'colorb': 0.04})
    tb.ensure(p, 'msp_bgadd', 'compositeTOP', 450, 0, pars={'operand': 'add'},
              inputs=['msp_glow', 'msp_bg'])
    tb.ensure(p, 'msp_tone', 'levelTOP', 600, 0, pars={'gamma1': 0.9},
              inputs=['msp_bgadd'])

    # HUD: 元動画の右上・左下に出るでたらめな小文字の塊
    spots = ((520, 830), (180, 500), (520, 640))   # (x, y) ピクセル、原点は左下
    for i, (x, y) in enumerate(spots):
        tb.ensure(p, f'msp_txt{i}', 'textTOP', 600, -200 - i * 120, res=RES, pars={
            'text': '', 'fontsizexunit': 'pixels', 'fontsizex': 13,
            'alignx': 'left', 'aligny': 'top', 'positionunit': 'pixels',
            'positionx': x, 'positiony': y - RES[1],   # 左上基準なので下へはマイナス
            'fontcolorr': 0.75, 'fontcolorg': 0.68, 'fontcolorb': 0.66, 'fontalpha': 0.55,
            'bgalpha': 0, 'linespacing': 6,
        })
    tb.ensure(p, 'msp_hud', 'compositeTOP', 800, 0, pars={'operand': 'over'},
              inputs=['msp_txt0', 'msp_txt1', 'msp_txt2', 'msp_tone'])
    tb.ensure(p, 'msp_out', 'nullTOP', 950, 0, inputs=['msp_hud'])

    tb.ensure(p, 'msp_tick', 'executeDAT', -600, -200, text=TICK,
              pars={'framestart': True, 'active': True})
    print('[build_spiral] done:', len([c for c in p.children if c.name.startswith(PREFIX)]), 'nodes')
    return p.op('msp_out')


if __name__ == '__main__':
    build_spiral()
