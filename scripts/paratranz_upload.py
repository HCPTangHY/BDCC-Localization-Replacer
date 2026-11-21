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
  --force-translation  译文回填改用 force=true（默认 false）。只有修错配/纠错这类一次性修复才用，
                       且务必配合 --file 限定到单个文件——force=true 会覆盖人工编辑过的译文。
  --strict             上传后计数核对不一致时以退出码 2 结束（默认只告警）

上传后会自动做一次计数核对（见 verify_counts）：ParaTranz 对每次原文更新会返回
revision{insert,update,remove}，这里用本地 fetch/（上传前快照）与本次载荷按 key 估算期望值，
两者对不上就告警——这是发现「key 换代后译文/原文错位」这类事故的最便宜信号。
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


def expected_counts(fetch_file: Path, payload_file: Path) -> dict:
    """用本地快照(fetch/)与本次载荷按 key 估算 ParaTranz 会报的 insert/update/remove。

    - insert: 载荷里有、快照里没有的 key
    - remove: 快照里有、载荷里没有的 key
    - update: 两边同 key 但原文不同的条目
    快照缺文件时按「全部新增」估算（首次入库）。
    """
    old = {i["key"]: i.get("original") for i in load_json(fetch_file)} if fetch_file.exists() else {}
    new = {i["key"]: i.get("original") for i in load_json(payload_file)}
    old_keys, new_keys = set(old), set(new)
    return {
        "insert": len(new_keys - old_keys),
        "remove": len(old_keys - new_keys),
        "update": sum(1 for k in new_keys & old_keys if new[k] != old[k]),
        "baseline": fetch_file.exists(),
    }


def verify_counts(rows: list[dict], tolerance: int = 2) -> tuple[list[dict], int]:
    """把接口返回的 revision 计数与本地期望值比对，返回 (不一致清单, 参与核对条数)。

    ParaTranz 的计数口径未在文档里写明，因此留 tolerance 容差（默认 2 条）：
    超差才当作异常，用于发现 key 换代后原文/译文错位、旧 key 未清理一类的事故。
    """
    checked, bad = 0, []
    for r in rows:
        got, exp = r.get("got"), r.get("expected")
        if not got or not exp:
            continue
        checked += 1
        diffs = {k: got[k] - exp[k] for k in ("insert", "update", "remove")}
        if any(abs(v) > tolerance for v in diffs.values()):
            bad.append({**r, "diffs": diffs})
    return bad, checked


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
    verify_rows: list[dict] = []

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
                if revision:
                    verify_rows.append({
                        "file": rel,
                        "expected": expected_counts(fetch_root / rel, local),
                        "got": {k: revision.get(k) or 0 for k in ("insert", "update", "remove")},
                    })
                if resp.get("file", {}).get("id"):
                    by_name[rel] = resp["file"]
            details.append({"file": rel, "action": "update" if info else "create"})
            if len(details) % 25 == 0:
                print(f"  change {len(details)}/{len(items)} …")
        report["steps"]["change"] = {"stats": stats, "details": details}
        print(f"change 完成: {stats}")

    # ---- 2. trans: 译文回填 ----
    if args.only in ("all", "trans"):
        if args.force_translation:
            print("!! 译文回填使用 force=true：会覆盖人工编辑过的译文，请确认已用 --file 限定范围")
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
                data={"force": "true" if args.force_translation else "false", "skip": "false"},
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

    # ---- 4. 计数核对：接口 revision 与本地期望 ----------------
    bad, checked = verify_counts(verify_rows)
    if checked:
        print(f"计数核对: 已核对 {checked} 个文件，异常 {len(bad)} 个")
        for r in bad[:20]:
            exp, got, d = r["expected"], r["got"], r["diffs"]
            print(
                f"  [异常] {r['file']}\n"
                f"         期望 insert={exp['insert']} update={exp['update']} remove={exp['remove']}"
                f"（基线{'有' if exp['baseline'] else '无'}）\n"
                f"         实际 insert={got['insert']} update={got['update']} remove={got['remove']}"
                f"  差 {d['insert']:+d}/{d['update']:+d}/{d['remove']:+d}"
            )
        if len(bad) > 20:
            print(f"  …其余 {len(bad) - 20} 个见 report")
        report["verify"] = {"checked": checked, "mismatches": bad}
    else:
        print("计数核对: 没有 revision 返回（dry-run 或全部 hashMatched），跳过")

    await client.close()
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"报告写入 {args.report}")
    if bad and args.strict:
        print("--strict 生效：计数核对存在异常，退出码 2")
        return 2
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
    p.add_argument("--force-translation", action="store_true",
                   help="译文回填用 force=true（默认 false）。仅用于修错配等一次性纠错，务必配合 --file")
    p.add_argument("--strict", action="store_true", help="计数核对异常时以退出码 2 结束")
    p.add_argument("--report", default="upload_report.json")
    args = p.parse_args()
    started = time.time()
    code = asyncio.run(run(args))
    print(f"耗时 {time.time() - started:.1f}s")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
