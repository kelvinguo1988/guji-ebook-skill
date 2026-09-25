#!/usr/bin/env python3
"""vYinn 式古籍电子印章合成（Python 移植，对齐 shanleiguang/vYinn v1.1 的 Perl 流程）

vYinn 的构造是：黑色画布 → 印框图层（阳文=黑底白框）→ 逐字图层（白=印泥）→
破残斑点 Multiply → OTSU 二值化 → 白色替换印泥色 / 黑色替换背景色 → 模糊·油墨。
本移植用 PIL/numpy 复刻同一分层与效果链，输出透明底 PNG 供复刻引擎贴图。

字体：fonts/chongxi_seal.otf（崇先篆书，vYinn 用方正小篆体，同属小篆系）。
参数命名与 vYinn cfg 一致，便于回查上游调参。
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'assets', 'seal_gzh.png')
FONT = os.path.join(ROOT, 'fonts', 'chongxi_seal.otf')

# ---- 画布 / 导出（vYinn: canvas_*, export_*）----
CW = CH = 1000
YIN_COLOR = '#874434'          # 印泥色（vYinn 默认，与本项目朱注同色系）
CROP = np.array([342, 42, 658, 958])   # 沿印框裁切的留白边界（长条框 +4）

# ---- 印框（frame_*）：阳文=白框黑底；长条形（鉴藏条章）----
FW, FH = 300, 900
FRAME_TYPE = 2                 # 0圆 1方 2圆角方 3椭圆
FOLW, FOLD = 22, 10            # 阳文边框宽度 / 边框与文字间距
FRAME_RADIUS = 26

# ---- 印文（yin_*）：读序自右列起，第一列=右 ----
YIN_TEXT = '郭仲和藏書'
YIN_TYPE = 1                   # 0阴文（白字黑底）1阳文（白字黑底反相）
# 每字：列序、行位（ROWS 格的分数行心）、字号、宽拉伸、长拉伸、旋转（正=顺时针）、描边
LAYOUT = [
    (0, 0.5, 150, 1.00, 1.02, -0.6, 2),
    (0, 1.5, 150, 1.02, 1.00,  0.4, 2),
    (0, 2.5, 150, 1.00, 1.04, -0.3, 2),
    (0, 3.5, 150, 1.01, 1.00,  0.5, 2),
    (0, 4.5, 150, 1.00, 1.03, -0.5, 2),
]
COLS = 1
ROWS = 5

# ---- 效果（effect_*）----
FRAME_SPREAD = 2              # 印框边缘扩散半径（Spread 等效）
CHARS_SPREAD = 1
BLUR = (2, 1.0)               # (radius, sigma) → 高斯近似
OILPAINT = 1                  # 油墨强度（MedianFilter 等效）
BROKENSPOTS = 30              # 随机破残斑点数量

rng = np.random.default_rng(20260925)


def canvas():
    """黑色画布：黑=背景，白=印泥（vYinn 约定）"""
    return Image.new('L', (CW, CH), 0)


def frame_layer():
    img = canvas()
    d = ImageDraw.Draw(img)
    x0, y0 = (CW - FW) / 2, (CH - FH) / 2
    x1, y1 = x0 + FW, y0 + FH
    if YIN_TYPE == 1:                      # 阳文：仅白框环，字亦白（白底朱字朱框）
        d.rounded_rectangle([x0 + FOLW / 2, y0 + FOLW / 2, x1 - FOLW / 2, y1 - FOLW / 2],
                            radius=FRAME_RADIUS, outline=255, width=FOLW)
    else:                                  # 阴文：整框填白、文字区黑挖（朱底白字）
        d.rounded_rectangle([x0, y0, x1, y1], radius=FRAME_RADIUS, fill=255)
        ix0, iy0 = x0 + FOLW + FOLD, y0 + FOLW + FOLD
        ix1, iy1 = x1 - FOLW - FOLD, y1 - FOLW - FOLD
        d.rounded_rectangle([ix0, iy0, ix1, iy1], radius=max(2, FRAME_RADIUS - FOLW), fill=0)
    return img


def char_cells():
    """文字区按 ROWS×COLS 分格，返回每字格心坐标（列序自右起）"""
    x0 = (CW - FW) / 2 + FOLW + FOLD
    y0 = (CH - FH) / 2 + FOLW + FOLD
    w = (FW - 2 * (FOLW + FOLD)) / COLS
    h = (FH - 2 * (FOLW + FOLD)) / ROWS
    def center(col, row):
        cx = x0 + w * (COLS - 1 - col) + w / 2      # 右起第一列
        cy = y0 + h * row
        return cx, cy
    return {i: center(c, r) for i, (c, r, *_rest) in enumerate(LAYOUT)}


def glyph(ch, size, wr, hr, rot, stroke):
    """单字图层：白字透明底，按拉伸/旋转变形（vYinn: Annotate + AdaptiveResize + rotate）"""
    f = ImageFont.truetype(FONT, size)
    pad = size
    img = Image.new('L', (size + pad * 2, size + pad * 2), 0)
    d = ImageDraw.Draw(img)
    d.text((pad, pad), ch, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
    box = img.getbbox()
    img = img.crop(box) if box else img
    img = img.resize((max(1, int(img.width * wr)), max(1, int(img.height * hr))), Image.LANCZOS)
    if abs(rot) > 0.05:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True, fillcolor=0)
    return img


def spread(img, radius):
    """ImageMagick Spread 等效：小块随机位移，制造边缘毛刺"""
    if radius <= 0:
        return img
    a = np.asarray(img)
    r = radius
    ys, xs = np.nonzero(a)
    if len(ys) == 0:
        return img
    out = a.copy()
    n = len(ys)
    dy = rng.integers(-r, r + 1, n)
    dx = rng.integers(-r, r + 1, n)
    src_y = np.clip(ys + dy, 0, a.shape[0] - 1)
    src_x = np.clip(xs + dx, 0, a.shape[1] - 1)
    out[ys, xs] = a[src_y, src_x]
    return Image.fromarray(out)


def compose():
    base = np.zeros((CH, CW), dtype=np.uint8)
    fr = np.asarray(spread(frame_layer(), FRAME_SPREAD))
    base = np.maximum(base, fr)
    cells = char_cells()
    for i, (ch, (col, row, size, wr, hr, rot, stroke)) in enumerate(zip(YIN_TEXT, LAYOUT)):
        g = spread(glyph(ch, size, wr, hr, rot, stroke), CHARS_SPREAD)
        cx, cy = cells[i]
        a = np.asarray(g)
        ah, aw = a.shape
        y0, x0 = int(cy - ah / 2), int(cx - aw / 2)
        ys, xs = max(0, y0), max(0, x0)
        ye, xe = min(CH, y0 + ah), min(CW, x0 + aw)
        base[ys:ye, xs:xe] = np.maximum(base[ys:ye, xs:xe], a[ys - y0:ye - y0, xs - x0:xe - x0])
    return Image.fromarray(base)


def brokenspots(img):
    """印框范围内随机破残：黑斑 Multiply 到印面上（vYinn: OilPaint+Blur+Multiply）"""
    a = np.asarray(img).astype(np.float32)
    x0, y0 = (CW - FW) / 2, (CH - FH) / 2
    for _ in range(BROKENSPOTS):
        s = 4 + rng.integers(0, 7)
        px, py = int(x0 + rng.random() * FW), int(y0 + rng.random() * FH)
        spot = Image.new('L', (s * 2, s * 2), 0)
        ImageDraw.Draw(spot).ellipse([s * 0.2, s * 0.45, s * 1.8, s * 1.55], fill=255)
        spot = spot.rotate(float(rng.uniform(-22, 22)), expand=True, fillcolor=0)
        spot = spot.filter(ImageFilter.GaussianBlur(1.1))
        m = np.asarray(spot).astype(np.float32) / 255.0
        ah, aw = m.shape
        sy, sx = max(0, py), max(0, px)
        ey, ex = min(CH, py + ah), min(CW, px + aw)
        if ey <= sy or ex <= sx:
            continue
        sub = m[:ey - sy, :ex - sx]
        a[sy:ey, sx:ex] *= (1 - sub * 0.80)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def finish(img):
    """OTSU 二值化 → 白=印泥色 / 黑=透明 → 整体模糊 + 油墨"""
    a = np.asarray(img.convert('L'))
    hist = np.bincount(a.ravel(), minlength=256).astype(np.float64)
    tot = a.size
    best, thr = -1.0, 127
    w0 = 0.0; sum0 = 0.0; sum_all = (np.arange(256) * hist).sum()
    for t in range(256):
        w0 += hist[t]
        if w0 == 0 or w0 == tot:
            continue
        sum0 += t * hist[t]
        m0 = sum0 / w0
        m1 = (sum_all - sum0) / (tot - w0)
        var = w0 * (tot - w0) * (m0 - m1) ** 2
        if var > best:
            best, thr = var, t
    binary = np.where(a > thr, 255, 0).astype(np.uint8)
    out = Image.fromarray(binary).filter(ImageFilter.GaussianBlur(BLUR[1]))
    if OILPAINT:
        out = out.filter(ImageFilter.MedianFilter(3))
    alpha = np.asarray(out)
    col = np.array([int(YIN_COLOR[i + 1:i + 3], 16) for i in (0, 2, 4)], dtype=np.uint8)
    rgba = np.dstack([np.broadcast_to(col, (CH, CW, 3)), alpha])
    im = Image.fromarray(rgba).crop(tuple(CROP.tolist()))
    return im


if __name__ == '__main__':
    im = compose()
    im = brokenspots(im)
    im = finish(im)
    im.save(OUT)
    print(OUT, im.size)
