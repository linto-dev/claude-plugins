#!/usr/bin/env bash
# 決定と学びの記録の材料を集めて Markdown で出す。判定はしない（どれを ADR にするかは、
# 読んだ Claude がスキルの規則で判定する）。
#   1. 要件定義書（requirements.md）の「決めたこと」「用語」「品質特性」「権限とデータ」の節をそのまま
#      （要件定義のスキルが、製品の判断と業務の知識を書いたもの。要件定義書が無ければ出さない）
#   2. 計画の README の「決めたこと」の節（計画のスキルが、どう作るかを決めた時点の文脈を書いたもの）をそのまま
#   3. 機能ブランチの各コミット（origin/<基準>..HEAD）の本文の「決めたこと」の項目をそのまま
#      （実装の途中で案を比べて決めたこと。前の版のワーカーのコミットは「計画から変えた点」）。
#      「なし」だけの項目と、項目の無いコミット（main の取り込みなど）は出さない
# 先に git fetch origin しておくこと（このスクリプトはネットワークに出ない）。
#
# 使い方: gather-decisions.sh <計画のディレクトリ> [<基準のブランチ>]
#   基準のブランチを省くと origin/HEAD が指すブランチ（無ければ main）を使う。
set -euo pipefail

if [ $# -lt 1 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  echo "使い方: $0 <計画のディレクトリ> [<基準のブランチ>]" >&2
  exit 2
fi
plan_dir="${1%/}"
readme="$plan_dir/README.md"
if [ ! -f "$readme" ]; then
  echo "$readme がありません。計画のディレクトリを渡してください" >&2
  exit 2
fi
if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "git のリポジトリの中で実行してください" >&2
  exit 2
fi
if [ $# -ge 2 ]; then
  base="$2"
else
  base="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##' || true)"
  base="${base:-main}"
fi
if ! git rev-parse --verify --quiet "refs/remotes/origin/$base" >/dev/null; then
  echo "origin/$base がありません。基準のブランチを 2 つ目の引数で渡してください" >&2
  exit 2
fi

# 見出しの文字列から番号（「2.」「3-4.」など）を除いたものが $2 の見出しを探し、
# 同じか上の階層の次の見出しの前までを出す。コードブロックの中の「#」は見出しとみなさない。
section_of() {
  awk -v want="$2" '
    /^```/ { in_fence = !in_fence }
    !in_fence && /^#+[ \t]/ {
      level = match($0, /[^#]/) - 1
      title = $0
      sub(/^#+[ \t]+/, "", title)
      sub(/^[0-9][0-9.-]*[ \t]*/, "", title)
      sub(/[ \t]+$/, "", title)
      if (in_sec && level <= sec_level) exit
      if (!in_sec && title == want) { in_sec = 1; sec_level = level; next }
    }
    in_sec { print }
  ' "$1"
}

# $1 のファイルの $2 の節を、見出し「# $2（ファイル）」を付けて出す。
print_section() {
  local section
  section="$(section_of "$1" "$2")"
  echo "# $2（$1）"
  echo
  if [ -n "$(printf '%s' "$section" | tr -d '[:space:]')" ]; then
    printf '%s\n' "$section"
  else
    echo "（「$2」の見出しが無いか、中身が空です）"
  fi
  echo
}

requirements="$plan_dir/requirements.md"
if [ -f "$requirements" ]; then
  for title in 決めたこと 用語 品質特性 権限とデータ; do
    print_section "$requirements" "$title"
  done
else
  echo "（要件定義書 $requirements がありません。要件定義のスキルより前に書いた計画です）"
  echo
fi
print_section "$readme" 決めたこと

echo
echo "# 実装の途中で決めたこと（origin/$base..HEAD のコミットの「決めたこと」、古い順）"
count=0
for sha in $(git rev-list --reverse "origin/$base..HEAD"); do
  message="$(git log -1 --format=%B "$sha")"
  # 「決めたこと」（前の版は「計画から変えた点」）の行の次から、空行の後に箇条書きでも字下げでもない行（次の項目の見出し）が来るまで。
  block="$(printf '%s\n' "$message" | awk '
    /^(決めたこと|計画から変えた点)[:：]?[ \t]*$/ { in_b = 1; next }
    in_b {
      if ($0 ~ /^[ \t]*$/) { blank = 1; next }
      if (blank && $0 !~ /^[ \t]*-/ && $0 !~ /^[ \t]/) exit
      blank = 0
      print
    }
  ')"
  trimmed="$(printf '%s' "$block" | tr -d '[:space:]')"
  if [ -z "$trimmed" ] || [ "$trimmed" = "なし" ] || [ "$trimmed" = "-なし" ]; then
    continue
  fi
  count=$((count + 1))
  echo
  echo "## $(git rev-parse --short "$sha") $(git log -1 --format=%s "$sha")"
  printf '%s\n' "$message" | grep -E '^フェーズ' | head -n 1 || true
  echo
  printf '%s\n' "$block"
done
if [ "$count" -eq 0 ]; then
  echo
  echo "（どのコミットにもありません）"
fi
