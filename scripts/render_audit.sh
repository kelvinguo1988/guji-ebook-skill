#!/usr/bin/env bash
# 通用 HTML → PDF 渲染器：Edge/Chrome 无头打印 + 字体审计 + 自动重渲
# 用法：render_audit.sh <输入.html> <输出.pdf> [virtual-time-budget]
set -e
HTML="$1"; OUT="${2:-${1%.html}.pdf}"; BUDGET="${3:-30000}"
[ -f "$HTML" ] || { echo "输入不存在: $HTML"; exit 1; }

# 找一个 Chromium 系浏览器
EDGE="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ -x "$EDGE" ]; then BROWSER="$EDGE"; elif [ -x "$CHROME" ]; then BROWSER="$CHROME"
else echo "未找到 Edge/Chrome"; exit 1; fi

render() {
  pkill -9 -f "$(basename "$BROWSER") .*headless" 2>/dev/null || true
  sleep 1
  timeout 400 "$BROWSER" --headless --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="$OUT" --virtual-time-budget="$BUDGET" \
    "file://$(cd "$(dirname "$HTML")" && pwd)/$(basename "$HTML")" 2>&1 | grep -v CVDisplay | tail -1
}

audit() {  # 0=无系统字体回退
  python3 - "$OUT" <<'EOF'
import fitz, sys, re
d = fitz.open(sys.argv[1])
SYSTEM = re.compile(r'ST(Songti|Kaiti|Xihei|Heiti)|SongtiSC|PingFang|Hiragino|Lantinghei|HeitiTC', re.I)
bad = set()
for page in d:
    for f in page.get_fonts():
        if SYSTEM.search(f[3]):
            bad.add(f[3])
print(f"{len(d)} pages, fallback-fonts: {len(bad)}")
if bad:
    print("FALLBACK:", sorted(bad)[:8])
sys.exit(1 if bad else 0)
EOF
}

for i in 1 2 3 4; do
  echo "--- render attempt $i ---"
  render
  if audit; then echo "BUILD OK"; exit 0; fi
  echo "字体回退，重渲..."
done
echo "BUILD FAILED：多次重渲仍存在系统字体回退——大概率是字族覆盖缺陷（见 SKILL.md §1.1），而非加载竞态"
exit 1
