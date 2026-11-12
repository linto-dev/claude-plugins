# claude-plugins

linto-dev の [Claude Code](https://code.claude.com/docs) プラグインのマーケットプレイスです。

| プラグイン | 中身 |
| --- | --- |
| [plan-phases](plugins/plan-phases/README.md) | 要件定義から実装計画、フェーズごとの実装、機能の PR の仕上げまでを、人に聞かないワーカーで進める開発フロー（Cloudflare と TypeScript のモノレポ向け。受託・自社・個人のどの開発でも使える） |

## 入れ方

Claude Code の会話で次を打ちます。

```txt
/plugin marketplace add linto-dev/claude-plugins
/plugin install plan-phases@linto-dev
```

スキルは `/plan-phases:defining-requirements` のように、プラグインの名前を付けて呼びます。使い方は各プラグインの README にあります。

## English

A Claude Code plugin marketplace. `plan-phases` is a development workflow that turns a feature request into a requirements document and an implementation plan (both settled with you interactively), then implements the plan phase by phase with unattended `claude -p` workers, one commit per phase, and finalizes the feature pull request. The skills are written in Japanese and assume a Cloudflare + TypeScript monorepo.

```txt
/plugin marketplace add linto-dev/claude-plugins
/plugin install plan-phases@linto-dev
```

## ライセンス

[MIT](LICENSE)
