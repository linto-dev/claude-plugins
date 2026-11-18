#!/usr/bin/env -S python3 -I
"""Claude Code と Claude のモデル・API の変化を、前回見たところから集める（判断はしない）。

  diff      前回の状態と比べ、新しい版の変更履歴と、見ている文書の差分を集める
  validate  最新の Claude Code で claude plugin validate を流す
  save      diff が集めたところまでを「見た」として、状態のブランチに書く

状態は origin の claude/harness-watch-state ブランチ（state.json と、見ている文書の写し pages/）に置く。
main にも PR にも触らない。毎回 clone し直すクラウドの会話でも、前回の続きから見られる。

標準出力は 1 つの JSON（要約）。詳しいものは作業フォルダ（.git/harness-watch/。コミットされない）に書く。
終了コードは 0 成功／1 失敗・確かめた結果が合わない（error か results に理由）／2 使い方の誤り。
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CONTRACTS = HERE.parent / "contracts.json"
STATE_BRANCH = "claude/harness-watch-state"
STATE_REF = "refs/harness-watch/state"
VERSION_HEADING = re.compile(r"^## (\d+\.\d+\.\d+)\s*$")
# 互換を崩しうる項目の目印。判定は Claude がするので、ここでは目印を付けるだけ。変更履歴の項目は動詞で始まる
# （Added・Fixed・Changed・Removed・Improved）ので、Changed と Removed は頭の動詞だけを見る（本文の remove は多すぎる）。
FLAG_WORDS = {
    "removed": re.compile(r"^Removed\b"),
    "changed": re.compile(r"^Changed\b"),
    "deprecated": re.compile(r"\bdeprecat", re.I),
    "renamed": re.compile(r"\brenamed\b", re.I),
    "breaking": re.compile(r"\bbreaking change", re.I),
    "requires": re.compile(r"\bnow requires?\b", re.I),
}


class Failure(Exception):
    pass


def run(cmd: list[str], cwd: Path | None = None, input: str | None = None, timeout: int = 120,
        check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(cmd, cwd=cwd, input=input, capture_output=True, text=True, encoding="utf-8",
                              timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise Failure(f"{' '.join(cmd[:4])} が {timeout} 秒で終わりませんでした")
    if check and proc.returncode != 0:
        raise Failure(f"{' '.join(cmd[:4])} が失敗しました（{proc.returncode}）: {(proc.stderr or proc.stdout).strip()[-500:]}")
    return proc


def fetch(url: str) -> str:
    """curl で読む（クラウドの会話のプロキシの設定をそのまま使う。試験では file:// を読む）。"""
    proc = run(["curl", "-fsSL", "--max-time", "60", "--retry", "2", "-A", "harness-watch", url], check=False, timeout=240)
    if proc.returncode != 0:
        raise Failure(f"{url} を読めませんでした（curl {proc.returncode}）: {proc.stderr.strip()[-300:]}")
    return proc.stdout


def vkey(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in version.split("."))


def parse_changelog(text: str) -> dict[str, list[str]]:
    """「## 2.1.327」の節ごとの項目（「- 」の行。続きの行はつなぐ）。"""
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        heading = VERSION_HEADING.match(line)
        if heading:
            current = sections.setdefault(heading.group(1), [])
        elif line.startswith("#"):
            current = None
        elif current is None or not line.strip():
            continue
        elif line.startswith("- "):
            current.append(line[2:].strip())
        elif line.startswith(" ") and current:
            current[-1] += " " + line.strip()
    return sections


def contract_hits(text: str, contracts: list[dict]) -> list[str]:
    """項目に当たる約束。keywords の要素は語（含めば当たる）か、語の並び（すべてを含めば当たる）。"""
    low = text.lower()

    def hit(keyword: str | list[str]) -> bool:
        words = [keyword] if isinstance(keyword, str) else keyword
        return all(w.lower() in low for w in words)

    return [c["id"] for c in contracts if any(hit(k) for k in c.get("keywords", []))]


def flags_of(text: str) -> list[str]:
    return [name for name, pattern in FLAG_WORDS.items() if pattern.search(text)]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_contracts(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("baseline", "sources", "pages", "contracts"):
        if key not in data:
            raise Failure(f"{path} に「{key}」がありません")
    return data


# ---------------------------------------------------------------- git


def repo_root() -> Path:
    return Path(run(["git", "rev-parse", "--show-toplevel"]).stdout.strip())


def work_dir(root: Path) -> Path:
    path = Path(run(["git", "rev-parse", "--git-path", "harness-watch"], cwd=root).stdout.strip())
    return path if path.is_absolute() else root / path


def github_repo(root: Path) -> str | None:
    """origin の owner/name。クラウドの会話では origin がプロキシの URL になるので、末尾の 2 つから取る。"""
    url = run(["git", "remote", "get-url", "origin"], cwd=root, check=False).stdout.strip()
    match = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url)
    return f"{match.group(1)}/{match.group(2)}" if match else None


