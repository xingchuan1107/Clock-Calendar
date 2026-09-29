# -*- coding: utf-8 -*-
"""蔷薇浮雕纹样生成器 + index.html 配色/面板补丁

用途
----
1. 参数化生成三套「蔷薇浮雕」纹样（base64 data-URI）：
   - --tex-rose-tile  320x320 无缝平铺蔷薇格（背景满屏平铺）
   - --tex-rose-one   200x200 单枝蔷薇（月历卡角花水印）
   - --tex-rose-med   200x200 蔷薇圆花饰（时钟卡中心浮雕水印）
2. 把新的变量、背景层叠、面板「同料半透明 + 浮雕边」样式打到 index.html。

设计要点
--------
* 平铺无缝：整个纹样由「中心大蔷薇（内部）+ 四角小蔷薇 + 四条中线小枝 + 四点缀珠」组成，
  四角/小枝/缀珠的位置构成 90° 旋转对称，四个 tile 的份角各自贡献一个象限，
  拼起来正好合成完整的蔷薇（切—转—贴 = 原图）。
* 去条纹：取消原来贯穿整幅的 S 形长卷草与所有回字纹重复带，
  只保留「花—空—花」的疏朗节奏，视线不再被横竖条带切割。
* 浮雕：每个花体分三层描边绘制（阴影 / 高光 / 墨线，各偏 0.9 单位），
  在浅底上形成浅浮雕的隆起感；背景平铺层因线条过细，只用单层墨线避免糊成一团。
"""

import base64
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "index.html")
OUT_CSS = os.path.join(ROOT, "tools", "rose-texture-vars.css")

TILE = 320


# --------------------------------------------------------------------------- #
# 基础几何：数字压缩 + 花瓣 / 叶片路径
# --------------------------------------------------------------------------- #
def f(v):
    """压掉多余字符，减小 data-URI 体积。"""
    s = "%.1f" % v
    if s.endswith(".0"):
        s = s[:-2]
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-." + s[3:]
    return s


def _cubic(pts):
    return "M0 0C" + " ".join("%s %s" % (f(x), f(y)) for x, y in pts) + " 0 0"


def petal_path(L, HW):
    """向上的宽瓣蔷薇花瓣：圆肩、钝尖。HW = 最大宽度的一半。"""
    return " ".join([
        "M0 0",
        "C", f(0.50 * HW), f(-0.05 * L), f(0.88 * HW), f(-0.42 * L), f(0.66 * HW), f(-0.82 * L),
        "C", f(0.54 * HW), f(-0.95 * L), f(0.21 * HW), f(-1.00 * L), "0", f(-L),
        "C", f(-0.21 * HW), f(-1.00 * L), f(-0.54 * HW), f(-0.95 * L), f(-0.66 * HW), f(-0.82 * L),
        "C", f(-0.88 * HW), f(-0.42 * L), f(-0.50 * HW), f(-0.05 * L), "0", "0",
    ])


def leaf_path(L, W):
    """向上的叶片（比花瓣更瘦、更尖）。"""
    return _cubic([(W, -0.30 * L), (0.66 * W, -0.78 * L), (0, -L),
                   (-0.66 * W, -0.78 * L), (-W, -0.30 * L)])


# --------------------------------------------------------------------------- #
# 单元件（半径统一归一化为 100，用 transform 缩放）
# --------------------------------------------------------------------------- #
def spiral_path(r0, r1, turns, n=44):
    """阿基米德螺线：用作蔷薇花心，比再叠一圈花瓣干净得多。"""
    pts = []
    for i in range(n + 1):
        t = i / n
        a = t * turns * 2 * math.pi
        rr = r0 + (r1 - r0) * t
        pts.append("%s %s" % (f(rr * math.sin(a)), f(-rr * math.cos(a))))
    return "M" + " L".join(pts)


