---
name: merging-main-into-feature
description: 作業中に進んだ main を、実装計画の機能ブランチにマージコミットで取り込む（rebase はしない）。衝突は計画書と main 側の意図を読んで直し、検査とテストを通し、まだ終わっていないフェーズの計画書の前提が崩れていないかを確かめてから push する。CI は待たない（次のフェーズが、自分の push の前に確かめて直す）。人には聞かず、決められないときは理由を書いて止まる。shipstack run が次のフェーズの前に claude -p で起動するほか、「main を機能ブランチに取り込んで」と計画のディレクトリを渡されたときに使う。
argument-hint: <計画のディレクトリ>
disable-model-invocation: true
compatibility: Claude Code 向け。git、gh、python3（3.9 以上）が要る。shipstack プラグインの一部として入れる（同じプラグインの shipstack-shared のスクリプトを使う）
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: '"${CLAUDE_PLUGIN_ROOT}/skills/shipstack-shared/scripts/guard.sh" merge-main'
          timeout: 30
          onFailure: block
---

# main を機能ブランチに取り込む

引数: `$ARGUMENTS`（計画のディレクトリ）

rebase すると push 済みの機能ブランチの履歴を書き換えることになるので、マージコミットで取り込む。判断の要らない操作は共通のスクリプト `${CLAUDE_SKILL_DIR}/../shipstack-shared/scripts/shipstack` で行う。出力は JSON で、`ok` が false なら `problems` か `error` を読む。スクリプトはリポジトリのルートで実行する。

利用者への報告と結果ファイルは日本語で書く。

## 守ること

決まりに反する git・gh・wrangler の操作は、frontmatter のフック（`shipstack-shared/scripts/guard.py`）が止める。止められたら、回り込まずに理由を読み、止まる。

- 人には聞かない。止まるのは、衝突の直し方が計画書の「変えてはいけないこと」と食い違うとき、main の変更でまだ終わっていないフェーズの目的が果たせなくなったとき、同じ問題で 2 回直して失敗したときだけ。止まるときは手順 6 の結果ファイルを `--status stopped` で書いて終える
- git の操作は、`{{機能ブランチ}}` への `origin/main` の merge、コミット、push に限る
- main への直接のコミットと push、force push、rebase、`reset --hard` はしない

## 値を読む

```bash
${CLAUDE_SKILL_DIR}/../shipstack-shared/scripts/shipstack values <計画のディレクトリ> --require 計画名 機能ブランチ インストール 静的解析 テスト
```

`values` の値を、以下の `{{…}}` に使う。表に無い欄があると失敗するので、推測で埋めずに止まる。

## 手順

```txt
- [ ] 1. 始める前の確認
- [ ] 2. main をマージする
- [ ] 3. 検査とテスト
- [ ] 4. 計画への影響を確かめる
- [ ] 5. コミットと push
- [ ] 6. 結果ファイルを書いて報告する
```

### 1. 始める前の確認

`shipstack preflight <計画のディレクトリ>` を実行する（機能ブランチで、origin と同じで、未コミットの変更が無い）。`ok` が false なら止まる。`git merge-base --is-ancestor origin/main HEAD` が終了コード 0（取り込み済み）なら、何もせずにそう報告する（結果ファイルは `--status done`、`--commit` なし）。

### 2. main をマージする

`git merge --no-ff --no-commit origin/main` を実行する。衝突したら、計画書と main 側の変更の意図を読んで直す。

### 3. 検査とテスト

`{{インストール}}` を実行し、`{{静的解析}}` と `{{テスト}}` を通す。

### 4. 計画への影響を確かめる

main から入った変更が、まだ終わっていないフェーズの計画書の前提（変更するファイル、変えてはいけないこと、既存のコードの形）を崩していないかを確かめる。崩していれば、計画書の該当箇所を直し、直したことを 6 の結果ファイルの `--summary` に書く（計画書はリポジトリの外にあって使い捨てなので、コミットメッセージには書かない）。計画書を書き換えてよいのは、このスキルだけ。

### 5. コミットと push

1. 下書きを出す。「取り込んだ範囲」はスクリプトが `git log` から写す

   ```bash
   ${CLAUDE_SKILL_DIR}/../shipstack-shared/scripts/shipstack commit-skeleton merge-main <計画のディレクトリ>
   ```

2. 「衝突と直し方」を埋め、次の 1 回の Bash で、書く・確かめる・コミットする。`commit-check` が `problems` を出したらコミットされないので、直してもう一度実行する

   ```bash
   msg="$(git rev-parse --git-path shipstack-message.txt)"
   cat > "$msg" <<'EOF'
   <埋めたコミットメッセージの全文>
   EOF
   ${CLAUDE_SKILL_DIR}/../shipstack-shared/scripts/shipstack commit-check merge-main "$msg" && git commit -F "$msg"
   ```

3. `git push` する。CI は待たない。次のフェーズのワーカーが、自分の push の前にこの push の CI を確かめ、落ちていれば直す。CI を待つコマンド（`shipstack ci`、`gh pr checks --watch`、Monitor）は使わずに 6 に進む

### 6. 結果ファイルを書いて報告する

止まったときも書く（`--status stopped --stopped-reason "<止めた理由と、人に決めてほしいこと>"`）。

```bash
${CLAUDE_SKILL_DIR}/../shipstack-shared/scripts/shipstack result <計画のディレクトリ> --name {{計画名}}-merge-main --skill merging-main-into-feature --status done --commit <マージコミットの短いハッシュ> --summary "<取り込んだ範囲と、計画書を直したか（直した計画書と箇所）>"
```

そのうえで、マージコミットのハッシュを、終わったことの報告として示す。
