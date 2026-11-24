# shipstack

要件定義から実装計画、フェーズごとの実装、機能の PR の仕上げまでを、Claude Code で進める開発フローのプラグインです。要件と計画は利用者と対話して決め、実装は人に聞かないワーカー（`claude -p`）が 1 フェーズずつ、機能ブランチに 1 コミットずつ積みます。受託・自社・個人のどの開発でも使えます。

設計の決まり（`skills/writing-implementation-plan/references/design/`）は、1 人と AI で業務アプリを **Cloudflare と TypeScript のモノレポ** で作る前提の既定値です。ほかの技術のリポジトリでも、計画はリポジトリの CLAUDE.md と既存のコードを優先します。

## 流れ

```txt
/shipstack:defining-requirements <要求>          要件定義書（requirements.md）を書く。製品の判断を利用者に聞く
        ↓ 新しい会話で
/shipstack:writing-implementation-plan <計画のディレクトリ>
                                                    計画（README とフェーズごとの計画書）を書く。技術の判断を利用者に聞く
        ↓ 利用者が計画を読んで承認する
<プラグインの場所>/bin/shipstack run <計画のディレクトリ>
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
| `defining-requirements` | `/shipstack:defining-requirements <要求>` | 何を、なぜ、どこまで作るかを決め、要件定義書を書く |
| `reviewing-requirements` | 要件定義のスキルが呼ぶ | 要件定義書を点検する |
| `writing-implementation-plan` | `/shipstack:writing-implementation-plan <計画のディレクトリ>` | どう作るかを決め、計画を書く |
| `reviewing-implementation-plan` | 計画のスキルが呼ぶ | 計画を点検する |
| `implementing-plan-phase` | 指揮役が起動する | 1 フェーズを実装する |
| `merging-main-into-feature` | 指揮役が起動する | main を機能ブランチに取り込む |
| `recording-plan-decisions` | 指揮役が起動する | 決定と学びを記録する |
| `finalizing-feature-pr` | 指揮役が起動する | 機能の PR を仕上げる |

スキルの外に、全スキルが使う共通のスクリプトがあります。`bin/shipstack`（指揮役とサブコマンド。スキルの会話では Bash の PATH に入る）と `scripts/guard.py`（決まりのフック）です。動きは [docs/cli.md](docs/cli.md) にあります。

## 要るもの

- Claude Code 2.1.295 以上（2.1.327 で確かめた）
- GitHub のリポジトリと、ログイン済みの `gh`（機能の PR を作り、CI の結果を読む）
- GitHub Actions の CI（ワーカーは push の後の CI を、次のフェーズと仕上げで確かめる）
- `git`、`python3`（3.9 以上）、`jq`

本番へのデプロイは、機能の PR を main にマージしたときにだけ GitHub Actions が行う前提です。ワーカーはデプロイしません。

## 入れ方

Claude Code の会話で次を打ちます。

```txt
/plugin marketplace add linto-dev/claude-plugins
/plugin install shipstack@linto-dev
```

要件定義と計画を打つ設定のフォルダ（`CLAUDE_CONFIG_DIR`。既定は `~/.claude`）に入れます。ワーカー（`claude -p`）には、指揮役が `--plugin-dir` で自分と同じ版のプラグインを読ませるので、ワーカーだけを 2 つ目のアカウントで動かすときは、そのアカウントに入れなくても動きます。更新は `/plugin marketplace update linto-dev` で受け取ります。

### 0.6.0 で変わったこと

指揮役の場所が `skills/shipstack-shared/scripts/shipstack` から `bin/shipstack` に変わりました。指揮役を打つコマンドの `<プラグインの場所>` の後ろを `bin/shipstack` に替えます。途中の計画はそのまま続けられます。

### 前の名前（plan-phases）から移る

0.4.0 で名前を plan-phases から shipstack に変えました。設定のフォルダごとに、マーケットプレイスを更新してから入れ直します。

```bash
claude plugin marketplace update linto-dev
claude plugin uninstall plan-phases@linto-dev
claude plugin install shipstack@linto-dev
```

- スキルは `/shipstack:<スキル>`、指揮役は `<プラグインの場所>/bin/shipstack run …` で呼ぶ。スキルの名前は変わらない
- 環境変数の頭は `PLAN_PHASES_` から `SHIPSTACK_` に変わった（`SHIPSTACK_MODEL` など）
- 途中の計画はそのまま続けられる（計画のディレクトリ、`.runs/`、コミットの「フェーズ:」の行は名前に頼らない）。`usage` は前の名前で動かした会話も数える

## 使い方

1. リポジトリのルートで Claude Code を開き、`/shipstack:defining-requirements <要求>` を打つ。計画のディレクトリは、リポジトリの隣の `plans/<計画名>/` に作られる（リポジトリの外に置き、コミットしない）。作業フォルダの外なので、計画の置き場所が既にあれば、スキルを打つ前に `/add-dir <計画の置き場所>` を打つ（打たなくても、書くたびに許可を聞かれるだけで進む。スキルの途中で打つと、そこでスキルのエフォートが外れる）
2. 新しい会話で `/shipstack:writing-implementation-plan <計画のディレクトリ>` を打つ。最後の報告に、指揮役を動かすコマンド（プラグインの場所を埋めたもの）が出る
3. 計画を読んで承認し、「開始前に人がすること」を済ませてから、リポジトリのルートで指揮役を動かす

   ```bash
   <プラグインの場所>/bin/shipstack run <計画のディレクトリ> --dry-run
   <プラグインの場所>/bin/shipstack run <計画のディレクトリ>
   ```

4. 仕上げが済んだら、PR の本文の「マージの前に行う確認」をしてから、マージコミットでマージする

計画のディレクトリの `.runs/` に、ワーカーの記録と、手順ごとの時間・トークン（`shipstack usage <計画のディレクトリ>`）が残ります。

## エフォート

Claude Opus 5.5 の公式の推奨（既定の `medium` から始めて明示し、上げるのは差を測った仕事だけ）に沿って、手順ごとに決めています。

| 手順 | エフォート | 決める所 |
| --- | --- | --- |
| 要件定義・計画とその点検 | `high` | 各スキルの frontmatter |
| フェーズ | `medium`（新しいものを足すだけ）か `high`（既存の振る舞いを変える、お金・権限・並行・移行・削除に触れる） | 計画のフェーズ表（計画のスキルが書く）。指揮役が `--effort` で渡す |
| main の取り込み・決定と学びの記録・仕上げ | `medium` | 指揮役が `--effort` で渡す |

ワーカーへの `--effort` は設定ファイルの `effortLevel`・`modelSettings` より強く、環境変数 `CLAUDE_CODE_EFFORT_LEVEL` より弱いです。根拠と、流し比べ方は [docs/cli.md](docs/cli.md#エフォート) にあります。

## 守っていること

- ワーカーは `--permission-mode auto` で動き、決まりのフック（`guard.py`）が force push、main への push、PR のマージ、履歴の書き換えなどを止めます。フックが落ちたり時間切れになったりしたときも、コマンドを通さずに止めます（`onFailure: block`）
- 指揮役は、ワーカーが auto mode で始まったこと、shipstack を読み込んだこと、`--settings` のフックが動くこと（`--bare` などでは動かない）を、モデルを呼ぶ前に確かめ、合わなければ止めます。利用者とリポジトリの設定の `ultracode` と `disableAllHooks` は、ワーカーには効かせません（[起動の確かめ](docs/cli.md#起動の確かめ)）
- 計画書と要件定義書はリポジトリの外に置く使い捨ての文書です。コミットメッセージとコードには、計画書が無いと読めない番号や名前を書きません（`commit-check` が止める）
- 残すべき決定は、全フェーズの後に ADR と `docs/domain/`・`docs/security.md` に書きます

## 開発

リポジトリをクローンし、手元のディレクトリをマーケットプレイスとして足すと、編集がそのまま効きます（次の会話か `/reload-plugins` から）。

```bash
claude plugin marketplace add ./claude-plugins
claude plugin install shipstack@linto-dev
```

試験と形の確かめは、リポジトリのルートで流します。CI（`.github/workflows/ci.yml`）は、試験を Python 3.9（要るものの下限）と最新の版の両方で流します。

```bash
python3 -I -B -m unittest discover -s plugins/shipstack/tests -v
claude plugin validate .
claude plugin validate plugins/shipstack
```

版を出すときは、`.claude-plugin/plugin.json` の `version` を上げます。上げないと、入れた人に変更が届きません。