def rose_unit(r=100):
    """五出蔷薇：五枚萼叶 + 外层宽瓣 + 内层错位瓣 + 螺线花心。"""
    out = []
    # 萼叶垫在最底层，从花瓣空隙探出去
    for k in range(5):
        out.append('<path transform="rotate(%d)" d="%s"/>' % (36 + 72 * k, leaf_path(r * 1.18, r * 0.19)))
    # 外层宽瓣
    for k in range(5):
        out.append('<path transform="rotate(%d)" d="%s"/>' % (72 * k, petal_path(r, r * 0.45)))
    # 内层错位瓣（夹在两外瓣之间，明显更短小）
    for k in range(5):
        out.append('<path transform="rotate(%d)" d="%s"/>' % (36 + 72 * k, petal_path(r * 0.52, r * 0.24)))
    # 螺线花心
    out.append('<path d="%s"/>' % spiral_path(r * 0.045, r * 0.175, 1.8))
    return '<g id="R">' + "".join(out) + "</g>"


def sprig_unit(r=100):
    """三叶小枝：中点对称，用来填花与花之间的大片空白。"""
    out = [
        '<path transform="rotate(0)" d="%s"/>' % petal_path(r * 0.36, r * 0.15),
        '<path transform="rotate(-38)" d="%s"/>' % leaf_path(r * 0.80, r * 0.20),
        '<path transform="rotate(38)" d="%s"/>' % leaf_path(r * 0.80, r * 0.20),
        '<path transform="rotate(180)" d="%s"/>' % leaf_path(r * 0.58, r * 0.15),
        '<circle r="%s"/>' % f(r * 0.08),
    ]
    return '<g id="S">' + "".join(out) + "</g>"


def _use(hid, transform, sw):
    return ('<use xlink:href="#%s" href="#%s" transform="%s" stroke-width="%s"/>'
            % (hid, hid, transform, sw))


def _asset(vb, body, defs):
    return ('<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            'width="%d" height="%d" viewBox="0 0 %d %d">'
            '<defs>%s</defs>%s</svg>' % (vb, vb, vb, vb, defs, body))


def b64(svg):
    return base64.b64encode(svg.encode("utf-8")).decode("ascii")


# --------------------------------------------------------------------------- #
# 纹样一：背景满屏平铺的蔷薇格
# --------------------------------------------------------------------------- #
def tile_svg(ink, opacity):
    """中心大蔷薇 + 四角小蔷薇 + 四条中线小枝 + 四点缀珠。"""
    place = [
        # 四角小蔷薇（第一次画在原点，其余三个角由 90/180/270 度拷贝生成）
        _use("R", "scale(.27)", 2.3),
        # 中心大蔷薇
        _use("R", "translate(160 160) scale(.46)", 2.0),
    ]
    for p in ((160, 46), (274, 160), (160, 274), (46, 160)):
        place.append(_use("S", "translate(%d %d) scale(.15)" % p, 2.6))
    # 四角小蔷薇的 90/180/270 度拷贝
    for a in (90, 180, 270):
        place.append('<g transform="rotate(%d 160 160)">' % a + _use("R", "scale(.27)", 2.3) + "</g>")
    # 对角缀珠（细碎的点，只作「精致」的余韵，不成线）
    for p in ((207, 113), (207, 207), (113, 207), (113, 113)):
        place.append('<path transform="translate(%d %d)" d="M0 0h0" stroke-width="3.2"/>')

    body = ('<g fill="none" stroke="%s" stroke-linecap="round" stroke-linejoin="round" '
            'opacity="%s">' % (ink, opacity) + "".join(place) + "</g>")
    return _asset(TILE, body, rose_unit() + sprig_unit())


# --------------------------------------------------------------------------- #
# 纹样二：单枝蔷薇（卡角水印，斜向构图）
# --------------------------------------------------------------------------- #
def sprig_svg(ink, hi, hi_o, sh, sh_o):
    BODY = "".join([
        _use("R", "translate(126 60) scale(.46)", 2.4),
        '<path d="M116 96C96 122 74 146 44 166" stroke-width="2.2"/>',
        '<path transform="translate(102 112) rotate(-118)" d="%s" stroke-width="2.0"/>' % leaf_path(30, 8),
        '<path transform="translate(82 133) rotate(148)" d="%s" stroke-width="2.0"/>' % leaf_path(27, 7.2),
        '<path transform="translate(62 152) rotate(-124)" d="%s" stroke-width="1.9"/>' % leaf_path(24, 6.4),
    ])

    def layer(stroke, so, dx, dy):
        return ('<g fill="none" stroke="%s" stroke-opacity="%s" stroke-linecap="round" '
                'stroke-linejoin="round" transform="translate(%s %s)">%s</g>'
                % (stroke, so, f(dx), f(dy), BODY))

    body = (layer(sh, sh_o, 0.9, 0.9) + layer(hi, hi_o, -0.9, -0.9) + layer(ink, "1", 0, 0))
    return _asset(200, body, rose_unit())


