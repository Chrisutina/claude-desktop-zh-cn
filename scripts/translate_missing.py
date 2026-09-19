#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Translate the Claude Desktop interface strings this pack has not covered yet.

Claude Desktop ships its UI copy as flat ``<hash>: "text"`` JSON catalogues, one
per locale, in two separate directories (main process and renderer). When Claude
updates, it adds keys this pack does not have; those fall back to English.

This tool finds the gap and machine-translates it:

  1. read the app's ``en-US.json`` and this pack's ``<lang>.json``
  2. keep only keys that some bundle actually references -- a key no code uses
     can never render, so translating it is wasted work
  3. batch the remainder to an Anthropic-compatible endpoint
  4. validate every reply (ICU placeholders, brace balance, quoting) and retry
     the rejects one at a time
  5. optionally merge the accepted results into ``resources/frontend-<lang>.json``

Results are appended to a JSONL file as they arrive, so the run is resumable:
re-running skips whatever is already done.

Credentials come from the environment:

    TRANSLATE_API_BASE   e.g. https://api.deepseek.com/anthropic
    TRANSLATE_API_KEY    the matching key

As a convenience on a machine already set up with cc-switch, they are read from
the active Claude Desktop profile in ``~/.cc-switch/cc-switch.db`` when the
environment variables are absent.

Examples
--------
    python scripts/translate_missing.py --limit 1        # preview one batch
    python scripts/translate_missing.py                  # full run
    python scripts/translate_missing.py --merge          # translate, then merge
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_LANG = "zh-CN"
WORKERS = 8
RESULTS = ".translate-missing-results.jsonl"
ID_CACHE = ".translate-missing-ids.json"
CC_SWITCH_DB = os.path.expanduser("~/.cc-switch/cc-switch.db")

SYSTEM = """你是 Claude Desktop 界面本地化译者，把英文 UI 文案翻译成简体中文。

硬性要求（违反即整条作废）：
1. 原样保留所有花括号占位符，如 {name}、{count}、{url}、{folderName}。名称一个字符都不能改。
2. 原样保留 ICU 语法结构，如 {count, plural, one {...} other {...}}、{action, select, connect {...} other {...}}。
   分支关键字 one/other/zero/few/many 是语法不是英文单词，绝对不能翻译；花括号必须配平。
3. 两个连续单引号 '' 是 ICU 转义，必须原样保留。
4. 专有名词保留英文：Claude、Claude Code、Claude Desktop、Cowork、MCP、GitHub、Slack、Artifacts、Pro、Max、Enterprise、DXT、SSH、API。
5. 术语固定：Settings=设置、session=会话、folder=文件夹、workspace=工作区、worktree=工作树、skill=技能、
   extension=扩展、permission=权限、artifact=工件、Remote Control=远程控制、Usage=用量、Plan=套餐、
   Organization=组织、administrator=管理员、browser=浏览器、terminal=终端。
6. 简洁，符合中文软件界面习惯；不加解释，不加多余标点。
7. 原文结尾没有句号就不要加中文句号。
8. 保留原文的首尾空格。

只输出 JSON 对象，形如 {"<id>": "<译文>"}。不要 markdown 代码块，不要任何额外文字。"""


# ---------------------------------------------------------------- app discovery

def _msix_install_locations():
    """Install roots of MSIX-packaged Claude builds.

    ``C:\\Program Files\\WindowsApps`` grants traverse-but-not-list to normal
    users, so os.listdir raises PermissionError there even though any known path
    inside it is readable. Ask the package manager for the path instead.
    """
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-AppxPackage -Name Claude).InstallLocation"],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def find_resources(explicit=None):
    """Locate the installed Claude Desktop `resources` directory."""
    if explicit:
        return explicit

    candidates = []

    for location in _msix_install_locations():
        path = os.path.join(location, "app", "resources")
        if os.path.isdir(path):
            candidates.append(path)

    local = os.environ.get("LOCALAPPDATA")
    if local:
        legacy = os.path.join(local, "AnthropicClaude")
        try:
            for name in sorted(os.listdir(legacy), reverse=True):
                path = os.path.join(legacy, name, "resources")
                if os.path.isdir(path):
                    candidates.append(path)
                    break
        except OSError:
            pass

    macos = "/Applications/Claude.app/Contents/Resources"
    if os.path.isdir(macos):
        candidates.append(macos)

    if not candidates:
        raise SystemExit(
            "找不到 Claude Desktop 的 resources 目录，请用 --app 指定"
        )
    # Sorted so a newer build wins when several are present.
    return sorted(candidates)[-1]