def fetch_state(root: Path) -> str | None:
    """origin の状態のブランチを STATE_REF に取ってくる。まだ無ければ None。"""
    heads = run(["git", "ls-remote", "--heads", "origin", STATE_BRANCH], cwd=root, timeout=120).stdout.strip()
    if not heads:
        run(["git", "update-ref", "-d", STATE_REF], cwd=root, check=False)
        return None
    run(["git", "fetch", "--quiet", "--no-tags", "origin", f"+refs/heads/{STATE_BRANCH}:{STATE_REF}"], cwd=root, timeout=300)
    return run(["git", "rev-parse", STATE_REF], cwd=root).stdout.strip()


def read_state_file(root: Path, path: str) -> str | None:
    proc = run(["git", "show", f"{STATE_REF}:{path}"], cwd=root, check=False)
    return proc.stdout if proc.returncode == 0 else None


def identity_env(root: Path) -> dict:
    """commit-tree に要る名前とメール。設定に無いとき（CI など）だけ補う。"""
    env = dict(os.environ)
    if not run(["git", "config", "user.email"], cwd=root, check=False).stdout.strip():
        for kind in ("AUTHOR", "COMMITTER"):
            env.setdefault(f"GIT_{kind}_NAME", "harness-watch")
            env.setdefault(f"GIT_{kind}_EMAIL", "harness-watch@users.noreply.github.com")
    return env


# ---------------------------------------------------------------- サブコマンド