# --------------------------------------------------------------------------- #
# 纹样三：蔷薇圆花饰（时钟卡中心浮雕水印）
# --------------------------------------------------------------------------- #
def medallion_svg(ink, hi, hi_o, sh, sh_o):
    parts = [
        '<circle cx="100" cy="100" r="86" stroke-width="2.4"/>',
        '<circle cx="100" cy="100" r="72.5" stroke-width="1"/>',
        _use("R", "translate(100 100) scale(.56)", 1.15),
    ]
    for k in range(12):
        parts.append('<path transform="translate(100 100) rotate(%d) translate(0 -79.2)" '
                     'd="M0 0h0" stroke-width="2.6"/>' % (30 * k))
    for k in range(4):
        parts.append('<path transform="translate(100 100) rotate(%d) translate(0 -86)" d="%s" '
                     'stroke-width="1.4"/>' % (45 + 90 * k, leaf_path(13, 3.4)))
    BODY = "".join(parts)

    def layer(stroke, so, dx, dy):
        return ('<g fill="none" stroke="%s" stroke-opacity="%s" stroke-linecap="round" '
                'stroke-linejoin="round" transform="translate(%s %s)">%s</g>'
                % (stroke, so, f(dx), f(dy), BODY))

    body = (layer(sh, sh_o, 1.0, 1.0) + layer(hi, hi_o, -1.0, -1.0) + layer(ink, "1", 0, 0))
    return _asset(200, body, rose_unit())


THEMES = {
    "light": dict(
        ink="#a8905e", hi="#ffffff", hi_o=".78", sh="#7d6b45", sh_o=".30",
        tile_o=".30",
    ),
    "dark": dict(
        ink="#c9a95f", hi="#ffe9b8", hi_o=".30", sh="#000000", sh_o=".62",
        tile_o=".35",
    ),
}


def build_assets():
    res = {}
    for name, c in THEMES.items():
        res[name] = {
            "tile": b64(tile_svg(c["ink"], c["tile_o"])),
            "one": b64(sprig_svg(c["ink"], c["hi"], c["hi_o"], c["sh"], c["sh_o"])),
            "med": b64(medallion_svg(c["ink"], c["hi"], c["hi_o"], c["sh"], c["sh_o"])),
        }
    return res


LIGHT_VARS = """    /* ---- 蔷薇浮雕纹样（浅色：宣纸金线 · 疏朗蔷薇格，无贯穿条纹） ---- */
    --tex-rose-tile:url("data:image/svg+xml;base64,%(tile)s");
    --tex-rose-one:url("data:image/svg+xml;base64,%(one)s");
    --tex-rose-med:url("data:image/svg+xml;base64,%(med)s");
    /* ---- 内容区柔光：把纹样在视觉中心轻轻压下去，卡片与背景自然过渡 ---- */
    --halo:rgba(251,250,247,.60);
    --halo2:rgba(251,250,247,.32);
    /* ---- 同料半透明面板 + 浅浮雕边 ---- */
    --panel-a:rgba(255,255,255,.74);
    --panel-b:rgba(255,255,255,.62);
    --panel-2-a:rgba(252,251,248,.66);
    --field:rgba(255,255,255,.84);
    --field-focus:rgba(255,255,255,.94);
    --bevel-hi:rgba(255,255,255,.95);
    --bevel-lo:rgba(147,133,104,.12);
    --ring:rgba(179,148,87,.16);
    --bevel:inset 0 0 0 1px var(--ring), inset 0 1px 0 var(--bevel-hi), inset 0 -1px 0 var(--bevel-lo);
    --lift:0 1px 2px rgba(35,42,51,.04), 0 10px 30px rgba(35,42,51,.06);"""