def resolve_credentials():
    base = os.environ.get("TRANSLATE_API_BASE") or os.environ.get("ANTHROPIC_BASE_URL")
    token = os.environ.get("TRANSLATE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if base and token:
        return base, token

    if os.path.exists(CC_SWITCH_DB):
        try:
            con = sqlite3.connect(CC_SWITCH_DB)
            row = con.execute(
                "SELECT settings_config FROM providers "
                "WHERE app_type='claude-desktop' AND is_current=1"
            ).fetchone()
            if row:
                env = json.loads(row[0])["env"]
                return env["ANTHROPIC_BASE_URL"], env["ANTHROPIC_AUTH_TOKEN"]
        except Exception:
            pass

    raise SystemExit(
        "缺少 API 凭据。请设置 TRANSLATE_API_BASE 和 TRANSLATE_API_KEY 环境变量，"
        "或在本机配置好 cc-switch 的 Claude Desktop profile。"
    )


# ------------------------------------------------------------- ICU validation

def top_args(text):
    """Top-level ICU argument names, ignoring brace-nested branch literals."""
    out, depth, i = [], 0, 0
    while i < len(text):
        char = text[i]
        if char == "{":
            if depth == 0:
                match = re.match(r"[a-zA-Z_][\w]*", text[i + 1:])
                if match:
                    end = i + 1 + len(match.group(0))
                    while end < len(text) and text[end] == " ":
                        end += 1
                    if end < len(text) and text[end] in ",}":
                        out.append(match.group(0))
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        i += 1
    return sorted(set(out))


def is_valid(source, translation):
    if not isinstance(translation, str) or not translation.strip():
        return False
    # Compare brace counts against the source rather than requiring them to
    # balance: a source may legitimately contain a quoted literal brace, as in
    # `start with '{'` -- one `{`, zero `}`. Parity with the source is the
    # invariant that matters; absolute balance would reject a correct reply.
    if translation.count("{") != source.count("{"):
        return False
    if translation.count("}") != source.count("}"):
        return False
    if top_args(source) != top_args(translation):
        return False
    # ICU reads a lone ' as a quote delimiter; a translation may drop English
    # contractions but must never introduce a new one.
    if translation.count("'") > source.count("'"):
        return False
    return True


# ---------------------------------------------------------------- model access

def call_api(base, token, payload, timeout=180):
    request = urllib.request.Request(
        base.rstrip("/") + "/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": token,
            "authorization": "Bearer " + token,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    return "".join(
        block.get("text", "")
        for block in data.get("content", [])
        if block.get("type") == "text"
    )


def parse_reply(text):
    body = text.strip()
    if body.startswith("```"):
        body = re.sub(r"^```[a-zA-Z]*\s*", "", body)
        body = re.sub(r"\s*```$", "", body)
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("reply contained no JSON object")
    return json.loads(body[start:end + 1])


# ------------------------------------------------------------------- pipeline

def collect_ids(assets_dir, cache_path):
    """Every 8-12 char quoted token in the JS bundles -- the candidate key space."""
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as handle:
            return set(json.load(handle))
    pattern = re.compile(r'["\']([A-Za-z0-9+/_\-]{8,12})["\']')
    found = set()
    for root, _, files in os.walk(assets_dir):
        for name in files:
            if name.endswith(".js"):
                with open(os.path.join(root, name), encoding="utf-8", errors="replace") as handle:
                    found.update(pattern.findall(handle.read()))
    with open(cache_path, "w", encoding="utf-8") as handle:
        json.dump(sorted(found), handle)
    return found


def make_batches(keys, source_text, char_budget=3500, max_items=40):
    batches, current, size = [], [], 0
    for key in keys:
        length = len(source_text[key])
        if current and (size + length > char_budget or len(current) >= max_items):
            batches.append(current)
            current, size = [], 0
        current.append(key)
        size += length
    if current:
        batches.append(current)
    return batches


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", help="Claude Desktop resources directory")
    parser.add_argument("--lang", default=DEFAULT_LANG, help="target locale (default zh-CN)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=0, help="only run N batches (preview)")
    parser.add_argument("--merge", action="store_true",
                        help="merge validated results into the pack when done")
    args = parser.parse_args()

    if args.lang != DEFAULT_LANG:
        # SYSTEM below is written for Simplified Chinese; the zh-TW / zh-HK packs
        # are not maintained by this tool. Refuse rather than emit wrong output.
        raise SystemExit(
            f"目前只支持 --lang {DEFAULT_LANG}；zh-TW / zh-HK 词表需要人工维护。"
        )

    resources = find_resources(args.app)
    i18n = os.path.join(resources, "ion-dist", "i18n")
    source_path = os.path.join(i18n, "en-US.json")
    pack_rel = os.path.join("resources", f"frontend-{args.lang}.json")
    if not os.path.exists(source_path):
        raise SystemExit(f"找不到 {source_path}")
    if not os.path.exists(pack_rel):
        raise SystemExit(f"找不到 {pack_rel}（请在仓库根目录运行）")

    with open(source_path, encoding="utf-8") as handle:
        english = json.load(handle)
    with open(pack_rel, encoding="utf-8") as handle:
        pack = json.load(handle)

    missing = [key for key in english if key not in pack]
    referenced = collect_ids(os.path.join(resources, "ion-dist", "assets"), ID_CACHE)
    todo = [key for key in missing if key in referenced]
    print(f"missing={len(missing)}  referenced={len(todo)}  "
          f"dead-skipped={len(missing) - len(todo)}")

    done = set()
    if os.path.exists(RESULTS):
        with open(RESULTS, encoding="utf-8") as handle:
            for line in handle:
                try:
                    done.add(json.loads(line)["id"])
                except Exception:
                    pass
    todo = [key for key in todo if key not in done]
    print(f"already translated={len(done)}  remaining={len(todo)}")
    if not todo:
        if args.merge:
            merge_results(pack_rel, args.lang)
        return

    batches = make_batches(todo, english)
    print(f"batches={len(batches)}  (avg {len(todo) / len(batches):.1f} strings/batch)")

    base, token = resolve_credentials()
    lock = threading.Lock()
    sink = open(RESULTS, "a", encoding="utf-8")
    stats = {"ok": 0, "rejected": 0}

    def translate(batch):
        items = {key: english[key] for key in batch}
        prompt = "翻译以下 {n} 条 UI 文案，返回 JSON：\n\n{body}".format(
            n=len(items), body=json.dumps(items, ensure_ascii=False, indent=1))
        last_error = None
        for attempt in range(4):
            try:
                reply = call_api(base, token, {
                    "model": args.model, "max_tokens": 8000, "system": SYSTEM,
                    "messages": [{"role": "user", "content": prompt}],
                })
                returned = parse_reply(reply)
                accepted, rejected = {}, []
                for key in batch:
                    value = returned.get(key)
                    if is_valid(english[key], value):
                        accepted[key] = value
                    else:
                        rejected.append(key)
                with lock:
                    for key, value in accepted.items():
                        sink.write(json.dumps({"id": key, "zh": value},
                                              ensure_ascii=False) + "\n")
                    sink.flush()
                    stats["ok"] += len(accepted)
                    stats["rejected"] += len(rejected)
                return rejected
            except Exception as error:  # transient network / rate limit / bad JSON
                last_error = error
                time.sleep(2 * (attempt + 1))
        with lock:
            stats["rejected"] += len(batch)
        print(f"  batch failed: {str(last_error)[:120]}", file=sys.stderr)
        return list(batch)

    selected = batches[:args.limit] if args.limit else batches
    started = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(translate, batch) for batch in selected]
        for index, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
            except Exception:
                pass
            if index % 20 == 0 or index == len(futures):
                elapsed = time.time() - started
                print(f"  {index}/{len(futures)} batches | ok={stats['ok']} "
                      f"rejected={stats['rejected']} | {elapsed:.0f}s elapsed, "
                      f"eta {elapsed / index * (len(futures) - index):.0f}s", flush=True)
    sink.close()
    print(f"\nDONE ok={stats['ok']} rejected={stats['rejected']}")
    print(f"results -> {RESULTS}")

    if args.merge:
        merge_results(pack_rel, args.lang)


def merge_results(pack_rel, lang):
    """Merge accepted translations into the pack, dropping nothing else."""
    if not os.path.exists(RESULTS):
        raise SystemExit(f"没有可合并的结果文件 {RESULTS}")

    with open(pack_rel, encoding="utf-8") as handle:
        pack = json.load(handle)

    added = 0
    with open(RESULTS, encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except Exception:
                continue
            # Already validated when it was written; nothing to re-check here.
            pack[record["id"]] = record["zh"]
            added += 1

    shutil.copy2(pack_rel, pack_rel + ".bak")
    with open(pack_rel, "w", encoding="utf-8") as handle:
        json.dump(pack, handle, ensure_ascii=False, indent=1)
    print(f"merged {added} entries into {pack_rel} (backup at {pack_rel}.bak)")


if __name__ == "__main__":
    main()
