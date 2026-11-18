# claude-plugins

linto-dev の [Claude Code](https://code.claude.com/docs) プラグインのマーケットプレイスです。

| プラグイン | 中身 |
| --- | --- |
| [shipstack](plugins/shipstack/README.md) | 要件定義から実装計画、フェーズごとの実装、機能の PR の仕上げまでを、人に聞かないワーカーで進める開発フロー（Cloudflare と TypeScript のモノレポ向け。受託・自社・個人のどの開発でも使える） |

## 入れ方

Claude Code の会話で次を打ちます。

```txt
/plugin marketplace add linto-dev/claude-plugins
/plugin install shipstack@linto-dev
```

スキルは `/shipstack:defining-requirements` のように、プラグインの名前を付けて呼びます。使い方は各プラグインの README にあります。

## ハーネスの追従（このリポジトリの開発）

プラグインは Claude Code の CLI・スキル・フック・プラグインの仕様と、Claude のモデルの推奨に頼っています。頼っている約束を [.claude/skills/harness-watch/contracts.json](.claude/skills/harness-watch/contracts.json) に書き、毎朝 7:07（日本時間）の Claude Code の scheduled task が `harness-watch` スキルで確かめます。

- 前回見たところからの Claude Code の変更履歴と、公式の文書 20 ページの差分を、`scripts/collect.py` が集める（判断はしない）
- 約束ごとに、必須（壊れる・非推奨になる）・取り入れ候補・影響なしに分ける。必須は `claude/harness-watch-<日付>` で直して draft PR にし、取り入れ候補は報告する。マージは人が行う
- 結果は、タスクのプッシュ通知から開いた会話の最後の発言。どこまで見たかは `claude/harness-watch-state` ブランチ（`state.json` と文書の写し）に残す
- クラウドの会話では、`.claude/settings.json` のフック（`.claude/hooks/cloud-push-guard.py`）が、`claude/` 以外への push と PR のマージを止める。手元の会話では何もしない

手で確かめるときは、リポジトリのルートで Claude Code を開いて「ハーネスの追従を確かめて」と頼みます。新しい挙動に頼ったら、contracts.json に約束を足します（公式の文書に無い挙動は `"documented": false` にし、確かめ方を `verify` に書く）。

```bash
python3 -I .claude/skills/harness-watch/scripts/collect.py diff
python3 -I -B -m unittest discover -s .claude/skills/harness-watch/tests -v
```

## English

A Claude Code plugin marketplace. `shipstack` is a development workflow that turns a feature request into a requirements document and an implementation plan (both settled with you interactively), then implements the plan phase by phase with unattended `claude -p` workers, one commit per phase, and finalizes the feature pull request. The skills are written in Japanese and assume a Cloudflare + TypeScript monorepo.

```txt
/plugin marketplace add linto-dev/claude-plugins
/plugin install shipstack@linto-dev
```

## ライセンス

[MIT](LICENSE)
