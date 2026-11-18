#!/usr/bin/env bash
# 実装計画のスキルの frontmatter の hooks（PreToolUse）から呼ぶ入口。guard.py に渡す。
#
# 使い方: guard.sh <implement|decisions|finalize|merge-main>（標準入力に PreToolUse の JSON）
#
# python3 が無いと guard.py が動かず、フックの失敗は Claude Code では止めない扱い（素通り）になる。
# そのときは git・gh・wrangler だけを止めて知らせる（ほかのコマンドまで止めると、何もできなくなるため）。
set -u
here="$(cd "$(dirname "$0")" && pwd)"
input="$(cat)"
if command -v python3 >/dev/null 2>&1; then
  printf '%s' "$input" | python3 -I "$here/guard.py" "$@"
  exit $?
fi
if printf '%s' "$input" | grep -qE '"command"[[:space:]]*:[[:space:]]*"[^"]*(^|[[:space:];&|(])(git|gh|wrangler[^[:space:]]*)[[:space:]]'; then
  echo "[計画のスキルの決まり] python3 が見つからないので、決まりを確かめられません。git・gh・wrangler は止めます（python3 を入れてからやり直す）" >&2
  exit 2
fi
exit 0