DARK_VARS = """    /* ---- 蔷薇浮雕纹样（深色：鎏金线 · 同款蔷薇格） ---- */
    --tex-rose-tile:url("data:image/svg+xml;base64,%(tile)s");
    --tex-rose-one:url("data:image/svg+xml;base64,%(one)s");
    --tex-rose-med:url("data:image/svg+xml;base64,%(med)s");
    --halo:rgba(9,11,17,.54);
    --halo2:rgba(9,11,17,.28);
    --panel-a:rgba(23,28,41,.74);
    --panel-b:rgba(26,31,45,.64);
    --panel-2-a:rgba(29,35,50,.62);
    --field:rgba(25,30,44,.86);
    --field-focus:rgba(30,36,52,.94);
    --bevel-hi:rgba(178,196,232,.16);
    --bevel-lo:rgba(0,0,0,.50);
    --ring:rgba(201,169,95,.18);
    --bevel:inset 0 0 0 1px var(--ring), inset 0 1px 0 var(--bevel-hi), inset 0 -1px 0 var(--bevel-lo);
    --lift:0 2px 6px rgba(0,0,0,.32), 0 14px 36px rgba(0,0,0,.34);"""


# --------------------------------------------------------------------------- #
# 补丁
# --------------------------------------------------------------------------- #
PLATE_BLUR = ("backdrop-filter:blur(16px) saturate(1.05);"
              "-webkit-backdrop-filter:blur(16px) saturate(1.05);")


