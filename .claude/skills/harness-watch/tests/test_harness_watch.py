"""harness-watch の収集のスクリプトと、クラウドの会話の push の決まりのフックの試験。

使い捨てのリポジトリ（origin の代わりの bare リポジトリ）と、file:// で読む変更履歴・npm の札・文書を毎回作る。
ネットワークには出ない。リポジトリのルートで流す:

  python3 -I -B -m unittest discover -s .claude/skills/harness-watch/tests -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
ROOT = SKILL.parent.parent.parent
COLLECT = SKILL / "scripts" / "collect.py"
GUARD = ROOT / ".claude" / "hooks" / "cloud-push-guard.py"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
       "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
ENV.pop("CLAUDE_CODE_REMOTE", None)

CHANGELOG = """# Changelog

## 1.0.2

- Added `--bar` to the CLI
- Fixed a crash when
  the transcript was empty

## 1.0.1

- Initial release
"""


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, capture_output=True, text=True, check=True).stdout.strip()


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])
        origin = self.tmp / "origin.git"
        git(self.tmp, "init", "--quiet", "--bare", "--initial-branch=main", str(origin))
        self.repo = self.tmp / "repo"
        git(self.tmp, "clone", "--quiet", str(origin), str(self.repo))
        (self.repo / "README.md").write_text("demo\n")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "--quiet", "-m", "init")
        git(self.repo, "push", "--quiet", "origin", "HEAD:main")
        self.origin = origin
        fx = self.tmp / "fixtures"
        fx.mkdir()
        (fx / "CHANGELOG.md").write_text(CHANGELOG)
        (fx / "dist-tags.json").write_text(json.dumps({"latest": "1.0.2", "stable": "1.0.1"}))
        (fx / "a.md").write_text("# A\n\n`--foo` takes a value.\n")
        (fx / "b.md").write_text("# B\n")
        self.fx = fx
        self.contracts = self.tmp / "contracts.json"
        self.write_contracts(baseline="1.0.1")

    def write_contracts(self, baseline: str) -> None:
        self.contracts.write_text(json.dumps({
            "baseline": {"claude_code": baseline},
            "sources": {"changelog": (self.fx / "CHANGELOG.md").as_uri(), "dist_tags": (self.fx / "dist-tags.json").as_uri()},
            "pages": {"page-a": (self.fx / "a.md").as_uri(), "page-b": (self.fx / "b.md").as_uri()},
            "contracts": [{"id": "flag-foo", "claim": "--foo を使う", "documented": True, "pages": ["page-a"],
                           "keywords": ["--foo"], "used_in": [], "verify": "", "verified": "1.0.1"}],
        }))

    def collect(self, *args: str) -> tuple[int, dict]:
        proc = subprocess.run([sys.executable, "-I", str(COLLECT), "--contracts", str(self.contracts), *args],
                              cwd=self.repo, env=ENV, capture_output=True, text=True)
        return proc.returncode, json.loads(proc.stdout)

    def test_first_run_reads_versions_after_the_baseline_and_snapshots_the_pages(self):
        code, out = self.collect("diff")
        self.assertEqual(code, 0, out)
        self.assertTrue(out["first_run"])
        self.assertEqual(out["claude_code"]["new_versions"], ["1.0.2"])
        self.assertEqual(out["claude_code"]["latest"], "1.0.2")
        self.assertEqual(sorted(out["pages"]["added"]), ["page-a", "page-b"])
        self.assertTrue(out["save_needed"])
        changelog = Path(out["files"]["changelog"]).read_text()
        self.assertIn("- Fixed a crash when the transcript was empty", changelog)  # 続きの行はつなぐ
        self.assertNotIn("Initial release", changelog)  # baseline の版は見たもの

    def test_save_then_nothing_new(self):
        self.write_contracts(baseline="1.0.2")
        code, out = self.collect("diff")
        self.assertEqual((out["nothing_new"], out["save_needed"]), (True, True), out)  # 初回は写しだけ取る
        code, saved = self.collect("save")
        self.assertEqual(code, 0, saved)
        self.assertTrue(saved["saved"])
        self.assertIn("claude/harness-watch-state", git(self.origin, "branch", "--list"))
        self.assertEqual(json.loads(git(self.origin, "show", "claude/harness-watch-state:state.json"))["claude_code"]["seen"], "1.0.2")
        self.assertEqual(git(self.origin, "show", "claude/harness-watch-state:pages/page-b.md"), "# B")
        self.assertEqual(git(self.origin, "rev-parse", "main"), git(self.repo, "rev-parse", "HEAD"))  # main は動かない
        code, out = self.collect("diff")
        self.assertEqual((out["first_run"], out["nothing_new"], out["save_needed"]), (False, True, False), out)
        code, saved = self.collect("save")
        self.assertEqual(saved, {"ok": True, "saved": False, "reason": "前回の状態と同じ"})

    def test_new_version_and_page_change_are_found_with_hints(self):
        self.write_contracts(baseline="1.0.2")
        self.collect("diff")
        self.collect("save")
        (self.fx / "CHANGELOG.md").write_text(CHANGELOG.replace("## 1.0.2", "## 1.0.3\n\n- Removed the `--foo` flag\n\n## 1.0.2"))
        (self.fx / "a.md").write_text("# A\n\n`--foo` was removed.\n")
        code, out = self.collect("diff")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["claude_code"]["new_versions"], ["1.0.3"])
        self.assertFalse(out["nothing_new"])
        self.assertEqual((out["claude_code"]["entries_with_contracts"], out["claude_code"]["entries_flagged"]), (1, 1))
        details = json.loads(Path(out["files"]["details"]).read_text())
        self.assertEqual(details["changelog"][0]["contracts"], ["flag-foo"])
        self.assertEqual(details["changelog"][0]["flags"], ["removed"])
        self.assertIn("[flag-foo] [removed]", Path(out["files"]["changelog"]).read_text())
        [change] = out["pages"]["changed"]
        self.assertEqual((change["page"], change["added_lines"], change["removed_lines"], change["contracts"]),
                         ("page-a", 1, 1, ["flag-foo"]))
        self.assertIn("+`--foo` was removed.", Path(change["diff"]).read_text())
        code, saved = self.collect("save")
        self.assertEqual(saved["seen"], "1.0.3")
        self.assertEqual(git(self.origin, "rev-list", "--count", "claude/harness-watch-state"), "2")

    def test_keyword_groups_need_every_word_and_flags_read_the_leading_verb(self):
        import importlib.machinery, importlib.util
        loader = importlib.machinery.SourceFileLoader("collect", str(COLLECT))
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader("collect", loader))
        loader.exec_module(module)
        contracts = [{"id": "resume-hooks", "keywords": [["resume", "hook"]]}, {"id": "settings", "keywords": ["--settings"]}]
        self.assertEqual(module.contract_hits("Fixed skill hooks not running after --resume", contracts), ["resume-hooks"])
        self.assertEqual(module.contract_hits("Fixed a crash on resume", contracts), [])  # 片方の語だけでは当たらない
        self.assertEqual(module.contract_hits("Added `--settings` merging", contracts), ["settings"])
        self.assertEqual(module.flags_of("Removed the `--foo` flag"), ["removed"])
        self.assertEqual(module.flags_of("Fixed removing a file twice"), [])  # 本文の remove は目印にしない
        self.assertEqual(module.flags_of("Changed X; the old name is deprecated"), ["changed", "deprecated"])

    def test_an_unreadable_page_keeps_its_last_copy(self):
        self.write_contracts(baseline="1.0.2")
        self.collect("diff")
        self.collect("save")
        (self.fx / "b.md").unlink()
        code, out = self.collect("diff")
        self.assertEqual(code, 0, out)
        self.assertEqual([f["page"] for f in out["pages"]["failed"]], ["page-b"])
        self.assertEqual((out["nothing_new"], out["save_needed"]), (True, False))  # 前の写しのまま
        self.assertEqual((Path(out["files"]["details"]).parent / "new" / "pages" / "page-b.md").read_text(), "# B\n")

    def test_an_unreadable_changelog_fails_without_touching_the_state(self):
        (self.fx / "CHANGELOG.md").unlink()
        code, out = self.collect("diff")
        self.assertEqual(code, 1)
        self.assertIn("CHANGELOG.md を読めませんでした", out["error"])
        self.assertNotIn("claude/harness-watch-state", git(self.origin, "branch", "--list"))

    def test_repo_is_read_from_a_proxied_origin(self):
        git(self.repo, "remote", "set-url", "origin", "http://local_proxy@127.0.0.1:41337/git/linto-dev/claude-plugins")
        sys.path.insert(0, str(COLLECT.parent))
        self.addCleanup(sys.path.remove, str(COLLECT.parent))
        import importlib.machinery, importlib.util
        loader = importlib.machinery.SourceFileLoader("collect", str(COLLECT))
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader("collect", loader))
        loader.exec_module(module)
        self.assertEqual(module.github_repo(self.repo), "linto-dev/claude-plugins")
        git(self.repo, "remote", "set-url", "origin", "git@github.com:linto-dev/claude-plugins.git")
        self.assertEqual(module.github_repo(self.repo), "linto-dev/claude-plugins")


class CloudPushGuardTest(unittest.TestCase):
    def guard(self, command: str, remote: bool = True) -> int:
        env = {**ENV, "CLAUDE_CODE_REMOTE": "true"} if remote else ENV
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        proc = subprocess.run([sys.executable, "-I", str(GUARD)], input=payload, env=env, capture_output=True, text=True)
        self.last_stderr = proc.stderr
        return proc.returncode

    def test_allowed_in_the_cloud(self):
        for command in ("git push -u origin claude/harness-watch-20261119",
                        "git push origin HEAD:claude/harness-watch-20261119",
                        "git push origin HEAD:refs/heads/claude/harness-watch-20261119 2>&1",
                        "git -C /tmp/x push origin claude/a",
                        "git status && git log -1",
                        "gh api repos/o/r/pulls -X POST -f base=main -f head=claude/a -F draft=true",
                        "gh api 'repos/o/r/pulls?state=open' --jq '.[].title'",
                        "python3 -I .claude/skills/harness-watch/scripts/collect.py save",
                        "echo 'git push origin main'"):
            self.assertEqual(self.guard(command), 0, f"{command} は通るはず: {self.last_stderr}")

    def test_denied_in_the_cloud(self):
        for command in ("git push", "git push origin", "git push origin main", "git push origin HEAD",
                        "git push origin HEAD:main", "git push --force origin claude/a", "git push -f origin claude/a",
                        "git push --force-with-lease origin claude/a", "git push origin +claude/a",
                        "git push origin :claude/a", "git push --delete origin claude/a", "git push --tags origin claude/a",
                        "cd sub && git push origin main", "env GIT_TRACE=1 git push origin main",
                        "gh pr merge 3", "gh api repos/o/r/pulls/3/merge -X PUT",
                        "gh api -X DELETE repos/o/r/git/refs/heads/claude/a",
                        "gh api repos/o/r/git/refs -X POST -f ref=refs/heads/main",
                        "echo \"unbalanced; git push origin main"):
            self.assertEqual(self.guard(command), 2, f"{command} は止まるはず")
            self.assertIn("[ハーネスの追従の決まり]", self.last_stderr)

    def test_local_sessions_are_not_touched(self):
        self.assertEqual(self.guard("git push origin main", remote=False), 0)

    def test_project_settings_register_the_guard_and_block_on_failure(self):
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
        [entry] = settings["hooks"]["PreToolUse"]
        self.assertEqual(entry["matcher"], "Bash")
        [hook] = entry["hooks"]
        self.assertIn(".claude/hooks/cloud-push-guard.py", hook["command"])
        self.assertEqual(hook["onFailure"], "block")


class ContractsTest(unittest.TestCase):
    def test_contracts_are_consistent_with_the_repository(self):
        data = json.loads((SKILL / "contracts.json").read_text(encoding="utf-8"))
        ids = [c["id"] for c in data["contracts"]]
        self.assertEqual(len(ids), len(set(ids)), "約束の id が重なっている")
        for contract in data["contracts"]:
            for key in ("id", "claim", "documented", "pages", "keywords", "used_in", "verify", "verified"):
                self.assertIn(key, contract, contract.get("id"))
            self.assertTrue(contract["keywords"], contract["id"])
            for page in contract["pages"]:
                self.assertIn(page, data["pages"], f"{contract['id']} の {page} が pages に無い")
            for path in contract["used_in"]:
                self.assertTrue((ROOT / path).exists(), f"{contract['id']} の {path} が無い")
        self.assertRegex(data["baseline"]["claude_code"], r"^\d+\.\d+\.\d+$")

    def test_skill_follows_the_authoring_limits(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        description = next(l for l in text.split("---")[1].splitlines() if l.startswith("description: "))
        self.assertLessEqual(len(description) - len("description: "), 1024)
        self.assertLess(text.count("\n"), 500)


if __name__ == "__main__":
    unittest.main()
