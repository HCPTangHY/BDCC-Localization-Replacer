"""检查翻译词条中的疑似代码标识符。

提取出的词条偶尔会是单个单词，但实际上是多个单词拼合而成的标识符
（PascalCase 如 AbcAbc / DevTools、camelCase 如 abcAbc / lineIndex、
snake_case 如 Abc_abc / after_sex、kebab-case 如 high-security），
这类内容很可能不应被翻译（id、类名、枚举值、标签等）。

本模块扫描翻译词条目录，把所有「原文为标识符形态、且译文与原文不一致」
的词条输出到控制台，并生成一份文本报告，便于人工查证后决定是否回退。
"""

import json
import re
from pathlib import Path
from typing import List, Tuple, Union

from .consts import DIR_CHECK, DIR_TRANS
from .log import logger

#: PascalCase：大写字母开头，如 AbcAbc / DevTools / HTTPResponse
PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
#: camelCase：小写字母开头，如 abcAbc / lineIndex
CAMEL_RE = re.compile(r"^[a-z][A-Za-z0-9]*$")
#: snake_case：下划线分隔，如 Abc_abc / after_sex / SOME_CONST
SNAKE_RE = re.compile(r"^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+$")
#: kebab-case：连字符分隔，如 high-security / some-tag
KEBAB_RE = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+$")


def is_identifier_like(text: str) -> bool:
    """判断原文是否为疑似代码标识符的单个单词。

    只匹配不含空白、引号、括号、运算符等符号的纯标识符形态；
    普通的单个英文单词（Health / player / LV1）不算。
    """
    if not text or len(text) < 2:
        return False
    # 多行字符串占位符，不是标识符
    if "__NEWLINE__" in text:
        return False
    if PASCAL_RE.match(text):
        # 大写开头，且内部大小写混合（至少两个大写字母、且大写后跟小写），
        # 排除 Health 这类单个大写开头的普通单词
        if len(re.findall(r"[A-Z]", text)) < 2:
            return False
        return bool(re.search(r"[A-Z]+[a-z]", text))
    if CAMEL_RE.match(text):
        # 小写开头，且首字母之后出现大写
        return bool(re.search(r"[A-Z]", text[1:]))
    if SNAKE_RE.match(text):
        return True
    if KEBAB_RE.match(text):
        return True
    return False


def check_identifier(
    trans_path: Union[Path, str] = DIR_TRANS,
    report_path: Union[Path, str] = None,
):
    """扫描翻译词条，输出原文为标识符形态且译文与原文不一致的词条。"""
    if isinstance(trans_path, str):
        trans_path = Path(trans_path)
    if report_path is None:
        report_path = DIR_CHECK / "identifier_check.txt"
    elif isinstance(report_path, str):
        report_path = Path(report_path)

    if not trans_path.exists():
        logger.error(f"{trans_path} not exist")
        return

    total_identifier = 0  # 标识符形态词条总数
    total_translated = 0  # 其中已有译文的词条数
    total_diff = 0  # 其中原文与译文不一致的词条数
    per_file: List[Tuple[Path, int, List[dict]]] = []

    for file in sorted(trans_path.glob("**/*.json")):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
        file_diffs = []
        for item in data:
            original = item.get("original", "")
            translation = item.get("translation", "")
            if not is_identifier_like(original):
                continue
            total_identifier += 1
            if not translation:
                continue
            total_translated += 1
            if translation != original:
                total_diff += 1
                file_diffs.append(item)
        if file_diffs:
            per_file.append((file, len(file_diffs), file_diffs))

    # 控制台输出
    logger.info(
        f"identifier-like: {total_identifier} total, {total_translated} translated, "
        f"{total_diff} original != translation"
    )
    if total_diff == 0:
        logger.info("no suspicious entry found")
        return

    for file, count, diffs in per_file:
        logger.warning(f"[{count}] {file}")
        for item in diffs:
            logger.warning(
                f"  {item['original']!r} -> {item['translation']!r} "
                f"(key={item['key']}, stage={item.get('stage', '?')})"
            )

    # 生成报告文件
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "标识符形态词条检查报告",
        "=" * 60,
        f"扫描目录: {trans_path}",
        f"标识符形态词条总数: {total_identifier}",
        f"其中已有译文的: {total_translated}",
        f"其中原文与译文不一致的: {total_diff}",
        "",
    ]
    for file, count, diffs in per_file:
        lines.append(f"===== {file} ({count}) =====")
        for item in diffs:
            lines.append(f"[key={item['key']}, stage={item.get('stage', '?')}]")
            lines.append(f"  original:    {item['original']}")
            lines.append(f"  translation: {item['translation']}")
        lines.append("")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info(f"report saved to {report_path}")


if __name__ == "__main__":
    check_identifier()
