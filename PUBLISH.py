#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime

CONFIG_PATH = "config.yaml"
CHANGELOG_PATH = "CHANGELOG.md"
OWNER = "Nanako718"
REPO = "ha-fusion"

def sh(cmd, check=True):
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check)

def http_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "publish-bot"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())

def fetch_latest_release(owner: str, repo: str):
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        data = http_json(url)
        tag = data.get("tag_name") or ""
        body = data.get("body") or ""
        if not tag:
            raise ValueError("missing tag_name")
        if not tag.startswith("v"):
            tag = "v" + tag
        return tag, body
    except urllib.error.HTTPError as e:
        # 404: 仓库没有任何 release；其他错误也兜底
        print(f"WARN: fetch latest release failed: {e}")
        return None, None
    except Exception as e:
        print(f"WARN: fetch latest release error: {e}")
        return None, None

def strip_v(tag: str) -> str:
    return tag.lstrip("v").strip()

def detect_config_version():
    if not os.path.exists(CONFIG_PATH):
        return ""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^\s*version:\s*(.+?)\s*$", line)
            if m:
                return m.group(1).strip().strip('"').strip("'")
    return ""

def write_config_version(version_no_v: str, dry=False):
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"{CONFIG_PATH} not found")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    replaced = False
    for line in lines:
        if re.match(r"^\s*version:\s*", line) and not replaced:
            indent = re.match(r"^(\s*)", line).group(1)
            new_lines.append(f"{indent}version: {version_no_v}\n")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"version: {version_no_v}\n")
    if dry:
        print(f"[dry-run] would write version={version_no_v} to {CONFIG_PATH}")
        return
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"INFO: {CONFIG_PATH} updated to {version_no_v}")

def write_changelog(text: str, dry=False):
    text = text or "# Changelog\n\nManual release."
    if dry:
        print("[dry-run] would write CHANGELOG (preview):")
        print("\n".join(text.splitlines()[:20]))
        return
    with open(CHANGELOG_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    print("INFO: CHANGELOG.md updated")

def git_add_commit(files, message, dry=False):
    if dry:
        print(f"[dry-run] git add {' '.join(files)} && git commit -m \"{message}\"")
        return
    sh(["git", "add", *files])
    sh(["git", "commit", "-m", message], check=False)  # 允许空提交

def git_force_tag_and_push(tag_with_v: str, push=True, dry=False):
    if dry:
        print(f"[dry-run] re-tag {tag_with_v} and push")
        return
    # 先删同名远端/本地 tag，再重打，确保覆盖
    sh(["git", "tag", "-d", tag_with_v], check=False)
    sh(["git", "push", "origin", f":refs/tags/{tag_with_v}"], check=False)
    sh(["git", "tag", tag_with_v])
    if push:
        sh(["git", "push"])
        sh(["git", "push", "origin", tag_with_v])

def git_push(dry=False):
    if dry:
        print("[dry-run] git push")
        return
    sh(["git", "push"])

def auto_version() -> str:
    today = datetime.now().strftime("%Y.%m.%d")
    cur = detect_config_version()
    n = 1
    if cur.startswith(today):
        parts = cur.split(".")
        try:
            n = int(parts[-1]) + 1
        except Exception:
            n = 2
    return f"{today}.{n}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", help="手动指定版本（不带 v），或写 auto 自动生成（YYYY.MM.DD.N）")
    ap.add_argument("--notes", default="", help="自定义 release notes")
    ap.add_argument("--latest-only", action="store_true", help="只触发 latest 构建：不打 tag，仅 push")
    ap.add_argument("--no-push", action="store_true", help="不推远端（仅本地操作）")
    ap.add_argument("--dry-run", action="store_true", help="演练模式")
    args = ap.parse_args()

    # 1) 来源优先级：手动指定 > GitHub Release > 自动版本
    if args.version:
        version_no_v = args.version if args.version != "auto" else auto_version()
        tag_with_v = "v" + version_no_v
        notes = args.notes or f"# {tag_with_v}\n\nManual release."
    else:
        tag_with_v, notes = fetch_latest_release(OWNER, REPO)
        if tag_with_v:
            version_no_v = strip_v(tag_with_v)
            notes = args.notes or notes or f"# {tag_with_v}\n"
        else:
            # 没有任何 release → fallback
            version_no_v = auto_version()
            tag_with_v = "v" + version_no_v
            notes = args.notes or f"# {tag_with_v}\n\nAuto fallback (no releases in repo)."

    print(f"PLAN: config.version={version_no_v}  tag={tag_with_v}  latest_only={args.latest_only}")

    # 2) 写文件
    write_config_version(version_no_v, dry=args.dry_run)
    write_changelog(notes, dry=args.dry_run)

    # 3) 提交
    git_add_commit([CONFIG_PATH, CHANGELOG_PATH], f"release: {version_no_v}", dry=args.dry_run)

    # 4) 推送
    if args.no_push:
        print("INFO: --no-push set, skip pushing")
        return

    if args.latest_only:
        git_push(dry=args.dry_run)
        print("\n✅ pushed (latest only).")
    else:
        git_force_tag_and_push(tag_with_v, push=True, dry=args.dry_run)
        print("\n✅ pushed with tag and latest.")
    print("Done.")

if __name__ == "__main__":
    main()