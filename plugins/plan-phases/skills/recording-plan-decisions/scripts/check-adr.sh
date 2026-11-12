#!/usr/bin/env bash
# ADR の形を機械で確かめる（references/adr-rules.md のうち、機械で判定できるものだけ）。
# 中身の正しさ（理由・代償・出典が妥当か、URL の先に書いたことがあるか、守り方のテストが実在するか）は
# 確かめない。それは Claude が開いて確かめ、利用者が機能の PR で読む。
#
# 使い方: check-adr.sh [--plan-dir <計画のディレクトリ>] <ADR のファイル>...
#   リポジトリの中で実行する。--plan-dir を渡すと、ADR がその場所（リポジトリから読めない計画書）を指していないかも確かめる。
# 出力: 問題ごとに「ERROR <ファイル>: <内容>」か「WARN <ファイル>: <内容>」、最後に件数の行。
# 終了コード: 0 ERROR なし（WARN は残ってよい）／1 ERROR あり／2 使い方の誤り
set -euo pipefail

# ADR の長さの目安（1〜2 ページ）。超えたら、問題が 2 つ混ざっていないか、
# 実装の説明を書いていないかを見直す。目安なので WARN にとどめる。
max_lines=60

plan_dir=""
files=()
while [ $# -gt 0 ]; do
  case "$1" in
    --plan-dir) plan_dir="${2:-}"; shift 2 ;;
    -h|--help) echo "使い方: $0 [--plan-dir <計画のディレクトリ>] <ADR のファイル>..." >&2; exit 2 ;;
    --) shift; files+=("$@"); break ;;
    -*) echo "知らない引数です: $1" >&2; exit 2 ;;
    *) files+=("$1"); shift ;;
  esac
done
if [ "${#files[@]}" -eq 0 ]; then
  echo "使い方: $0 [--plan-dir <計画のディレクトリ>] <ADR のファイル>..." >&2
  exit 2
fi
if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "git のリポジトリの中で実行してください" >&2
  exit 2
fi

