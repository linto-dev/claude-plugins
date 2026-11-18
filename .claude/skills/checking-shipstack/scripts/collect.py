#!/usr/bin/env -S python3 -I
"""Claude Code と Claude のモデル・API の変化を、前回見たところから集める（判断はしない）。

  diff      前回の写しと比べ、新しい版の変更履歴と、見ている文書の差分を集める
  validate  最新の Claude Code で claude plugin validate を流す
  save      diff が集めたところまでを「見た」として、R2 に新しい写しを書く

状態は Cloudflare R2 のバケット（contracts.json の store）に、日時ごとの写しとして置く:
  runs/<UTC の日時>/pages/<ページ>.md   見ている文書の写し
  runs/<UTC の日時>/state.json          見た版と、ページごとのハッシュ（最後に書く。これがある写しだけを使う）
上書きはしない（R2 にはバージョニングが無い）。90 日を過ぎた写しはバケットのライフサイクルの規則が消すので、
変化が無くても 30 日ごとに写しを書き直す。

R2 には S3 互換の API で、このバケットだけに絞ったトークン（Object Read & Write）で読み書きする。署名（SigV4）は
ここで作り、送るのは curl に任せる（クラウドの会話のプロキシの設定をそのまま使う）。鍵は環境変数から読む:
  SHIPSTACK_CHECK_R2_ENDPOINT           https://<アカウントの ID>.r2.cloudflarestorage.com
  SHIPSTACK_CHECK_R2_ACCESS_KEY_ID
  SHIPSTACK_CHECK_R2_SECRET_ACCESS_KEY
無ければ、diff は初回として動き（前回の写しと比べない）、save は止まる。

標準出力は 1 つの JSON（要約）。詳しいものは作業フォルダ（.git/shipstack-check/。コミットされない）に書く。
終了コードは 0 成功／1 失敗・確かめた結果が合わない（error か results に理由）／2 使い方の誤り。
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CONTRACTS = HERE.parent / "contracts.json"
ENV_PREFIX = "SHIPSTACK_CHECK_R2_"
STORE_ENV = ("ENDPOINT", "ACCESS_KEY_ID", "SECRET_ACCESS_KEY")
RUN_NAME = re.compile(r"^\d{8}T\d{6}Z$")
# 90 日で消える写しが、変化の無い日が続いても消えないように書き直す間隔。
REFRESH_DAYS = 30
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
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
        check: bool = True) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(cmd, cwd=cwd, input=input, capture_output=True, text=True, encoding="utf-8",
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Failure(f"{' '.join(cmd[:4])} が {timeout} 秒で終わりませんでした")
    if check and proc.returncode != 0:
        raise Failure(f"{' '.join(cmd[:4])} が失敗しました（{proc.returncode}）: {(proc.stderr or proc.stdout).strip()[-500:]}")
    return proc


def fetch(url: str) -> str:
    """curl で読む（クラウドの会話のプロキシの設定をそのまま使う。試験では file:// を読む）。"""
    proc = run(["curl", "-fsSL", "--max-time", "60", "--retry", "2", "-A", "shipstack-check", url], check=False, timeout=240)
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
    for key in ("baseline", "sources", "store", "pages", "contracts"):
        if key not in data:
            raise Failure(f"{path} に「{key}」がありません")
    return data


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# ---------------------------------------------------------------- R2（S3 互換の API）


def sigv4_headers(method: str, url: str, access_key: str, secret_key: str, payload_hash: str, when: dt.datetime,
                  region: str = "auto", service: str = "s3", extra: dict | None = None) -> dict:
    """AWS Signature Version 4 の署名を付けた見出し。url のパスとクエリは、すでに符号化してあるものとして扱う。"""
    parts = urllib.parse.urlsplit(url)
    amz_date = when.strftime("%Y%m%dT%H%M%SZ")
    headers = {"host": parts.netloc, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date,
               **{k.lower(): v for k, v in (extra or {}).items()}}
    query = sorted(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    canonical_query = "&".join(f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(v, safe='-_.~')}"
                               for k, v in query)
    signed = ";".join(sorted(headers))
    canonical_headers = "".join(f"{k}:{' '.join(str(headers[k]).split())}\n" for k in sorted(headers))
    canonical_request = "\n".join([method, parts.path or "/", canonical_query, canonical_headers, signed, payload_hash])
    scope = f"{amz_date[:8]}/{region}/{service}/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical_request.encode()).hexdigest()])
    key = ("AWS4" + secret_key).encode()
    for part in (amz_date[:8], region, service, "aws4_request"):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    headers["authorization"] = (f"AWS4-HMAC-SHA256 Credential={access_key}/{scope},SignedHeaders={signed},"
                                f"Signature={signature}")
    return headers


