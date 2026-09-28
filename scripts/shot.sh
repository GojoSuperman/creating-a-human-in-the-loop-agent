#!/usr/bin/env bash
# 헤드리스 크롬(Windows)으로 화면을 캡처한다. 사용: scripts/shot.sh <URL> <out.png> [W,H]
set -euo pipefail
CHROME="/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
TMP_WIN_DIR="/mnt/c/Users/minah/Downloads"
TMP="$TMP_WIN_DIR/_hitl_shot_$$.png"
timeout 100 "$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size="${3:-1440,900}" \
  --virtual-time-budget=${VT:-6000} --screenshot="$(wslpath -w "$TMP")" "$1" >/dev/null 2>&1 || true
mkdir -p "$(dirname "$2")"
mv "$TMP" "$2"
ls -la "$2"
