#!/usr/bin/env python3
"""通用页码盖印：在 PDF 地脚居中盖「· N ·」样式页码。
用法：stamp_folios.py <pdf> [--skip-first N] [--start-number N] [--format '· {n} ·']
默认：跳过第 1 页（封面），第 2 物理页标 1。
"""
import fitz, sys, argparse

ap = argparse.ArgumentParser()
ap.add_argument('pdf')
ap.add_argument('--skip-first', type=int, default=1, help='跳过前 N 物理页不盖码')
ap.add_argument('--start-number', type=int, default=1, help='首个页码数字')
ap.add_argument('--format', default='· {n} ·')
ap.add_argument('--fontsize', type=float, default=8.5)
a = ap.parse_args()

d = fitz.open(a.pdf)
W, H = d[0].rect.width, d[0].rect.height
n = a.start_number
count = 0
for i in range(a.skip_first, len(d)):
    label = a.format.format(n=n)
    tw = fitz.get_text_length(label, fontname='helv', fontsize=a.fontsize)
    d[i].insert_text((W / 2 - tw / 2, H - 24), label,
                     fontname='helv', fontsize=a.fontsize, color=(0.42, 0.39, 0.33))
    n += 1
    count += 1
d.saveIncr()
print(f'folios stamped: {count} pages')
