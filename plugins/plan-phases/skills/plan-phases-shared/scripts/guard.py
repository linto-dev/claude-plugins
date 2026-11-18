#!/usr/bin/env -S python3 -I
"""実装計画のスキルの「守ること」を、文章の指示ではなく仕組みで守る PreToolUse フック。

各スキルの frontmatter の hooks から、役目（下の ROLES）を引数にして呼ばれる。標準入力に PreToolUse の
JSON が来る。決まりに反する操作なら、理由を標準エラーに書いて終了コード 2 で止める（Claude Code がツールの
呼び出しを取り消し、理由を Claude に返す）。反しなければ何も出さずに 0 で終わり、ふつうの許可の流れに任せる。

これは間違いを止めるためのもので、わざと回り込む相手を防ぐものではない。コマンドは shlex で読み、
引用符の中（コミットメッセージなど）とヒアドキュメントの本文は見ない。

使い方: guard.py <implement|decisions|finalize|merge-main>
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROLES = {"implement", "decisions", "finalize", "merge-main"}
# 機能の PR を作ってよい役目（最初のフェーズを実装する）。
CAN_CREATE_PR = {"implement"}
# 機能の PR のタイトルから WIP: を外してよい役目（仕上げだけ）。
CAN_FINISH_PR = {"finalize"}
# shlex は続いた記号を 1 つのトークンにする（「);」など）。; & | ( ) だけでできたトークンは区切りとみなす。
SEPARATOR = re.compile(r"[;&|()]+")
# shlex が切り出すリダイレクトの記号（>、>>、<、>&、&>、&>>）。
REDIRECT = re.compile(r"[<>]+&?|&>>?")
WRAPPERS = {"command", "builtin", "exec", "nohup", "time", "env", "sudo"}
# パッケージのコマンドを動かす前置き（npx wrangler、pnpm exec wrangler、pnpm dlx wrangler@4 など）。
RUNNERS = {"npx", "pnpx", "pnpm", "yarn", "bunx", "bun"}
WRANGLER = re.compile(r"wrangler(@[\w.^~-]+)?")
# wrangler の、値を取るオプション（positionals で値をサブコマンドと取り違えないため）。
WRANGLER_VALUE_FLAGS = {"--name", "--env", "-e", "--config", "-c", "--cwd", "--profile", "--scopes", "--comment",
                        "--value", "--secret-id", "--page", "--per-page", "--persist-to", "--env-file",
                        "--secrets-file"}


def deny(message: str) -> None:
    print(f"[計画のスキルの決まり] {message}", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------- git の状態


class Repo:
    def __init__(self, cwd: str):
        self.cwd = cwd

    def git(self, *args: str) -> str | None:
        proc = subprocess.run(["git", "-C", self.cwd, *args], capture_output=True, text=True)
        return proc.stdout.strip() if proc.returncode == 0 else None

    def ok(self, *args: str) -> bool:
        return subprocess.run(["git", "-C", self.cwd, *args], capture_output=True).returncode == 0

    def branch(self) -> str | None:
        return self.git("symbolic-ref", "--quiet", "--short", "HEAD")

    def protected(self) -> set[str]:
        names = {"main", "master"}
        ref = self.git("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
        if ref:
            names.add(ref.removeprefix("origin/"))
        return names

    def on_remote(self, rev: str) -> bool:
        """rev がどこかのリモートのブランチから辿れる（push 済み）。"""
        return bool(self.git("branch", "-r", "--contains", rev))

    def commit_of(self, rev: str) -> str | None:
        return self.git("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")


# ---------------------------------------------------------------- コマンドを読む


def strip_heredocs(command: str) -> str:
    """ヒアドキュメントの本文を除く（コミットメッセージの中の文字をコマンドと取り違えないため）。"""
    out: list[str] = []
    pending: list[tuple[str, bool]] = []
    for line in command.split("\n"):
        if pending:
            delimiter, strip_tabs = pending[0]
            if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                pending.pop(0)
            continue
        out.append(line)
        for dash, quoted in re.findall(r"<<(-?)\s*(['\"]?[A-Za-z_][A-Za-z0-9_]*['\"]?)", line):
            pending.append((quoted.strip("'\""), dash == "-"))
    return "\n".join(out)


def segments(command: str) -> list[list[str]] | None:
    """コマンドを ; && || | などで切った、単純なコマンドの並び。読めなければ None。"""
    text = strip_heredocs(command).replace("\\\n", " ")
    # 改行もコマンドの区切り。引用符の中の改行は、トークンの中に入るだけで害はない。
    text = text.replace("\n", " ; ")
    lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    result: list[list[str]] = [[]]
    skip_target = False
    for token in tokens:
        if skip_target:
            skip_target = False
            continue
        if REDIRECT.fullmatch(token):
            # 2>&1・> /dev/null などのリダイレクトは引数ではない。fd の番号と、行き先のトークンも除く。
            if result[-1] and result[-1][-1].isdigit():
                result[-1].pop()
            skip_target = True
            continue
        if SEPARATOR.fullmatch(token):
            result.append([])
        else:
            result[-1].append(token)
    return [s for s in result if s]


def program(argv: list[str]) -> list[str]:
    """環境変数の代入や command・env などの前置きを除いた argv。"""
    i = 0
    while i < len(argv):
        word = argv[i]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", word):
            i += 1
        elif os.path.basename(word) in WRAPPERS:
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                i += 1
        else:
            break
    return argv[i:]


def has(args: list[str], *flags: str) -> bool:
    """長い形（--force、--force=…）と短い形の束（-fu）の両方で探す。"""
    for arg in args:
        if arg == "--":
            break
        for flag in flags:
            if flag.startswith("--"):
                if arg == flag or arg.startswith(flag + "="):
                    return True
            elif re.fullmatch(r"-[A-Za-z]+", arg) and flag[1] in arg[1:]:
                return True
    return False


def positionals(args: list[str], with_value: set[str] = frozenset()) -> list[str]:
    out, skip, after_dashdash = [], False, False
    for arg in args:
        if skip:
            skip = False
            continue
        if after_dashdash:
            out.append(arg)
        elif arg == "--":
            after_dashdash = True
        elif arg.startswith("-"):
            if arg in with_value:
                skip = True
        else:
            out.append(arg)
    return out


# ---------------------------------------------------------------- git


def check_git(args: list[str], role: str, cwd: str) -> None:
    # git -C <dir> などの前置きのオプションを読む。
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            cwd = str(Path(cwd, args[i + 1]))
            i += 2
        elif args[i] in ("-c", "--git-dir", "--work-tree", "--namespace") and i + 1 < len(args):
            i += 2
        else:
            i += 1
    if i >= len(args):
        return
    sub, rest = args[i], args[i + 1:]
    repo = Repo(cwd)

    if sub == "push":
        check_push(rest, role, repo)
    elif sub == "commit":
        branch = repo.branch()
        if branch in repo.protected():
            deny(f"{branch} には直接コミットしません。機能ブランチにコミットします")
        if has(rest, "--amend") and repo.on_remote("HEAD"):
            deny("push 済みのコミットは書き換えません（amend しない）。直すときは新しいコミットを足します")
    elif sub == "rebase":
        if not has(rest, "--abort", "--quit"):
            deny("rebase はしません（push 済みの履歴を書き換えることになる）。main はマージコミットで取り込みます")
    elif sub == "pull":
        deny("ワーカーは git pull しません。手元が origin と違うなら、触らずに止めます（手元を合わせるのは指揮役の plan-phases run）")
    elif sub == "reset":
        check_reset(rest, role, repo)
    elif sub in ("checkout", "switch"):
        creating = has(rest, "-b", "-B", "--orphan") if sub == "checkout" else has(rest, "-c", "-C", "--create", "--force-create", "--orphan")
        if creating:
            deny("ブランチは作りません（機能ブランチは指揮役の plan-phases run が作る）")
    elif sub == "branch":
        check_branch(rest, role)
    elif sub == "tag":
        if has(rest, "-d", "--delete", "-a", "--annotate", "-s", "--sign", "-f", "--force", "-m", "-F"):
            deny("タグは作りも消しもしません")
        if not has(rest, "-l", "--list") and positionals(rest, {"--sort", "--format", "--contains", "--points-at", "--merged", "--no-merged", "-n"}):
            deny("タグは作りません")
    elif sub == "worktree":
        action = rest[0] if rest else ""
        if action in ("remove", "prune", "move", "add", "lock", "unlock", "repair"):
            deny(f"worktree の {action} はしません（フェーズは機能ブランチのチェックアウトで 1 つずつ実装する）")
    elif sub == "merge":
        check_merge(rest, role, repo)
    elif sub == "clean":
        if not has(rest, "-n", "--dry-run") and has(rest, "-f", "--force"):
            deny("git clean で未追跡のファイルを消しません（.env などの Git の管理外のファイルが消える）")
    elif sub in ("filter-branch", "filter-repo", "update-ref", "replace"):
        deny(f"git {sub} で履歴や参照を直接書き換えません")


def check_push(args: list[str], role: str, repo: Repo) -> None:
    if has(args, "-n", "--dry-run"):
        return
    if has(args, "-f", "--force", "--force-with-lease", "--force-if-includes"):
        deny("force push はしません。直すときは新しいコミットを足して push します")
    if has(args, "-d", "--delete", "--mirror", "--all", "--branches", "--tags", "--follow-tags", "--prune"):
        deny("push で、ブランチを消す・すべてのブランチやタグを送ることはしません。機能ブランチだけを push します")
    refspecs = positionals(args, {"-o", "--push-option", "--repo", "--receive-pack", "--exec"})[1:]
    protected = repo.protected()
    branch = repo.branch()
    if not refspecs:
        refspecs = [branch or "HEAD"]
    for spec in refspecs:
        if spec.startswith("+"):
            deny("force push（+ の付いた refspec）はしません")
        src, _, dst = spec.partition(":")
        if _ and not src:
            deny("push でリモートのブランチを消しません")
        dst = dst or src
        dst = dst.removeprefix("refs/heads/")
        if dst == "HEAD":
            dst = branch or "HEAD"
        if dst.startswith("refs/tags/"):
            deny("タグは push しません")
        if dst in protected:
            deny(f"{dst} には push しません（main へのマージは本番へのデプロイ。機能の PR を利用者がマージする）")
        if not repo.ok("rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{dst}"):
            deny(f"origin に無いブランチ（{dst}）は push しません（機能ブランチは指揮役の plan-phases run が作る）")


def check_reset(args: list[str], role: str, repo: Repo) -> None:
    if has(args, "--hard", "--merge", "--keep"):
        deny("git reset --hard（--merge・--keep）はしません。作業中の変更や push 済みの履歴を失う")
    targets = positionals(args)
    target = targets[0] if targets and repo.commit_of(targets[0]) else None
    if target is None:
        return  # 取り消すのは index だけ（git reset、git reset -- <ファイル>）
    head = repo.commit_of("HEAD")
    if repo.commit_of(target) == head:
        return
    # 外すコミット（target..HEAD）に、push 済みのものがあってはいけない。
    dropped = (repo.git("rev-list", f"{target}..HEAD") or "").split()
    if dropped and repo.on_remote(dropped[-1]):
        deny("push 済みのコミットを外す reset はしません。push する前の一時的なコミットをまとめるときだけ reset --soft を使います")


def check_branch(args: list[str], role: str) -> None:
    if has(args, "-m", "-M", "--move", "-c", "-C", "--copy", "-f", "--force"):
        deny("ブランチの名前の変更・複製・強制の上書きはしません")
    if has(args, "-d", "-D", "--delete"):
        deny("ブランチは消しません（機能ブランチの後片付けは、マージの後に人が行う）")
    listing = has(args, "-l", "--list", "-a", "--all", "-r", "--remotes", "-v", "-vv", "--show-current",
                  "--contains", "--no-contains", "--merged", "--no-merged", "--points-at", "--format", "--sort",
                  "-u", "--set-upstream-to", "--unset-upstream", "--edit-description")
    if not listing and positionals(args):
        deny("ブランチは作りません（機能ブランチは指揮役の plan-phases run が作る）")


def check_merge(args: list[str], role: str, repo: Repo) -> None:
    if has(args, "--abort", "--continue", "--quit"):
        return
    sources = positionals(args, {"-m", "-F", "--file", "-s", "--strategy", "-X", "--strategy-option"})
    if role == "merge-main":
        allowed = {f"origin/{name}" for name in repo.protected()}
        if not sources or not all(s in allowed for s in sources):
            deny("取り込むのは origin の既定のブランチ（origin/main など）だけです")
        if has(args, "--squash", "--ff-only"):
            deny("main はマージコミットで取り込みます（--no-ff --no-commit）")
        return
    deny("このスキルは git merge をしません")


# ---------------------------------------------------------------- gh


def option_value(args: list[str], *names: str) -> str | None:
    for i, arg in enumerate(args):
        for name in names:
            if arg == name and i + 1 < len(args):
                return args[i + 1]
            if name.startswith("--") and arg.startswith(name + "="):
                return arg.split("=", 1)[1]
    return None


def check_gh(args: list[str], role: str) -> None:
    group, action = (args + ["", ""])[:2]
    rest = args[2:]
    if group == "pr":
        if action == "merge":
            deny("PR はマージしません（main へのマージは本番へのデプロイ。利用者が GitHub で行う）")
        if action in ("close", "reopen"):
            deny(f"機能の PR を {action} しません")
        if action == "create":
            if role not in CAN_CREATE_PR:
                deny("このスキルは PR を作りません（機能の PR は最初のフェーズが plan-phases pr-create で作る）")
            title = option_value(rest, "-t", "--title") or ""
            if not title.startswith("WIP: "):
                deny("機能の PR は、タイトルの先頭に「WIP: 」を付けて作ります（仕上げるまでマージしない印）")
        if action == "edit":
            if option_value(rest, "-B", "--base") is not None:
                deny("機能の PR の向き先（base）は変えません")
            title = option_value(rest, "-t", "--title")
            if title is not None and not title.startswith("WIP: ") and role not in CAN_FINISH_PR:
                deny("タイトルの WIP: を外せるのは、仕上げ（finalizing-feature-pr）だけです")
    elif group == "api":
        method = (option_value(args, "-X", "--method") or "").upper()
        writes_fields = has(args, "-f", "-F", "--field", "--raw-field", "--input")
        if not method:
            method = "POST" if writes_fields else "GET"
        fields = [args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-f", "-F", "--raw-field", "--field")]
        fields += [a.split("=", 1)[1] for a in args if a.startswith(("--raw-field=", "--field="))]
        if "graphql" in positionals(args[1:], {"-X", "--method", "-f", "-F", "--raw-field", "--field", "-H", "--header", "--input", "-q", "--jq", "-t", "--template", "--hostname", "--cache"}):
            if not any("mutation" in f for f in fields):
                return  # GraphQL の読み取り（query）は POST でも読むだけ
        if method != "GET":
            deny("gh api で書き込む操作（GET 以外、GraphQL の mutation）はしません。PR の作成と本文の更新は決まった gh pr のコマンドで行います")
    elif group == "repo" and action in ("delete", "archive", "rename", "edit", "transfer"):
        deny(f"gh repo {action} はしません")
    elif group == "release" and action not in ("list", "view", "download"):
        deny("リリースは作りも変えもしません")
    elif group == "workflow" and action in ("run", "enable", "disable"):
        deny("ワークフローを手で動かしません（デプロイは main へのマージで GitHub Actions が行う）")
    elif group in ("secret", "variable") and action in ("set", "delete"):
        deny(f"gh {group} {action} はしません")


# ---------------------------------------------------------------- wrangler


def wrangler_args(argv: list[str]) -> list[str] | None:
    """wrangler の呼び出しなら、wrangler の後ろの引数。そうでなければ None。"""
    if WRANGLER.fullmatch(os.path.basename(argv[0])):
        return argv[1:]
    if os.path.basename(argv[0]) in RUNNERS:
        for i, word in enumerate(argv[1:], start=1):
            if WRANGLER.fullmatch(os.path.basename(word)):
                return argv[i + 1:]
    return None


def check_wrangler(args: list[str]) -> None:
    """秘密の値を書く操作を止める。登録と入れ替えは人がする（計画の「開始前に人がすること」）。"""
    words = positionals(args, WRANGLER_VALUE_FLAGS)
    message = ("秘密の値は書きません（Worker の secret と Secrets Store の作成・更新・削除）。"
               "登録は人がするので、計画の「開始前に人がすること」に書きます")
    if words[:1] == ["secret"] and words[1:2] in (["put"], ["delete"], ["bulk"]):
        deny(message)
    if words[:2] == ["versions", "secret"] and words[2:3] in (["put"], ["delete"], ["bulk"]):
        deny(message)
    if words[:2] == ["secrets-store", "secret"] and words[2:3] in (["create"], ["update"], ["delete"], ["duplicate"]):
        deny(message)
    if words[:2] == ["secrets-store", "store"] and words[2:3] in (["create"], ["delete"]):
        deny(message)
    if words[:1] in (["deploy"], ["versions"]) and has(args, "--secrets-file"):
        deny(message)


# ---------------------------------------------------------------- 入口


def check_bash(command: str, role: str, cwd: str) -> None:
    parsed = segments(command)
    if parsed is None:
        if re.search(r"(^|[\s;&|(])(git|gh|wrangler(@\S*)?)\s", command):
            deny("コマンドを読めませんでした（引用符の対応など）。git・gh・wrangler は、1 つずつ単純な形で実行します")
        return
    for argv in parsed:
        argv = program(argv)
        if not argv:
            continue
        name = os.path.basename(argv[0])
        if name == "cd" and len(argv) > 1:
            cwd = str(Path(cwd, os.path.expanduser(argv[1])))
        elif name == "git":
            check_git(argv[1:], role, cwd)
        elif name == "gh":
            check_gh(argv[1:], role)
        else:
            wrangler = wrangler_args(argv)
            if wrangler is not None:
                check_wrangler(wrangler)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ROLES:
        print(f"使い方: guard.py <{'|'.join(sorted(ROLES))}>", file=sys.stderr)
        return 2
    role = sys.argv[1]
    data = json.load(sys.stdin)
    tool = data.get("tool_name")
    tool_input = data.get("tool_input") or {}
    cwd = data.get("cwd") or os.getcwd()
    if tool == "Bash":
        check_bash(tool_input.get("command") or "", role, cwd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