class Store:
    """R2 のバケットの中の、日時ごとの写し。"""

    def __init__(self, endpoint: str, bucket: str, prefix: str, access_key: str, secret_key: str):
        self.endpoint = endpoint.rstrip("/")
        self.bucket = bucket
        self.prefix = prefix
        self.access_key = access_key
        self.secret_key = secret_key

    @classmethod
    def from_env(cls, store: dict) -> tuple[Store | None, list[str]]:
        missing = [ENV_PREFIX + name for name in STORE_ENV if not os.environ.get(ENV_PREFIX + name)]
        if missing:
            return None, missing
        env = {name: os.environ[ENV_PREFIX + name] for name in STORE_ENV}
        return cls(env["ENDPOINT"], store["bucket"], store["prefix"], env["ACCESS_KEY_ID"], env["SECRET_ACCESS_KEY"]), []

    def url(self, key: str = "", query: dict | None = None) -> str:
        path = f"/{self.bucket}" + (f"/{urllib.parse.quote(key, safe='/-_.~')}" if key else "")
        # 署名の正規化と同じ符号化にする（空白は %20、/ は %2F）。
        encoded = urllib.parse.urlencode(sorted((query or {}).items()), quote_via=urllib.parse.quote, safe="-_.~")
        return self.endpoint + path + (f"?{encoded}" if encoded else "")

    def request(self, method: str, url: str, body: bytes = b"", content_type: str | None = None) -> tuple[int, bytes]:
        headers = sigv4_headers(method, url, self.access_key, self.secret_key, hashlib.sha256(body).hexdigest(), now_utc())
        with tempfile.TemporaryDirectory() as tmp:
            out, data = Path(tmp) / "out", Path(tmp) / "body"
            cmd = ["curl", "-sS", "--max-time", "120", "-X", method, "-o", str(out), "-w", "%{http_code}", url]
            for name, value in headers.items():
                if name != "host":
                    cmd += ["-H", f"{name}: {value}"]
            if method == "PUT":
                data.write_bytes(body)
                cmd += ["-H", f"content-type: {content_type or 'application/octet-stream'}", "--data-binary", f"@{data}"]
            proc = run(cmd, check=False, timeout=300)
            if proc.returncode != 0:
                raise Failure(f"R2 に届きませんでした（{method} {url.split('?')[0]}、curl {proc.returncode}）: {proc.stderr.strip()[-300:]}")
            return int(proc.stdout.strip() or 0), out.read_bytes() if out.exists() else b""

    def get(self, key: str) -> str | None:
        status, body = self.request("GET", self.url(key))
        if status == 404:
            return None
        if status != 200:
            raise Failure(f"R2 の {key} を読めませんでした（HTTP {status}）: {body.decode(errors='replace')[-300:]}")
        return body.decode("utf-8")

    def put(self, key: str, text: str, content_type: str) -> None:
        status, body = self.request("PUT", self.url(key), text.encode("utf-8"), content_type)
        if status != 200:
            raise Failure(f"R2 に {key} を書けませんでした（HTTP {status}）: {body.decode(errors='replace')[-300:]}")

    def runs(self) -> list[str]:
        """写しの日時（runs/<日時>/）を古い順に。"""
        names, token = [], None
        while True:
            query = {"list-type": "2", "prefix": self.prefix, "delimiter": "/"}
            if token:
                query["continuation-token"] = token
            status, body = self.request("GET", self.url(query=query))
            if status != 200:
                raise Failure(f"R2 の写しの一覧を読めませんでした（HTTP {status}）: {body.decode(errors='replace')[-300:]}")
            root = ET.fromstring(body)
            for element in root.iter():
                if element.tag.endswith("CommonPrefixes"):
                    prefix = next((c.text for c in element if c.tag.endswith("Prefix")), "") or ""
                    name = prefix[len(self.prefix):].strip("/")
                    if RUN_NAME.match(name):
                        names.append(name)
            truncated = next((e.text for e in root if e.tag.endswith("IsTruncated")), "false")
            token = next((e.text for e in root if e.tag.endswith("NextContinuationToken")), None)
            if truncated != "true" or not token:
                return sorted(names)

    def latest(self) -> tuple[str, dict] | None:
        """state.json まで書き終えた、いちばん新しい写し（途中で切れた写しは飛ばす）。"""
        for name in reversed(self.runs()):
            text = self.get(f"{self.prefix}{name}/state.json")
            if text is not None:
                return name, json.loads(text)
        return None


