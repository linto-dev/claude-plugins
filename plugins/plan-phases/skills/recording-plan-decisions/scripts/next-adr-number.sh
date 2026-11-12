#!/usr/bin/env bash
# 次に振る ADR の番号（4 桁）を出す。番号は欠番を詰めず、消した ADR の番号も再利用しない（references/adr-rules.md 3 章）ので、
# 次のどこかで一度でも使われた番号の最大に 1 を足す。
#   files       ADR のディレクトリにある今のファイル（作業ツリー。まだコミットしていないものも）
#   history     手元にあるすべての ref の Git の履歴で、そのディレクトリにあったことのあるファイル（消した ADR を含む。
#               fetch してあれば、origin のほかのブランチで足された ADR も入る）
#   references  Git の管理外でないファイルの中の「ADR-NNNN」の参照（ADR のファイルを Git に入れていなかった
#               リポジトリでは、番号がコードのコメントにだけ残っていることがある）
# 先に git fetch origin しておくこと（このスクリプトはネットワークに出ない）。
#
# 使い方: next-adr-number.sh <ADR のディレクトリ>（リポジトリのルートからの相対パス。例: docs/adr/）
# 出力: {"next":"0026","highest":25,"seen":{"files":25,"history":24,"references":25}}
#   どこにも番号が無ければ next は "0001"、各欄は 0。1 本書いたら、次の 1 本の前にもう一度実行する（files に入る）。
set -euo pipefail

if [ $# -ne 1 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  echo "使い方: $0 <ADR のディレクトリ>（例: docs/adr/）" >&2
  exit 2
fi
if ! top="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "git のリポジトリの中で実行してください" >&2
  exit 2
fi
cd "$top"
dir="${1%/}"

# 標準入力の 4 桁の番号のうち最大のもの（無ければ 0）。grep は一致が無いと終了コード 1 を返し、pipefail で
# スクリプトごと終わる（ADR が 1 本も無いリポジトリで何も出さずに失敗していた）ので、それは失敗にしない。
max_number() {
  { grep -oE '^[0-9]{4}' || true; } | awk 'BEGIN { m = 0 } { n = $1 + 0; if (n > m) m = n } END { print m }'
}

files_max="$( (ls "$dir" 2>/dev/null || true) | max_number)"
history_max="$( (git log --all --format= --name-only -- "$dir" 2>/dev/null || true) | sed 's#.*/##' | max_number)"
# git grep は見つからないと終了コード 1 を返すので、それは失敗にしない。
references_max="$( (git grep --untracked -h -o -E 'ADR-[0-9]{4}' 2>/dev/null || true) | sed 's/^ADR-//' | max_number)"

highest="$files_max"
[ "$history_max" -gt "$highest" ] && highest="$history_max"
[ "$references_max" -gt "$highest" ] && highest="$references_max"

jq -nc \
  --arg next "$(printf '%04d' $((highest + 1)))" \
  --argjson highest "$highest" \
  --argjson files "$files_max" \
  --argjson history "$history_max" \
  --argjson references "$references_max" \
  '{next:$next, highest:$highest, seen:{files:$files, history:$history, references:$references}}'
