#!/usr/bin/env python3
"""One-way Codex -> Obsidian Markdown synchronizer.

The source files remain authoritative. Obsidian receives byte-preserved raw
copies plus a generated index. Source deletions are retained as history and
marked source_missing in the state/index; this tool never writes to Codex
memory or other source roots.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_child(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise RuntimeError(f"path_outside_root: {relative}")
    return candidate


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def heading(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    for line in text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return match.group(1)
    return ""


def source_files(source: dict) -> list[tuple[Path, str]]:
    root = Path(source["root"]).expanduser().resolve()
    if not root.is_dir():
        return []
    extensions = {str(x).lower() for x in source.get("extensions", [".md"])}
    excluded = set(source.get("exclude_dirs", []))
    results = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if any(part in excluded for part in relative.parts):
            continue
        if path.suffix.lower() not in extensions:
            continue
        results.append((path, relative.as_posix()))
    return results


def raw_relative(destination_root: str, alias: str, relative: str) -> str:
    return f"{destination_root}/原始/{alias}/{relative}"


def render_index(config: dict, entries: list[dict], synced_at: str) -> str:
    current = [item for item in entries if item["status"] == "current"]
    missing = [item for item in entries if item["status"] == "source_missing"]
    lines = [
        "---",
        "id: CODEX-SYNC-INDEX-001",
        "type: index",
        "project: global",
        f"updated: {synced_at}",
        "freshness: current",
        "sync_direction: codex_to_obsidian",
        f"current_count: {len(current)}",
        f"source_missing_count: {len(missing)}",
        "---",
        "",
        "# Codex → Obsidian 单向同步索引",
        "",
        f"> 最后同步：{synced_at}。原始文件由 Codex 源目录提供，Obsidian 中的副本只用于检索、引用和历史留存。",
        "> 本索引由 `codex_to_obsidian_sync.py` 生成；不要手工修改索引内容。",
        "",
        f"当前文件：{len(current)}；源文件已删除但本地保留：{len(missing)}。",
        "",
        "| 状态 | 类型 | 标题 | Codex源路径 | Obsidian原始副本 | 更新时间 | SHA-256 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in sorted(entries, key=lambda x: (x["status"] != "current", x["source_path"])):
        status = "当前" if item["status"] == "current" else "源已删除（保留）"
        title = (item.get("title") or item["relative_path"]).replace("|", "\\|")
        source = item["source_path"].replace("|", "\\|")
        raw = f"[[{item['raw_path']}|打开原始副本]]"
        digest = item.get("sha256", "")[:12]
        lines.append(
            f"| {status} | {item['kind']} | {title} | `{source}` | {raw} | {item.get('modified_at','')} | `{digest}` |"
        )
    lines.extend([
        "",
        "## 使用边界",
        "",
        "- 这是 Codex → Obsidian 单向同步；不会把 Obsidian 的修改写回 Codex。",
        "- `原始/` 下文件是源文件的字节保留副本，不添加 frontmatter，不改写正文。",
        "- 需要引用内容时，先查本索引，再打开原始副本；需要判断当前状态时回到 Codex 源路径。",
        "- 源文件删除后，Obsidian 副本默认保留并标记为“源已删除（保留）”，避免历史资料丢失。",
    ])
    return "\n".join(lines) + "\n"


def sync(vault: Path, config_path: Path, quiet: bool = False) -> dict:
    config = load_json(config_path, None)
    if not isinstance(config, dict) or config.get("direction") != "codex_to_obsidian":
        raise RuntimeError("invalid_one_way_sync_config")
    destination_root = str(config.get("destination_root", "收件箱/Codex同步")).strip("/")
    index_path = str(config.get("index_path", f"{destination_root}/索引/Codex同步索引.md"))
    state_path = str(config.get("state_path", "系统/Codex单向同步状态.json"))
    destination = safe_child(vault, destination_root)
    index_file = safe_child(vault, index_path)
    state_file = safe_child(vault, state_path)
    readme_file = destination / "同步-Codex到Obsidian.md"
    state = load_json(state_file, {"entries": []})
    previous = {item.get("key"): item for item in state.get("entries", []) if item.get("key")}
    entries = []
    changed = 0

    for source in config.get("sources", []):
        alias = str(source["alias"])
        kind = str(source.get("kind", "codex_document"))
        root = Path(source["root"]).expanduser().resolve()
        seen = set()
        for path, relative in source_files(source):
            key = f"{alias}:{relative}"
            seen.add(key)
            raw_path = raw_relative(destination_root, alias, relative)
            target = safe_child(vault, raw_path)
            data = path.read_bytes()
            digest = sha256_bytes(data)
            old = previous.get(key)
            if old and old.get("sha256") == digest and target.is_file():
                pass
            else:
                atomic_write(target, data)
                changed += 1
            stat = path.stat()
            entries.append({
                "key": key,
                "alias": alias,
                "kind": kind,
                "source_root": str(root),
                "relative_path": relative,
                "source_path": str(path),
                "raw_path": raw_path,
                "sha256": digest,
                "bytes": len(data),
                "title": heading(data),
                "modified_at": dt.datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                "status": "current",
            })
        for key, old in previous.items():
            if old.get("alias") == alias and key not in seen:
                old = dict(old)
                old["status"] = "source_missing"
                entries.append(old)

    synced_at = now()
    state_out = {
        "direction": "codex_to_obsidian",
        "synced_at": synced_at,
        "source_count": len(config.get("sources", [])),
        "current_count": sum(item["status"] == "current" for item in entries),
        "source_missing_count": sum(item["status"] == "source_missing" for item in entries),
        "changed_count": changed,
        "entries": sorted(entries, key=lambda x: x["key"]),
    }
    atomic_write(state_file, (json.dumps(state_out, ensure_ascii=False, indent=2) + "\n").encode())
    atomic_write(index_file, render_index(config, entries, synced_at).encode())
    # Remove the former unclassified generated name after the first upgrade.
    old_readme = destination / "README.md"
    if old_readme.exists() and old_readme != readme_file:
        old_readme.unlink()
    atomic_write(readme_file, (
        "---\n"
        "id: CODEX-SYNC-README-001\n"
        "type: sync_boundary\n"
        "project: global\n"
        f"updated: {synced_at}\n"
        "freshness: current\n"
        "---\n\n"
        "# Codex 同步到 Obsidian\n\n"
        "这里是 Codex → Obsidian 的单向接收区。`原始/` 保存字节保留的 Markdown，`索引/` 保存方便检索的快照。\n\n"
        "Obsidian 修改不会回写 Codex；删除源文件也不会自动删除这里的历史副本。\n"
    ).encode())
    result = {"ok": True, "synced_at": synced_at, "changed": changed, "current": state_out["current_count"], "source_missing": state_out["source_missing_count"], "index": index_path}
    if not quiet:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def locked_sync(vault: Path, config_path: Path, quiet: bool = False) -> dict:
    lock_path = Path.home() / ".codex" / "work-knowledge-codex-sync.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"ok": True, "skipped": "already_running"}
        return sync(vault, config_path, quiet=quiet)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True)
    parser.add_argument("--config", default="")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("command", choices=["sync", "watch"])
    args = parser.parse_args()
    vault = Path(args.vault).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve() if args.config else vault / "系统/Codex单向同步.json"
    try:
        if args.command == "sync":
            locked_sync(vault, config_path, quiet=args.quiet)
            return 0
        config = load_json(config_path, {})
        interval = max(10, int(config.get("interval_seconds", 30)))
        while True:
            try:
                locked_sync(vault, config_path, quiet=args.quiet)
            except Exception as exc:  # Keep launchd alive; next pass retries.
                if not args.quiet:
                    print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            time.sleep(interval)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
