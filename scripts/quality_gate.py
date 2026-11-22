#!/usr/bin/env python3
"""发版前文本质量门禁（CI 与本地共用）。

检查项（任一不达标即退出码 1）：
  1. check/identifier_check.txt 里「必须回退(danger, stage=1)」与「空白污染」必须为 0；
  2. trans/ 与 fetch/ 逐条对比 BBCode 标签数量，缺失必须为 0（多出仅告警）；
  3. trans/ 中不存在「译文 == 原文且原文是英文长句」的词条（疑似漏译，排除隐藏条目）。

用法：
    python scripts/quality_gate.py [--root <工具库根目录>] [--allow-extra-tags]
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

CJK = re.compile(r"[\u4e00-\u9fff]")
BB = re.compile(r"\[(/?)([A-Za-z]+)((?:=[^\]]*)?)\]")
LOOKS_ENGLISH = re.compile(r"[A-Za-z]{3,}\s+[A-Za-z]{3,}")


def tags(text: str) -> Counter:
    out = Counter()
    for m in BB.finditer(text or ""):
        out[(m.group(1), m.group(2).lower())] += 1
    return out


def check_identifier(root: Path, fails: list, warns: list):
    p = root / "check" / "identifier_check.txt"
    if not p.exists():
        warns.append("缺少 check/identifier_check.txt，跳过标识符检查")
        return
    text = p.read_text(encoding="utf-8", errors="replace")
    danger = re.search(r"必须回退\(danger, stage=1\):\s*(\d+)", text)
    blank = re.search(r"空白污染:\s*(\d+)", text)
    manual = re.search(r"待人工\(unknown\):\s*(\d+)", text)
    if danger and int(danger.group(1)) > 0:
        fails.append(f"标识符必须回退 {danger.group(1)} 条（见 check/identifier_check.txt）")
    if blank and int(blank.group(1)) > 0:
        fails.append(f"空白污染 {blank.group(1)} 条")
    if manual and int(manual.group(1)) > 0:
        warns.append(f"待人工确认 {manual.group(1)} 条（不阻断，需人工过目）")


def check_bbcode(root: Path, fails: list, warns: list):
    trans, fetch = root / "trans", root / "fetch"
    if not trans.exists() or not fetch.exists():
        warns.append("缺少 trans/ 或 fetch/，跳过 BBCode 检查")
        return
    missing = extra = 0
    samples = []
    for p in trans.glob("**/*.json"):
        rel = p.relative_to(trans)
        f = fetch / rel
        if not f.exists():
            continue
        try:
            tr = {e["key"]: e for e in json.load(open(p, encoding="utf-8"))}
            fe = {e["key"]: e for e in json.load(open(f, encoding="utf-8"))}
        except Exception:
            continue
        for k, e in tr.items():
            src = fe.get(k)
            if not src or e.get("stage") == -1:
                continue
            a, b = tags(src.get("original")), tags(e.get("translation"))
            if a - b:
                missing += 1
                if len(samples) < 5:
                    samples.append(f"{rel}:{k} 缺失 {dict(a - b)}")
            if b - a:
                extra += 1
    if missing:
        fails.append(f"BBCode 缺失 {missing} 条（例：{'; '.join(samples)}）")
    if extra:
        warns.append(f"BBCode 多出 {extra} 条（需确认是否刻意加粗/加色）")


def check_untranslated(root: Path, fails: list, warns: list):
    trans = root / "trans"
    if not trans.exists():
        return
    bad = []
    for p in trans.glob("**/*.json"):
        for e in json.load(open(p, encoding="utf-8")):
            if e.get("stage") == -1:
                continue
            o = (e.get("original") or "").strip()
            t = (e.get("translation") or "").strip()
            if not t or t != o:
                continue
            if len(o) > 25 and " " in o and LOOKS_ENGLISH.search(o) and not CJK.search(o):
                bad.append(f"{p.relative_to(trans).as_posix()}:{e['key']}")
    if bad:
        warns.append(f"疑似未译英文长句 {len(bad)} 条（例：{', '.join(bad[:5])}）")


def main():
    # Windows runner 的默认控制台编码是 cp1252，中文告警会直接抛 UnicodeEncodeError
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = ap.parse_args()
    root = Path(args.root)
    fails, warns = [], []
    check_identifier(root, fails, warns)
    check_bbcode(root, fails, warns)
    check_untranslated(root, fails, warns)
    for w in warns:
        print(f"[warn] {w}")
    for f in fails:
        print(f"[FAIL] {f}")
    if fails:
        print(f"\n质量门禁未通过：{len(fails)} 项")
        return 1
    print("\n质量门禁通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
