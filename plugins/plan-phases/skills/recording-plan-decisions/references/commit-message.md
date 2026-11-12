# 決定と学びの記録のコミットメッセージ

計画書はリポジトリの外にあり、リポジトリからは読めない。何を残し、何を残さなかったかを main の履歴に残すため、本文に書く。

下書きは `plan-phases commit-skeleton decisions <計画のディレクトリ>` が作り、`plan-phases commit-check decisions` が確かめる（「手順:」の行、項目の有無と順番、置き換える場所が残っていないこと）。

- タイトル: 平易な Conventional Commits（例: `docs: record why page2md runs locally and skips the build`）
- 本文: 次の項目をこの順で書く。計画の README の `{{PR の決まり}}` に追加の項目があれば、それも書く

```txt
手順: <計画名>-decisions（決定と学びの記録）

なぜ
<残す決定と対策を 1〜2 文で>

残したもの
- ADR-NNNN: <表題>（新規。または「ADR-NNNN を置き換え」）
- <仕組み（型・lint の規則・テスト・CLAUDE.md の行・フック）>: <どこに足し、何を防ぐか>
- docs/domain/glossary.md: <足した・直した語>（業務の知識。docs/domain/characteristics.md と docs/security.md も同じ形で）

残さなかった決定
- <決定>: <理由（コードから読み取れる、1 か所のコメントで足りる、比べた案が 1 つだけ、など）>

確認したこと
- check-adr.sh の結果、開いて確かめた参照、{{静的解析}} と {{テスト}} の結果
```

「手順:」の行は、指揮役（plan-phases run）がこのコミットを見分けるのに使う。`<計画名>-decisions` を正確に書く。
