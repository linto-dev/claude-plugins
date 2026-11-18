"""checking-shipstack の収集のスクリプトと、クラウドの会話の push の決まりのフックの試験。

R2 の代わりに、S3 互換の API の一部（一覧、読む、書く）を手元で真似るサーバーを毎回立てる。変更履歴・npm の札・
文書は file:// で読む。ネットワークには出ない。リポジトリのルートで流す:

  python3 -I -B -m unittest discover -s .claude/skills/checking-shipstack/tests -v
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
ROOT = SKILL.parent.parent.parent
COLLECT = SKILL / "scripts" / "collect.py"
GUARD = ROOT / ".claude" / "hooks" / "cloud-push-guard.py"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
       "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
for key in ("CLAUDE_CODE_REMOTE", "SHIPSTACK_CHECK_R2_ENDPOINT", "SHIPSTACK_CHECK_R2_ACCESS_KEY_ID",
            "SHIPSTACK_CHECK_R2_SECRET_ACCESS_KEY"):
    ENV.pop(key, None)

CHANGELOG = """# Changelog

## 1.0.2

- Added `--bar` to the CLI
- Fixed a crash when
  the transcript was empty

## 1.0.1

- Initial release
"""


def load_collect():
    loader = importlib.machinery.SourceFileLoader("collect", str(COLLECT))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("collect", loader))
    loader.exec_module(module)
    return module


class FakeR2(ThreadingHTTPServer):
    """S3 互換の API のうち、ListObjectsV2（delimiter つき）・GetObject・PutObject だけを真似る。署名の形と、
    本文のハッシュが x-amz-content-sha256 と合うことも確かめる。"""

    def __init__(self):
        super().__init__(("127.0.0.1", 0), Handler)
        self.objects: dict[str, bytes] = {}
        self.bad_requests: list[str] = []


class Handler(BaseHTTPRequestHandler):
    server: FakeR2

    def log_message(self, *args):
        pass

    def check_signature(self, body: bytes) -> bool:
        auth = self.headers.get("Authorization", "")
        ok = (auth.startswith("AWS4-HMAC-SHA256 Credential=test-key/") and "/auto/s3/aws4_request" in auth
              and self.headers.get("x-amz-content-sha256") == hashlib.sha256(body).hexdigest()
              and self.headers.get("x-amz-date"))
        if not ok:
            self.server.bad_requests.append(f"{self.command} {self.path}")
            self.send_response(403)
            self.end_headers()
        return bool(ok)

    def split(self) -> tuple[str, str, dict]:
        parts = urllib.parse.urlsplit(self.path)
        bucket, _, key = parts.path.lstrip("/").partition("/")
        return bucket, urllib.parse.unquote(key), dict(urllib.parse.parse_qsl(parts.query))

    def do_GET(self):
        if not self.check_signature(b""):
            return
        bucket, key, query = self.split()
        if not key and query.get("list-type") == "2":
            prefix, delimiter = query.get("prefix", ""), query.get("delimiter", "")
            common = sorted({prefix + k[len(prefix):].split(delimiter, 1)[0] + delimiter
                             for k in self.server.objects if k.startswith(prefix) and delimiter in k[len(prefix):]})
            body = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
                    "<ListBucketResult xmlns=\"http://s3.amazonaws.com/doc/2006-03-01/\">"
                    f"<Name>{bucket}</Name><IsTruncated>false</IsTruncated>"
                    + "".join(f"<CommonPrefixes><Prefix>{escape(p)}</Prefix></CommonPrefixes>" for p in common)
                    + "</ListBucketResult>").encode()
            self.send_response(200)
        elif key in self.server.objects:
            body = self.server.objects[key]
            self.send_response(200)
        else:
            body = b"<Error><Code>NoSuchKey</Code></Error>"
            self.send_response(404)
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if not self.check_signature(body):
            return
        _, key, _ = self.split()
        self.server.objects[key] = body
        self.send_response(200)
        self.end_headers()


class SigV4Test(unittest.TestCase):
    def test_matches_the_aws_get_object_example(self):
        """AWS の文書の「Example: GET Object」と同じ署名になる。"""
        headers = load_collect().sigv4_headers(
            "GET", "https://examplebucket.s3.amazonaws.com/test.txt", "AKIAIOSFODNN7EXAMPLE",
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", hashlib.sha256(b"").hexdigest(),
            dt.datetime(2013, 5, 24, tzinfo=dt.timezone.utc), region="us-east-1", extra={"Range": "bytes=0-9"})
        self.assertEqual(headers["authorization"],
                         "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request,"
                         "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date,"
                         "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])
        self.repo = self.tmp / "repo"
        subprocess.run(["git", "init", "--quiet", str(self.repo)], env=ENV, check=True)
        subprocess.run(["git", "remote", "add", "origin", "git@github.com:linto-dev/claude-plugins.git"], cwd=self.repo,
                       env=ENV, check=True)
        fx = self.tmp / "fixtures"
        fx.mkdir()
        (fx / "CHANGELOG.md").write_text(CHANGELOG)
        (fx / "dist-tags.json").write_text(json.dumps({"latest": "1.0.2", "stable": "1.0.1"}))
        (fx / "a.md").write_text("# A\n\n`--foo` takes a value.\n")
        (fx / "b.md").write_text("# B\n")
        self.fx = fx
        self.contracts = self.tmp / "contracts.json"
        self.write_contracts(baseline="1.0.1")
        self.r2 = FakeR2()
        threading.Thread(target=self.r2.serve_forever, daemon=True).start()
        self.addCleanup(self.r2.server_close)
        self.addCleanup(self.r2.shutdown)
        self.env = {**ENV, "SHIPSTACK_CHECK_R2_ENDPOINT": f"http://127.0.0.1:{self.r2.server_address[1]}",
                    "SHIPSTACK_CHECK_R2_ACCESS_KEY_ID": "test-key", "SHIPSTACK_CHECK_R2_SECRET_ACCESS_KEY": "test-secret"}

    def tearDown(self):
        self.assertEqual(self.r2.bad_requests, [], "署名か本文のハッシュが合わない要求があった")

    def write_contracts(self, baseline: str) -> None:
        self.contracts.write_text(json.dumps({
            "baseline": {"claude_code": baseline},
            "sources": {"changelog": (self.fx / "CHANGELOG.md").as_uri(), "dist_tags": (self.fx / "dist-tags.json").as_uri()},
            "store": {"bucket": "shipstack-checks", "prefix": "runs/"},
            "pages": {"page-a": (self.fx / "a.md").as_uri(), "page-b": (self.fx / "b.md").as_uri()},
            "contracts": [{"id": "flag-foo", "claim": "--foo を使う", "documented": True, "pages": ["page-a"],
                           "keywords": ["--foo"], "used_in": [], "verify": "", "verified": "1.0.1"}],
        }))

    def collect(self, *args: str, env: dict | None = None) -> tuple[int, dict]:
        proc = subprocess.run([sys.executable, "-I", str(COLLECT), "--contracts", str(self.contracts), *args],
                              cwd=self.repo, env=env or self.env, capture_output=True, text=True)
        return proc.returncode, json.loads(proc.stdout)

    def runs(self) -> list[str]:
        return sorted({k.split("/")[1] for k in self.r2.objects})

    def test_first_run_reads_versions_after_the_baseline_and_snapshots_the_pages(self):
        code, out = self.collect("diff")
        self.assertEqual(code, 0, out)
        self.assertTrue(out["first_run"])
        self.assertEqual(out["store"], {"run": None, "age_days": None})
        self.assertEqual(out["claude_code"]["new_versions"], ["1.0.2"])
        self.assertEqual(sorted(out["pages"]["added"]), ["page-a", "page-b"])
        self.assertTrue(out["save_needed"])
        self.assertEqual(out["repo"], "linto-dev/claude-plugins")
        changelog = Path(out["files"]["changelog"]).read_text()
        self.assertIn("- Fixed a crash when the transcript was empty", changelog)  # 続きの行はつなぐ
        self.assertNotIn("Initial release", changelog)  # baseline の版は見たもの

    def test_save_writes_a_dated_snapshot_with_the_state_last(self):
        self.write_contracts(baseline="1.0.2")
        code, out = self.collect("diff")
        self.assertEqual((out["nothing_new"], out["save_needed"]), (True, True), out)  # 初回は写しだけ取る
        code, saved = self.collect("save")
        self.assertEqual(code, 0, saved)
        [run] = self.runs()
        self.assertRegex(run, r"^\d{8}T\d{6}Z$")
        self.assertEqual(saved["run"], f"shipstack-checks/runs/{run}/")
        self.assertEqual(sorted(self.r2.objects), [f"runs/{run}/pages/page-a.md", f"runs/{run}/pages/page-b.md",
                                                   f"runs/{run}/state.json"])
        self.assertEqual(list(self.r2.objects)[-1], f"runs/{run}/state.json")  # 状態は最後に書く
        self.assertEqual(json.loads(self.r2.objects[f"runs/{run}/state.json"])["claude_code"]["seen"], "1.0.2")
        code, out = self.collect("diff")
        self.assertEqual((out["first_run"], out["nothing_new"], out["save_needed"]), (False, True, False), out)
        self.assertEqual(out["store"]["run"], run)

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
        self.assertEqual((details["changelog"][0]["contracts"], details["changelog"][0]["flags"]), (["flag-foo"], ["removed"]))
        [change] = out["pages"]["changed"]
        self.assertEqual((change["page"], change["added_lines"], change["removed_lines"], change["contracts"]),
                         ("page-a", 1, 1, ["flag-foo"]))
        self.assertIn("+`--foo` was removed.", Path(change["diff"]).read_text())

    def test_an_interrupted_snapshot_is_skipped(self):
        self.write_contracts(baseline="1.0.2")
        self.collect("diff")
        self.collect("save")
        [run] = self.runs()
        self.r2.objects["runs/29991231T000000Z/pages/page-a.md"] = b"half written"  # state.json の無い新しい写し
        code, out = self.collect("diff")
        self.assertEqual(out["store"]["run"], run)
        self.assertEqual(out["pages"]["changed"], [])

    def test_an_old_snapshot_is_written_again_before_it_expires(self):
        self.write_contracts(baseline="1.0.2")
        self.collect("diff")
        self.collect("save")
        [run] = self.runs()
        old = "20200101T000000Z"
        for key in list(self.r2.objects):
            self.r2.objects[key.replace(run, old)] = self.r2.objects.pop(key)
        code, out = self.collect("diff")
        self.assertEqual((out["nothing_new"], out["save_needed"]), (True, True), out)
        self.assertGreaterEqual(out["store"]["age_days"], 30)

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

    def test_an_unreadable_changelog_fails_without_writing(self):
        (self.fx / "CHANGELOG.md").unlink()
        code, out = self.collect("diff")
        self.assertEqual(code, 1)
        self.assertIn("CHANGELOG.md を読めませんでした", out["error"])
        self.assertEqual(self.r2.objects, {})

    def test_without_the_keys_diff_runs_as_a_first_run_and_save_refuses(self):
        code, out = self.collect("diff", env=ENV)
        self.assertEqual(code, 0, out)
        self.assertTrue(out["first_run"])
        self.assertIn("SHIPSTACK_CHECK_R2_ENDPOINT", out["store"]["unavailable"])
        code, out = self.collect("save", env=ENV)
        self.assertEqual(code, 1)
        self.assertIn("SHIPSTACK_CHECK_R2_SECRET_ACCESS_KEY", out["error"])

    def test_keyword_groups_need_every_word_and_flags_read_the_leading_verb(self):
        module = load_collect()
        contracts = [{"id": "resume-hooks", "keywords": [["resume", "hook"]]}, {"id": "settings", "keywords": ["--settings"]}]
        self.assertEqual(module.contract_hits("Fixed skill hooks not running after --resume", contracts), ["resume-hooks"])
        self.assertEqual(module.contract_hits("Fixed a crash on resume", contracts), [])  # 片方の語だけでは当たらない
        self.assertEqual(module.contract_hits("Added `--settings` merging", contracts), ["settings"])
        self.assertEqual(module.flags_of("Removed the `--foo` flag"), ["removed"])
        self.assertEqual(module.flags_of("Fixed removing a file twice"), [])  # 本文の remove は目印にしない
        self.assertEqual(module.flags_of("Changed X; the old name is deprecated"), ["changed", "deprecated"])

    def test_repo_is_read_from_a_proxied_origin(self):
        module = load_collect()
        subprocess.run(["git", "remote", "set-url", "origin", "http://local_proxy@127.0.0.1:41337/git/linto-dev/claude-plugins"],
                       cwd=self.repo, env=ENV, check=True)
        self.assertEqual(module.github_repo(self.repo), "linto-dev/claude-plugins")


class CloudPushGuardTest(unittest.TestCase):
    def guard(self, command: str, remote: bool = True) -> int:
        env = {**ENV, "CLAUDE_CODE_REMOTE": "true"} if remote else ENV
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        proc = subprocess.run([sys.executable, "-I", str(GUARD)], input=payload, env=env, capture_output=True, text=True)
        self.last_stderr = proc.stderr
        return proc.returncode

    def test_allowed_in_the_cloud(self):
        for command in ("git push -u origin claude/shipstack-check-20261119",
                        "git push origin HEAD:claude/shipstack-check-20261119",
                        "git push origin HEAD:refs/heads/claude/shipstack-check-20261119 2>&1",
                        "git -C /tmp/x push origin claude/a",
                        "git status && git log -1",
                        "gh api repos/o/r/pulls -X POST -f base=main -f head=claude/a -F draft=true",
                        "gh api 'repos/o/r/pulls?state=open' --jq '.[].title'",
                        "python3 -I .claude/skills/checking-shipstack/scripts/collect.py save",
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
            self.assertIn("[shipstack の点検の決まり]", self.last_stderr)

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
        self.assertEqual(data["store"], {"bucket": "shipstack-checks", "prefix": "runs/"})
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
        frontmatter = text.split("---")[1]
        self.assertIn("\nname: checking-shipstack\n", frontmatter)
        description = next(l for l in frontmatter.splitlines() if l.startswith("description: "))
        self.assertLessEqual(len(description) - len("description: "), 1024)
        self.assertLess(text.count("\n"), 500)


if __name__ == "__main__":
    unittest.main()
