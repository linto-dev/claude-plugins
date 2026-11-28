# claude-plugins

linto-dev の [Claude Code](https://code.claude.com/docs) プラグインのマーケットプレイスです。

| プラグイン | 中身 |
| --- | --- |
| [shipstack](plugins/shipstack/README.md) | 要件定義から実装計画、フェーズごとの実装、機能の PR の仕上げまでを、人に聞かないワーカーで進める開発フロー（Cloudflare と TypeScript のモノレポ向け。受託・自社・個人のどの開発でも使える） |
| [explainer-video](plugins/explainer-video/README.md) | 原稿（解説・ノート・記事・資料）から、図と字幕と VOICEVOX の読み上げで解説する動画を Remotion で作る。企画と台本・読み上げ・シーン・点検・書き出しまでを工程ごとのスキルで進める（雛形のプロジェクトつき） |

## 入れ方

Claude Code の会話で次を打ちます。

```txt
/plugin marketplace add linto-dev/claude-plugins
/plugin install shipstack@linto-dev
/plugin install explainer-video@linto-dev
```

スキルは `/shipstack:defining-requirements`・`/explainer-video:making-video` のように、プラグインの名前を付けて呼びます。使い方は各プラグインの README にあります。

## shipstack の点検（このリポジトリの開発）

shipstack は Claude Code の CLI・スキル・フック・プラグインの仕様と、Claude のモデルの推奨に頼っています。頼っている約束を [.claude/skills/checking-shipstack/contracts.json](.claude/skills/checking-shipstack/contracts.json) に書き、毎朝 7:07（日本時間）の Claude Code の scheduled task「shipstack の点検」が `checking-shipstack` スキルで確かめます。

- 前回見たところからの Claude Code の変更履歴と、公式の文書 22 ページの差分を、`scripts/collect.py` が集める（判断はしない）
- 約束ごとに、必須（壊れる・非推奨になる）・取り入れ候補・影響なしに分ける。必須は `claude/shipstack-check-<日付>` で直して draft PR にし、取り入れ候補は報告する。マージは人が行う
- 結果は、タスクのプッシュ通知から開いた会話の最後の発言
- どこまで見たか（見た版と文書の写し）は、Cloudflare R2 のバケット `shipstack-checks`（linto のアカウント）の `runs/<UTC の日時>/` に残す。上書きせず、90 日でライフサイクルの規則が消す（変化が無くても 30 日ごとに書き直す）
- R2 にはこのバケットだけに絞ったトークン（Object Read & Write）で、S3 互換の API で読み書きする。鍵はタスク専用のクラウド環境の環境変数（`SHIPSTACK_CHECK_R2_ENDPOINT`・`SHIPSTACK_CHECK_R2_ACCESS_KEY_ID`・`SHIPSTACK_CHECK_R2_SECRET_ACCESS_KEY`）に置く。クラウドのネットワークシークレットは AWS 以外の SigV4 を署名できないため
- クラウドの会話では、`.claude/settings.json` のフック（`.claude/hooks/cloud-push-guard.py`）が、`claude/` 以外への push と PR のマージを止める。手元の会話では何もしない

手で点検するときは、リポジトリのルートで Claude Code を開いて「shipstack を点検して」と頼みます（R2 の鍵が無ければ、文書の写しと比べずに変更履歴だけを判定する）。新しい挙動に頼ったら、contracts.json に約束を足します（公式の文書に無い挙動は `"documented": false` にし、確かめ方を `verify` に書く）。

```bash
python3 -I .claude/skills/checking-shipstack/scripts/collect.py diff
python3 -I -B -m unittest discover -s .claude/skills/checking-shipstack/tests -v
```

## English

A Claude Code plugin marketplace. `explainer-video` turns a Japanese source document into a narrated explainer video with Remotion (planning, VOICEVOX narration, scenes, independent review, rendering), shipping a project template. `shipstack` is a development workflow that turns a feature request into a requirements document and an implementation plan (both settled with you interactively), then implements the plan phase by phase with unattended `claude -p` workers, one commit per phase, and finalizes the feature pull request; it assumes a Cloudflare + TypeScript monorepo. The skills of both plugins are written in Japanese.

```txt
/plugin marketplace add linto-dev/claude-plugins
/plugin install shipstack@linto-dev
/plugin install explainer-video@linto-dev
```

## ライセンス

[MIT](LICENSE)