def build_edits(a):
    L, D = a["light"], a["dark"]
    light_vars = LIGHT_VARS % L
    dark_vars = DARK_VARS % D

    edits = []

    # ---- 1. 变量 ----
    edits.append((
        "浅色纹样变量",
        re.compile(r'    /\* 满屏平铺的古典卷草大马士革纹（浅色：宣纸金线） \*/\n    --tex-damask:url\("data:image/svg\+xml,[^"]*"\);'),
        light_vars,
    ))
    edits.append((
        "深色纹样变量",
        re.compile(r'    --tex-damask:url\("data:image/svg\+xml,[^"]*"\);'),
        dark_vars,
    ))

    # ---- 2. body 背景层叠：柔光 + 双色晕染 + 蔷薇格 + 纸底 ----
    edits.append((
        "body 背景层叠",
        """    background-image:
      var(--tex-damask),
      radial-gradient(1200px 640px at 8% -12%, var(--wash-1) 0%, rgba(0,0,0,0) 62%),
      radial-gradient(980px 520px at 102% -4%, var(--wash-2) 0%, rgba(0,0,0,0) 58%),
      linear-gradient(180deg,var(--bg2) 0%, var(--bg) 100%);
    background-size:260px 260px, auto, auto, auto;
    background-repeat:repeat, no-repeat, no-repeat, no-repeat;
    background-attachment:fixed;""",
        """    background-image:
      radial-gradient(96% 68% at 50% 24%, var(--halo) 0%, var(--halo2) 52%, rgba(0,0,0,0) 100%),
      radial-gradient(1200px 640px at 8% -12%, var(--wash-1) 0%, rgba(0,0,0,0) 62%),
      radial-gradient(980px 520px at 102% -4%, var(--wash-2) 0%, rgba(0,0,0,0) 58%),
      var(--tex-rose-tile),
      linear-gradient(180deg,var(--bg2) 0%, var(--bg) 100%);
    background-size:auto, auto, auto, 320px 320px, auto;
    background-repeat:no-repeat, no-repeat, no-repeat, repeat, no-repeat;
    background-attachment:fixed;""",
    ))

    # ---- 3. 装饰件：细线压边 + 卡面同料纹（替换原方格网纹） ----
    edits.append((
        "frieze 条纹带 → 点金细线",
        """  .frieze{
    position:absolute;left:0;right:0;height:11px;pointer-events:none;
    background-image:var(--tex-meander);background-repeat:repeat-x;background-size:auto 11px;
    opacity:.4;
  }
  .frieze.t{top:0}
  .frieze.b{bottom:0}
  .frieze.v{position:static;left:auto;right:auto;height:11px;margin:0}
  /* 方格纹底纹 */
  .weave{
    position:absolute;inset:0;pointer-events:none;
    background-image:var(--tex-lattice);background-size:22px 22px;opacity:.2;
    -webkit-mask-image:radial-gradient(78% 82% at 50% 12%,#000 0%,rgba(0,0,0,.35) 55%,transparent 82%);
    mask-image:radial-gradient(78% 82% at 50% 12%,#000 0%,rgba(0,0,0,.35) 55%,transparent 82%);
  }""",
        """  /* 上下沿只留一道点金细线：原先的回字纹重复带已撤掉，避免横向条纹感 */
  .frieze{
    position:absolute;left:11%;right:11%;height:1px;pointer-events:none;
    background:linear-gradient(90deg,transparent 0%,var(--gold) 24%,var(--gold) 76%,transparent 100%);
    opacity:.32;
  }
  .frieze.t{top:0;box-shadow:0 1px 0 var(--bevel-hi)}
  .frieze.b{bottom:0;opacity:.2}
  .frieze.v{position:static;left:auto;right:auto;height:1px;margin:0;box-shadow:none}
  /* 卡面自身的「同料」纹样：中心留白、四角渐显，
     让卡片像是从同一张纹样纸上裁下来的，而不是浮在背景上 */
  .panel-rose{
    position:absolute;inset:0;pointer-events:none;
    background-image:var(--tex-rose-tile);background-size:320px 320px;
    opacity:.5;
    -webkit-mask-image:radial-gradient(88% 74% at 50% 50%,transparent 0%,rgba(0,0,0,.5) 47%,#000 100%);
    mask-image:radial-gradient(88% 74% at 50% 50%,transparent 0%,rgba(0,0,0,.5) 47%,#000 100%);
  }""",
    ))
    edits.append((
        "角花收敛",
        "  .corner{position:absolute;width:15px;height:15px;border:1px solid var(--gold);opacity:.42;pointer-events:none}",
        "  .corner{position:absolute;width:16px;height:16px;border:1px solid var(--gold);opacity:.3;pointer-events:none}",
    ))

    # ---- 4. 时钟卡：同料底 + 浮雕边 + 中心圆花饰 ----
    edits.append((
        "时钟卡底与浮雕边",
        """    background:var(--panel);
    border:1px solid var(--line);
    border-radius:clamp(20px,2vw,32px);
    box-shadow:var(--shadow-md);
    text-align:center;""",
        """    background:var(--panel-a);
    border:1px solid var(--line);
    border-radius:clamp(20px,2vw,32px);
    box-shadow:var(--bevel), var(--lift);
    text-align:center;
    backdrop-filter:blur(20px) saturate(1.06);
    -webkit-backdrop-filter:blur(20px) saturate(1.06);""",
    ))
    edits.append((
        "时钟卡中心圆花饰",
        """  .clock-card::after{
    content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;
    background:radial-gradient(1400px 340px at 50% -30%, var(--accent-soft), transparent 70%);
  }""",
        """  .clock-card::after{
    content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;
    background:radial-gradient(1400px 340px at 50% -30%, var(--accent-soft), transparent 70%);
  }
  /* 时钟卡中心的蔷薇圆花饰：浅浮雕水印，只在余光里被察觉 */
  .clock-card::before{
    content:"";position:absolute;left:50%;top:45%;width:min(620px,84%);
    aspect-ratio:1/1;transform:translate(-50%,-50%);pointer-events:none;
    background:var(--tex-rose-med) center/contain no-repeat;
    opacity:.3;
  }""",
    ))

    # ---- 5. 页头：半透明 + 细金线 ----
    edits.append((
        "页头底",
        """    background:linear-gradient(180deg,rgba(255,254,251,.94) 0%,rgba(255,254,251,.86) 100%);
    backdrop-filter:blur(14px) saturate(1.2);
    -webkit-backdrop-filter:blur(14px) saturate(1.2);""",
        """    background:linear-gradient(180deg,rgba(255,254,251,.80) 0%,rgba(255,254,251,.64) 100%);
    backdrop-filter:blur(20px) saturate(1.15);
    -webkit-backdrop-filter:blur(20px) saturate(1.15);""",
    ))
    edits.append((
        "页头深色底",
        '  html[data-theme="dark"] .page-head{background:linear-gradient(180deg,rgba(26,29,33,.94) 0%,rgba(26,29,33,.86) 100%)}',
        '  html[data-theme="dark"] .page-head{background:linear-gradient(180deg,rgba(15,18,26,.82) 0%,rgba(15,18,26,.66) 100%)}',
    ))
    edits.append((
        "页头回字纹带 → 细金线",
        """  .page-head::after{
    content:"";position:absolute;left:0;right:0;bottom:0;height:10px;pointer-events:none;
    background-image:var(--tex-meander);background-repeat:repeat-x;background-size:auto 10px;
    opacity:.28;
  }""",
        """  .page-head::after{
    content:"";position:absolute;left:0;right:0;bottom:0;height:1px;pointer-events:none;
    background:linear-gradient(90deg,transparent 0%,var(--gold) 28%,var(--gold) 72%,transparent 100%);
    opacity:.3;
  }""",
    ))

    # ---- 6. 各面板改「同料半透明 + 浮雕边」 ----
    edits.append((
        "日期条",
        """    padding:16px 20px 16px 22px;margin-bottom:18px;
    background:var(--panel);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow-sm);""",
        """    padding:16px 20px 16px 22px;margin-bottom:18px;
    background:var(--panel-a);border:1px solid var(--line);border-radius:18px;
    box-shadow:var(--bevel), var(--lift);""" + PLATE_BLUR,
    ))
    edits.append((
        "图例条",
        """    padding:13px 20px;margin-bottom:var(--gap);
    background:var(--panel);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow-sm);""",
        """    padding:13px 20px;margin-bottom:var(--gap);
    background:var(--panel-a);border:1px solid var(--line);border-radius:14px;
    box-shadow:var(--bevel), var(--lift);""" + PLATE_BLUR,
    ))
    edits.append((
        "月视图导航",
        """    padding:12px 16px;margin-bottom:var(--gap);
    background:var(--panel);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow-sm);""",
        """    padding:12px 16px;margin-bottom:var(--gap);
    background:var(--panel-a);border:1px solid var(--line);border-radius:14px;
    box-shadow:var(--bevel), var(--lift);""" + PLATE_BLUR,
    ))
    edits.append((
        "数据说明条",
        """    background:var(--panel);border:1px solid var(--line);border-radius:14px;
    padding:14px 20px 14px 22px;box-shadow:var(--shadow-sm);""",
        """    background:var(--panel-a);border:1px solid var(--line);border-radius:14px;
    padding:14px 20px 14px 22px;box-shadow:var(--bevel), var(--lift);""" + PLATE_BLUR,
    ))
    edits.append((
        "月份卡 + 角花",
        """  .month{
    display:flex;flex-direction:column;
    background:var(--panel);border:1px solid var(--line);border-radius:18px;
    padding:18px 16px 16px;box-shadow:var(--shadow-sm);
    scroll-margin-top:104px;
    transition:box-shadow .28s, border-color .28s, transform .28s;
  }""",
        """  .month{
    position:relative;overflow:hidden;
    display:flex;flex-direction:column;
    background:var(--panel-a);border:1px solid var(--line);border-radius:18px;
    padding:18px 16px 16px;
    box-shadow:var(--bevel), var(--lift);
    scroll-margin-top:104px;
    transition:box-shadow .28s, border-color .28s, transform .28s;
    backdrop-filter:blur(14px) saturate(1.04);
    -webkit-backdrop-filter:blur(14px) saturate(1.04);
  }
  /* 月份卡右下的蔷薇角花：浅浮雕水印 */
  .month::after{
    content:"";position:absolute;right:4px;bottom:2px;width:128px;height:128px;
    pointer-events:none;background:var(--tex-rose-one) center/contain no-repeat;opacity:.17;
    -webkit-mask-image:radial-gradient(circle at 58% 58%,#000 34%,rgba(0,0,0,.45) 62%,transparent 84%);
    mask-image:radial-gradient(circle at 58% 58%,#000 34%,rgba(0,0,0,.45) 62%,transparent 84%);
  }""",
    ))
    edits.append((
        "笔记区外壳",
        "  .notes-wrap{margin-top:28px;background:var(--panel);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow-sm);overflow:hidden}",
        "  .notes-wrap{margin-top:28px;background:var(--panel-a);border:1px solid var(--line);border-radius:18px;"
        "box-shadow:var(--bevel), var(--lift);overflow:hidden;" + PLATE_BLUR + "}",
    ))
    edits.append((
        "笔记区标题",
        "background:linear-gradient(180deg,var(--panel-2),var(--panel))}",
        "background:linear-gradient(180deg,var(--panel-2-a),var(--panel-a))}",
    ))
    edits.append((
        "笔记条目",
        "    background:var(--panel-2);border:1px solid var(--line);\n  }\n  .note-item::before",
        "    background:var(--panel-2-a);border:1px solid var(--line);\n    box-shadow:inset 0 1px 0 var(--bevel-hi);\n  }\n  .note-item::before",
    ))
    edits.append((
        "笔记条目 hover",
        "  .note-item:hover{background:var(--panel);border-color:var(--accent-line);box-shadow:var(--shadow-sm);transform:translateY(-1px)}",
        "  .note-item:hover{background:var(--panel-b);border-color:var(--accent-line);box-shadow:var(--bevel), var(--lift);transform:translateY(-1px)}",
    ))
    edits.append((
        "右键菜单",
        "    background:var(--panel);backdrop-filter:blur(12px);",
        "    background:var(--panel-a);backdrop-filter:blur(20px) saturate(1.06);-webkit-backdrop-filter:blur(20px) saturate(1.06);",
    ))
    edits.append((
        "笔记弹窗卡",
        "    position:relative;width:min(660px,100%);background:var(--panel);border:1px solid var(--line);border-radius:20px;\n    box-shadow:var(--shadow-lg);overflow:hidden;animation:pop .26s cubic-bezier(.2,.8,.3,1);",
        "    position:relative;width:min(660px,100%);background:var(--panel-a);border:1px solid var(--line);border-radius:20px;\n"
        "    box-shadow:var(--bevel), var(--shadow-lg);overflow:hidden;animation:pop .26s cubic-bezier(.2,.8,.3,1);\n"
        "    backdrop-filter:blur(20px) saturate(1.06);-webkit-backdrop-filter:blur(20px) saturate(1.06);",
    ))
    edits.append((
        "弹窗回字纹带 → 细金线",
        '  .card::before{content:"";position:absolute;left:0;top:0;right:0;height:10px;background-image:var(--tex-meander);background-repeat:repeat-x;background-size:auto 10px;opacity:.3;pointer-events:none}',
        '  .card::before{content:"";position:absolute;left:0;top:0;right:0;height:1px;pointer-events:none;'
        'background:linear-gradient(90deg,transparent 0%,var(--gold) 26%,var(--gold) 74%,transparent 100%);opacity:.34}',
    ))
    edits.append((
        "输入框",
        "    border:1px solid var(--line);background:var(--panel-2);color:var(--text);\n    outline:none;transition:.18s;",
        "    border:1px solid var(--line);background:var(--field);color:var(--text);\n    outline:none;transition:.18s;",
    ))
    edits.append((
        "输入框 focus",
        "  textarea:focus{border-color:var(--accent-line);background:var(--panel);box-shadow:0 0 0 4px var(--accent-soft)}",
        "  textarea:focus{border-color:var(--accent-line);background:var(--field-focus);box-shadow:0 0 0 4px var(--accent-soft)}",
    ))
    edits.append((
        "模板按钮",
        "    padding:5px 11px;border-radius:999px;border:1px solid var(--line);background:var(--panel);",
        "    padding:5px 11px;border-radius:999px;border:1px solid var(--line);background:var(--panel-b);",
    ))
    edits.append((
        "通用按钮",
        "    appearance:none;border:1px solid var(--line);background:var(--panel);color:var(--text2);",
        "    appearance:none;border:1px solid var(--line);background:var(--panel-b);color:var(--text2);",
    ))
    edits.append((
        "复选方框",
        "    width:14px;height:14px;border-radius:4px;border:1.5px solid var(--line);position:relative;flex:0 0 14px;transition:.18s;\n    background:var(--panel);",
        "    width:14px;height:14px;border-radius:4px;border:1.5px solid var(--line);position:relative;flex:0 0 14px;transition:.18s;\n    background:var(--panel-b);",
    ))
    edits.append((
        "节气勾选框",
        "    border:1.4px solid var(--line);border-radius:4px;background:var(--panel);",
        "    border:1.4px solid var(--line);border-radius:4px;background:var(--panel-b);",
    ))
    edits.append((
        "年份控件",
        "  .year-box{display:flex;align-items:center;gap:4px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:3px;box-shadow:var(--shadow-sm)}",
        "  .year-box{display:flex;align-items:center;gap:4px;background:var(--panel-b);border:1px solid var(--line);border-radius:12px;padding:3px;box-shadow:var(--bevel), var(--lift)}",
    ))
    edits.append((
        "视图分段控件",
        "  .seg{display:inline-flex;align-items:center;gap:2px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:3px;box-shadow:var(--shadow-sm)}",
        "  .seg{display:inline-flex;align-items:center;gap:2px;background:var(--panel-b);border:1px solid var(--line);border-radius:12px;padding:3px;box-shadow:var(--bevel), var(--lift)}",
    ))
    edits.append((
        "右下浮动主题钮",
        "    background:var(--panel);border:1px solid var(--accent-line);box-shadow:var(--shadow-md);",
        "    background:var(--panel-a);border:1px solid var(--accent-line);box-shadow:var(--bevel), var(--shadow-md);\n"
        "    backdrop-filter:blur(16px) saturate(1.05);-webkit-backdrop-filter:blur(16px) saturate(1.05);",
    ))
    edits.append((
        "移动端底栏",
        "      background:var(--panel);border-top:1px solid var(--line);",
        "      background:var(--panel-a);border-top:1px solid var(--line);\n"
        "      backdrop-filter:blur(20px) saturate(1.05);-webkit-backdrop-filter:blur(20px) saturate(1.05);",
    ))

    # ---- 7. HTML：卡面纹样 div 改名 ----
    edits.append((
        "时钟卡装饰 div",
        '      <div class="weave" aria-hidden="true"></div>',
        '      <div class="panel-rose" aria-hidden="true"></div>',
    ))
    return edits


