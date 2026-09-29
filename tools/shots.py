# -*- coding: utf-8 -*-
"""无头 Chrome 批量截图（CLI --screenshot 模式，无需 CDP）。

用临时副本注入主题（原页面主题存在 localStorage，file:// 下不便预置），
再按 #clock / #year / #month 入口逐个出图。

用法：python shots.py <主题:light|dark> <视图:clock|year|month> <宽> <高> <输出png>
"""
import os
import shutil
import subprocess
import sys

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(ROOT, "_shotsrc")


def make_src(theme, probe=False):
    """把主题强制写死的临时副本，放在应用目录内，保证相对路径可用。"""
    os.makedirs(TMP, exist_ok=True)
    with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as fp:
        src = fp.read()
    old = 'pref = localStorage.getItem("calendar_clock_theme") || "auto";'
    assert src.count(old) == 1, "主题读取语句未命中"
    src = src.replace(old, 'pref = "%s";' % theme)
    # 无头截图下平滑滚动会在虚拟时间里停在半途，导致 sticky 页头错位；改成瞬时滚动
    src = src.replace('{ behavior: smooth ? "smooth" : "auto", block: "nearest" }',
                      '{ behavior: "auto", block: "nearest" }')
    # 预览不自动滚动：headless 对 fixed 背景页截图会把视口吸附层画偏，索性停在页首
    src = src.replace("function scrollToMonth(mo, flash, smooth) {",
                      "function scrollToMonth(mo, flash, smooth) { if (window.__noscroll) return;")
    # 必须在应用脚本之前置位：#year 入口的滚动发生在解析期，而非 load 之后
    src = src.replace("</head>", "<script>window.__noscroll = 1;</script></head>")
    if probe:
        src = src.replace("</body>", """<script>
window.addEventListener("load", function () {
  window.__noscroll = 1;
  setTimeout(function () {
    var h = document.querySelector(".page-head"), r = h.getBoundingClientRect(),
        cs = getComputedStyle(h), s = document.documentElement,
        m = document.querySelectorAll(".month")[8],
        mr = m ? m.getBoundingClientRect() : null,
        w = document.querySelector(".wrap");
    var t = "scrollY=" + (window.scrollY || s.scrollTop)
      + " | headTop=" + r.top.toFixed(1) + " pos=" + cs.position + " top=" + cs.top
      + " | docH=" + s.scrollHeight + " vh=" + innerHeight
      + " | wrapOF=" + getComputedStyle(w).overflow
      + " | bodyOF=" + getComputedStyle(document.body).overflow
      + (mr ? " | sepTop=" + mr.top.toFixed(1) : "");
    var d = document.createElement("pre");
    d.style.cssText = "position:fixed;left:4px;top:4px;z-index:99999;background:#000;color:#0f0;font:12px monospace;padding:6px;margin:0;white-space:pre";
    d.textContent = t;
    document.body.appendChild(d);
  }, 500);
});
</script></body>""")
    out = os.path.join(TMP, "app-%s.html" % theme)
    with open(out, "w", encoding="utf-8") as fp:
        fp.write(src)
    return out


def shot(theme, view, w, h, out, budget=5000, wait_vf=True, probe=False):
    src = make_src(theme, probe)
    url = "file:///" + src.replace("\\", "/")
    if view != "clock":
        url += "#" + view
    args = [CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
            "--hide-scrollbars", "--disable-smooth-scrolling",
            "--force-device-scale-factor=1",
            "--window-size=%d,%d" % (w, h),
            "--screenshot=" + out, url]
    if wait_vf:
        args.insert(-1, "--virtual-time-budget=%d" % budget)
    r = subprocess.run(args, capture_output=True, timeout=120)
    err = r.stderr.decode("utf-8", "ignore")
    bad = [l for l in err.splitlines() if "ERROR" in l and "optimization_guide" not in l and "ntp" not in l]
    ok = os.path.exists(out) and os.path.getsize(out) > 2000
    print("%-6s %-7s %dx%d -> %s  %s" % (theme, view, w, h, os.path.basename(out),
                                         "OK %dKB" % (os.path.getsize(out) // 1024) if ok else "FAIL"))
    for l in bad[:4]:
        print("    " + l[:160])
    return ok


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(0 if shot(a[0], a[1], int(a[2]), int(a[3]), a[4]) else 1)
