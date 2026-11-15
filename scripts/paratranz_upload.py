#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 BDCC-Localization-Replacer 的产物上传到 ParaTranz。

三步（顺序固定）：
  1. change/      → update_file(incremental=True) 或 create_file   （更新原文，新 key 入库）
  2. trans/       → upload_file_translation(force=False)           （回填译文，含迁移过来的旧译）
  3. deprecated/  → 过时/ 下 update_file(incremental=True) 或 create_file（归档，只增不删）

依赖 paratranz-mcp 里的客户端实现，用它的 venv 跑：

  cd E:/Projects/Games/BDCC/BDCC-Localization-Replacer
  PARATRANZ_API_TOKEN=xxx \
  E:/Projects/AI/MCPs/paratranz-mcp/.venv/Scripts/python.exe scripts/paratranz_upload.py --dry-run

常用参数：
  --dry-run            只打印计划，不发写请求
  --only change|trans|deprecated   只做其中一步
  --file <substr>      只处理路径包含该子串的文件（先做单文件试传）
  --limit N            最多处理 N 个文件
  --report out.json    处理明细写入 JSON
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

DEFAULT_MCP_DIR = "E:/Projects/AI/MCPs/paratranz-mcp"


def load_client(mcp_dir: str):
    """从 paratranz-mcp 导入客户端（复用它的重试/连接池实现）。"""
    sys.path.insert(0, mcp_dir)
    try:
        import paratranz_mcp  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            f"无法导入 paratranz_mcp（{mcp_dir}）：{exc}\n"
            "请改用 paratranz-mcp 的 venv 运行本脚本。"
        ) from exc
    if not os.environ.get("PARATRANZ_API_TOKEN"):
        raise SystemExit("缺少环境变量 PARATRANZ_API_TOKEN")
    return paratranz_mcp


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def needs_translation_backfill(trans_file: Path, trans_root: Path, fetch_root: Path) -> bool:
    """trans 与 fetch 在 key/译文/stage 上有差异，且存在可推的非空译文。"""
    rel = trans_file.relative_to(trans_root)
    fetch_file = fetch_root / rel
    cur = {i["key"]: i for i in load_json(trans_file)}
    old = {i["key"]: i for i in load_json(fetch_file)} if fetch_file.exists() else {}
    for key, item in cur.items():
        if not item.get("translation"):
            continue
        prev = old.get(key)
        if prev is None or prev.get("translation") != item["translation"] or prev.get("stage") != item["stage"]:
            return True
    return False


