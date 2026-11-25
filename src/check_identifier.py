"""检查翻译词条中可能破坏代码的译文。

提取出的词条偶尔是代码里的字面量而不是给人看的文本：id、类名、枚举值、
资源路径、状态机状态名等。这类内容一旦被翻译，游戏里就会出现「分支永不命中」
「物品查不到」「场景加载失败」这类静默故障。

判定分两层：

1. **形状筛选**（`is_identifier_like`）：原文像标识符或资源路径。只用来收窄
   「待人工」一档的噪音，不作为结论。PascalCase 如 `DevTools`、camelCase 如
   `lineIndex`、snake_case 如 `after_sex`、kebab-case 如 `high-security`
   （后者仅当段内出现数字/内部驼峰，或匹配 `zh-CN` 这类语言代码时才收）。
2. **sink 判定**（`classify_sink`）：在源码行里看字面量**左侧的落点**——
   `id=` / `sceneID=` 赋值、`== "…"` 比较、`hasItemID(` 之类的函数实参
   判为 danger；`text=` / `roomName` / `addButton(` 首个实参 / `getName()`
   返回判为 safe（只统计，不告警）；其余判为 unknown（保留人工核查）。

**文案函数的后续实参不是文案**：`addButton(text, tooltip, method, args…)` 的
第三参起是 action id（`"continue"`、`"loot"`、`"submit"`），翻译后
`match` 不到对应方法、按钮点了没反应、剧情卡死。这类字面量往往不像标识符
（纯小写单词），形状筛选抓不到，必须靠调用点参数表判 danger——
见 `TEXT_CALL_ARG_SPEC`。

源码行的取法：`.gd` 词条优先用 `context` 里的语句；`context` 为空时用 `key`
的字符偏移回读 `source/` 同名文件（偏移处即字面量，向前取行首到字面量之间
的文本作左侧）。`.tscn` 的 `key` 是行号，按行号窗口回读。

报告分四节：必须回退（danger 且 stage=1）、待确认（danger 但 stage≠1）、
空白污染（译文与原文只差空白）、待人工（形状像标识符但 sink 未识别）。
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .consts import DIR_CHECK, DIR_SOURCE, DIR_TRANS
from .log import logger

#: PascalCase：大写字母开头，如 AbcAbc / DevTools / HTTPResponse
PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
#: camelCase：小写字母开头，如 abcAbc / lineIndex
CAMEL_RE = re.compile(r"^[a-z][A-Za-z0-9]*$")
#: snake_case：下划线分隔，如 Abc_abc / after_sex / SOME_CONST
SNAKE_RE = re.compile(r"^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+$")
#: kebab-case：连字符分隔，如 high-security / some-tag
KEBAB_RE = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+$")
#: kebab 段内的代码特征：数字或内部驼峰（WoodenHorseIdle-loop / face-fuck2）
KEBAB_CODE_SEG_RE = re.compile(r"\d|[a-z][A-Z]")
#: 语言/区域代码，如 zh-CN / zh-Hans / pt-BR
LOCALE_RE = re.compile(r"^[a-z]{2,3}-(?:[A-Z]{2}|[A-Z][a-z]{3})$")
#: 字体资源路径：中文包会故意把它们换成中文字体，不算误译
FONT_PATH_RE = re.compile(r"res://.*\.(?:otf|ttf|woff2?)$", re.I)
#: 资源路径：翻译必然破坏加载
RES_PATH_RE = re.compile(r"res://")

#: 赋值目标是这些名字时，字面量是代码里的标识
DANGER_TARGET_RE = re.compile(
    r"(?i)^("
    r"tag|key|group|groups|animation|animation_name|current_animation|"
    r"path|resource|state|action|mode|slot|fluid|type_code"
    r")$"
)
#: 动画名专用：`animName` / `animNameKnockedDown` / `anim` —— 动画名必须与
#: AnimationPlayer / 状态机里的节点名逐字一致，翻译后 `play("咬")` 找不到动画，
#: 于是「站着不播放、倒地才有动画」（倒地那份 `KnockedDownXxx` 往往没被翻译）
DANGER_ANIM_TARGET_RE = re.compile(r"(?i)^anim[a-z_]*$")
#: 标识形态的目标名后缀（**区分大小写**）：camelCase 写 `ID`，snake 写 `_id`
DANGER_ID_SUFFIX_RE = re.compile(r"(?:ID|_id)$|^id$")
#: 赋值目标是这些文本属性时，翻译是安全的
SAFE_TARGET_RE = re.compile(
    r"(?i)^("
    r"text|bbcode_text|tooltip_text|hint_tooltip|label|title|description|desc|"
    r"room_name|roomname|room_description|roomdescription|show_name|showname|"
    r"name|message|msg|prompt|help_text|helptext|note|body"
    r")$"
)
#: 这些函数的**首个实参**是字典键 / 属性名，翻译了就查不到（`.get("Output", {})`）
KEY_CALL_RE = re.compile(r"(?i)^(get|has|hasall|has_all|erase|pop|pop_front|pop_back)$")
#: 这些函数的实参是 id / 路径 / 节点名 / 动画名，翻译会断
DANGER_CALL_RE = re.compile(
    r"(?i)^("
    r"hasitemid|createitem|getitem|getitemid|"
    r"getnode|hasnode|findnode|"
    r"isingroup|addtogroup|removefromgroup|getnodesingroup|"
    r"load|preload|setmeta|hasmeta|getmeta|hasmethod|"
    r"call|connect|emitsignal|travel|play|getevent|addtrigger|adduniquetrigger|"
    r"playanimraw|playanim|playattack|playattackreaction|playattackpayload"
    r")$"
)
#: 这些函数的前两个实参是给人看的文案
SAFE_CALL_RE = re.compile(
    r"(?i)^("
    r"addbutton|adddisabledbutton|addbuttonwithchecks|addbuttonwithcheck|"
    r"addunlesslate|addbuttonat|adddisabledbuttonat|"
    r"say|sayn|saynn|addtext|settext|setdeferred|"
    r"print|printerr|pusherror|pushwarning|tr|format|addline|"
    r"bbcode|appendbbcode"
    r")$"
)
#: 文案函数里「从第几个实参起是代码 id」。
#: `addButton(text, tooltip, method, args)` 第三参是 action id——翻译成
#: `addButton("继续", …, "继续")` 后 `match method` 恒不命中，按钮点了没反应、
#: 剧情停在这里；`addButtonAt(place, text, tooltip, method)` 的 method 是第四参。
#: 这类字面量通常是纯小写单词（`continue`/`loot`/`submit`），形状规则抓不到，
#: 所以必须在调用点按位置判 danger。表里没有的函数沿用「>=2 只算 unknown」。
TEXT_CALL_ARG_SPEC: Dict[str, int] = {
    "addbutton": 2,
    "addbuttonwithchecks": 2,
    "addbuttonwithcheck": 2,
    "addunlesslate": 2,
    "addbuttonat": 3,
    "adddisabledbuttonat": 3,
}
#: 返回值落点：函数名像「取显示文本」时，翻译安全
SAFE_FUNC_RE = re.compile(
    r"(?i)^_?(get|_)?("
    r"name|officialname|displayname|visiblename|pillname|effectname|"
    r"status|textforlevel|desc|description|buttondesc|butt\w*|lewd\w*|"
    r"title|label|prompt|message|tooltip|info|rank\w*|adjective\w*"
    r")"
)

#: sink 档位
DANGER = "danger"
SAFE = "safe"
UNKNOWN = "unknown"


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
    if RES_PATH_RE.search(text):
        return not FONT_PATH_RE.search(text)
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
        # GDScript 里 `-` 是减号，连字符串几乎全是显示文本
        # （high-security / Bio-lab / Face-fucking）；只有段内带数字、
        # 内部驼峰（WoodenHorseIdle-loop）或语言代码（zh-CN）才收
        if LOCALE_RE.match(text):
            return True
        return any(KEBAB_CODE_SEG_RE.search(seg) for seg in text.split("-"))
    return False


def _literal_head(text: str, size: int = 40) -> str:
    """取原文首行前若干字符，用于在源码行里定位字面量。"""
    return text.split("\n")[0][:size]


def _find_literal_index(line: str, original: str) -> int:
    """在源码行里定位字面量的起始引号位置，找不到返回 -1。"""
    head = _literal_head(original)
    for quote in ('"', "'"):
        idx = line.find(f"{quote}{head}")
        if idx >= 0:
            return idx
    return -1


def _last_segment(target: str) -> str:
    """取赋值目标最后一段标识符，如 `a.b["c"].text` -> `text`。

    先剔除字符串字面量与方括号下标，`notFit[slaveID]` 取到的是 `notFit`
    而不是下标里的 `slaveID`。
    """
    cleaned = re.sub(r"\"[^\"]*\"|'[^']*'|\[[^\]]*\]", "", target)
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", cleaned)
    return words[-1] if words else ""


def _is_danger_target(target: str) -> bool:
    """赋值目标是否意味着「这是代码里的标识」。"""
    if not target:
        return False
    if DANGER_TARGET_RE.match(target) or DANGER_ANIM_TARGET_RE.match(target):
        return True
    return bool(DANGER_ID_SUFFIX_RE.search(target))


def _count_top_level_commas(text: str) -> int:
    """数实参列表里顶层的逗号个数（字符串、括号内的逗号不算）。"""
    depth = 0
    quote = ""
    count = 0
    for ch in text:
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            count += 1
    return count


def _call_arguments(left: str) -> Tuple[str, int, str]:
    """从字面量左侧文本还原「包住它的容器」「函数名」「实参序号」。

    返回 `(callee, arg_index, opener)`：`opener` 是包住字面量的字符
    （`(` 调用 / `[` 下标或列表 / `{` 字典），`arg_index` 为 0 表示第一个实参。
    没找到未闭合的容器时返回 `("", 0, "")`。
    """
    depth = 0
    for i in range(len(left) - 1, -1, -1):
        ch = left[i]
        if ch in ")]}":
            depth += 1
        elif ch in "([{":
            if depth:
                depth -= 1
                continue
            match = re.search(r"([A-Za-z_][\w\.]*)\s*$", left[:i])
            callee = match.group(1).split(".")[-1] if match else ""
            return callee, _count_top_level_commas(left[i + 1 :]), ch
    return "", 0, ""


def _is_subscript(left: str, opener: str) -> bool:
    """`data["key"]` 是下标取值，`pick(["key"])` 只是列表字面量。"""
    if opener != "[" or not left.endswith("["):
        return False
    if len(left) < 2:
        return False
    prev = left[-2]
    return prev.isalnum() or prev in "_]"


def _classify_left(raw_left: str, original: str, func_name: str = "") -> Tuple[str, str]:
    """按「字面量左侧文本」判断落点，返回 `(档位, sink 说明)`。"""
    raw_left = raw_left.rstrip()
    callee, arg_index, opener = _call_arguments(raw_left)

    # 下标取值：data["key"] / FEATURE_TO_COMMAND["vibrate"]
    if _is_subscript(raw_left, opener):
        return DANGER, f"index:{callee}"

    left = raw_left
    # 列表里的字面量：去掉包住它的方括号/逗号再看左侧（不要吃函数左括号）
    while left.endswith(("[", ",")):
        left = left[:-1].rstrip()
    window = left[-60:]

    # 与字面量做比较：状态机、枚举、配置键
    if re.search(r"(?:==|!=|\bin)\s*$", window):
        return DANGER, "compare"

    # 赋值：看目标名
    match = re.search(r"(?::=|=)\s*$", window)
    if match:
        target = _last_segment(window[: match.start()])
        if _is_danger_target(target):
            return DANGER, f"assign:{target}"
        if SAFE_TARGET_RE.match(target):
            return SAFE, f"text:{target}"
        return UNKNOWN, f"assign:{target or '?'}"

    # 函数实参：看函数名与实参位置（`.get("键", 默认值)` 的首参是字典键）
    if opener == "(" and callee:
        if KEY_CALL_RE.match(callee):
            if arg_index == 0:
                return DANGER, f"key:{callee}"
            return UNKNOWN, f"default:{callee}"
        if DANGER_CALL_RE.match(callee):
            return DANGER, f"call:{callee}"
        if SAFE_CALL_RE.match(callee):
            spec = TEXT_CALL_ARG_SPEC.get(callee.lower())
            if spec is not None:
                # 文案函数：显示文本之后的实参是 action/method id
                if arg_index < spec:
                    return SAFE, f"text:{callee}"
                return DANGER, f"action:{callee}"
            # 未登记参数角色的文案函数只有前两个实参算文案，后面算待人工
            if arg_index <= 1:
                return SAFE, f"text:{callee}"
            return UNKNOWN, f"arg{arg_index}:{callee}"
        return UNKNOWN, f"call:{callee}"

    # 返回值：看外层函数名
    if re.search(r"\b(?:return|case|match)\b", window) or not window:
        if func_name:
            if re.search(r"(?i)id$", func_name):
                return DANGER, f"return:{func_name}"
            if SAFE_FUNC_RE.match(func_name):
                return SAFE, f"return:{func_name}"
            return UNKNOWN, f"return:{func_name}"
    return UNKNOWN, ""


def classify_sink(line: str, original: str, func_name: str = "") -> Tuple[str, str]:
    """按字面量左侧的落点判断翻译是否安全。

    返回 `(档位, sink 说明)`，档位取 `danger` / `safe` / `unknown`。
    """
    if FONT_PATH_RE.search(original):
        return SAFE, "font"
    idx = _find_literal_index(line, original)
    raw_left = line[:idx] if idx >= 0 else line
    return _classify_left(raw_left, original, func_name)


def _resolve_source_path(
    trans_file: Path, trans_root: Path, source_root: Path
) -> Optional[Path]:
    """把 `trans/a/b.gd.json` 映射到 `source/a/b.gd`。"""
    if trans_file.suffix != ".json":
        return None
    rel = trans_file.relative_to(trans_root)
    stripped = rel.with_suffix("")  # a/b.gd
    for candidate in (source_root / stripped, source_root / stripped.with_suffix("")):
        if candidate.exists():
            return candidate
    return None


def _source_text(source: Path, cache: Dict[Path, Optional[str]]) -> Optional[str]:
    """按文件缓存源码全文（`key` 偏移回读用）。"""
    if source not in cache:
        try:
            cache[source] = source.read_text(encoding="utf-8", errors="replace")
        except OSError:
            cache[source] = None
    return cache[source]


def _line_at_span(
    item: dict,
    trans_file: Path,
    trans_root: Path,
    source_root: Path,
    cache: Dict[Path, Optional[str]],
) -> Optional[Tuple[str, str]]:
    """用 `key` 的字符偏移回读源码，返回 `(整行文本, 字面量左侧文本)`。

    `.gd` 的 `key` 是 `"(开始, 结束)"` 字符偏移（不是行号）：偏移即字面量，
    多行字符串的偏移常落在开引号之后的转义处，所以偏移前一个字符是引号时
    把字面量起点左移一位，保证左侧文本里的引号是配平的。
    """
    match = re.match(r"\((\d+)", str(item.get("key", "")))
    if not match:
        return None
    source = _resolve_source_path(trans_file, trans_root, source_root)
    if source is None:
        return None
    text = _source_text(source, cache)
    if text is None:
        return None
    start = int(match.group(1))
    if start >= len(text):
        return None
    lit = start
    if lit > 0 and text[lit - 1] in "\"'":
        lit -= 1
    line_start = text.rfind("\n", 0, lit) + 1
    line_end = text.find("\n", lit)
    if line_end < 0:
        line_end = len(text)
    return text[line_start:line_end].strip(), text[line_start:lit]


def _entry_line(
    item: dict,
    trans_file: Path,
    trans_root: Path,
    source_root: Path,
    cache: Dict[Path, Optional[str]],
    line_cache: Dict[Path, List[str]],
) -> Tuple[str, str]:
    """取「含该词条原文的那一行」源码与「字面量左侧文本」；取不到返回空串。

        取法优先级：
        1. `.gd` 词条的 `context` 里直接带语句（`Function Name: xxx` 之后）；
        2. `context` 为空或语句被截断时，用 `key` 的字符偏移回读源码；
        3. `.tscn` 词条的 `context` 只有节点头，用 `key` 的起始行号回读源码。
    """
    original = item.get("original", "")
    context = item.get("context") or ""
    header = _literal_head(original)
    if not context.startswith("[node"):
        for line in context.split("\n"):
            if header and header in line:
                idx = _find_literal_index(line, original)
                left = line[:idx] if idx >= 0 else line
                return line.strip(), left
        span = _line_at_span(item, trans_file, trans_root, source_root, cache)
        return span if span is not None else ("", "")

    source = _resolve_source_path(trans_file, trans_root, source_root)
    if source is None:
        return "", ""
    lines = line_cache.get(source)
    if lines is None:
        text = _source_text(source, cache)
        lines = text.splitlines() if text else []
        line_cache[source] = lines
    match = re.match(r"\((\d+)", item.get("key", ""))
    if not match or not lines:
        return "", ""
    start = int(match.group(1))
    for line in lines[max(0, start - 2) : start + 4]:
        if header and header in line:
            idx = _find_literal_index(line, original)
            left = line[:idx] if idx >= 0 else line
            return line.strip(), left
    return "", ""


def _func_name(item: dict) -> str:
    """从 context 里取 `Function Name: xxx`。"""
    match = re.search(r"Function Name:\s*(\w+)", item.get("context") or "")
    return match.group(1) if match else ""


def _collect(trans_path: Path, source_path: Path) -> Tuple[List[dict], Dict[str, int]]:
    """扫描词条，返回命中列表与统计。"""
    text_cache: Dict[Path, Optional[str]] = {}
    line_cache: Dict[Path, List[str]] = {}
    rows: List[dict] = []
    stats = {
        "identifier": 0,
        "translated": 0,
        "diff": 0,
        "danger": 0,
        "safe": 0,
        "unknown": 0,
        "whitespace": 0,
        "no_source": 0,
    }

    for file in sorted(trans_path.glob("**/*.json")):
        # `.gd` 词条的 context 里直接带源码行，逐条判 sink 才有召回；
        # `.tscn` 词条要回读源码文件，只判标识符形态/空白污染的
        is_script = file.name.endswith(".gd.json")
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            original = item.get("original", "")
            translation = item.get("translation", "")
            identifier_like = is_identifier_like(original)
            if identifier_like:
                stats["identifier"] += 1
            if not translation:
                continue
            if identifier_like:
                stats["translated"] += 1
            if translation == original:
                continue
            if identifier_like:
                stats["diff"] += 1
            # 只差空白：译文等于原文多/少几个空格，等于没翻
            polluted = translation.strip() == original.strip()
            if polluted:
                stats["whitespace"] += 1
            if not is_script and not identifier_like and not polluted:
                continue

            func_name = _func_name(item)
            line, raw_left = _entry_line(
                item, file, trans_path, source_path, text_cache, line_cache
            )
            if line:
                bucket, sink = _classify_left(raw_left, original, func_name)
            else:
                bucket, sink = UNKNOWN, "no-source"
                stats["no_source"] += 1
            stats[bucket] += 1
            # 文本落点不告警；形状不像标识符、sink 又没识别的也不进报告
            if bucket == SAFE:
                continue
            if bucket == UNKNOWN and not identifier_like:
                continue
            if polluted and bucket != DANGER:
                sink = f"{sink},whitespace" if sink else "whitespace"
            rows.append(
                {
                    "file": file.relative_to(trans_path).as_posix(),
                    "key": item.get("key"),
                    "original": original,
                    "translation": translation,
                    "stage": item.get("stage"),
                    "bucket": bucket,
                    "sink": sink,
                    "line": line,
                    "polluted": polluted,
                    "identifier_like": identifier_like,
                }
            )
    return rows, stats


def _bucket_of(row: dict) -> str:
    """报告分节：danger 且 stage=1 才算「必须回退」。"""
    if row["bucket"] == DANGER:
        return "danger" if row["stage"] == 1 else "pending_stage"
    if row["polluted"]:
        return "pending_whitespace"
    return "unknown"


_SECTION_TITLES = {
    "danger": "【必须回退】译文覆盖了代码位置（stage=1，下次打包就会被替换）",
    "pending_stage": "【待确认】落在代码位置，但 stage≠1（暂不替换，确认后会出事）",
    "pending_whitespace": "【空白污染】译文与原文只差空白，等于没翻",
    "unknown": "【待人工】形状像标识符，sink 未识别",
}


def check_identifier(
    trans_path: Union[Path, str] = DIR_TRANS,
    report_path: Union[Path, str] = None,
    source_path: Union[Path, str] = DIR_SOURCE,
):
    """扫描翻译词条，按 sink 分档输出可能破坏代码的译文。"""
    trans_path = Path(trans_path)
    source_path = Path(source_path)
    if report_path is None:
        report_path = DIR_CHECK / "identifier_check.txt"
    else:
        report_path = Path(report_path)

    if not trans_path.exists():
        logger.error(f"{trans_path} not exist")
        return
    if not source_path.exists():
        logger.warning(f"{source_path} not exist, sink check degraded to shape only")
        source_path = trans_path / "__no_source__"

    rows, stats = _collect(trans_path, source_path)
    sections: Dict[str, List[dict]] = {
        "danger": [],
        "pending_stage": [],
        "pending_whitespace": [],
        "unknown": [],
    }
    for row in rows:
        if row["bucket"] == SAFE:
            continue
        sections[_bucket_of(row)].append(row)

    logger.info(
        f"identifier-like: {stats['identifier']} total, {stats['translated']} translated, "
        f"{stats['diff']} original != translation"
    )
    logger.info(
        f"sink: {len(sections['danger'])} danger(stage=1), "
        f"{len(sections['pending_stage'])} pending, "
        f"{len(sections['pending_whitespace'])} whitespace, "
        f"{len(sections['unknown'])} unknown "
        f"(judged {stats['danger'] + stats['safe'] + stats['unknown']}, "
        f"safe {stats['safe']}, no-source {stats['no_source']})"
    )
    if not any(sections.values()):
        logger.info("no suspicious entry found")
        return

    for name in ("danger", "pending_stage", "pending_whitespace", "unknown"):
        items = sections[name]
        if not items:
            continue
        emit = logger.warning if name == "danger" else logger.info
        emit(f"{_SECTION_TITLES[name]} — {len(items)} 条")
        for row in items:
            emit(
                f"  [{row['sink']}] {row['original']!r} -> {row['translation']!r} "
                f"({row['file']} key={row['key']} stage={row['stage']})"
            )
            if name == "danger" and row["line"]:
                emit(f"      source: {row['line'][:160]}")

    lines = [
        "标识符形态词条检查报告",
        "=" * 60,
        f"扫描目录: {trans_path}",
        f"源码目录: {source_path}",
        f"标识符形态词条总数: {stats['identifier']}",
        f"其中已有译文的: {stats['translated']}",
        f"其中原文与译文不一致的: {stats['diff']}",
        "",
        f"必须回退(danger, stage=1): {len(sections['danger'])}",
        f"待确认(danger, stage≠1): {len(sections['pending_stage'])}",
        f"空白污染: {len(sections['pending_whitespace'])}",
        f"待人工(unknown): {len(sections['unknown'])}",
        f"取不到源码行(no-source): {stats['no_source']}",
        "",
    ]
    for name in ("danger", "pending_stage", "pending_whitespace", "unknown"):
        items = sections[name]
        if not items:
            continue
        lines.append(f"===== {_SECTION_TITLES[name]} — {len(items)} =====")
        for row in items:
            lines.append(
                f"[{row['sink']}] key={row['key']} stage={row['stage']} file={row['file']}"
            )
            lines.append(f"  original:    {row['original']}")
            lines.append(f"  translation: {row['translation']}")
            if row["line"]:
                lines.append(f"  source:      {row['line']}")
            lines.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info(f"report saved to {report_path}")


if __name__ == "__main__":
    check_identifier()
