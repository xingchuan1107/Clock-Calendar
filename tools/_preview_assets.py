# -*- coding: utf-8 -*-
"""临时的纹样检视页：把生成的三套蔷薇纹样平铺/放大渲染，供截图核对。"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("gt", os.path.join(os.path.dirname(os.path.abspath(__file__)), "gen-rose-texture.py"))
gt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gt)

A = gt.build_assets()

BLOCKS = []
for theme, bg, fg in (("light", "#f7f6f2", "#1c2530"), ("dark", "#0a0c12", "#e8eaef")):
    d = A[theme]
    BLOCKS.append(f"""
<h2>{theme}</h2>
<div class="row" style="background:{bg};color:{fg}">
  <div class="cell">
    <p>tile 320 (2x2 检验无缝)</p>
    <div class="tile" style="background-image:url('data:image/svg+xml;base64,{d['tile']}')"></div>
  </div>
  <div class="cell">
    <p>tile 96 (实际观感)</p>
    <div class="tile small" style="background-image:url('data:image/svg+xml;base64,{d['tile']}')"></div>
  </div>
  <div class="cell">
    <p>one 单枝蔷薇</p>
    <img class="orn" src="data:image/svg+xml;base64,{d['one']}">
  </div>
  <div class="cell">
    <p>med 圆花饰</p>
    <img class="orn" src="data:image/svg+xml;base64,{d['med']}">
  </div>
</div>""")

HTML = """<!doctype html><meta charset="utf-8"><style>
body{font:13px/1.6 system-ui;margin:0;padding:16px;background:#888}
h2{margin:14px 0 6px;font-size:14px}
.row{display:grid;grid-template-columns:auto auto auto auto;gap:14px;padding:14px;align-items:start}
.cell p{margin:0 0 6px;opacity:.7;font-size:12px}
.tile{width:640px;height:640px;background-size:320px 320px;border:1px solid #0002}
.tile.small{width:320px;height:320px;background-size:96px 96px}
.orn{width:200px;height:200px}
</style>""" + "".join(BLOCKS)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tex_preview.html")
with open(out, "w", encoding="utf-8") as fp:
    fp.write(HTML)
print(out)