# 計画書の場所の書き方（絶対パス、~ から始まる形、「plans/<計画名>」のような末尾 2 つ）。
plan_patterns=()
if [ -n "$plan_dir" ] && [ -d "$plan_dir" ]; then
  abs="$(cd "$plan_dir" && pwd)"
  plan_patterns+=("$abs")
  case "$abs" in "$HOME"/*) plan_patterns+=("~${abs#"$HOME"}") ;; esac
  plan_patterns+=("$(basename "$(dirname "$abs")")/$(basename "$abs")")
fi

errors=0
warnings=0
report() { # <ERROR|WARN> <ファイル> <内容>
  printf '%s %s: %s\n' "$1" "$2" "$3"
  if [ "$1" = "ERROR" ]; then errors=$((errors + 1)); else warnings=$((warnings + 1)); fi
}

for file in "${files[@]}"; do
  if [ ! -f "$file" ]; then
    report ERROR "$file" "ファイルがありません"
    continue
  fi
  name="$(basename "$file")"
  fnum=""
  if printf '%s' "$name" | grep -qE '^[0-9]{4}-[a-z0-9]+(-[a-z0-9]+)*\.md$'; then
    fnum="${name:0:4}"
  else
    report ERROR "$file" "ファイル名は「4 桁の番号-英小文字とハイフンの短い名前.md」にする（例: 0026-search-with-instr.md）"
  fi

  # 同じ番号のファイルが同じディレクトリにほかにある（並行する PR とぶつかった。後からマージする方が振り直す）。
  if [ -n "$fnum" ]; then
    for other in "$(dirname "$file")/$fnum"-*.md; do
      [ -e "$other" ] || continue
      [ "$(basename "$other")" = "$name" ] && continue
      report ERROR "$file" "番号 $fnum が $(basename "$other") と重なっている。next-adr-number.sh で振り直す"
    done
  fi

  # 表題・頭の行・節を読む。awk は「E<TAB>内容」「W<TAB>内容」「OLD<TAB>旧番号の行」を出す。
  while IFS=$'\t' read -r kind detail; do
    case "$kind" in
      E) report ERROR "$file" "$detail" ;;
      W) report WARN "$file" "$detail" ;;
      OLD)
        # 置き換えた ADR は消し、参照は新しい番号に直してある（references/adr-rules.md 3 章）。
        for old in $(printf '%s' "$detail" | grep -oE 'ADR-[0-9]{4}'); do
          onum="${old#ADR-}"
          for left in "$(dirname "$file")/$onum"-*.md; do
            [ -e "$left" ] && report ERROR "$file" "旧番号 $old のファイル $(basename "$left") が残っている。消す（古い本文は Git の履歴に残る）"
          done
          refs="$(git grep --untracked -n -F "$old" -- . ":(exclude)$file" 2>/dev/null | head -n 5 || true)"
          if [ -n "$refs" ]; then
            report ERROR "$file" "旧番号 $old を指す箇所が残っている。新しい番号に直す: $(printf '%s' "$refs" | tr '\n' ' ')"
          fi
        done
        ;;
    esac
  done < <(awk -v fnum="$fnum" -v max_lines="$max_lines" '
    function e(msg) { print "E\t" msg }
    function w(msg) { print "W\t" msg }
    BEGIN {
      n = split("状況 決定 採らなかった案 影響 守り方 見直す条件", want, " ")
      idx = 0
    }
    # 計画書はリポジトリの外にあり、リポジトリからは読めないので、根拠に指さない。
    index($0, "計画書") { e(NR " 行目: 計画書を指している。根拠は ADR の中に書く（計画書はリポジトリから読めない）") }
    NR == 1 {
      if ($0 !~ /^# ADR-[0-9][0-9][0-9][0-9]: ./) {
        e("1 行目は「# ADR-NNNN: <決定を言い切る短い文>」にする（YAML の front matter は使わない）")
      } else if (fnum != "" && substr($0, 7, 4) != fnum) {
        e("表題の番号 ADR-" substr($0, 7, 4) " がファイル名の番号 " fnum " と違う")
      }
      next
    }
    /^```/ { in_fence = !in_fence }
    !in_fence && /^## / {
      h = $0
      sub(/^## +/, "", h)
      sub(/[ \t]+$/, "", h)
      idx++
      if (idx > n) {
        e("余分な節「" h "」がある。節は「状況」「決定」「採らなかった案」「影響」「守り方」「見直す条件」の 6 つだけ")
      } else if (h != want[idx]) {
        e(idx " 番目の節が「" h "」になっている。「" want[idx] "」にする（名前と順番は固定）")
      }
      cur = h
      seen[cur] = 1
      next
    }
    idx == 0 {
      if ($0 ~ /^[ \t]*$/) next
      if ($0 ~ /^- 日付: [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9][ \t]*$/) { has_date = 1; next }
      if ($0 ~ /^- 旧番号: ADR-[0-9][0-9][0-9][0-9]/) { line = $0; sub(/^- 旧番号: /, "", line); print "OLD\t" line; next }
      if ($0 ~ /^- 承認: ./) next
      e("頭の行に使えるのは「- 日付: YYYY-MM-DD」「- 旧番号: ADR-NNNN」「- 承認: …」だけ: " $0)
      next
    }
    $0 !~ /^[ \t]*$/ {
      filled[cur] = 1
      if (cur == "採らなかった案" && $0 ~ /^- /) alternatives++
      if (cur == "影響" && index($0, "代償")) has_cost = 1
      if (cur == "決定" && first_decision == "") first_decision = $0
    }
    END {
      if (!has_date) e("頭の行に「- 日付: YYYY-MM-DD」が無い")
      for (i = idx + 1; i <= n; i++) e("節「" want[i] "」が無い")
      for (i = 1; i <= n; i++) if (seen[want[i]] && !filled[want[i]]) e("節「" want[i] "」が空")
      if (seen["採らなかった案"] && alternatives == 0) e("「採らなかった案」に「- <案>: <採らなかった理由>」の行が無い。実際に比べた案だけを書く")
      if (seen["影響"] && !has_cost) e("「影響」に代償が無い。「代償:」を 1 つ以上書く")
      if (first_decision ~ /(と考える|がよい|べきだ|だろう|かもしれない)/) w("「決定」の 1 文目が意見の形になっている。「〜する。」と言い切る: " first_decision)
      if (NR > max_lines) w(NR " 行ある（目安は " max_lines " 行）。問題が 2 つ混ざっていないか、実装の説明を書いていないかを見直す")
    }
  ' "$file")

  # 計画書の場所を指していない。
  for pattern in ${plan_patterns[@]+"${plan_patterns[@]}"}; do
    if grep -qF -- "$pattern" "$file"; then
      report ERROR "$file" "計画書の場所（${pattern}）を指している。計画書はリポジトリから読めないので、根拠は ADR の中に書く"
    fi
  done
  if grep -qF -- ".runs/" "$file"; then
    report ERROR "$file" ".runs/ を指している。計画のディレクトリはリポジトリから読めない"
  fi

  # Markdown のリンクのうち、手元のファイルを指すものは実在する（URL は開いて確かめる。ここでは見ない）。
  while IFS= read -r target; do
    case "$target" in http://*|https://*|mailto:*|\#*|"") continue ;; esac
    path="${target%%#*}"
    case "$path" in /*) resolved="$path" ;; *) resolved="$(dirname "$file")/$path" ;; esac
    [ -e "$resolved" ] || report ERROR "$file" "リンク先 $target がありません"
  done < <(grep -oE '\]\([^) ]+\)' "$file" | sed -E 's/^\]\(//; s/\)$//' || true)
done

echo "ERROR ${errors} 件、WARN ${warnings} 件（${#files[@]} ファイル）"
[ "$errors" -eq 0 ]
