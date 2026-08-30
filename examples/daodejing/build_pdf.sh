#!/usr/bin/env bash
# 《道德經三版本對照箋注》样张构建：渲染 PDF + 字体嵌入审计（发现系统字体回退即重渲）
set -e
cd "$(dirname "$0")"
PDF="道德经三版本对照笺注-第一章样张.pdf"
EDGE="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

render() {
  "$EDGE" --headless --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="$PDF" --virtual-time-budget=30000 \
    "file://$(pwd)/book.html" 2>&1 | grep -v CVDisplay | tail -1
}

audit() {  # 0 = 干净（无系统字体回退）；1 = 发现回退
  python3 - "$PDF" <<'EOF'
import fitz, sys, re
d = fitz.open(sys.argv[1])
bad = set()
SYSTEM = re.compile(r'ST(Songti|Kaiti|Xihei|Heiti)|SongtiSC|PingFang|Hiragino|Heiti|Lantinghei', re.I)
for page in d:
    for f in page.get_fonts():
        name = f[3]
        if SYSTEM.search(name):
            bad.add(name)
if bad:
    print("FALLBACK DETECTED:", sorted(bad)); sys.exit(1)
print("fonts clean:", len(d), "pages, no system-font fallback")
EOF
}

for i in 1 2 3 4; do
  echo "--- render attempt $i ---"
  render
  if audit; then echo "BUILD OK"; exit 0; fi
  echo "retrying (font fallback race)..."
done
echo "BUILD FAILED after 4 attempts"; exit 1