def main():
    apply = "--apply" in sys.argv
    assets = build_assets()
    for name, d in assets.items():
        print("%-6s tile=%d  one=%d  med=%d  (base64 chars)" % (name, len(d["tile"]), len(d["one"]), len(d["med"])))

    with open(HTML, encoding="utf-8", newline="") as fp:
        src = fp.read()

    edits = build_edits(assets)
    ok, fail = [], []
    for name, pat, rep in edits:
        if isinstance(pat, re.Pattern):
            hits = len(pat.findall(src))
        else:
            hits = src.count(pat)
        if hits != 1:
            fail.append("%-22s 命中 %d 次" % (name, hits))
            continue
        src = pat.sub(lambda m: rep, src, count=1) if isinstance(pat, re.Pattern) else src.replace(pat, rep, 1)
        ok.append(name)

    print("\n[OK] %d 项：" % len(ok) + "、".join(ok))
    if fail:
        print("\n[FAIL] %d 项未命中：" % len(fail))
        for x in fail:
            print("   - " + x)
        print("\n未写入 index.html。")
        return 1

    if apply:
        with open(HTML, "w", encoding="utf-8", newline="") as fp:
            fp.write(src)
        with open(OUT_CSS, "w", encoding="utf-8", newline="") as fp:
            fp.write("/* 由 tools/gen-rose-texture.py 生成，供查阅纹样变量 */\n:root{\n"
                     + (LIGHT_VARS % assets["light"]) + "\n}\nhtml[data-theme=\"dark\"]{\n"
                     + (DARK_VARS % assets["dark"]) + "\n}\n")
        print("\n已写入 %s（%d 字节）与 %s" % (HTML, len(src.encode('utf-8')), OUT_CSS))
    else:
        print("\n[dry-run] 全部命中，加 --apply 才会写盘。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
