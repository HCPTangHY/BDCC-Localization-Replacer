"""sink 判定的正反例回归测试（改动 `classify_sink` 后先跑这个）。

用法：
    python scripts/test_sink.py        # 在工具库根目录执行，退出码 0 = 全过
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.check_identifier import (  # noqa: E402
    DANGER,
    SAFE,
    TEXT_CALL_ARG_SPEC,
    UNKNOWN,
    classify_sink,
)

#: (源码行, 原文, 外层函数名, 期望档位)
CASES = [
    # 比较 / 赋值 / 下标：代码标识
    ('if(state == "after_sex"):', 'after_sex', '', DANGER),
    ('if(fluidID == "Water"):', 'Water', '', DANGER),
    ('\tsceneID = "ERROR"', 'ERROR', '', DANGER),
    ('\tvar m = FEATURE_TO_COMMAND["vibrate"]', 'vibrate', '', DANGER),
    ('\thasItemID("StockWhip")', 'StockWhip', '', DANGER),
    ('\tvar f = preload("res://a.png")', 'res://a.png', '', DANGER),
    # 显示文本：不该告警
    ('\troomName = "Bio-lab"', 'Bio-lab', '', SAFE),
    ('\tpanel.name = "Room"', 'Room', '', SAFE),
    ('\treturn "TiTS"', 'TiTS', 'getPillName', SAFE),
    ('\tvar f = load("res://Titillium-Regular.otf")', 'res://Titillium-Regular.otf', '', SAFE),
    ('\tsaynn("Hello there")', 'Hello there', '', SAFE),
    ('\tprint("debug msg")', 'debug msg', '', SAFE),
    # 字典键：首参 danger，默认值 unknown
    ('\tvar v = toyData.get("Devices", {})', 'Devices', '', DANGER),
    ('\tvar v = toyData.get("type", "Vibrate")', 'Vibrate', '', UNKNOWN),
    # 赋值目标先剔下标
    ('\tnotFit[slaveID] = "x"', 'x', '', UNKNOWN),
    ('\treturn "ERROR"', 'ERROR', 'getItemID', DANGER),
    # 文案函数：前两个实参是文案，之后是 action id
    ('\taddButton("Name", "Why is he called like that", "name")', 'Name', '', SAFE),
    ('\taddButton("Name", "Why is he called like that", "name")',
     'Why is he called like that', '', SAFE),
    ('\taddButton("Name", "Why is he called like that", "name")', 'name', '', DANGER),
    ('\taddButton("Continue", "See what happens next", "continue")', 'continue', '', DANGER),
    ('\taddButtonAt(0, "Name", "tip", "method")', 'Name', '', SAFE),
    ('\taddButtonAt(0, "Name", "tip", "method")', 'tip', '', SAFE),
    ('\taddButtonAt(0, "Name", "tip", "method")', 'method', '', DANGER),
    ('\taddButtonWithChecks("Name", "tip", "method", [], checks)', 'method', '', DANGER),
    ('\taddDisabledButton("Name", "tip")', 'tip', '', SAFE),
    # 动画名：AnimationPlayer / 状态机的节点名，翻译后 play("咬") 找不到动画
    ('\ttheAnim.animName = "Bite"', 'Bite', '', DANGER),
    ('\ttheAnim.animNameKnockedDown = "KnockedDownBite"', 'KnockedDownBite', '', DANGER),
    ('\tanimPlayer.playAnimRaw(_indx, "Defeat")', 'Defeat', '', DANGER),
    ('\tanimPlayer.playAnimRaw(_indx, "Block", "", "", "", true)', 'Block', '', DANGER),
    ('\tstate_machine.travel("IDLE")', 'IDLE', '', DANGER),
    ('\tlabel.text = "Bite"', 'Bite', '', SAFE),
    # 未登记参数角色的文案函数：>=3 参只算待人工
    ('\tformat("%s and %s", a, b)', 'a', '', UNKNOWN),
]


def main() -> int:
    fails = 0
    for line, original, func, expect in CASES:
        bucket, sink = classify_sink(line, original, func)
        if bucket != expect:
            fails += 1
            print(f"FAIL expect={expect} got={bucket} [{sink}] <- {line.strip()}")
    print(f"{len(CASES) - fails}/{len(CASES)} passed; TEXT_CALL_ARG_SPEC={TEXT_CALL_ARG_SPEC}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
