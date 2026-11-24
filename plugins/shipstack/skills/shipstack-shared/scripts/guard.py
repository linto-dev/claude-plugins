#!/usr/bin/env -S python3 -I
"""実装計画のスキルの「守ること」を、文章の指示ではなく仕組みで守る PreToolUse フック。

各スキルの frontmatter の hooks から、役目（下の ROLES）を引数にして呼ばれる。標準入力に PreToolUse の JSON が来る。
決まりに反する操作なら、理由を標準エラーに書いて終了コード 2 で止める（Claude Code がツールの呼び出しを取り消し、理由を Claude に返す）。
反しなければ何も出さずに 0 で終わり、ふつうの許可の流れに任せる。

コマンドは bash と同じ区切りで読み、bash が動かすものはすべて同じ決まりで読む: シェルの予約語の後ろ（if … then、
{ …; }、for … do、! など）、前置きの後ろ（env・timeout・nice・sudo など）、別のシェルに渡す文字列（bash -c、sh -c、
eval）、コマンド置換（$(…)、`…`、<(…)。二重引用符の中と、引用符の無い区切りのヒアドキュメントの中も）、xargs と
find -exec が動かすコマンド。xargs と find -exec が足す引数は読めないので、引数しだいで決まりに反する git・gh・wrangler
を、それらで動かすことも止める。一重引用符の中（コミットメッセージなど）と、引用符の付いた区切りのヒアドキュメント
（<<'EOF'）の本文は、bash も動かさないので見ない。

これは間違いを止めるためのもので、わざと回り込む相手を防ぐものではない。変数で組み立てたコマンドの名前（$GIT push）、
シェルに渡すスクリプトのファイルと標準入力（bash x.sh、… | bash）は読まない。

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
# 単純なコマンドの頭に来るシェルの予約語。後ろの語が、動くコマンドになる（if git push …、{ git push …; } など）。
RESERVED = {"!", "{", "}", "if", "then", "elif", "else", "fi", "do", "done", "while", "until", "for", "select",
            "case", "esac", "coproc"}
# 後ろの語をコマンドとして動かす前置きと、その前置きの、値を取るオプション。
WRAPPERS = {
    "command": set(), "builtin": set(), "nohup": set(), "exec": {"-a"},
    "time": {"-o", "--output", "-f", "--format"},
    "env": {"-u", "--unset", "-C", "--chdir", "-P"},
    "sudo": {"-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt", "-C", "--close-from", "-D",
             "--chdir", "-r", "--role", "-t", "--type", "-U", "--other-user", "-T", "--command-timeout"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "nice": {"-n", "--adjustment"},
    "stdbuf": {"-i", "--input", "-o", "--output", "-e", "--error"},
}
# 前置きのうち、オプションの後に、コマンドより前の値を取るもの（timeout の時間）。
WRAPPER_OPERANDS = {"timeout": 1}
# -c に続く文字列をコマンドとして動かすシェルと、その値を取るオプション。
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "mksh", "ash"}
SHELL_VALUE_OPTIONS = {"-o", "+o", "-O", "+O", "--rcfile", "--init-file"}
XARGS_VALUE_OPTIONS = {"-a", "-d", "-E", "-I", "-J", "-L", "-n", "-P", "-R", "-s", "-S", "--arg-file", "--delimiter",
                       "--eof", "--replace", "--max-lines", "--max-args", "--max-procs", "--max-chars"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
# 入れ子（bash -c の中の bash -c、コマンド置換の中のコマンド置換など）を読む深さの上限。
MAX_DEPTH = 8
# 引数を足して動かすと、足した引数しだいで決まりに反する git のサブコマンド（check_git が引数を見るもの）。
GIT_CHECKED = {"push", "commit", "rebase", "pull", "reset", "checkout", "switch", "branch", "tag", "worktree", "merge",
               "clean", "filter-branch", "filter-repo", "update-ref", "replace"}
# 引数を足して動かすと、足した引数しだいで決まりに反する gh のコマンドと、そのうち読むだけの操作。
GH_CHECKED = {"pr", "api", "repo", "release", "workflow", "secret", "variable"}
GH_READS = {"pr": {"view", "list", "checks", "diff", "status"}, "repo": {"view", "list"},
            "release": {"list", "view", "download"}, "workflow": {"list", "view"}, "secret": {"list"},
            "variable": {"list", "get"}}
# 読めなかったコマンドが git・gh・wrangler を動かしそうか。
TOOLS = re.compile(r"(^|[\s;&|(){}`'\"])(git|gh|wrangler(@\S*)?)(\s|$)")
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


def scan(command: str) -> tuple[str, list[str]] | None:
    """bash と同じ区切りで読んだ文字列（ヒアドキュメントの本文とコメントを除き、引用符の外の改行を ; にしたもの）と、
    bash が動かすコマンド置換の中身（$(…)、`…`、<(…)、>(…)）。読めなければ None。

    コマンド置換は、二重引用符の中と、引用符の無い区切りのヒアドキュメント（<<EOF）の本文でも動く。一重引用符の中と、
    引用符の付いた区切りのヒアドキュメント（<<'EOF'。コミットメッセージなど）の本文では動かないので見ない。"""
    out: list[str] = []
    found: list[str] = []
    pending: list[tuple[str, bool, bool]] = []  # ヒアドキュメントの区切り、行頭のタブを除くか、本文を展開するか
    quote = ""
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        if quote == "'":
            quote = "" if c == "'" else quote
            out.append(c)
            i += 1
            continue
        if c == "\\":
            out.append(command[i:i + 2])
            i += 2
            continue
        if c == "`" or (c == "$" and command[i + 1:i + 2] == "(") or \
                (not quote and c in "<>" and command[i + 1:i + 2] == "("):
            end = substitution_end(command, i)
            if end is None:
                return None
            found.append(substitution_body(command, i, end))
            out.append(command[i:end])
            i = end
            continue
        if c == "'" and not quote:
            quote = "'"
        elif c == '"':
            quote = "" if quote else '"'
        elif not quote and command.startswith("<<<", i):
            out.append("<<<")
            i += 3
            continue
        elif not quote and command.startswith("<<", i):
            operator = heredoc_operator(command, i)
            if operator is not None:
                end, heredoc = operator
                pending.append(heredoc)
                out.append(command[i:end])
                i = end
                continue
        elif not quote and c == "#" and (i == 0 or command[i - 1] in " \t\n;&|()<>"):
            # コメントは行の終わりまで。bash は動かさない。
            end = command.find("\n", i)
            i = n if end == -1 else end
            continue
        elif not quote and c == "\n":
            # 改行もコマンドの区切り。引用符の中の改行は、文字列の中のまま残す（bash -c '…' の中で区切りになる）。
            out.append(" ; ")
            i += 1
            for delimiter, strip_tabs, expands in pending:
                body, i = heredoc_body(command, i, delimiter, strip_tabs)
                if body is None:
                    return None
                if expands:
                    inner = expansions(body)
                    if inner is None:
                        return None
                    found.extend(inner)
            pending = []
            continue
        out.append(c)
        i += 1
    if pending:
        return None  # 本文と区切りの行の無いヒアドキュメント
    return "".join(out), found


def substitution_end(text: str, i: int) -> int | None:
    """text[i] から始まるコマンド置換（`…`、$(…)、<(…)、>(…)）の、終わりの次の位置。"""
    if text[i] == "`":
        j = i + 1
        while j < len(text):
            if text[j] == "\\":
                j += 2
            elif text[j] == "`":
                return j + 1
            else:
                j += 1
        return None
    close = paren_end(text, i + 2)
    return None if close is None else close + 1


def substitution_body(text: str, i: int, end: int) -> str:
    if text[i] == "`":
        return re.sub(r"\\([$`\\])", r"\1", text[i + 1:end - 1])
    return text[i + 2:end - 1]


def paren_end(text: str, i: int) -> int | None:
    """開いた括弧の直後 text[i] から読んで、対応する ) の位置。中の引用符とコマンド置換は飛ばす。
    case … esac の中の、型を閉じる ) は数えない（$(case x in x) …;; esac) の最初の ) は、置換の終わりではない）。"""
    depth, cases, quote = 1, 0, ""
    while i < len(text):
        c = text[i]
        if quote == "'":
            quote = "" if c == "'" else quote
        elif c == "\\":
            i += 1
        elif c == "'" and not quote:
            quote = "'"
        elif c == '"':
            quote = "" if quote else '"'
        elif c == "`" or (c == "$" and text[i + 1:i + 2] == "("):
            end = substitution_end(text, i)
            if end is None:
                return None
            i = end
            continue
        elif not quote and (i == 0 or text[i - 1] in " \t\n;&|(") and re.match(r"(case|esac)(?=[\s;&|)]|$)", text[i:]):
            cases += 1 if text.startswith("case", i) else -1 if cases else 0
            i += 4
            continue
        elif not quote and c == "(":
            depth += 1
        elif not quote and c == ")":
            if depth == 1 and cases:
                pass  # case の型の終わり
            else:
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return None


def heredoc_operator(text: str, i: int) -> tuple[int, tuple[str, bool, bool]] | None:
    """text[i] の << から、区切りの語の終わりの位置と、（区切り、行頭のタブを除くか、本文を展開するか）。"""
    k = i + 2
    strip_tabs = text[k:k + 1] == "-"
    k += 1 if strip_tabs else 0
    while k < len(text) and text[k] in " \t":
        k += 1
    word: list[str] = []
    quoted = False
    while k < len(text) and text[k] not in " \t\n;&|<>()":
        c = text[k]
        if c in "'\"":
            end = text.find(c, k + 1)
            if end == -1:
                return None
            word.append(text[k + 1:end])
            quoted, k = True, end + 1
        elif c == "\\":
            word.append(text[k + 1:k + 2])
            quoted, k = True, k + 2
        else:
            word.append(c)
            k += 1
    if not word:
        return None
    return k, ("".join(word), strip_tabs, not quoted)


def heredoc_body(text: str, i: int, delimiter: str, strip_tabs: bool) -> tuple[str | None, int]:
    """text[i] の行から、区切りの行の前までの本文と、区切りの行の次の位置。区切りの行が無ければ None。"""
    lines: list[str] = []
    while True:
        end = text.find("\n", i)
        line = text[i:] if end == -1 else text[i:end]
        if (line.lstrip("\t") if strip_tabs else line) == delimiter:
            return "\n".join(lines), len(text) if end == -1 else end + 1
        if end == -1:
            return None, i
        lines.append(line)
        i = end + 1


def expansions(text: str) -> list[str] | None:
    """引用符の無い区切りのヒアドキュメントの本文で、bash が動かすコマンド置換の中身（本文の引用符は、ただの文字）。"""
    found: list[str] = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
        elif c == "`" or (c == "$" and text[i + 1:i + 2] == "("):
            end = substitution_end(text, i)
            if end is None:
                return None
            found.append(substitution_body(text, i, end))
            i = end
        else:
            i += 1
    return found


def segments(text: str) -> list[list[str]] | None:
    """scan で読んだ文字列を ; && || | などで切った、単純なコマンドの並び。読めなければ None。"""
    text = text.replace("\\\n", " ")
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
    """環境変数の代入、シェルの予約語（if、then、{、! など）、command・env・timeout などの前置きを除いた argv。"""
    i = 0
    while i < len(argv):
        word = argv[i]
        name = os.path.basename(word)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", word) or word in RESERVED:
            i += 1
        elif word == "function":
            i += 2  # function <名前> { … }
        elif name in WRAPPERS:
            i += 1
            while i < len(argv) and argv[i].startswith("-") and argv[i] != "-":
                option = argv[i]
                if option == "--":
                    i += 1
                    break
                if name == "env" and (option in ("-S", "--split-string") or option.startswith("--split-string=")):
                    # env -S '<コマンド>' は、文字列を語に分けて動かす。
                    attached = option.startswith("--split-string=")
                    value = option.split("=", 1)[1] if attached else " ".join(argv[i + 1:i + 2])
                    try:
                        words = shlex.split(value)
                    except ValueError:
                        words = value.split()
                    return program(words + argv[i + (1 if attached else 2):])
                i += 2 if option in WRAPPERS[name] else 1
            i += WRAPPER_OPERANDS.get(name, 0)
        else:
            break
    return argv[i:]


def shell_command(args: list[str]) -> tuple[bool, str | None]:
    """シェル（bash など）の引数から、-c でコマンドを動かすかと、動かす文字列（-c の後の最初の語。無ければ None）。"""
    i, runs = 0, False
    while i < len(args):
        arg = args[i]
        if arg == "--":
            i += 1
            break
        if arg in SHELL_VALUE_OPTIONS:
            i += 2
        elif arg.startswith("--"):
            i += 1
        elif re.fullmatch(r"[-+][A-Za-z]+", arg):
            runs = runs or (arg[0] == "-" and "c" in arg[1:])
            i += 1
        else:
            break
    return runs, (args[i] if runs and i < len(args) else None)


def xargs_command(args: list[str]) -> list[str]:
    """xargs の引数から、xargs が動かすコマンド（無ければ echo）。"""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "--":
            i += 1
            break
        i += 2 if args[i] in XARGS_VALUE_OPTIONS else 1
    return args[i:] or ["echo"]


def exec_commands(args: list[str]) -> list[list[str]]:
    """find の引数から、-exec・-execdir・-ok・-okdir で動かすコマンド（\\; で区切られて、-exec から始まる続きも）。"""
    commands, k = [], 0
    while k < len(args):
        if args[k] in FIND_EXEC:
            end = k + 1
            while end < len(args) and args[end] not in (";", "+"):
                end += 1
            commands.append(args[k + 1:end])
            k = end
        k += 1
    return [c for c in commands if c]


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


def split_git(args: list[str], cwd: str) -> tuple[str | None, list[str], str]:
    """git の引数から、サブコマンドとその引数と、git -C <dir> を当てた作業場所。サブコマンドが無ければ None。"""
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
        return None, [], cwd
    return args[i], args[i + 1:], cwd


def check_git(args: list[str], role: str, cwd: str) -> None:
    sub, rest, cwd = split_git(args, cwd)
    if sub is None:
        return
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
        deny("ワーカーは git pull しません。手元が origin と違うなら、触らずに止めます（手元を合わせるのは指揮役の shipstack run）")
    elif sub == "reset":
        check_reset(rest, role, repo)
    elif sub in ("checkout", "switch"):
        creating = has(rest, "-b", "-B", "--orphan") if sub == "checkout" else has(rest, "-c", "-C", "--create", "--force-create", "--orphan")
        if creating:
            deny("ブランチは作りません（機能ブランチは指揮役の shipstack run が作る）")
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
            deny(f"origin に無いブランチ（{dst}）は push しません（機能ブランチは指揮役の shipstack run が作る）")


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
        deny("ブランチは作りません（機能ブランチは指揮役の shipstack run が作る）")


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
                deny("このスキルは PR を作りません（機能の PR は最初のフェーズが shipstack pr-create で作る）")
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


def check_added_arguments(argv: list[str], via: str) -> None:
    """xargs・find -exec が引数を足して動かすコマンドのうち、足す引数しだいで決まりに反するものを止める（足す引数は読めない）。"""
    name = os.path.basename(argv[0])
    message = f"{via} で引数を足して {{}} を動かしません（足す引数が読めないため）。1 つずつ単純な形で実行します"
    if name == "git":
        sub = split_git(argv[1:], ".")[0]
        if sub in GIT_CHECKED:
            deny(message.format(f"git {sub}"))
    elif name == "gh":
        group, action = (argv[1:] + ["", ""])[:2]
        if group in GH_CHECKED and action not in GH_READS.get(group, set()):
            deny(message.format(f"gh {group}"))
    elif name == "eval":
        deny(message.format("eval"))
    else:
        wrangler = wrangler_args(argv)
        if wrangler is not None and positionals(wrangler, WRANGLER_VALUE_FLAGS)[:1] in (
                ["secret"], ["secrets-store"], ["versions"], ["deploy"]):
            deny(message.format("wrangler"))


def check_argv(argv: list[str], role: str, cwd: str, added: str, depth: int) -> str:
    """単純なコマンド 1 つを確かめる。added は、引数を足して動かすもの（xargs・find -exec。無ければ空）。
    返り値は、このコマンドの後の作業場所（cd を読む）。"""
    argv = program(argv)
    if not argv:
        return cwd
    name, args = os.path.basename(argv[0]), argv[1:]
    if added:
        check_added_arguments(argv, added)
    if name == "cd" and args:
        return str(Path(cwd, os.path.expanduser(args[0])))
    if name in SHELLS:
        runs, inner = shell_command(args)
        if runs and inner is None and added:
            deny(f"{added} で、シェルに動かすコマンドを渡しません（渡すコマンドが読めないため）。1 つずつ単純な形で実行します")
        if inner is not None:
            check_command(inner, role, cwd, added, depth + 1)
    elif name == "eval":
        check_command(" ".join(args), role, cwd, added, depth + 1)
    elif name == "xargs":
        check_argv(xargs_command(args), role, cwd, "xargs", depth + 1)
    elif name == "find" or name in FIND_EXEC:
        for command in exec_commands(argv if name in FIND_EXEC else args):
            check_argv(command, role, cwd, "find -exec", depth + 1)
    elif name == "git":
        check_git(args, role, cwd)
    elif name == "gh":
        check_gh(args, role)
    else:
        wrangler = wrangler_args(argv)
        if wrangler is not None:
            check_wrangler(wrangler)
    return cwd


def check_command(command: str, role: str, cwd: str, added: str = "", depth: int = 0) -> None:
    """コマンドの文字列を読み、決まりに反する操作があれば止める。bash -c・eval・コマンド置換の中も同じ決まりで読む。"""
    scanned = scan(command) if depth <= MAX_DEPTH else None
    parsed = segments(scanned[0]) if scanned is not None else None
    if scanned is None or parsed is None:
        if TOOLS.search(command):
            deny("コマンドを読めませんでした（引用符や括弧の対応、深い入れ子など）。git・gh・wrangler は、1 つずつ単純な形で実行します")
        return
    for body in scanned[1]:
        check_command(body, role, cwd, added, depth + 1)
    for argv in parsed:
        cwd = check_argv(argv, role, cwd, added, depth)


def check_bash(command: str, role: str, cwd: str) -> None:
    check_command(command, role, cwd)


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