# ---------------------------------------------------------------- git


def repo_root() -> Path:
    return Path(run(["git", "rev-parse", "--show-toplevel"]).stdout.strip())


def work_dir(root: Path) -> Path:
    path = Path(run(["git", "rev-parse", "--git-path", "shipstack-check"], cwd=root).stdout.strip())
    return path if path.is_absolute() else root / path


def github_repo(root: Path) -> str | None:
    """origin の owner/name。クラウドの会話では origin がプロキシの URL になるので、末尾の 2 つから取る。"""
    url = run(["git", "remote", "get-url", "origin"], cwd=root, check=False).stdout.strip()
    match = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url)
    return f"{match.group(1)}/{match.group(2)}" if match else None


# ---------------------------------------------------------------- サブコマンド


def cmd_diff(args) -> dict:
    root = repo_root()
    data = load_contracts(Path(args.contracts))
    contracts = data["contracts"]
    store, missing = Store.from_env(data["store"])
    latest = store.latest() if store else None
    run_name, state = latest if latest else (None, None)
    seen = state["claude_code"]["seen"] if state else data["baseline"]["claude_code"]
    age_days = None
    if run_name:
        age_days = (now_utc() - dt.datetime.strptime(run_name, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)).days

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
        old = store.get(f"{store.prefix}{run_name}/pages/{page}.md") if run_name and page in state.get("pages", {}) else None
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
    out = {
        "ok": True,
        "first_run": state is None,
        "nothing_new": not new_versions and not changed,
        "save_needed": state != new_state or (age_days is not None and age_days >= REFRESH_DAYS),
        "store": {"run": run_name, "age_days": age_days} if store else {"unavailable": f"環境変数がありません: {', '.join(missing)}"},
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
    data = load_contracts(Path(args.contracts))
    store, missing = Store.from_env(data["store"])
    if not store:
        raise Failure(f"R2 に書けません。環境変数がありません: {', '.join(missing)}")
    new = work_dir(root) / "new"
    if not (new / "state.json").exists():
        raise Failure("先に diff を流してください（作業フォルダに今回の状態がありません）")
    name = now_utc().strftime("%Y%m%dT%H%M%SZ")
    pages = sorted((new / "pages").glob("*.md"))
    for path in pages:
        store.put(f"{store.prefix}{name}/pages/{path.name}", path.read_text(encoding="utf-8"), "text/markdown; charset=utf-8")
    # state.json を最後に書く。これがある写しだけを読むので、途中で切れた写しは使われない。
    state = (new / "state.json").read_text(encoding="utf-8")
    store.put(f"{store.prefix}{name}/state.json", state, "application/json")
    return {"ok": True, "saved": True, "run": f"{store.bucket}/{store.prefix}{name}/", "pages": len(pages),
            "seen": json.loads(state)["claude_code"]["seen"]}


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
    sub.add_parser("save", help="diff が集めたところまでを、R2 に新しい写しとして書く")
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
