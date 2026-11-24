"""shipstack-shared のスクリプトの試験。

使い方（リポジトリのルートで）: python3 -I -B -m unittest discover -s plugins/shipstack/skills/shipstack-shared/tests -v

使い捨てのリポジトリ（origin の代わりの bare リポジトリ、main、計画の README と計画書）を毎回作って、guard.py と shipstack の決定論的なふるまいを確かめる。
GitHub と Claude には出ない。gh と claude は tests/fakes/ の偽物に差し替え、指揮役（shipstack run）を最後まで回す。
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import random
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# scripts/ に __pycache__ を作らない（shipstack を読み込んで関数を試すため）。
sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
FAKES = HERE / "fakes"
GUARD = SCRIPTS / "guard.py"
SHIPSTACK = SCRIPTS / "shipstack"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid", "SHIPSTACK_NOTIFY": "0",
       "PATH": f"{FAKES}{os.pathsep}{os.environ['PATH']}", "SHIPSTACK_CLAUDE": str(FAKES / "claude")}
for key in ("CLAUDE_JOB_DIR", "SHIPSTACK_REPO", "CLAUDE_CONFIG_DIR"):
    ENV.pop(key, None)

README = """# demo

## フェーズ表

| フェーズ | 作業名 | エフォート | 要約 |
| --- | --- | --- | --- |
| フェーズ 1 | `demo-p1` | medium | 名前 |
| フェーズ 2 | `demo-p2` | `high` | 言語 |

## 開始前に人がすること

{prerequisites}

## 決めたこと

なし

## プロンプトに入れる値

| 欄 | 値 |
| --- | --- |
| `{{{{計画の置き場所}}}}` | リポジトリの `plans/` |
| `{{{{計画名}}}}` | `demo` |
| `{{{{機能ブランチ}}}}` | `feature/demo` |
| `{{{{PR のタイトル}}}}` | `feat(greet): あいさつの言語を選べるようにする` |
| `{{{{インストール}}}}` | なし（依存が無い） |
| `{{{{静的解析}}}}` | `node --check app.ts \\| cat` |
| `{{{{テスト}}}}` | `node --test` |
| `{{{{テストの範囲}}}}` | 単体テストだけを書く |
| `{{{{UI の方針}}}}` | なし（画面が無い） |
| `{{{{PR の決まり}}}}` | なし |
| `{{{{ADR のディレクトリ}}}}` | `docs/adr/` |
| `{{{{許可するコマンド}}}}` | なし |
| `{{{{E2E}}}}` | なし（E2E が無い） |

## 機能の PR の本文

最初のフェーズが機能の PR を作るとき、次のブロックの中身をそのまま本文にする。

````md
> 作業中。仕上げるまでまだマージしない。main へのマージは本番へのデプロイ。

## なぜ

利用者の言語であいさつするため。

## 進捗

- [ ] フェーズ 1 demo-p1 名前
- [ ] フェーズ 2 demo-p2 言語
- [ ] 決定と学びの記録

## 機能の完了の条件

- `node app.ts --lang en` が Hello を出す

## マージの後に行うこと

- 本番で `node app.ts` を動かす

```bash
# この行は見出しではない（囲みの中のコメント）
node app.ts
```

## 変えてはいけないこと

- 既定の言語は日本語のまま

## 対象外

- 右から左に書く言語

## マージの方法

マージコミットでマージする。
````
"""

PHASE = """# フェーズ {n} — {title}

- **作業名**: `demo-p{n}`

## 完了の条件

- [ ] `node --test` が緑
- [ ] 実物: `node app.ts` の出力が期待どおり

## push の後の確認

- プレビュー環境で出力を見る

## 変えてはいけないこと

- 既存の `greet` の呼び出し方

## 対象外

- 国際化ライブラリの導入

## 変更するファイル

- `app{n}.ts`
"""

# 要件定義書。完了の条件の 1 つ目は README の「機能の完了の条件」に（文末の句点を除いて同じ文で）、2 つ目はマージの前に
# 確かめられないので「マージの後に行うこと」に写してある。
REQUIREMENTS = """# demo：あいさつの言語を選べるようにする

## 目的

利用者の言語であいさつするため。今は日本語だけで、英語の利用者が読めない。

## 材料

- 利用者との会話（2026-11-06）

## 範囲

### やること

- あいさつの言語を引数で選べる

### やらないこと

- 右から左に書く言語

### 後に回すこと

なし

## 用語

| 業務の語 | 意味 | 同義語・使わない言い方 | 出典 |
| --- | --- | --- | --- |
| あいさつ | 起動したときに出す 1 行 | 「メッセージ」とは呼ばない | 利用者との会話（2026-11-06） |

## 振る舞い

| # | 前提 | 操作・きっかけ | 結果 |
| --- | --- | --- | --- |
| 1 | なし | `--lang en` で起動する | Hello と出る |

## 完了の条件

1. `node app.ts --lang en` が Hello を出す。
2. 本番で `node app.ts` を動かす

## 品質特性

なし（手元で動く CLI で、量も権限も無い）

## 権限とデータ

- セキュリティの段階：A（個人情報が無い）

## 決めたこと

なし

## 計画に任せること

