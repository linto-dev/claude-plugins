#!/usr/bin/env -S python3 -I
"""クラウドの会話（scheduled task など）で、claude/ で始まるブランチ以外への push と、PR のマージを止める PreToolUse フック。

クラウドの会話は利用者の GitHub の権限で動き、push 先のブランチは制限されない（GitHub の規則も、利用者が迂回できるなら効かない）。
手元では main に直接 push するので、GitHub の規則ではなく、クラウドの会話（CLAUDE_CODE_REMOTE=true）だけをここで止める。手元の会話では何もしない。

標準入力に PreToolUse の JSON が来る。止めるときは理由を標準エラーに書いて終了コード 2 で終わる。
間違いを止めるためのもので、わざと回り込む相手を防ぐものではない（コマンドは shlex で読む）。
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

ALLOWED_PREFIX = "claude/"
SEPARATOR = re.compile(r"[;&|()]+")
REDIRECT = re.compile(r"[<>]+&?|&>>?")
WRAPPERS = {"command", "builtin", "exec", "nohup", "time", "env", "sudo"}
FORCE_FLAGS = {"-f", "--force", "--force-with-lease", "--force-if-includes", "--mirror", "--all", "--tags",
               "--delete", "-d", "--prune"}
# git の、値を取る全体のオプション（git -C <dir> push …）。
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
PUSH_VALUE_OPTIONS = {"-o", "--push-option", "--receive-pack", "--exec", "--repo"}


def deny(message: str) -> None:
    print(f"[ハーネスの追従の決まり] {message}", file=sys.stderr)
    sys.exit(2)


def segments(command: str) -> list[list[str]] | None:
    text = command.replace("\\\n", " ").replace("\n", " ; ")
    lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    result: list[list[str]] = [[]]
    skip = False
    for token in tokens:
        if skip:
            skip = False
        elif REDIRECT.fullmatch(token):
            if result[-1] and result[-1][-1].isdigit():
                result[-1].pop()
            skip = True
        elif SEPARATOR.fullmatch(token):
            result.append([])
        else:
            result[-1].append(token)
    return [argv for argv in result if argv]


def program(argv: list[str]) -> list[str]:
    """前に付いた環境変数の代入と包み（env、command など）を外す。"""
    i = 0
    while i < len(argv) and (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", argv[i]) or argv[i] in WRAPPERS):
        i += 1
    return argv[i:]


def check_push(args: list[str]) -> None:
    positionals: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in FORCE_FLAGS or arg.startswith("--force") or arg.startswith("--delete"):
            deny(f"push の {arg} は使いません。新しいコミットを足して claude/ のブランチに push します")
        if arg in PUSH_VALUE_OPTIONS:
            i += 2
            continue
        if not arg.startswith("-"):
            positionals.append(arg)
        i += 1
    if len(positionals) < 2:
        deny("push 先を明示します（git push -u origin claude/<ブランチ>）。上流の設定に任せた push はしません")
    for refspec in positionals[1:]:
        if refspec.startswith("+"):
            deny(f"強制の refspec（{refspec}）は使いません")
        destination = refspec.split(":", 1)[-1].removeprefix("refs/heads/")
        if refspec.startswith(":") or not destination.startswith(ALLOWED_PREFIX):
            deny(f"push できるのは {ALLOWED_PREFIX} で始まるブランチだけです（{refspec}）。main への変更は draft PR にします")


def check_git(argv: list[str]) -> None:
    i = 1
    while i < len(argv) and argv[i].startswith("-"):
        i += 2 if argv[i] in GIT_VALUE_OPTIONS else 1
    if i < len(argv) and argv[i] == "push":
        check_push(argv[i + 1:])


def check_gh(argv: list[str]) -> None:
    if argv[1:3] == ["pr", "merge"]:
        deny("PR はマージしません（マージは人が行う）")
    if len(argv) > 1 and argv[1] == "api":
        rest = argv[2:]
        method = next((rest[j + 1] for j, a in enumerate(rest[:-1]) if a in ("-X", "--method")), "")
        method = method or next((a.split("=", 1)[1] for a in rest if a.startswith("--method=")), "")
        if any(re.search(r"/pulls/\d+/merge\b|/merges\b", a) for a in rest):
            deny("PR とブランチはマージしません（マージは人が行う）")
        if method.upper() == "DELETE":
            deny("GitHub の API で消す操作はしません")
        if any("/git/refs" in a for a in rest) and method.upper() in ("POST", "PATCH", "PUT"):
            deny("ブランチは GitHub の API ではなく git push で作ります（claude/ のブランチだけ）")


def check(command: str) -> None:
    parsed = segments(command)
    if parsed is None:
        if re.search(r"(^|[\s;&|(])(git\s+push|gh)\s", command):
            deny("コマンドを読めませんでした（引用符の対応など）。git push と gh は、1 つずつ単純な形で実行します")
        return
    for argv in parsed:
        argv = program(argv)
        if not argv:
            continue
        name = os.path.basename(argv[0])
        if name == "git":
            check_git(argv)
        elif name == "gh":
            check_gh(argv)


def main() -> int:
    if os.environ.get("CLAUDE_CODE_REMOTE") != "true":
        return 0
    data = json.load(sys.stdin)
    if data.get("tool_name") == "Bash":
        check((data.get("tool_input") or {}).get("command") or "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