async def run(args) -> int:
    mod = load_client(args.mcp_dir)
    client = mod._make_client()  # 共享实例，自带重试
    root = Path(args.root).resolve()
    change_root, trans_root, dep_root = root / "change", root / "trans", root / "deprecated"
    fetch_root = root / "fetch"
    project = args.project

    project_files = await client.request("GET", f"/projects/{project}/files")
    by_name = {f["name"]: f for f in project_files}
    print(f"项目内文件 {len(by_name)} 个")

    report = {"project": project, "dry_run": args.dry_run, "steps": {}}

    def pick(files: list[Path], filter_sub: str | None) -> list[Path]:
        if filter_sub:
            files = [f for f in files if filter_sub in f.as_posix()]
        return files[: args.limit] if args.limit else files

    async def call(method: str, path: str, **kwargs):
        if args.dry_run:
            return {"dry_run": True, "method": method, "path": path}
        result = await client.request(method, path, **kwargs)
        if args.sleep > 0:
            await asyncio.sleep(args.sleep)
        return result

    # ---- 1. change: 原文 ----
    if args.only in ("all", "change"):
        items = pick(sorted(change_root.rglob("*.json")), args.file)
        stats = {"update": 0, "create": 0, "skipped": 0, "insert": 0, "remove": 0}
        details = []
        for local in items:
            rel = local.relative_to(change_root).as_posix()
            info = by_name.get(rel)
            if info:
                resp = await call(
                    "POST",
                    f"/projects/{project}/files/{info['id']}",
                    data={"skip": "false", "incremental": "true"},
                    files={"file": (local.name, local.read_bytes(), "application/octet-stream")},
                )
                stats["update"] += 1
            else:
                parent = rel.rsplit("/", 1)[0] + "/" if "/" in rel else ""
                resp = await call(
                    "POST",
                    f"/projects/{project}/files",
                    data={"path": parent} if parent else None,
                    files={"file": (local.name, local.read_bytes(), "application/octet-stream")},
                )
                stats["create"] += 1
            if isinstance(resp, dict):
                if resp.get("status") == "hashMatched":
                    stats["skipped"] += 1
                revision = resp.get("revision") or {}
                stats["insert"] += revision.get("insert") or 0
                stats["remove"] += revision.get("remove") or 0
                if resp.get("file", {}).get("id"):
                    by_name[rel] = resp["file"]
            details.append({"file": rel, "action": "update" if info else "create"})
            if len(details) % 25 == 0:
                print(f"  change {len(details)}/{len(items)} …")
        report["steps"]["change"] = {"stats": stats, "details": details}
        print(f"change 完成: {stats}")

    # ---- 2. trans: 译文回填 ----
    if args.only in ("all", "trans"):
        candidates = sorted(trans_root.rglob("*.json"))
        if args.file:
            candidates = [f for f in candidates if args.file in f.as_posix()]
        todo = []
        for f in candidates:
            rel = f.relative_to(trans_root).as_posix()
            if rel in by_name and needs_translation_backfill(f, trans_root, fetch_root):
                todo.append((f, rel))
        if args.limit:
            todo = todo[: args.limit]
        stats = {"uploaded": 0, "missing": 0}
        details = []
        for f, rel in todo:
            info = by_name[rel]
            resp = await call(
                "POST",
                f"/projects/{project}/files/{info['id']}/translation",
                data={"force": "false", "skip": "false"},
                files={"file": (f.name, f.read_bytes(), "application/json")},
            )
            stats["uploaded"] += 1
            details.append({"file": rel, "result": "ok" if isinstance(resp, dict) else "empty"})
            if len(details) % 25 == 0:
                print(f"  trans {len(details)}/{len(todo)} …")
        report["steps"]["trans"] = {"stats": stats, "details": details}
        print(f"trans 完成: {stats}")

    # ---- 3. deprecated: 归档到 过时/ ----
    if args.only in ("all", "deprecated"):
        items = pick(sorted(dep_root.rglob("*.json")), args.file)
        stats = {"update": 0, "create": 0}
        details = []
        for local in items:
            rel = local.relative_to(dep_root).as_posix()
            target = f"过时/{rel}"
            info = by_name.get(target)
            if info:
                await call(
                    "POST",
                    f"/projects/{project}/files/{info['id']}",
                    data={"skip": "false", "incremental": "true"},
                    files={"file": (local.name, local.read_bytes(), "application/octet-stream")},
                )
                stats["update"] += 1
            else:
                parent = target.rsplit("/", 1)[0] + "/"
                resp = await call(
                    "POST",
                    f"/projects/{project}/files",
                    data={"path": parent},
                    files={"file": (local.name, local.read_bytes(), "application/octet-stream")},
                )
                stats["create"] += 1
                if isinstance(resp, dict) and resp.get("file", {}).get("id"):
                    by_name[target] = resp["file"]
            details.append({"file": target, "action": "update" if info else "create"})
        report["steps"]["deprecated"] = {"stats": stats, "details": details}
        print(f"deprecated 完成: {stats}")

    await client.close()
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"报告写入 {args.report}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="上传 BDCC 汉化产物到 ParaTranz")
    p.add_argument("--project", type=int, default=10958)
    p.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    p.add_argument("--mcp-dir", default=os.environ.get("PARATRANZ_MCP_DIR", DEFAULT_MCP_DIR))
    p.add_argument("--only", choices=["all", "change", "trans", "deprecated"], default="all")
    p.add_argument("--file", default=None, help="只处理路径包含该子串的文件")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--sleep", type=float, default=0.15, help="每次写请求后的间隔秒数（限流用）")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--report", default="upload_report.json")
    args = p.parse_args()
    started = time.time()
    code = asyncio.run(run(args))
    print(f"耗时 {time.time() - started:.1f}s")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