- 引数の読み方
"""


def sh(*args: str, cwd: Path | str) -> str:
    return subprocess.run(args, cwd=cwd, env=ENV, check=True, capture_output=True, text=True).stdout.strip()


def load_script(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def load_shipstack():
    return load_script("shipstack", SHIPSTACK)


# シェルの書き方で、中のコマンド（CMD）を包む形。guard.py は、どれで包んでも中のコマンドを同じ決まりで読む。
SHELL_WRAPPERS = [
    "CMD",
    "if true; then CMD; fi",
    "if CMD; then :; fi",
    "if false; then :; else CMD; fi",
    "if false; then :; elif CMD; then :; fi",
    "{ CMD; }",
    "( CMD )",
    "for i in 1; do CMD; done",
    "while CMD; do break; done",
    "! CMD",
    "case x in x) CMD;; esac",
    "f() { CMD; }; f",
    "function g { CMD; }; g",
    "true && CMD",
    "false || CMD",
    "echo x | CMD",
    "CMD # note",
    "true\nCMD",
    "time CMD",
    "env CMD",
    "env -u HOME CMD",
    "command CMD",
    "nice -n 1 CMD",
    "X=1 CMD",
    "bash -c 'CMD'",
    'sh -c "CMD"',
    "bash -ec 'CMD'",
    "eval 'CMD'",
    'eval "CMD"',
    "echo $(CMD)",
    'echo "$(CMD)"',
    "echo `CMD`",
    'echo "`CMD`"',
    "cat <(CMD)",
    "cat <<EOF\n$(CMD)\nEOF",
]


def implement_command() -> str:
    """プラグインの中では /<プラグイン>:implementing-plan-phase、外では /implementing-plan-phase。"""
    return load_shipstack().skill_command("implementing-plan-phase")


class PluginTest(unittest.TestCase):
    def test_worker_skills_are_called_with_the_plugin_name(self):
        module = load_shipstack()
        manifest = SCRIPTS.parents[2] / ".claude-plugin" / "plugin.json"
        expected = json.loads(manifest.read_text(encoding="utf-8"))["name"] if manifest.exists() else None
        self.assertEqual(module.PLUGIN, expected)
        self.assertEqual(module.skill_command("implementing-plan-phase"),
                         f"/{expected}:implementing-plan-phase" if expected else "/implementing-plan-phase")

    def test_first_command_drops_the_plugin_name(self):
        module = load_shipstack()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.jsonl"
            for content, expected in [
                ("<command-message>x</command-message>\n<command-name>/shipstack:implementing-plan-phase</command-name>\n"
                 "<command-args>/p/phase-01.md</command-args>", ("implementing-plan-phase", "/p/phase-01.md")),
                ("/shipstack:recording-plan-decisions /p", ("recording-plan-decisions", "/p")),
                # 前の名前（plan-phases）で動かした計画の会話も数える
                ("<command-name>/plan-phases:implementing-plan-phase</command-name>\n<command-args>/p/phase-03.md</command-args>",
                 ("implementing-plan-phase", "/p/phase-03.md")),
                ("/implementing-plan-phase /p/phase-02.md", ("implementing-plan-phase", "/p/phase-02.md")),
            ]:
                path.write_text(json.dumps({"type": "user", "message": {"content": content}}) + "\n", encoding="utf-8")
                self.assertEqual(module.first_command(path), expected)


class Fixture(unittest.TestCase):
    """main だけを push したリポジトリと、2 フェーズの計画。機能ブランチ feature/demo はまだ無い。"""

    prerequisites = "なし"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.origin = root / "origin.git"
        self.repo = root / "repo"
        self.gh_state = root / "gh.json"
        self.env = {**ENV, "FAKE_GH_STATE": str(self.gh_state), "FAKE_CLAUDE_LOG": str(root / "claude.log")}
        sh("git", "init", "-q", "--bare", "-b", "main", str(self.origin), cwd=root)
        self.repo.mkdir()
        sh("git", "init", "-q", "-b", "main", cwd=self.repo)
        sh("git", "remote", "add", "origin", str(self.origin), cwd=self.repo)
        (self.repo / ".gitignore").write_text("plans/\n")
        (self.repo / "app.ts").write_text("x\n")
        sh("git", "add", ".", cwd=self.repo)
        sh("git", "commit", "-q", "-m", "chore: initial", cwd=self.repo)
        sh("git", "push", "-q", "-u", "origin", "main", cwd=self.repo)
        sh("git", "remote", "set-head", "origin", "main", cwd=self.repo)
        self.plan = (self.repo / "plans" / "demo").resolve()
        self.plan.mkdir(parents=True)
        (self.plan / "README.md").write_text(README.format(prerequisites=self.prerequisites), encoding="utf-8")
        (self.plan / "requirements.md").write_text(REQUIREMENTS, encoding="utf-8")
        for n, title in ((1, "名前"), (2, "言語")):
            (self.plan / f"phase-0{n}.md").write_text(PHASE.format(n=n, title=title), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def shipstack(self, *args: str, stdin: str = "", env: dict | None = None) -> tuple[int, dict | str]:
        proc = subprocess.run([sys.executable, "-I", str(SHIPSTACK), *args], cwd=self.repo, input=stdin,
                              env={**self.env, **(env or {})}, capture_output=True, text=True)
        self.last_stderr = proc.stderr
        try:
            return proc.returncode, json.loads(proc.stdout)
        except json.JSONDecodeError:
            return proc.returncode, proc.stdout

    def feature_with_p1(self):
        """feature/demo を作り、フェーズ 1 のコミットを push して、機能の PR を作った状態にする。"""
        sh("git", "switch", "-q", "-c", "feature/demo", cwd=self.repo)
        (self.repo / "app.ts").write_text("y\n")
        sh("git", "commit", "-q", "-am", "feat: p1\n\nフェーズ: demo-p1（phase-01.md）", cwd=self.repo)
        sh("git", "push", "-q", "-u", "origin", "feature/demo", cwd=self.repo)

    def gh(self) -> dict:
        return json.loads(self.gh_state.read_text())


class GuardHookTest(unittest.TestCase):
    def test_worker_skills_block_when_the_guard_fails(self):
        """ワーカーのスキルの frontmatter のフックは、役目を付けて guard.sh を呼び、落ちたり時間切れになったりしたら止める。
        Claude Code の既定では、失敗したフックはコマンドを通す。"""
        skills = HERE.parent.parent
        roles = {"implementing-plan-phase": "implement", "merging-main-into-feature": "merge-main",
                 "recording-plan-decisions": "decisions", "finalizing-feature-pr": "finalize"}
        for skill, role in roles.items():
            frontmatter = (skills / skill / "SKILL.md").read_text(encoding="utf-8").split("---\n")[1]
            self.assertIn(f"""command: '"${{CLAUDE_PLUGIN_ROOT}}/skills/shipstack-shared/scripts/guard.sh" {role}'""",
                          frontmatter, skill)
            self.assertRegex(frontmatter, r"\n {10}onFailure: block\n", skill)


class GuardTest(Fixture):
    def setUp(self):
        super().setUp()
        self.feature_with_p1()

    def guard(self, role: str, command: str, cwd=None) -> int:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd or self.repo)})
        proc = subprocess.run([sys.executable, "-I", str(GUARD), role], input=payload, capture_output=True, text=True, env=ENV)
        self.last_stderr = proc.stderr
        return proc.returncode

    def assertAllowed(self, role, command):
        self.assertEqual(self.guard(role, command), 0, f"{role}: {command} は通るはず: {self.last_stderr}")

    def assertDenied(self, role, command):
        self.assertEqual(self.guard(role, command), 2, f"{role}: {command} は止まるはず")
        self.assertIn("[計画のスキルの決まり]", self.last_stderr)

    def test_allowed_everyday_commands(self):
        for command in [
            "git status --porcelain",
            "git fetch origin && git log --oneline origin/main..HEAD",
            "git push",
            "git push -u origin feature/demo",
            "git push origin HEAD",
            "git commit -F /tmp/msg.txt",
            'git commit -m "fix: don\'t force push; git push -f origin main"',
            "git commit -F - <<'EOF'\nfeat: x\n\ngit push --force origin main\nEOF",
            "git -C . log -1",
            "git reset",
            "git reset -- app.ts",
            "git tag",
            "git tag -l 'v*'",
            "git branch --show-current",
            "git branch -vv",
            "git stash",
            "git worktree list --porcelain",
            "git push --dry-run --force origin main",
            "gh pr view feature/demo --json body -q .body",
            "gh pr checks feature/demo",
            "gh pr edit 1 --body-file /tmp/body.md",
            'gh pr create --base main --head feature/demo --title "WIP: feat: x" --body-file b.md',
            "gh api repos/o/r/pulls/1",
            "gh api graphql -f query='query { viewer { login } }'",
            "echo 'git push --force' > notes.txt",
            "git push 2>&1 | tail -3",
            "git push origin feature/demo > /dev/null 2>&1",
            "git push -u origin feature/demo &>/dev/null; echo done",
        ]:
            with self.subTest(command=command):
                self.assertAllowed("implement", command)

    def test_denied_for_every_worker(self):
        for command in [
            "git push -f",
            "git push --force-with-lease origin feature/demo",
            "git push origin main",
            "git push origin HEAD:main",
            "git push origin feature/demo:refs/heads/main",
            "git push origin +feature/demo",
            "git push origin :feature/demo",
            "git push --tags",
            "git push -u origin feature/other",
            "(git status); git push -f",
            "git status && git push origin main",
            "env FOO=1 git push --force",
            "git rebase origin/main",
            "git pull",
            "git reset --hard origin/feature/demo",
            "git reset --soft HEAD~1",
            "git switch -c other",
            "git checkout -b other",
            "git branch other",
            "git branch -D feature/demo",
            "git branch -m feature/demo x",
            "git tag v1",
            "git tag -d v1",
            "git worktree add ../x",
            "git worktree remove .claude/worktrees/demo-p2",
            "git clean -fdx",
            "git update-ref refs/heads/main HEAD",
            "gh pr merge 1 --merge",
            "gh pr close 1",
            "gh pr edit 1 --base develop",
            "gh api -X PATCH repos/o/r/pulls/1 -f title=x",
            "gh api repos/o/r/pulls/1/merge -X PUT",
            "gh api graphql -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }'",
            "gh workflow run deploy.yml",
        ]:
            for role in ("implement", "decisions", "finalize", "merge-main"):
                with self.subTest(role=role, command=command):
                    self.assertDenied(role, command)

    def test_secret_writes_are_denied_for_every_worker(self):
        # 秘密の値の登録と入れ替えは人がする。GitHub の secret・variable と、Worker の secret・Secrets Store の書き込みを止める。
        for command in [
            "gh secret set API_KEY",
            "gh variable delete APP_URL",
            "wrangler secret put API_KEY",
            "openssl rand -base64 32 | npx wrangler secret put SIGNING_KEY",
            "npx wrangler secret delete API_KEY --name api",
            "pnpm -F @app/api exec wrangler secret bulk secrets.json",
            "pnpm exec wrangler versions secret put API_KEY",
            "npx --yes wrangler@4 secrets-store secret create store1 --name app-prod_API_KEY --scopes workers --remote",
            "wrangler --profile prod secrets-store secret update store1 --secret-id abc --value x",
            "npx wrangler secrets-store secret delete store1 --secret-id abc --remote",
            "npx wrangler secrets-store store create default --remote",
            "npx wrangler deploy --secrets-file .env.production",
        ]:
            for role in ("implement", "decisions", "finalize", "merge-main"):
                with self.subTest(role=role, command=command):
                    self.assertDenied(role, command)

    def test_secret_reads_and_other_wrangler_commands_are_allowed(self):
        for command in [
            "npx wrangler secret list --name api",
            "npx wrangler secrets-store secret list store1 --remote --per-page 100",
            "npx wrangler versions view 1234 --name api --json",
            "pnpm wrangler types",
            "pnpm add -D wrangler",
            "echo 'wrangler secret put X' > notes.txt",
        ]:
            with self.subTest(command=command):
                self.assertAllowed("implement", command)

    def test_commit_on_main_is_denied(self):
        sh("git", "switch", "-q", "main", cwd=self.repo)
        self.assertDenied("implement", "git commit -m 'feat: x'")

    def test_amend_only_before_push(self):
        self.assertDenied("implement", "git commit --amend --no-edit")
        (self.repo / "b.txt").write_text("b\n")
        sh("git", "add", "b.txt", cwd=self.repo)
        sh("git", "commit", "-q", "-m", "wip", cwd=self.repo)
        self.assertAllowed("implement", "git commit --amend --no-edit")

    def test_pr_create_only_for_the_phase_worker(self):
        command = 'gh pr create --base main --head feature/demo --title "WIP: feat: x" --body-file b.md'
        for role in ("decisions", "finalize", "merge-main"):
            self.assertDenied(role, command)
        self.assertDenied("implement", 'gh pr create --title "feat: x" --body-file b.md')

    def test_only_finalize_removes_wip(self):
        self.assertAllowed("finalize", 'gh pr edit 1 --title "feat: x"')
        self.assertAllowed("implement", 'gh pr edit 1 --title "WIP: feat: x"')
        for role in ("implement", "decisions", "merge-main"):
            self.assertDenied(role, 'gh pr edit 1 --title "feat: x"')

    def test_merge_rules_by_role(self):
        self.assertAllowed("merge-main", "git merge --no-ff --no-commit origin/main")
        self.assertDenied("merge-main", "git merge --squash origin/main")
        self.assertDenied("merge-main", "git merge --no-ff feature/other")
        self.assertAllowed("merge-main", "git merge --abort")
        for role in ("implement", "decisions", "finalize"):
            self.assertDenied(role, "git merge origin/main")

    def test_removed_roles_are_unknown(self):
        for role in ("integrate", "conductor"):
            self.assertEqual(self.guard(role, "git status"), 2)

    def test_unparseable_git_is_denied(self):
        self.assertDenied("implement", "git commit -m 'unterminated")
        self.assertAllowed("implement", "echo 'unterminated")

    def test_shell_syntax_does_not_hide_a_denied_command(self):
        for wrapper in SHELL_WRAPPERS:
            for inner in ("git push --force", "gh pr merge 1"):
                command = wrapper.replace("CMD", inner)
                with self.subTest(command=command):
                    self.assertDenied("implement", command)

    def test_commands_run_by_other_commands_are_read(self):
        for command in [
            "timeout 60 git push --force",
            "timeout -s KILL 60 git push origin main",
            "sudo -u root git push --force",
            "env -S 'git push --force'",
            "if git diff --quiet; then git push --force; fi",
            'git commit -m "$(git push --force)"',
            "cat <<EOF\nnotes\n`gh pr merge 1`\nEOF",
            "bash -c 'cat <<EOF\n$(git push --force)\nEOF'",
            "find . -maxdepth 0 -exec git push --force \\;",
            "find . -name x -exec true \\; -exec git push --force \\;",
            "bash -c 'bash -c \"git push origin main\"'",
            # case の型の ) は、コマンド置換の終わりではない（bash 4 以降。macOS の bash 3.2 は読み違えて何も動かさない）
            'echo "$(case x in x) git push --force;; esac)"',
            "cat <<EOF\n$(case x in (x) gh pr merge 1;; esac)\nEOF",
        ]:
            with self.subTest(command=command):
                self.assertDenied("implement", command)

    def test_arguments_added_by_xargs_and_find_are_not_trusted(self):
        # xargs と find -exec が足す引数は読めないので、git・gh・wrangler の書き込みに引数を足す形は止める。
        for command in [
            "echo --force | xargs git push",
            "echo main | xargs -n1 git push origin",
            "echo 1 | xargs gh pr merge",
            "echo 1 | xargs -I{} gh api repos/o/r/pulls/{}",
            "printf 'x\\0' | xargs -0 bash -c",
            "echo K | xargs npx wrangler secret put",
            "find . -name '*.lock' -exec git checkout {} +",
        ]:
            with self.subTest(command=command):
                self.assertDenied("implement", command)
        for command in [
            "git ls-files -m | xargs git add",
            "git log --format=%h -3 | xargs -n1 git show --stat",
            "echo 1 | xargs gh pr view",
            "find . -name '*.ts' -exec grep -l x {} +",
            "find . -name '*.sh' -exec bash -n {} \\;",
        ]:
            with self.subTest(command=command):
                self.assertAllowed("implement", command)

    def test_shell_syntax_around_allowed_commands_is_still_allowed(self):
        for command in [
            "if git diff --quiet; then echo clean; else git status --short; fi",
            'for f in a b; do git add "$f"; done',
            "{ git status; git log -1; } > /tmp/x",
            "bash -c 'git status && git push'",
            'echo "$(git rev-parse HEAD)"',
            'git commit -m "use `pnpm test` to check"',
            "git commit -F - <<EOF\nfeat: x\n\ngit push --force origin main\nEOF",
            "timeout 600 git push",
            "nice -n 5 git status",
            "env -u FOO git status",
            "echo $((1 << 2))",
        ]:
            with self.subTest(command=command):
                self.assertAllowed("implement", command)


class GuardShellOracleTest(Fixture):
    """本物の bash を正解の役にして、生成したコマンドで guard.py を確かめる。

    git と gh は、受け取った引数を記録するだけの偽物にする。bash が、止めるべき操作（FORBIDDEN）を実際に動かした
    コマンドは、guard.py も止めていなければならない。シェルの読み方を確かめる検証器は無いので、本物のコードに
    生成した入力を流す。種は固定する（落ちたら同じコマンドで再現できる）。"""

    SEED = 20261124
    COUNT = 400
    FORBIDDEN_ATOMS = [
        "git push --force",
        "git push origin main",
        "git push origin +HEAD",
        "gh pr merge 1",
        "git reset --hard HEAD~1",
        "git rebase origin/main",
        "echo --force | xargs git push",
        "echo 1 | xargs gh pr merge",
        "find . -maxdepth 0 -exec git push --force \\;",
    ]
    ALLOWED_ATOMS = ["git status", "git push", "git log -1", "gh pr view 1", "echo ok", ":"]
    # bash の上で実際に動いたとき、止めるべき操作の引数（偽物の git・gh が記録する形）。
    FORBIDDEN = {
        ("git", "push", "--force"),
        ("git", "push", "origin", "main"),
        ("git", "push", "origin", "+HEAD"),
        ("gh", "pr", "merge", "1"),
        ("git", "reset", "--hard", "HEAD~1"),
        ("git", "rebase", "origin/main"),
    }

    def setUp(self):
        super().setUp()
        # PATH で最初に見つかる bash（macOS に Homebrew の bash 5 があればそれ）。/bin/bash 3.2 は、
        # $(case x in x) …;; esac) を読み違えて何も動かさないので、正解の役として弱い。
        self.bash = shutil.which("bash")
        if not self.bash:
            self.skipTest("bash が無い")
        self.feature_with_p1()
        self.guard_module = load_script("shipstack_guard", GUARD)
        box = Path(self.tmp.name) / "oracle"
        self.bin, self.work, self.log = box / "bin", box / "work", box / "calls.log"
        self.bin.mkdir(parents=True)
        self.work.mkdir()
        for name in ("git", "gh"):
            stub = self.bin / name
            stub.write_text('#!/bin/sh\n{ printf %s "${0##*/}"; for a in "$@"; do printf "\\037%s" "$a"; done; '
                            'printf "\\n"; } >> "$ORACLE_LOG"\n')
            stub.chmod(0o755)
        self.oracle_env = {"PATH": f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin", "HOME": str(box),
                           "ORACLE_LOG": str(self.log), "LC_ALL": "C"}

    def run_in_bash(self, command: str) -> list[tuple[str, ...]]:
        """bash が実際に動かした git と gh の呼び出し。"""
        self.log.write_text("")
        try:
            subprocess.run([self.bash, "--noprofile", "--norc", "-c", command], cwd=self.work, env=self.oracle_env,
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return [tuple(line.split("\x1f")) for line in self.log.read_text().splitlines() if line]

    def denied(self, command: str) -> bool:
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                self.guard_module.check_bash(command, "implement", str(self.repo))
            except SystemExit as stop:
                return stop.code == 2
        return False

    def generate(self, rng: random.Random) -> str:
        atoms = self.FORBIDDEN_ATOMS if rng.random() < 0.75 else self.ALLOWED_ATOMS
        command = rng.choice(atoms)
        for _ in range(rng.randint(1, 3)):
            command = rng.choice(SHELL_WRAPPERS).replace("CMD", command)
        if rng.random() < 0.3:
            command = f"{rng.choice(self.ALLOWED_ATOMS)}{rng.choice(['; ', ' && ', chr(10)])}{command}"
        return command

    def test_whatever_bash_runs_that_is_forbidden_is_denied(self):
        rng = random.Random(self.SEED)
        reached, misses = 0, []
        for _ in range(self.COUNT):
            command = self.generate(rng)
            calls = self.run_in_bash(command)
            if any(call in self.FORBIDDEN for call in calls):
                reached += 1
                if not self.denied(command):
                    misses.append(f"{command!r} → bash は {[' '.join(c) for c in calls]} を動かした")
        # 生成したコマンドの多くが、止めるべき操作まで届いていなければ、この確かめは空回りしている。
        self.assertGreaterEqual(reached, self.COUNT // 4, f"止めるべき操作まで届いたのは {reached} 件だけ")
        self.assertEqual(misses, [], f"{len(misses)} 件が通った。初めの 5 件:\n" + "\n".join(misses[:5]))


class PlanPhasesTest(Fixture):
    def test_values(self):
        code, out = self.shipstack("values", str(self.plan), "--require", "機能ブランチ", "テスト", "PR のタイトル")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["plan_name"], "demo")
        self.assertEqual(out["values"]["機能ブランチ"], "feature/demo")
        self.assertIsNone(out["values"]["インストール"])
        self.assertEqual(out["values"]["静的解析"], "node --check app.ts | cat")
        code, out = self.shipstack("values", str(self.plan), "--require", "存在しない欄")
        self.assertEqual(code, 1)
        self.assertEqual(out["missing"], ["存在しない欄"])

    def test_preflight(self):
        self.feature_with_p1()
        code, out = self.shipstack("preflight", str(self.plan))
        self.assertEqual((code, out["ok"]), (0, True), out)
        (self.repo / "app.ts").write_text("dirty\n")
        code, out = self.shipstack("preflight", str(self.plan))
        self.assertEqual(code, 1)
        self.assertTrue(any("未コミット" in p for p in out["problems"]))
        sh("git", "checkout", "--", "app.ts", cwd=self.repo)
        code, out = self.shipstack("preflight", str(self.plan), "--require-phases-done")
        self.assertEqual((code, out["phases"]["missing"]), (1, ["demo-p2"]))

    def test_scripts_work_from_outside_the_repository(self):
        """計画のディレクトリが Git の外でも、ワーカーがそこに cd して呼んで動く（今までは gh が落ちた）。"""
        self.feature_with_p1()
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        proc = subprocess.run([sys.executable, "-I", str(SHIPSTACK), "preflight", str(self.plan)], cwd=outside,
                              env={**self.env, "SHIPSTACK_REPO": str(self.repo)}, capture_output=True, text=True)
        self.assertEqual(json.loads(proc.stdout)["ok"], True, proc.stdout)

    def test_check_off(self):
        module = load_shipstack()
        body = "## 進捗\r\n\r\n- [ ] フェーズ 1 demo-p1 名前\r\n- [ ] フェーズ 10 demo-p10 x\r\n- [ ] 決定と学びの記録\r\n"
        new, before, after = module.check_off(body, "demo-p1", "a1b2c3d")
        self.assertEqual(after, "- [x] フェーズ 1 demo-p1 名前（a1b2c3d）\r")
        self.assertEqual(new.replace(after, before), body)  # ほかの行は 1 文字も変わらない
        again, _, _ = module.check_off(new, "demo-p1", "a1b2c3d")
        self.assertEqual(again, new)  # 2 回目は変えない
        with self.assertRaises(module.Failure):
            module.check_off(body, "demo-p9", "x")

    def test_pr_create_unfences_the_body_and_adds_attribution(self):
        self.feature_with_p1()
        code, out = self.shipstack("pr-create", str(self.plan))
        self.assertEqual(code, 0, out)
        pr = self.gh()["prs"][0]
        self.assertEqual(pr["title"], "WIP: feat(greet): あいさつの言語を選べるようにする")
        self.assertTrue(pr["body"].startswith("> 作業中。"), pr["body"][:40])
        self.assertNotIn("````", pr["body"])
        self.assertNotIn("次のブロックの中身", pr["body"])  # 囲みの前の説明の文は入れない
        self.assertIn("# この行は見出しではない", pr["body"])  # 囲みの中のコードブロックは残す
        self.assertIn("## マージの方法", pr["body"])  # 中の bash の # で節が切れない
        self.assertTrue(pr["body"].rstrip().endswith("Generated with [Claude Code](https://claude.com/claude-code)"))
        code, out = self.shipstack("pr-create", str(self.plan))
        self.assertEqual((code, out["created"]), (0, False))

    def test_result_and_stops(self):
        code, out = self.shipstack("result", str(self.plan), "--name", "demo-p2", "--skill", "implementing-plan-phase",
                                     "--status", "done", "--summary", "実装した", "--commit", "abc1234", "--ci", "pass",
                                     "--manual-step", "画面で確かめる")
        self.assertEqual(code, 0, out)
        written = json.loads((self.plan / ".runs" / "demo-p2.json").read_text())
        self.assertEqual(written["manual_steps"], ["画面で確かめる"])
        code, out = self.shipstack("result", str(self.plan), "--name", "demo-p2", "--skill", "implementing-plan-phase",
                                     "--status", "stopped", "--summary", "止めた")
        self.assertEqual(code, 1)
        code, out = self.shipstack("stops", str(self.plan))
        self.assertEqual((code, out["count"]), (0, 0))

    def test_previous_waits_for_the_last_push_and_lists_post_push_checks(self):
        code, out = self.shipstack("previous", str(self.plan), "demo-p1", "--interval", "0", "--appear-grace", "0")
        self.assertEqual((code, out["ci"], out["previous"]), (0, "none", None), out)  # 機能の PR がまだ無い
        self.feature_with_p1()
        # 完了の条件のうち push の後にしか確かめられないものは、ワーカーが結果ファイルの post_push に書く
        self.shipstack("result", str(self.plan), "--name", "demo-p1", "--skill", "implementing-plan-phase", "--status", "done",
                         "--summary", "実装した", "--post-push", "画面の幅 375px で崩れない")
        # 前の版のワーカーは、コミットメッセージの完了の条件に印を付けていた（それも読む）
        (self.repo / "app1.ts").write_text("p1\n")
        sh("git", "add", "app1.ts", cwd=self.repo)
        sh("git", "commit", "-q", "-m", "feat: p1 の続き\n\nフェーズ: demo-p1（phase-01.md）\n\n完了の条件:\n"
           "- [x] `node --test` が緑\n- [x] 実物: `node app.ts` の出力が期待どおり（push の後に確かめる）", cwd=self.repo)
        sh("git", "push", "-q", cwd=self.repo)
        self.shipstack("pr-create", str(self.plan))
        code, out = self.shipstack("previous", str(self.plan), "demo-p2", "--interval", "0", "--appear-grace", "0")
        self.assertEqual((code, out["ci"]), (0, "pass"), out)
        self.assertEqual(out["previous"]["name"], "demo-p1")
        self.assertEqual(out["previous"]["file"], str(self.plan / "phase-01.md"))
        self.assertEqual(out["previous"]["post_push"], ["プレビュー環境で出力を見る", "画面の幅 375px で崩れない",
                                                        "実物: `node app.ts` の出力が期待どおり"])
        code, out = self.shipstack("previous", str(self.plan), "demo-p9")
        self.assertEqual(code, 1)
        self.assertIn("フェーズ表にありません", out["error"])

    def test_failed_ci_names_the_run_to_read(self):
        self.feature_with_p1()
        self.shipstack("pr-create", str(self.plan))
        state = self.gh()
        state["checks"] = [{"name": "ci", "bucket": "fail", "link": "https://github.com/o/r/actions/runs/123/job/456"},
                           {"name": "lint", "bucket": "pass", "link": "https://github.com/o/r/actions/runs/123/job/457"}]
        self.gh_state.write_text(json.dumps(state))
        code, out = self.shipstack("ci", str(self.plan), "--interval", "0")
        self.assertEqual((code, out["ci"], out["checks"][0]["run_id"]), (0, "fail", "123"), out)
        self.assertIn("--log-failed", out["note"])

    def test_phase_commit_message(self):
        plan_file = str(self.plan / "phase-02.md")
        code, skeleton = self.shipstack("commit-skeleton", "phase", plan_file)
        self.assertEqual(code, 0)
        # 計画書は使い捨てなので、計画書が無いと読めない中身（節の写し、計画書のファイル名、計画との差）は書かない
        self.assertIn("\nフェーズ: demo-p2\n", skeleton)
        self.assertNotIn("phase-02.md", skeleton)
        self.assertNotIn("[ ]", skeleton)
        self.assertNotIn("計画から変えた点", skeleton)
        self.assertIn("\n決めたこと\n", skeleton)
        message = Path(self.tmp.name) / "msg.txt"
        message.write_text(skeleton)
        code, out = self.shipstack("commit-check", "phase", str(message), "--plan", plan_file)
        self.assertEqual(code, 1)
        self.assertTrue(any("置き換える場所" in p for p in out["problems"]), out)
        module = load_shipstack()
        filled = (skeleton.replace(module.PLACEHOLDERS["title"], "feat(greet): 言語を選べるようにする")
                  .replace(module.PLACEHOLDERS["why"], "利用者の言語であいさつするため。")
                  .replace(module.PLACEHOLDERS["decided"], "なし")
                  .replace(module.PLACEHOLDERS["verified_phase"], "node --test が緑（12 件）"))
        message.write_text(filled)
        code, out = self.shipstack("commit-check", "phase", str(message), "--plan", plan_file)
        self.assertEqual((code, out["problems"]), (0, []))
        # 前の形（計画書のファイル名つき）の「フェーズ:」の行は通さない
        message.write_text(filled.replace("フェーズ: demo-p2", "フェーズ: demo-p2（phase-02.md）"))
        code, out = self.shipstack("commit-check", "phase", str(message), "--plan", plan_file)
        self.assertTrue(any("「フェーズ: demo-p2」の行" in p for p in out["problems"]), out)
        # 計画書と要件定義書にだけある番号・記号・名前は、メッセージに書かない
        message.write_text(filled.replace("node --test が緑", "README の規則 B と要件の #28 に従い、demo-p1 と同じく計画どおり。node --test が緑"))
        code, out = self.shipstack("commit-check", "phase", str(message), "--plan", plan_file)
        self.assertEqual(code, 1)
        problem = next(p for p in out["problems"] if "番号・記号・名前" in p)
        for word in ("README の規則", "要件の #2", "demo-p1", "計画どおり"):
            self.assertIn(word, problem)
        # git add した変更のコメントにも書かない
        message.write_text(filled)
        (self.repo / "greet.ts").write_text("// 規則 C（要件定義書の決めたこと 2）に従う\nexport const greet = 1;\n")
        sh("git", "add", "greet.ts", cwd=self.repo)
        code, out = self.shipstack("commit-check", "phase", str(message), "--plan", plan_file)
        self.assertEqual(code, 1)
        problem = next(p for p in out["problems"] if "git add した変更" in p)
        self.assertIn("greet.ts:1", problem)
        for word in ("規則 C", "要件定義書", "決めたこと 2"):
            self.assertIn(word, problem)
        sh("git", "reset", "-q", cwd=self.repo)

    def test_decisions_and_merge_main_messages(self):
        self.feature_with_p1()
        code, skeleton = self.shipstack("commit-skeleton", "decisions", str(self.plan))
        self.assertIn("手順: demo-decisions（決定と学びの記録）", skeleton)
        message = Path(self.tmp.name) / "msg.txt"
        message.write_text(skeleton.replace("フェーズ", "x"))
        code, out = self.shipstack("commit-check", "decisions", str(message), "--plan", str(self.plan))
        self.assertEqual(code, 1)
        code, skeleton = self.shipstack("commit-skeleton", "merge-main", str(self.plan))
        self.assertTrue(skeleton.startswith("Merge origin/main into feature/demo"), skeleton)
        self.assertNotIn("計画への影響", skeleton)  # 計画書の直しは結果ファイルに書く（計画書はリポジトリの外）


class NextTest(Fixture):
    def next(self) -> dict:
        code, out = self.shipstack("next", str(self.plan))
        self.assertEqual(code, 0, out)
        return out["next"]

    def test_order_of_steps(self):
        self.assertEqual(self.next()["action"], "create-branch")
        self.feature_with_p1()
        step = self.next()
        self.assertEqual((step["kind"], step["name"]), ("phase", "demo-p2"))
        self.assertEqual(step["prompt"], f"{implement_command()} {self.plan / 'phase-02.md'}")
        # main が進んだら、次のフェーズより先に取り込む
        sh("git", "switch", "-q", "main", cwd=self.repo)
        (self.repo / "hotfix.txt").write_text("h")
        sh("git", "add", "hotfix.txt", cwd=self.repo)
        sh("git", "commit", "-q", "-m", "fix: hotfix", cwd=self.repo)
        sh("git", "push", "-q", "origin", "main", cwd=self.repo)
        sh("git", "switch", "-q", "feature/demo", cwd=self.repo)
        self.assertEqual(self.next()["kind"], "merge-main")

    def test_a_branch_just_made_from_main_is_not_merged(self):
        sh("git", "push", "-q", "origin", "main:refs/heads/feature/demo", cwd=self.repo)
        step = self.next()
        self.assertEqual((step["kind"], step["name"]), ("phase", "demo-p1"))

    def test_merged_plan_does_nothing(self):
        self.feature_with_p1()
        sh("git", "switch", "-q", "main", cwd=self.repo)
        sh("git", "merge", "-q", "--no-ff", "feature/demo", "-m", "Merge feature/demo", cwd=self.repo)
        sh("git", "push", "-q", "origin", "main", cwd=self.repo)
        self.assertEqual(self.next()["action"], "complete")


class RunTest(Fixture):
    def run_plan(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(SHIPSTACK), "run", str(self.plan), *args], cwd=self.repo,
                              env={**self.env, **(env or {})}, capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def history(self) -> list[dict]:
        path = self.plan / ".runs" / "history.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_dry_run_changes_nothing(self):
        proc = self.run_plan("--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("feature/demo がまだありません", proc.stdout)
        self.assertFalse(git_ok_remote(self.repo, "feature/demo"))
        self.assertFalse((self.plan / ".runs").exists())

    def test_runs_the_whole_plan_and_stops_at_merge(self):
        proc = self.run_plan()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        names = [h["name"] for h in self.history()]
        self.assertEqual(names, ["demo-p1", "demo-p2", "demo-decisions", "demo-finalize"])
        self.assertTrue(all(h["ok"] for h in self.history()))
        pr = self.gh()["prs"][0]
        self.assertEqual(pr["title"], "feat(greet): あいさつの言語を選べるようにする")
        self.assertNotIn("まだマージしない", pr["body"])
        self.assertIn("- [x] `node app.ts --lang en` が Hello を出す — 試験で確かめた", pr["body"])
        self.assertIn("1. demo-p1 の画面を確かめる", pr["body"])
        self.assertIn("- 既定の言語は日本語のまま", pr["body"])
        self.assertIn("- 既存の `greet` の呼び出し方", pr["body"])
        self.assertIn("次にあなたがすること", proc.stdout)
        self.assertIn("- 本番で `node app.ts` を動かす", pr["body"].replace("1. ", "- "))
        self.assertIn("マージの前: プレビューで確かめる", proc.stdout)
        # フェーズの後は CI を待たない。フェーズは push の前に前の push の CI を確かめ、仕上げの後だけ指揮役が待つ
        self.assertIn("✓ demo-p1（0 分、前の push の CI none）", proc.stdout)
        self.assertIn("✓ demo-p2（0 分、前の push の CI pass）", proc.stdout)
        self.assertIn("✓ demo-decisions（0 分）", proc.stdout)
        self.assertIn("✓ demo-finalize（0 分、CI pass）", proc.stdout)
        # ワーカーは誰にも聞かない設定で、プロンプトは標準入力で受け取っている
        calls = [json.loads(line) for line in Path(self.env["FAKE_CLAUDE_LOG"]).read_text().splitlines()]
        self.assertTrue(all("--permission-prompts" in c["argv"] and "none" in c["argv"] for c in calls))
        # 許可ルールの欄が無い計画なので、渡す設定は決まりのフックだけ。無人で動くので、API の失敗は Claude Code に待たせる
        roles = {"implementing-plan-phase": "implement", "recording-plan-decisions": "decisions", "finalizing-feature-pr": "finalize"}
        for call in calls:
            settings = json.loads(call["argv"][call["argv"].index("--settings") + 1])
            self.assertNotIn("permissions", settings)
            hook = settings["hooks"]["PreToolUse"][0]["hooks"][0]
            self.assertEqual(hook["command"], f"{SCRIPTS / 'guard.sh'} {roles[call['prompt'].split()[0].lstrip('/').split(':')[-1]]}")
            # フックが落ちたり時間切れになったりしても、コマンドを通さない
            self.assertEqual(hook["onFailure"], "block")
            self.assertEqual(call["watchdog"], "1")
            # 起動の確かめのフックと、利用者とリポジトリの設定に左右されないための値
            self.assertIn(load_shipstack().HOOKS_ON, settings["hooks"]["SessionStart"][0]["hooks"][0]["command"])
            self.assertIs(settings["ultracode"], False)
            self.assertIs(settings["disableAllHooks"], False)
            # 指揮役と同じ版のスキルで動かす
            self.assertEqual(call["argv"][call["argv"].index("--plugin-dir") + 1], str(SCRIPTS.parents[2]))
        self.assertFalse((self.plan / ".runs" / "active.json").exists())
        self.assertEqual(calls[0]["prompt"], f"{implement_command()} {self.plan / 'phase-01.md'}")
        # もう一度打っても何も起動しない
        again = self.run_plan()
        self.assertEqual(again.returncode, 0)
        self.assertEqual(len(self.history()), 4)

    def test_a_stopped_worker_stops_the_run_and_resumes(self):
        proc = self.run_plan(env={"FAKE_CLAUDE_STOP": "demo-p2"})
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("試験で止めた", proc.stdout)
        self.assertIn("claude -r ", proc.stdout)
        self.assertEqual([(h["name"], h["ok"], h["stopped"]) for h in self.history()],
                         [("demo-p1", True, False), ("demo-p2", False, True)])
        code, out = self.shipstack("stops", str(self.plan))
        self.assertEqual(out["count"], 1)
        # 2 回続けてうまくいかなければ、--retry が無いと 3 回目は起動しない
        self.run_plan(env={"FAKE_CLAUDE_STOP": "demo-p2"})
        third = self.run_plan()
        self.assertEqual(third.returncode, 1)
        self.assertIn("2 回続けて", third.stdout)
        resumed = self.run_plan("--retry")
        self.assertEqual(resumed.returncode, 0, resumed.stdout)
        self.assertEqual(self.history()[-1]["name"], "demo-finalize")

    def test_resume_command_names_the_account(self):
        """会話は設定のフォルダごとに保存されるので、~/.claude 以外で動かしたら、開くコマンドにその指定を付ける。"""
        stopped = {"FAKE_CLAUDE_STOP": "demo-p1"}
        proc = self.run_plan(env=stopped)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertRegex(proc.stdout, r"会話を開いて続ける: cd .* && claude -r [0-9a-f-]{36}\n")
        self.assertNotIn("CLAUDE_CONFIG_DIR=", proc.stdout)
        self.assertEqual(self.history()[-1]["config_dir"], str(Path("~/.claude").expanduser().resolve()))

        other = Path(self.tmp.name) / "claude b"
        other.mkdir()
        proc = self.run_plan("--retry", env={**stopped, "CLAUDE_CONFIG_DIR": str(other)})
        self.assertEqual(proc.returncode, 1, proc.stdout)
        command = f"CLAUDE_CONFIG_DIR={shlex.quote(str(other.resolve()))} claude -r "
        self.assertIn(f"会話: {command}", proc.stdout)
        self.assertIn(f"会話を開いて続ける: cd {self.repo.resolve()} && {command}", proc.stdout)
        self.assertEqual(self.history()[-1]["config_dir"], str(other.resolve()))

    def test_resume_command_under_home_keeps_the_tilde(self):
        module = load_shipstack()
        old = os.environ.get("CLAUDE_CONFIG_DIR")
        try:
            os.environ["CLAUDE_CONFIG_DIR"] = str(Path.home() / ".claude-b")
            self.assertEqual(module.resume_command("abc"), "CLAUDE_CONFIG_DIR=~/.claude-b claude -r abc")
            os.environ["CLAUDE_CONFIG_DIR"] = "~/.claude"
            self.assertEqual(module.resume_command("abc"), "claude -r abc")
        finally:
            if old is None:
                os.environ.pop("CLAUDE_CONFIG_DIR", None)
            else:
                os.environ["CLAUDE_CONFIG_DIR"] = old

    def test_dirty_checkout_is_not_touched(self):
        (self.repo / "app.ts").write_text("dirty\n")
        sh("git", "push", "-q", "origin", "main:refs/heads/feature/demo", cwd=self.repo)
        proc = self.run_plan()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("未コミットの変更", proc.stdout)
        self.assertEqual((self.repo / "app.ts").read_text(), "dirty\n")
        self.assertEqual(self.history(), [])

    def add_allow_rules(self, cell: str) -> None:
        readme = self.plan / "README.md"
        text = readme.read_text(encoding="utf-8")
        row = "| `{{テスト}}` | `node --test` |\n"
        self.assertIn(row, text)
        readme.write_text(text.replace(row, row + f"| `{{{{許可するコマンドのルール}}}}` | {cell} |\n"), encoding="utf-8")

    def worker_calls(self) -> list[dict]:
        return [json.loads(line) for line in Path(self.env["FAKE_CLAUDE_LOG"]).read_text().splitlines()]

    def test_allow_rules_are_passed_to_workers(self):
        self.add_allow_rules("`Bash(gh pr edit * --add-label preview)`、`Bash(gh pr view *)`")
        proc = self.run_plan("--once")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("ワーカーに渡す許可ルール: Bash(gh pr edit * --add-label preview)、Bash(gh pr view *)", proc.stdout)
        argv = self.worker_calls()[0]["argv"]
        settings = json.loads(argv[argv.index("--settings") + 1])
        self.assertEqual(settings["permissions"], {"allow": ["Bash(gh pr edit * --add-label preview)", "Bash(gh pr view *)"]})
        self.assertEqual(list(settings), ["permissions", "hooks", "ultracode", "disableAllHooks"])
        self.assertEqual(argv[-2:], ["--add-dir", str(self.plan)])  # --add-dir は値をいくつでも取るので最後のまま
        dry = self.run_plan("--dry-run")
        self.assertIn("--settings '{\"permissions\"", dry.stdout)

    def test_a_single_rule_without_list(self):
        self.add_allow_rules("`Bash(gh pr view *)`")
        self.assertEqual(load_shipstack().Plan(str(self.plan)).allow_rules, ["Bash(gh pr view *)"])

    def test_broad_allow_rules_stop_before_any_worker(self):
        for i, cell in enumerate(("`Bash(*)`", "`Bash`", "`Bash(gh *)`", "`Bash(* --help)`", "`Bash(gh pr view *)`、`Read(**)`")):
            with self.subTest(cell=cell):
                if i:
                    self.tearDown()
                    self.setUp()
                self.add_allow_rules(cell)
                proc = self.run_plan("--once")
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertIn("広すぎるか読めないルール", proc.stdout)
                self.assertFalse(Path(self.env["FAKE_CLAUDE_LOG"]).exists())

    def test_narrow_rules(self):
        narrow = load_shipstack().narrow_rule
        for rule in ("Bash(gh pr edit * --add-label preview)", "Bash(gh run view *)", "WebFetch(domain:example.com)",
                     "mcp__claude-in-chrome__navigate", "Edit(docs/**)"):
            self.assertTrue(narrow(rule), rule)
        self.assertTrue(narrow("Bash(pnpm test)"))
        for rule in ("Bash", "Bash(*)", "Bash(gh*)", "Bash(gh *)", "Bash(gh:*)", "Bash(*gh pr view)", "Bash(:*)", "Read(**)",
                     "Edit(*)", "gh pr view", ""):
            self.assertFalse(narrow(rule), rule)

    def test_a_plan_with_problems_stops_before_any_worker(self):
        (self.plan / "phase-02.md").unlink()
        proc = self.run_plan("--once")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("計画の形が決まりと合いません", proc.stdout)
        self.assertIn("demo-p2: 計画書がありません", proc.stdout)
        self.assertFalse(Path(self.env["FAKE_CLAUDE_LOG"]).exists())

    def test_denials_are_recorded(self):
        proc = self.run_plan("--once", env={"FAKE_CLAUDE_DENY": "gh pr edit 1 --add-label preview"})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("⚠ 権限で拒否: [External System Writes] — gh pr edit 1 --add-label preview", proc.stdout)
        entry = self.history()[0]
        self.assertEqual(entry["permission_denials"], 1)
        self.assertEqual(entry["denials"], [{"tool": "Bash", "reason": "[External System Writes]",
                                             "input": "gh pr edit 1 --add-label preview"}])

    # ---- 起動の確かめ

    def assert_stopped_at_launch(self, proc: subprocess.CompletedProcess, message: str) -> dict:
        """起動の確かめで止まった。ワーカーは何もしておらず、再開もせず、失敗としても数えない。"""
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("■ demo-p1（implementing-plan-phase）のワーカーを、起動の確かめで止めました", proc.stdout)
        self.assertIn(message, proc.stdout)
        self.assertEqual(len(self.worker_calls()), 1)
        self.assertFalse((self.repo / "demo-p1.txt").exists())
        self.assertFalse((self.plan / ".runs" / "demo-p1.json").exists())
        entry = self.history()[-1]
        self.assertEqual((entry["name"], entry["ok"], entry["launch"]), ("demo-p1", False, True))
        self.assertEqual(load_shipstack().recent_failures(self.history(), "demo-p1"), 0)
        return entry

    def test_worker_that_did_not_start_in_auto_mode_is_stopped(self):
        """auto mode が使えず Manual で始まったワーカーは、モデルを呼ぶ前に止める（書き込みがすべて拒否されるため）。"""
        proc = self.run_plan(env={"FAKE_CLAUDE_PERMISSION_MODE": "default"})
        entry = self.assert_stopped_at_launch(proc, "ワーカーが auto ではなく default の権限のモードで始まりました")
        self.assertNotIn("session_id", entry)  # 何もしていない新しい会話は、usage に数えない
        self.assertFalse((self.plan / ".runs" / "active.json").exists())
        # 直して打ち直すと、新しい会話で進む（--retry は要らない）
        again = self.run_plan("--once")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("✓ demo-p1", again.stdout)
        self.assertNotIn("--resume", self.worker_calls()[1]["argv"])

    def test_worker_without_hooks_is_stopped(self):
        """--settings のフックが動かない会話（--bare など）では、決まりのフックが効かないので止める。"""
        proc = self.run_plan(env={"FAKE_CLAUDE_NO_HOOKS": "1"})
        self.assert_stopped_at_launch(proc, "ワーカーで --settings のフックが動きませんでした")

    def test_worker_without_the_plugin_is_stopped(self):
        if load_shipstack().PLUGIN is None:
            self.skipTest("プラグインの外に置いたスクリプトは、プラグインを確かめない")
        proc = self.run_plan(env={"FAKE_CLAUDE_NO_PLUGIN": "1"})
        self.assert_stopped_at_launch(proc, "プラグインが読み込まれませんでした")

    def test_another_copy_of_the_plugin_only_warns(self):
        if load_shipstack().PLUGIN is None:
            self.skipTest("プラグインの外に置いたスクリプトは、プラグインを確かめない")
        proc = self.run_plan("--once", env={"FAKE_CLAUDE_PLUGIN_PATH": "/elsewhere/shipstack"})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("⚠ ワーカーが読んだ shipstack は /elsewhere/shipstack", proc.stdout)

    def test_a_resume_stopped_at_launch_keeps_the_conversation(self):
        """続きから再開しようとした会話を起動の確かめで止めたら、その会話を残し、直してから打ち直すと続きから進む。"""
        cut = self.run_plan(env={"FAKE_CLAUDE_CRASH": "demo-p1:3", "SHIPSTACK_RESUME_PAUSE": "0"})
        self.assertEqual(cut.returncode, 1, cut.stdout + cut.stderr)
        session = self.session_of(self.worker_calls()[0])
        proc = self.run_plan(env={"FAKE_CLAUDE_NO_HOOKS": "1"})
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("起動の確かめで止めました", proc.stdout)
        self.assertEqual(self.history()[-1]["session_id"], session)
        self.assertEqual(json.loads((self.plan / ".runs" / "active.json").read_text())["session_id"], session)
        again = self.run_plan("--once")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("--resume", self.worker_calls()[-1]["argv"])
        self.assertTrue(self.session_of(self.worker_calls()[-1]).endswith(f"{session}.jsonl")
                        or self.session_of(self.worker_calls()[-1]) == session)

    # ---- 途中で切れたワーカー

    def session_of(self, call: dict) -> str:
        argv = call["argv"]
        return argv[argv.index("--session-id") + 1] if "--session-id" in argv else argv[argv.index("--resume") + 1]

    def test_interrupted_worker_continues_in_the_same_conversation(self):
        """API に届かないまま終わったワーカーは、新しいワーカーではなく、同じ会話を続きから再開する。"""
        proc = self.run_plan(env={"FAKE_CLAUDE_CRASH": "demo-p2:1", "SHIPSTACK_RESUME_PAUSE": "0"})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("↻ demo-p2 が途中で切れました（API Error: Can't reach the API server — check your internet or DNS (ENOTFOUND)）",
                      proc.stdout)
        self.assertIn("↻ demo-p2（implementing-plan-phase）の会話を続きから再開します（1 回目）", proc.stdout)
        self.assertIn("✓ demo-p2（0 分、前の push の CI pass、途中で切れて 1 回再開）", proc.stdout)
        self.assertNotIn("↺ API に戻りました", proc.stdout)  # 使い切ったときの API Error の発言は、戻ったことにしない
        # 再開した会話の費用は会話の合計で返るので、記録には前の実行の分を引いた、その実行の分だけを残す
        self.assertEqual([h["cost_usd"] for h in self.history() if h["name"] == "demo-p2"], [1, 1])
        self.assertEqual([(h["name"], h["ok"], h.get("interrupted", False)) for h in self.history()],
                         [("demo-p1", True, False), ("demo-p2", False, True), ("demo-p2", True, False),
                          ("demo-decisions", True, False), ("demo-finalize", True, False)])
        p2 = [c for c in self.worker_calls() if "phase-02.md" in c["prompt"]]
        self.assertEqual(len(p2), 2)
        self.assertNotIn("--resume", p2[0]["argv"])
        self.assertIn("--resume", p2[1]["argv"])
        self.assertEqual(self.session_of(p2[1]), self.session_of(p2[0]))
        self.assertIn(f"「{implement_command()} {self.plan / 'phase-02.md'}」", p2[1]["prompt"])
        self.assertIn("preflight）はやり直さない", p2[1]["prompt"])
        # 再開した会話にはスキルのフックが登録されないので、決まりのフックは指揮役が渡す
        settings = json.loads(p2[1]["argv"][p2[1]["argv"].index("--settings") + 1])
        self.assertTrue(settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"].endswith("guard.sh implement"))
        self.assertEqual(settings["hooks"]["PreToolUse"][0]["hooks"][0]["onFailure"], "block")
        self.assertFalse((self.plan / ".runs" / "active.json").exists())

    def test_rerun_continues_after_auto_resumes_run_out(self):
        proc = self.run_plan(env={"FAKE_CLAUDE_CRASH": "demo-p2:3", "SHIPSTACK_RESUME_PAUSE": "0"})
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("■ demo-p2 が途中で切れました", proc.stdout)
        self.assertIn("同じコマンドを打ち直すと、この会話の続きから再開します", proc.stdout)
        active = json.loads((self.plan / ".runs" / "active.json").read_text())
        self.assertEqual((active["name"], active["resumes"]), ("demo-p2", 2))
        self.assertIn("demo-p2.txt", sh("git", "status", "--porcelain", cwd=self.repo))
        first = self.session_of([c for c in self.worker_calls() if "phase-02.md" in c["prompt"]][0])
        # 打ち直すと、手元の変更があっても止まらずに、同じ会話の続きから進む（切れた記録は「続けて失敗」に数えない）
        again = self.run_plan(env={"FAKE_CLAUDE_CRASH": "demo-p2:3"})
        self.assertEqual(again.returncode, 0, again.stdout)
        self.assertIn("会話を続きから再開します（3 回目）", again.stdout)
        p2 = [c for c in self.worker_calls() if "phase-02.md" in c["prompt"]]
        self.assertEqual(len(p2), 4)
        self.assertEqual({self.session_of(c) for c in p2}, {first})
        self.assertEqual(self.history()[-1]["name"], "demo-finalize")

    def test_fresh_discards_the_interrupted_conversation(self):
        self.run_plan(env={"FAKE_CLAUDE_CRASH": "demo-p2:3", "SHIPSTACK_RESUME_PAUSE": "0"})
        proc = self.run_plan("--fresh")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("途中で切れた demo-p2 の会話は続けずに捨てます", proc.stdout)
        self.assertIn("未コミットの変更", proc.stdout)
        self.assertFalse((self.plan / ".runs" / "active.json").exists())
        sh("git", "clean", "-fdq", "-e", "plans", cwd=self.repo)
        proc = self.run_plan()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        last = [c for c in self.worker_calls() if "phase-02.md" in c["prompt"]][-1]
        self.assertIn("--session-id", last["argv"])
        self.assertNotIn("--resume", last["argv"])

    def test_ctrl_c_keeps_the_conversation_for_the_next_run(self):
        import signal
        import time
        hang = Path(self.env["FAKE_CLAUDE_LOG"] + ".hang")
        proc = subprocess.Popen([sys.executable, "-I", str(SHIPSTACK), "run", str(self.plan)], cwd=self.repo,
                                env={**self.env, "FAKE_CLAUDE_HANG": "demo-p1"}, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, start_new_session=True)
        for _ in range(300):
            if hang.exists():
                break
            time.sleep(0.1)
        os.killpg(proc.pid, signal.SIGINT)  # 端末の Ctrl+C と同じく、指揮役とワーカーの両方に届く
        out = proc.communicate(timeout=60)[0]
        self.assertEqual(proc.returncode, 130, out)
        self.assertIn("止めました。同じコマンドを打ち直すと、demo-p1 の会話の続きから再開します", out)
        self.assertEqual(self.history()[-1]["problems"], ["Ctrl+C で止めました"])
        self.assertTrue(self.history()[-1]["interrupted"])
        again = self.run_plan("--once")
        self.assertEqual(again.returncode, 0, again.stdout)
        p1 = [c for c in self.worker_calls() if "phase-01.md" in c["prompt"]]
        self.assertEqual(len(p1), 2)
        self.assertEqual(self.session_of(p1[1]), self.session_of(p1[0]))
        self.assertIn("人が Ctrl+C で止めた", p1[1]["prompt"])

    def test_interruption_recorded_by_the_old_run_is_resumed(self):
        """active.json を書く前の指揮役が「ワーカーが失敗で終わりました」と記録したワーカーも、手元が汚れていれば再開する。"""
        self.run_plan(env={"FAKE_CLAUDE_CRASH": "demo-p1:3", "SHIPSTACK_RESUME_PAUSE": "0"})
        (self.plan / ".runs" / "active.json").unlink()
        history = self.history()
        old = {k: v for k, v in history[-1].items() if k not in ("interrupted", "resumes", "api_retries")}
        old["problems"] = ["ワーカーが失敗で終わりました（終了コード 1）: API Error: Can't reach the API server (ENOTFOUND)"]
        (self.plan / ".runs" / "history.jsonl").write_text(json.dumps(old, ensure_ascii=False) + "\n")
        proc = self.run_plan("--once")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("demo-p1（implementing-plan-phase）の会話を続きから再開します（1 回目）", proc.stdout)
        self.assertEqual(self.session_of(self.worker_calls()[-1]), old["session_id"])

    def test_a_conversation_finished_by_hand_is_verified_without_launching(self):
        self.run_plan("--once")
        (self.plan / ".runs" / "active.json").write_text(json.dumps({
            "name": "demo-p1", "kind": "phase", "skill": "implementing-plan-phase", "session_id": "s",
            "config_dir": None, "started": 0, "resumes": 1}))
        proc = self.run_plan("--once")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("demo-p1 は結果ファイルを書き終えています。起動せずに確かめます", proc.stdout)
        self.assertEqual(len(self.worker_calls()), 1)
        self.assertFalse((self.plan / ".runs" / "active.json").exists())

    def test_api_retries_are_shown_without_flooding(self):
        proc = self.run_plan("--once", env={"FAKE_CLAUDE_RETRY": "3"})
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(proc.stdout.count("⏳ API に届かないので再試行を待っています"), 1)
        self.assertIn("（通信の失敗など、1/300 回目、次は ", proc.stdout)
        self.assertIn("↺ API に戻りました（0 分待った）", proc.stdout)
        self.assertEqual(self.history()[-1]["api_retries"], 3)

    def test_failed_ci_does_not_stop_phases_but_stops_after_finalize(self):
        """CI の失敗は次のフェーズが直すので、フェーズの後では止めない。仕上げの後の CI が通らなければ止める。"""
        self.gh_state.write_text(json.dumps({"prs": [], "checks": [{"name": "ci", "bucket": "fail", "link": ""}]}))
        proc = self.run_plan()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("✓ demo-p2（0 分、前の push の CI fail）", proc.stdout)
        self.assertIn("■ demo-finalize が確かめた結果が合いません", proc.stdout)
        self.assertIn("CI が fail", proc.stdout)
        self.assertEqual([(h["name"], h["ok"]) for h in self.history()],
                         [("demo-p1", True), ("demo-p2", True), ("demo-decisions", True), ("demo-finalize", False)])
        self.assertEqual(json.loads((self.plan / ".runs" / "demo-p2.json").read_text())["previous_ci"], "fail")

    def test_efforts_are_passed_to_workers(self):
        """フェーズはフェーズ表の「エフォート」、ほかの手順は決まった値を --effort で渡し、記録に残す。"""
        proc = self.run_plan(env={"FAKE_CLAUDE_CRASH": "demo-p2:1", "SHIPSTACK_RESUME_PAUSE": "0"})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("▶ demo-p1（implementing-plan-phase、エフォート medium）を始めます", proc.stdout)
        efforts = [(c["prompt"].split()[0].split(":")[-1] if not c["prompt"].startswith("（") else "再開",
                    c["argv"][c["argv"].index("--effort") + 1]) for c in self.worker_calls()]
        # 途中で切れて再開した会話にも、同じエフォートを渡す
        self.assertEqual(efforts, [("implementing-plan-phase", "medium"), ("implementing-plan-phase", "high"), ("再開", "high"),
                                   ("recording-plan-decisions", "medium"), ("finalizing-feature-pr", "medium")])
        self.assertEqual([(h["name"], h["effort"]) for h in self.history() if h["ok"]],
                         [("demo-p1", "medium"), ("demo-p2", "high"), ("demo-decisions", "medium"), ("demo-finalize", "medium")])

    def test_effort_environment_variable_wins(self):
        """CLAUDE_CODE_EFFORT_LEVEL は --effort より強いので、付いていればそう知らせ、その値を記録する。"""
        proc = self.run_plan("--once", env={"CLAUDE_CODE_EFFORT_LEVEL": "xhigh"})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("CLAUDE_CODE_EFFORT_LEVEL（xhigh）が付いているので", proc.stdout)
        self.assertIn("エフォート xhigh）を始めます", proc.stdout)
        self.assertEqual(self.history()[0]["effort"], "xhigh")

    def test_a_plan_without_the_effort_column_runs_phases_at_high(self):
        """エフォートの列の無い前の版の計画も動き、フェーズは high で動く。"""
        readme = self.plan / "README.md"
        text = readme.read_text(encoding="utf-8")
        for old, new in (("| エフォート |", "|"), ("| --- | --- | --- | --- |", "| --- | --- | --- |"), (" medium |", ""), (" `high` |", "")):
            text = text.replace(old, new, 1)
        readme.write_text(text, encoding="utf-8")
        self.run_plan("--once")
        dry = self.run_plan("--dry-run")
        self.assertIn("次: demo-p2（implementing-plan-phase、エフォート high）", dry.stdout)
        self.assertIn("--effort high", dry.stdout)
        self.assertEqual(self.history()[0]["effort"], "high")


class UsageTest(Fixture):
    """時間・モデル・エフォート・トークンを、会話の記録から集めて写す（usage）。"""

    def setUp(self):
        super().setUp()
        self.config = Path(self.tmp.name) / "config"
        self.folder = self.config / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(self.repo.resolve()))
        self.folder.mkdir(parents=True)
        self.env = {**self.env, "CLAUDE_CONFIG_DIR": str(self.config), "SHIPSTACK_REPO": str(self.repo)}

    def transcript(self, sid: str, events: list[dict], sub: list[dict] | None = None) -> Path:
        path = self.folder / f"{sid}.jsonl"
        path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events))
        if sub:
            (self.folder / sid / "subagents").mkdir(parents=True)
            (self.folder / sid / "subagents" / "agent-1.jsonl").write_text("".join(json.dumps(e) + "\n" for e in sub))
        return path

    @staticmethod
    def said(at: str, mid: str, inp: int, out: int, effort: str = "xhigh", model: str = "claude-opus-5-5", think: int = 0) -> dict:
        return {"type": "assistant", "timestamp": at, "effort": effort, "message": {"id": mid, "model": model, "usage": {
            "input_tokens": inp, "cache_read_input_tokens": inp * 10, "cache_creation_input_tokens": 0, "output_tokens": out,
            "output_tokens_details": {"thinking_tokens": think}}}}

    def test_session_is_recorded_once_and_checked(self):
        sid = "11111111-2222-3333-4444-555555555555"
        for _ in range(2):
            code, out = self.shipstack("session", str(self.plan), "requirements", sid, env=self.env)
            self.assertEqual(code, 0, out)
        self.assertFalse(out["recorded"])
        self.assertEqual(len((self.plan / ".runs" / "sessions.jsonl").read_text().splitlines()), 1)
        code, out = self.shipstack("session", str(self.plan), "plan", "${CLAUDE_SESSION_ID}", env=self.env)
        self.assertEqual(code, 1, out)
        self.assertIn("展開されていない", out["error"])

    def test_usage_counts_each_step_and_keeps_a_copy(self):
        req, p1, p2 = ("aaaaaaaa-0000-0000-0000-000000000001", "bbbbbbbb-0000-0000-0000-000000000002",
                       "cccccccc-0000-0000-0000-000000000003")
        # 要件定義: 実装が始まった（10:00）後の発言は数えない。ターンの時間を AI が動いた時間にする。サブエージェントも数える
        self.transcript(req, [
            {"type": "user", "timestamp": "2026-11-07T08:00:00.000Z", "message": {"content": "/defining-requirements 通知"}},
            self.said("2026-11-07T08:01:00.000Z", "r1", 100, 10, think=5),
            {"type": "system", "subtype": "turn_duration", "durationMs": 120000, "timestamp": "2026-11-07T08:02:00.000Z"},
            # 重なったターンの記録（08:01〜08:02 は上と重なる）。重なった所は 1 回だけ数える
            {"type": "system", "subtype": "turn_duration", "durationMs": 120000, "timestamp": "2026-11-07T08:03:00.000Z"},
            self.said("2026-11-07T08:01:00.000Z", "r1", 100, 10),  # 同じ発言を 2 行に書くことがある（数えるのは 1 回）
            self.said("2026-11-07T11:00:00.000Z", "r2", 999, 999),
        ], sub=[self.said("2026-11-07T08:01:30.000Z", "s1", 50, 5, effort="high")])
        self.shipstack("session", str(self.plan), "requirements", req, env=self.env)
        self.transcript(p1, [self.said("2026-11-07T10:01:00.000Z", "w1", 200, 20),
                             {"type": "cost-state", "totalCostUSD": 1.5, "totalAPIDuration": 60000}])
        # 指揮役の外で動いたワーカー（最初のコマンドで見つける）
        self.transcript(p2, [
            {"type": "user", "timestamp": "2026-11-07T10:30:00.000Z", "message": {"content":
                f"<command-message>implementing-plan-phase</command-message>\n<command-name>/implementing-plan-phase</command-name>\n"
                f"<command-args>{self.plan / 'phase-02.md'}</command-args>"}},
            self.said("2026-11-07T10:31:00.000Z", "w2", 300, 30, model="claude-sonnet-5-5", effort="medium"),
            {"type": "assistant", "timestamp": "2026-11-07T10:32:00.000Z", "message": {"id": "e", "model": "<synthetic>", "usage": {"input_tokens": 0}}},
        ])
        (self.plan / ".runs" / "history.jsonl").write_text(json.dumps({
            "at": "2026-11-07T19:10:00+09:00", "name": "demo-p1", "skill": "implementing-plan-phase", "session_id": p1,
            "config_dir": str(self.config), "seconds": 600, "ok": True}) + "\n")
        code, out = self.shipstack("usage", str(self.plan), "--json", env=self.env)
        self.assertEqual(code, 0, out)
        steps = {s["step"]: s for s in out["steps"]}
        self.assertEqual([s["step"] for s in out["steps"]], ["要件定義", "demo-p1", "demo-p2"])
        r = steps["要件定義"]
        self.assertEqual(r["seconds"], 180)
        self.assertEqual(r["models"]["claude-opus-5-5"]["input"], 150)
        self.assertEqual(r["models"]["claude-opus-5-5"]["cache_read"], 1500)
        self.assertEqual(r["models"]["claude-opus-5-5"]["thinking"], 5)
        self.assertEqual(r["efforts"], {"xhigh": 1, "high": 1})
        self.assertFalse(r["cost_known"])
        self.assertEqual(steps["demo-p1"]["seconds"], 600)  # ワーカーは指揮役が測った経過
        self.assertEqual(steps["demo-p1"]["cost_usd"], 1.5)
        self.assertEqual(steps["demo-p2"]["models"], {"claude-sonnet-5-5": {"input": 300, "cache_read": 3000, "cache_write": 0,
                                                                            "output": 30, "thinking": 0, "requests": 1}})
        snapshot = json.loads((self.plan / ".runs" / "usage" / f"{req}.json").read_text())
        self.assertEqual(snapshot["not_counted_after_start"], 1)
        # 会話の記録が消えても、写しから出す
        for path in self.folder.glob("*.jsonl"):
            path.unlink()
        code, again = self.shipstack("usage", str(self.plan), "--json", env=self.env)
        self.assertEqual(code, 0, again)
        self.assertEqual([s["models"] for s in again["steps"] if s["step"] != "demo-p2"],
                         [s["models"] for s in out["steps"] if s["step"] != "demo-p2"])
        text = subprocess.run([sys.executable, "-I", str(SHIPSTACK), "usage", str(self.plan)], cwd=self.repo,
                              env={**self.env}, capture_output=True, text=True).stdout
        self.assertIn("= 合計", text)
        self.assertIn("opus-5-5（xhigh・high）", text)

    def test_run_records_usage_of_every_worker(self):
        proc = subprocess.run([sys.executable, "-I", str(SHIPSTACK), "run", str(self.plan)], cwd=self.repo,
                              env={**self.env, "FAKE_CLAUDE_TRANSCRIPTS": "1", "FAKE_CLAUDE_CRASH": "demo-p2:1",
                                   "SHIPSTACK_RESUME_PAUSE": "0"},
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("使った時間とトークン", proc.stdout)
        self.assertIn("= 実装", proc.stdout)
        code, out = self.shipstack("usage", str(self.plan), "--json", env=self.env)
        steps = {s["step"]: s for s in out["steps"]}
        self.assertEqual(set(steps), {"demo-p1", "demo-p2", "demo-decisions", "demo-finalize"})
        # 途中で切れて再開した demo-p2 は、同じ会話の 2 回の起動を 1 つの手順として数える
        self.assertEqual(steps["demo-p2"]["sessions"], 1)
        self.assertEqual(steps["demo-p2"]["models"]["claude-opus-5-5"]["requests"], 2)
        self.assertEqual(steps["demo-p2"]["models"]["claude-opus-5-5"]["output"], 200)
        self.assertEqual(steps["demo-p1"]["efforts"], {"xhigh": 1})
        self.assertEqual(len(list((self.plan / ".runs" / "usage").glob("*.json"))), 4)


class CheckPlanTest(Fixture):
    def edit(self, name: str, old: str, new: str) -> None:
        path = self.plan / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, name)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def check(self) -> tuple[int, dict]:
        code, out = self.shipstack("check-plan", str(self.plan))
        self.assertIsInstance(out, dict, out)
        return code, out

    def test_the_fixture_plan_has_no_problems(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertEqual((out["problems"], out["warnings"], out["assumptions"]), ([], [], []))
        self.assertEqual(out["phases"], ["demo-p1", "demo-p2"])

    def test_problems(self):
        cases = [
            (lambda: self.edit("README.md", "## 開始前に人がすること", "## 前提"), "節「開始前に人がすること」がありません"),
            (lambda: self.edit("README.md", "| `{{ADR のディレクトリ}}` | `docs/adr/` |\n", ""), "欄がありません: ADR のディレクトリ"),
            (lambda: self.edit("README.md", "| `node --test` |", "| なし |"), "「テスト」は「なし」にできません"),
            (lambda: self.edit("README.md", "| `demo-p2` |", "| `demo-p3` |"), "1 から順に付けます"),
            (lambda: (self.plan / "phase-02.md").unlink(), "demo-p2: 計画書がありません"),
            (lambda: self.edit("phase-01.md", "- 国際化ライブラリの導入", ""), "phase-01.md: 節「対象外」が空です"),
            (lambda: self.edit("phase-02.md", "- [ ] `node --test` が緑\n- [ ] 実物", "- `node --test` が緑\n- 実物"),
             "phase-02.md「完了の条件」: チェックボックス"),
            (lambda: self.edit("README.md", "- [ ] 決定と学びの記録\n", ""), "「決定と学びの記録」を含むチェックボックスの行が 0 行"),
            (lambda: self.edit("README.md", "- 右から左に書く言語", "- [ ] 右から左に書く言語"), "チェックボックスは「進捗」だけ"),
            (lambda: self.edit("README.md", "まだマージしない", "マージ待ち"), "先頭の注意に「まだマージしない」がありません"),
            (lambda: self.edit("README.md", "`feat(greet): あいさつ", "`あいさつ"), "Conventional Commits"),
            (lambda: self.edit("README.md", "| medium |", "| 普通 |"), "demo-p1 の「エフォート」は low・medium・high・xhigh・max"),
            (lambda: self.edit("README.md", "| `high` |", "| |"), "demo-p2 の「エフォート」は"),
        ]
        for i, (broken, expected) in enumerate(cases):
            with self.subTest(expected=expected):
                if i:
                    self.tearDown()
                    self.setUp()
                broken()
                code, out = self.check()
                self.assertEqual(code, 1, out)
                self.assertTrue(any(expected in p for p in out["problems"]), out["problems"])

    def test_warnings_and_assumptions(self):
        self.edit("README.md", "## 決めたこと\n\nなし", "## 決めたこと\n\n"
                  "| # | 決定 | 比べた案と採らなかった理由 | 選んだ理由 | 根拠と出典 | 関係するフェーズ |\n| --- | --- | --- | --- | --- | --- |\n"
                  "| 1 | 既定は日本語 | **英語**：利用者が読めない | 技術：— 業務：利用者が日本語 | 見立て | 1 |\n"
                  "| 2 | 言語は引数で選ぶ | — | 速い | | 2 |")
        self.edit("README.md", "{prerequisites}".format(prerequisites="なし") + "\n\n## 決めたこと", "- PR に preview ラベルを貼る\n- `gh auth login` で GitHub にログインしておく\n\n## 決めたこと")
        self.edit("README.md", "| `{{許可するコマンド}}` | なし |", "| `{{許可するコマンド}}` | `gh pr edit <番号> --add-label preview` |")
        self.edit("phase-01.md", "- `app1.ts`", "- `app1.ts`（{{目的}}のため、適切に分ける）")
        self.edit("phase-02.md", "- [ ] `node --test` が緑", "- [ ] プレビュー環境で出力が出る")
        self.edit("README.md", "| `{{E2E}}` | なし（E2E が無い） |\n", "")
        self.edit("README.md", "| medium |", "| xhigh |")
        self.edit("README.md", "- 本番で `node app.ts` を動かす", "- 本番で `node app.ts` を動かす\n- E2E を流して記録をコミットする（マージの前に人が行う）")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        warnings = "\n".join(out["warnings"])
        for expected in ("#2: 「比べた案と採らなかった理由」が空", "#2: 「根拠と出典」が空", "#2: 「選んだ理由」に技術と業務",
                         "Claude がコマンドやブラウザでできる作業", "「許可するコマンドのルール」がありません",
                         "phase-01.md:24: 実装が一意にならない言葉「適切に」", "phase-01.md:24: 値の表に無い欄 {{目的}}",
                         "phase-02.md:7: push の後にしか確かめられない条件", "「E2E」の欄がありません",
                         "「マージの後に行うこと」に、マージの前の作業が入っています",
                         "demo-p1 の「エフォート」が xhigh です"):
            self.assertIn(expected, warnings)
        self.assertEqual(out["assumptions"], ["#1 既定は日本語"])
        self.assertNotIn("gh auth login", warnings)  # 資格情報の入力が要る作業は人の作業のまま

    def test_a_dropped_requirement_is_a_problem(self):
        """要件定義書の完了の条件を、機能の PR の本文に写し忘れたら指揮役を動かさない。"""
        self.edit("README.md", "- `node app.ts --lang en` が Hello を出す", "- `node app.ts --lang en` が終了コード 0 で終わる")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertEqual(len(out["problems"]), 1, out["problems"])
        self.assertIn("要件定義書の完了の条件", out["problems"][0])
        self.assertIn("`node app.ts --lang en` が Hello を出す", out["problems"][0])

    def test_a_plan_without_requirements_only_warns(self):
        """要件定義のスキルより前に書いた計画も、指揮役で動かせる。"""
        (self.plan / "requirements.md").unlink()
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertEqual(out["problems"], [])
        self.assertTrue(any("requirements.md がありません" in w for w in out["warnings"]), out["warnings"])

    def test_a_plan_without_the_effort_column_only_warns(self):
        """エフォートの列より前に書いた計画も、指揮役で動かせる。"""
        self.edit("README.md", "| フェーズ | 作業名 | エフォート | 要約 |\n| --- | --- | --- | --- |",
                  "| フェーズ | 作業名 | 要約 |\n| --- | --- | --- |")
        self.edit("README.md", "| medium |", "|")
        self.edit("README.md", "| `high` |", "|")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertEqual(out["warnings"], ["README.md「フェーズ表」: 「エフォート」の列がありません。フェーズのワーカーはすべて high で動きます"
                                           "（フェーズごとに medium か high を書く）"])


    def test_value_keys_cover_every_skill(self):
        """各スキルが values --require で読む欄が、check-plan の確かめる欄に入っている（スキルを変えたら追いつかせる）。"""
        keys = set(load_shipstack().VALUE_KEYS)
        skills = HERE.parent.parent
        seen = 0
        for skill in ("implementing-plan-phase", "merging-main-into-feature", "recording-plan-decisions", "finalizing-feature-pr"):
            for line in (skills / skill / "SKILL.md").read_text(encoding="utf-8").splitlines():
                if "shipstack values" in line and "--require" in line:
                    required = shlex.split(line.split("--require", 1)[1])
                    self.assertLessEqual(set(required), keys, skill)
                    seen += 1
        self.assertEqual(seen, 4)

class CheckRequirementsTest(Fixture):
    def edit(self, old: str, new: str) -> None:
        path = self.plan / "requirements.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def check(self) -> tuple[int, dict]:
        code, out = self.shipstack("check-requirements", str(self.plan))
        self.assertIsInstance(out, dict, out)
        return code, out

    def test_the_fixture_requirements_have_no_problems(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertEqual((out["problems"], out["warnings"], out["assumptions"]), ([], [], []))
        self.assertEqual(out["conditions"], ["`node app.ts --lang en` が Hello を出す。", "本番で `node app.ts` を動かす"])

    def unlist_conditions(self) -> None:
        self.edit("1. `node app.ts", "`node app.ts")
        self.edit("2. 本番", "本番")

    def test_problems(self):
        cases = [
            (lambda: self.edit("## 品質特性", "## 性能"), "節「品質特性」がありません"),
            (lambda: self.edit("- 引数の読み方", ""), "節「計画に任せること」が空です"),
            (lambda: self.edit("### やらないこと", "### しないこと"), "「やらないこと」の見出しがありません"),
            (lambda: self.edit("### 後に回すこと\n\nなし", "### 後に回すこと\n"), "「後に回すこと」が空です"),
            (self.unlist_conditions, "「完了の条件」: 箇条書きがありません"),
            (lambda: (self.plan / "requirements.md").write_text("目的だけ\n", encoding="utf-8"), "タイトルの見出し"),
        ]
        for i, (broken, expected) in enumerate(cases):
            with self.subTest(expected=expected):
                if i:
                    self.tearDown()
                    self.setUp()
                broken()
                code, out = self.check()
                self.assertEqual(code, 1, out)
                self.assertTrue(any(expected in p for p in out["problems"]), out["problems"])

    def test_missing_file_fails(self):
        (self.plan / "requirements.md").unlink()
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("requirements.md がありません", out["error"])

    def test_warnings_and_assumptions(self):
        self.edit("# demo：", "# greet：")
        self.edit("- あいさつの言語を引数で選べる", "- あいさつの言語を引数で選べる（既定の言語は TBD）")
        self.edit("- セキュリティの段階：A（個人情報が無い）", "- 誰でも使える")
        self.edit("## 計画に任せること\n\n- 引数の読み方", "## 計画に任せること\n\n- <計画が決めること>")
        self.edit("## 決めたこと\n\nなし", "## 決めたこと\n\n"
                  "| # | 決定 | 比べた案と採らなかった理由 | 選んだ理由 | 根拠と出典 |\n| --- | --- | --- | --- | --- |\n"
                  "| 1 | 既定は日本語 | **英語**：利用者が読めない | 技術：—。業務：利用者が日本語 | 見立て |\n"
                  "| 2 | 言語は引数で選ぶ | — | 速い | 利用者の判断（2026-11-06） |")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        warnings = "\n".join(out["warnings"])
        for expected in ("タイトルが「# demo：<1 行の要約>」の形ではありません", "一意にならない言葉「TBD」",
                         "セキュリティの段階（A・B・C）がありません", "置き換える場所 <計画が決めること> が残っています",
                         "#2: 「比べた案と採らなかった理由」が空", "#2: 「選んだ理由」に技術と業務"):
            self.assertIn(expected, warnings)
        self.assertEqual(out["assumptions"], ["#1 既定は日本語"])

    def test_placeholders_in_code_are_examples(self):
        """コードの書式の中の <名前> は書き方の例として読み、雛形の残りとはみなさない（2026-11-06 の実行で 13 件の誤検出）。"""
        self.edit("| 1 | なし | `--lang en` で起動する | Hello と出る |",
                  "| 1 | なし | `node app.js <名前> --lang ja` で起動する | `こんにちは、<名前>さん！` と出る |")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertEqual(out["warnings"], [])


class PrBodyTest(Fixture):
    def test_not_kept_decisions_come_from_the_result_when_nothing_was_committed(self):
        self.feature_with_p1()
        self.shipstack("result", str(self.plan), "--name", "demo-decisions", "--skill", "recording-plan-decisions",
                         "--status", "done", "--summary", "なし", "--not-kept", "既定を日本語にした: コードから読み取れる")
        code, body = self.shipstack("pr-body", str(self.plan))
        self.assertEqual(code, 0, body)
        self.assertIn("- 既定を日本語にした: コードから読み取れる", body)
        self.assertIn("- [ ] `node app.ts --lang en` が Hello を出す", body)
        self.assertIn("利用者の言語であいさつするため。", body)


class PrerequisitesTest(Fixture):
    prerequisites = "- プレビュー環境の API キーを入れた"

    def test_asks_once_before_starting(self):
        proc = subprocess.run([sys.executable, "-I", str(SHIPSTACK), "run", str(self.plan), "--once"], cwd=self.repo,
                              env=self.env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("プレビュー環境の API キーを入れた", proc.stdout)
        self.assertIn("--yes", proc.stdout)
        proc = subprocess.run([sys.executable, "-I", str(SHIPSTACK), "run", str(self.plan), "--once", "--yes"],
                              cwd=self.repo, env=self.env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertTrue((self.plan / ".runs" / "prerequisites.json").exists())


def git_ok_remote(repo: Path, branch: str) -> bool:
    return subprocess.run(["git", "ls-remote", "--exit-code", "origin", branch], cwd=repo, capture_output=True).returncode == 0


if __name__ == "__main__":
    unittest.main()
