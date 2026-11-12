# plan-phases

要件定義から実装計画、フェーズごとの実装、機能の PR の仕上げまでを、Claude Code で進める開発フローのプラグインです。要件と計画は利用者と対話して決め、実装は人に聞かないワーカー（`claude -p`）が 1 フェーズずつ、機能ブランチに 1 コミットずつ積みます。受託・自社・個人のどの開発でも使えます。

設計の決まり（`skills/writing-implementation-plan/references/design/`）は、1 人と AI で業務アプリを **Cloudflare と TypeScript のモノレポ** で作る前提の既定値です。ほかの技術のリポジトリでも、計画はリポジトリの CLAUDE.md と既存のコードを優先します。

## 流れ

```txt
/plan-phases:defining-requirements <要求>          要件定義書（requirements.md）を書く。製品の判断を利用者に聞く
        ↓ 新しい会話で
/plan-phases:writing-implementation-plan <計画のディレクトリ>
                                                    計画（README とフェーズごとの計画書）を書く。技術の判断を利用者に聞く
        ↓ 利用者が計画を読んで承認する
<プラグインの場所>/skills/plan-phases-shared/scripts/plan-phases run <計画のディレクトリ>
                                                    指揮役がワーカーを順に起動する（人に聞かない）
          implementing-plan-phase      フェーズごとに実装・検査・1 コミット・push、機能の PR を更新
          merging-main-into-feature    main が進んだら取り込む
          recording-plan-decisions     決定を ADR と docs/ に残す
          finalizing-feature-pr        E2E と CI を確かめ、PR の本文を仕上げる
        ↓
人が PR を読んでマージする（マージが本番へのデプロイ）
```

要件定義と計画は、書いた本人ではない点検（`reviewing-requirements`・`reviewing-implementation-plan`。会話を引き継がないサブエージェント）を 1 回ずつ通します。

| スキル | 呼び方 | 役目 |
| --- | --- | --- |
| `defining-requirements` | `/plan-phases:defining-requirements <要求>` | 何を、なぜ、どこまで作るかを決め、要件定義書を書く |
| `reviewing-requirements` | 要件定義のスキルが呼ぶ | 要件定義書を点検する |
| `writing-implementation-plan` | `/plan-phases:writing-implementation-plan <計画のディレクトリ>` | どう作るかを決め、計画を書く |
| `reviewing-implementation-plan` | 計画のスキルが呼ぶ | 計画を点検する |
| `implementing-plan-phase` | 指揮役が起動する | 1 フェーズを実装する |
| `merging-main-into-feature` | 指揮役が起動する | main を機能ブランチに取り込む |
| `recording-plan-decisions` | 指揮役が起動する | 決定と学びを記録する |
| `finalizing-feature-pr` | 指揮役が起動する | 機能の PR を仕上げる |

`plan-phases-shared` はスキルではなく、全スキルが使う共通のスクリプト（指揮役 `plan-phases`、決まりのフック `guard.py`）と試験です。サブコマンドと指揮役の動きは [skills/plan-phases-shared/README.md](skills/plan-phases-shared/README.md) にあります。

## 要るもの

- Claude Code（2.1.322 で確かめた）
- GitHub のリポジトリと、ログイン済みの `gh`（機能の PR を作り、CI の結果を読む）
- GitHub Actions の CI（ワーカーは push の後の CI を、次のフェーズと仕上げで確かめる）
- `git`、`python3`（3.9 以上）、`jq`

本番へのデプロイは、機能の PR を main にマージしたときにだけ GitHub Actions が行う前提です。ワーカーはデプロイしません。

## 入れ方

Claude Code の会話で次を打ちます。

```txt
/plugin marketplace add linto-dev/claude-plugins
/plugin install plan-phases@linto-dev
```

ワーカーは `claude -p` で動くので、ワーカーを動かす設定のフォルダ（`CLAUDE_CONFIG_DIR`。既定は `~/.claude`）ごとに入れます。更新は `/plugin marketplace update linto-dev` で受け取ります。

## 使い方

1. リポジトリのルートで Claude Code を開き、`/plan-phases:defining-requirements <要求>` を打つ。計画のディレクトリは、リポジトリの隣の `plans/<計画名>/` に作られる（リポジトリの外に置き、コミットしない）。作業フォルダの外なので、`/add-dir <計画の置き場所>` を打つ
2. 新しい会話で `/plan-phases:writing-implementation-plan <計画のディレクトリ>` を打つ。最後の報告に、指揮役を動かすコマンド（プラグインの場所を埋めたもの）が出る
3. 計画を読んで承認し、「開始前に人がすること」を済ませてから、リポジトリのルートで指揮役を動かす

   ```bash
   <プラグインの場所>/skills/plan-phases-shared/scripts/plan-phases run <計画のディレクトリ> --dry-run
   <プラグインの場所>/skills/plan-phases-shared/scripts/plan-phases run <計画のディレクトリ>
   ```

4. 仕上げが済んだら、PR の本文の「マージの前に行う確認」をしてから、マージコミットでマージする

計画のディレクトリの `.runs/` に、ワーカーの記録と、手順ごとの時間・トークン（`plan-phases usage <計画のディレクトリ>`）が残ります。

## 守っていること

- ワーカーは `--permission-mode auto` で動き、決まりのフック（`guard.py`）が force push、main への push、PR のマージ、履歴の書き換えなどを止めます
- 計画書と要件定義書はリポジトリの外に置く使い捨ての文書です。コミットメッセージとコードには、計画書が無いと読めない番号や名前を書きません（`commit-check` が止める）
- 残すべき決定は、全フェーズの後に ADR と `docs/domain/`・`docs/security.md` に書きます

## 開発

リポジトリをクローンし、手元のディレクトリをマーケットプレイスとして足すと、編集がそのまま効きます（次の会話か `/reload-plugins` から）。

```bash
claude plugin marketplace add ./claude-plugins
claude plugin install plan-phases@linto-dev
```

試験と形の確かめは、リポジトリのルートで流します。

```bash
python3 -I -B -m unittest discover -s plugins/plan-phases/skills/plan-phases-shared/tests -v
claude plugin validate .
claude plugin validate plugins/plan-phases
```

版を出すときは、`.claude-plugin/plugin.json` の `version` を上げます。上げないと、入れた人に変更が届きません。
