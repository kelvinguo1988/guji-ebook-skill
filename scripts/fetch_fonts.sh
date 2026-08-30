#!/usr/bin/env bash
# 下载本 skill 所需开源字体（SIL OFL，可商用），断点续传 + 完整性校验
# 用法：bash scripts/fetch_fonts.sh [目标目录]   （默认：examples/daodejing/fonts）
set -e
DEST="${1:-$(dirname "$0")/../examples/daodejing/fonts}"
mkdir -p "$DEST"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

fetch() { # $1=url $2=outfile $3=最小字节数
  local url="$1" out="$2" min="${3:-1000000}" sz=0
  for i in $(seq 1 8); do
    sz=$(stat -f%z "$out" 2>/dev/null || echo 0)
    [ "$sz" -ge "$min" ] && { echo "OK  $out ($sz bytes)"; return 0; }
    curl -sL -C - --max-time 300 -A "$UA" -o "$out" "$url" 2>/dev/null || true
  done
  sz=$(stat -f%z "$out" 2>/dev/null || echo 0)
  if [ "$sz" -lt "$min" ]; then echo "FAIL $out ($sz bytes, 需要 ≥$min)"; return 1; fi
  echo "OK  $out ($sz bytes)"
}

RAW="https://raw.githubusercontent.com/notofonts/noto-cjk/main/Serif/OTF/TraditionalChinese"
GHK="https://github.com/lxgw/LxgwWenKai/releases/download/v1.522"

echo "== 思源宋体 CJK TC 全字库（正文唯一字面，覆盖繁简+扩展A区）=="
fetch "$RAW/NotoSerifCJKtc-Regular.otf" "$DEST/NotoSerifCJKtc-Regular.otf" 20000000
fetch "$RAW/NotoSerifCJKtc-Bold.otf"    "$DEST/NotoSerifCJKtc-Bold.otf"    20000000

echo "== 霞鹜文楷（标题点缀，白名单字符集使用）=="
fetch "$GHK/LXGWWenKai-Regular.ttf" "$DEST/LXGWWenKai-Regular.ttf" 20000000
fetch "$GHK/LXGWWenKai-Medium.ttf"  "$DEST/LXGWWenKai-Medium.ttf"  20000000

echo "== 完整性校验（OTTO/wOF2 magic）=="
python3 - "$DEST" <<'EOF'
import os, struct, sys
d = sys.argv[1]
ok = True
for f in sorted(os.listdir(d)):
    p = os.path.join(d, f)
    data = open(p, 'rb').read()
    magic = data[:4]
    if magic == b'OTTO':
        n = struct.unpack('>H', data[4:6])[0]
        good = 8 <= n <= 30
    elif magic == b'wOF2':
        good = struct.unpack('>I', data[8:12])[0] == len(data)
    else:
        good = False
    print(('OK  ' if good else 'BAD '), f, magic)
    ok = ok and good
sys.exit(0 if ok else 1)
EOF
echo "字体就绪：$DEST"