def cmd_diff(args) -> dict:
    root = repo_root()
    data = load_contracts(Path(args.contracts))
    contracts = data["contracts"]
    state_commit = fetch_state(root)
    state = json.loads(read_state_file(root, "state.json") or "null") if state_commit else None
    seen = state["claude_code"]["seen"] if state else data["baseline"]["claude_code"]

    tags = json.loads(fetch(data["sources"]["dist_tags"]))
    changelog = parse_changelog(fetch(data["sources"]["changelog"]))
    new_versions = sorted((v for v in changelog if vkey(v) > vkey(seen)), key=vkey)

    work = work_dir(root)
    shutil.rmtree(work, ignore_errors=True)
    (work / "new" / "pages").mkdir(parents=True)
    (work / "diffs").mkdir()

    entries = [{"version": v, "text": text, "contracts": contract_hits(text, contracts), "flags": flags_of(text)}
               for v in reversed(new_versions) for text in changelog[v]]
    lines = []
    for v in reversed(new_versions):
        lines.append(f"## {v}\n")
        for e in (e for e in entries if e["version"] == v):
            marks = " ".join(f"[{m}]" for m in e["contracts"] + e["flags"])
            lines.append(f"- {e['text']}{'  ' + marks if marks else ''}\n")
        lines.append("\n")
    (work / "changelog.md").write_text("".join(lines), encoding="utf-8")

    changed, added, failed, hashes = [], [], [], {}
    for page, url in data["pages"].items():
        old = read_state_file(root, f"pages/{page}.md") if state_commit else None
        try:
            text = fetch(url)
        except Failure as e:
            failed.append({"page": page, "url": url, "error": str(e)})
            text = old  # 読めなかったページは前の写しのまま残す（次の回にもう一度比べる）
            if text is None:
                continue
        (work / "new" / "pages" / f"{page}.md").write_text(text, encoding="utf-8")
        hashes[page] = sha(text)
        if old is None:
            added.append(page)
        elif old != text:
            diff = "".join(difflib.unified_diff(old.splitlines(True), text.splitlines(True),
                                                f"前回/{page}.md", f"今回/{page}.md", n=3))
            path = work / "diffs" / f"{page}.diff"
            path.write_text(diff, encoding="utf-8")
            body = diff.splitlines()[2:]
            changed.append({"page": page, "url": url, "diff": str(path),
                            "added_lines": sum(1 for l in body if l.startswith("+")),
                            "removed_lines": sum(1 for l in body if l.startswith("-")),
                            "contracts": [c["id"] for c in contracts if page in c.get("pages", [])]})

    new_state = {"claude_code": {"seen": new_versions[-1] if new_versions else seen,
                                 "latest_tag": tags.get("latest"), "stable_tag": tags.get("stable")},
                 "pages": hashes}
    (work / "new" / "state.json").write_text(json.dumps(new_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    old_state = {"claude_code": {k: (state or {}).get("claude_code", {}).get(k) for k in ("seen", "latest_tag", "stable_tag")},
                 "pages": (state or {}).get("pages", {})}
    out = {
        "ok": True,
        "first_run": state is None,
        "nothing_new": not new_versions and not changed,
        "save_needed": new_state != old_state,
        "repo": github_repo(root),
        "claude_code": {"seen": seen, "latest": tags.get("latest"), "stable": tags.get("stable"),
                        "new_versions": new_versions, "entries": len(entries),
                        "entries_with_contracts": sum(1 for e in entries if e["contracts"]),
                        "entries_flagged": sum(1 for e in entries if e["flags"])},
        "pages": {"changed": changed, "added": added, "failed": failed,
                  "unchanged": len(data["pages"]) - len(changed) - len(added) - len(failed)},
        "files": {"changelog": str(work / "changelog.md"), "details": str(work / "diff.json")},
    }
    (work / "diff.json").write_text(json.dumps({**out, "changelog": entries}, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
    return out


def cmd_save(args) -> dict:
    root = repo_root()
    new = work_dir(root) / "new"
    if not (new / "state.json").exists():
        raise Failure("先に diff を流してください（作業フォルダに今回の状態がありません）")

    def blob(path: Path) -> str:
        return run(["git", "hash-object", "-w", str(path)], cwd=root).stdout.strip()

    pages = "".join(f"100644 blob {blob(p)}\t{p.name}\n" for p in sorted((new / "pages").glob("*.md")))
    pages_tree = run(["git", "mktree"], cwd=root, input=pages).stdout.strip()
    tree = run(["git", "mktree"], cwd=root,
               input=f"100644 blob {blob(new / 'state.json')}\tstate.json\n040000 tree {pages_tree}\tpages\n").stdout.strip()
    parent = fetch_state(root)
    if parent and run(["git", "rev-parse", f"{parent}^{{tree}}"], cwd=root).stdout.strip() == tree:
        return {"ok": True, "saved": False, "reason": "前回の状態と同じ"}
    seen = json.loads((new / "state.json").read_text(encoding="utf-8"))["claude_code"]["seen"]
    message = f"chore: 見たところを Claude Code {seen} まで進める"
    commit = run(["git", "commit-tree", tree, "-m", message] + (["-p", parent] if parent else []),
                 cwd=root, env=identity_env(root)).stdout.strip()
    run(["git", "push", "--quiet", "origin", f"{commit}:refs/heads/{STATE_BRANCH}"], cwd=root, timeout=300)
    run(["git", "update-ref", STATE_REF, commit], cwd=root)
    return {"ok": True, "saved": True, "branch": STATE_BRANCH, "commit": commit[:12], "seen": seen}


def cmd_validate(args) -> dict:
    root = repo_root()
    data = load_contracts(Path(args.contracts))
    version = args.version or json.loads(fetch(data["sources"]["dist_tags"]))["latest"]
    market = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    targets = ["."] + [p["source"] for p in market.get("plugins", []) if isinstance(p.get("source"), str)]
    results = []
    for target in targets:
        proc = run(["npx", "-y", f"@anthropic-ai/claude-code@{version}", "plugin", "validate", target],
                   cwd=root, check=False, timeout=600)
        output = (proc.stdout + proc.stderr).strip()
        results.append({"target": target, "passed": proc.returncode == 0, "tail": output[-1500:]})
    return {"ok": all(r["passed"] for r in results), "version": version, "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--contracts", default=str(DEFAULT_CONTRACTS), help="頼っている約束の一覧（既定はスキルの contracts.json）")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("diff", help="前回見たところからの変更履歴と文書の差分を集める")
    sub.add_parser("save", help="diff が集めたところまでを、状態のブランチに書く")
    validate = sub.add_parser("validate", help="最新の Claude Code で claude plugin validate を流す")
    validate.add_argument("--version", help="確かめる Claude Code の版（既定は npm の latest）")
    args = parser.parse_args()
    try:
        out = {"diff": cmd_diff, "save": cmd_save, "validate": cmd_validate}[args.command](args)
    except Failure as e:
        out = {"ok": False, "error": str(e)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
