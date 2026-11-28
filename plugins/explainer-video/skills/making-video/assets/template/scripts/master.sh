#!/bin/sh
# 書き出した動画の音量を YouTube 向けにそろえる（映像はそのままコピー）。
#   npm run master -- out/<slug>.mp4 out/<slug>-master.mp4
# 2 パスの loudnorm で、統合ラウドネス -15 LUFS・トゥルーピーク -1.5 dBTP にする。
set -eu
IN="${1:?使い方: npm run master -- <入力.mp4> <出力.mp4>}"; OUT="${2:?使い方: npm run master -- <入力.mp4> <出力.mp4>}"
TARGET="I=-15:TP=-1.5:LRA=11"
STATS=$(ffmpeg -hide_banner -nostats -i "$IN" -vn -af "loudnorm=$TARGET:print_format=json" -f null - 2>&1 | sed -n '/^{/,/^}/p')
val() { echo "$STATS" | grep "\"$1\"" | sed -E 's/.*: "([^"]+)".*/\1/'; }
ffmpeg -hide_banner -v error -y -i "$IN" -c:v copy \
  -af "loudnorm=$TARGET:measured_I=$(val input_i):measured_TP=$(val input_tp):measured_LRA=$(val input_lra):measured_thresh=$(val input_thresh):offset=$(val target_offset):linear=true" \
  -ar 48000 -c:a aac -b:a 192k -movflags +faststart "$OUT"
ffmpeg -hide_banner -nostats -i "$OUT" -vn -af ebur128=peak=true -f null - 2>&1 | grep -A20 'Summary:' | grep -E ' I:| Peak:'
