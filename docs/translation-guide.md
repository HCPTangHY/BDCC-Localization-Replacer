# BDCC 汉化文本规范（翻译 / 创译 / 代码混合文本）

面向译者与维护者。适用于 Paratranz 项目 10958 的全部词条，重点是 `Game/SexEngine/` 下
「代码与文本混在一起」的长字符串（`SexActivityBase.gd` 是典型）。

权威顺序：**技术约束 > 语义准确 > 文风**。任何文风处理都不得改变代码语义或空白结构。

---

## 1. 核心原则：拆解—重构（忘形）

不要逐词、逐句对应。先读懂原文的场面、动作、情绪，再**丢掉原文的句法**（逗号、连词、从句边界），
用中文重新组织。英文靠逗号串意群，中文该断成短句、该调换语序就调换。

> 原文：Exhausted, but satisfied with your work, you head back to the main hall, finding the others already gathered.
> ✗ 精疲力尽，但对你的工作感到满意，你回到主大厅，发现其他人已经聚集在那里。
> ✓ 你做完工作，虽然疲惫但也满足。你回到主大厅，发现其他人已经在了。

## 2. 中文文风

| 规则 | 做法 | 反例 → 正例 |
|---|---|---|
| 动词优先 | 禁止「作出/进行/造成/具有 + 抽象名词」 | 进行研究 → 详加研究 |
| 绝对主动 | 少用「被」字句 | 他不被人们接受 → 大家都不接受他 |
| 具体主语 | 用人或具体物作主语 | 恐惧笼罩着他 → 他怕得发抖 |
| 明确指代 | 把 it/that/this 落到实处 | good at it → 挤奶技术好 |
| 少「的/地」 | 形容词堆砌能省就省 | 一种令人愉悦的强烈感觉 → 一阵酥麻 |
| 意合优先 | 上下文能看懂就别用「关于/由于/当……时/和」 | 当高潮来临时 → 高潮来了 |
| 后饰优先 | 长定语后置，别头重脚轻 | 一个长得像你兄弟的陌生男人 → 一个陌生男人，长得像你兄弟 |
| 杜绝伪术语 | 不用「可读性强」「……之一」 | — |
| Furry 语境 | 可用圈内通行说法（尾巴、兽耳、发情、结、小穴、兽根等），但仍以通顺为第一 | — |

## 3. 技术硬约束（违反会导致游戏崩溃或排版崩坏）

1. **空白逐字保留**：换行、行首缩进（制表符/空格）、代码周围空格的**数量与位置**必须与原文一致。
   不做规范化、不 trim。多行数组/字典尤其注意。
2. **标识符不译**：帕斯卡/驼峰式（`SoftSlaveryPCOffer`）、枚举（`S_VAGINA`、`TYPE_NIL`、`TRIGGER_REACT`）、
   id 字符串（`id = "obey"`、`sceneID = "SlaveTPToLocScene"`、`args = [...]`、`scoreType = "sexUse"`）一律保留。
3. **BBCode 原样**：`[b] [i] [color=red] [/b] [say=avy] [/say] [sayOther] [console speed=40] [font=res://...] [table=7] [cell]` 等标记
   及参数整段保留（`[font=]` 需替换中文字体时除外，见 §5.4）。
4. **`#" 注释不译**；**只改字符串字面量**（及指引明确要求的位置，如 `addButton` 的按钮文本）。
5. **`__NEWLINE__` 是换行占位符**，原样保留，不要改成 `\n`，也不要删。
6. 表达式里的 **`"+...+`、`str(...)`、`getFlag(...)`、`RNG.pick([...])`、`replace("x","y")`** 等代码骨架保留；
   只改其中的英文文本。数组元素数、逗号、括号不能变。

## 4. `{...}` 占位符处理规则

游戏用 `GameParser` 解析 `{角色.命令}`，命令表在 `source/Util/GameParser.gd`。

| 形态 | 例子 | 处理 |
|---|---|---|
| 变格/人称代词 | `{<TOP>.You}` `{<BOTTOM>.yourHis}` `{x.youHe}` `{x.youHim}` `{x.theyre}` | **中文不需要变格**：直接换成中文（`他`/`她`/`TA`/`你`/`他的`…），或整句省略主语。**不要保留**，否则界面会打出 "his"/"you" |
| 英语屈折动词 | `{<TOP>.youVerb('ram')}` `{x.youHeVerb('grunt')}` | **连括号整体替换成中文动词**（`猛顶` / `低吼`），参数里的动词就是"该翻的那个词" |
| 含引号的函数调用 | `{x.youVerb('reach','reaches')}` `{x.nameSOrYou}` | 同上，翻引号内的英文后整体替换；`nameSOrYou` 这类无法用中文表达的（"your"/"Name's"）需改写句子绕开 |
| 纯取值、无英文输出 | `{x.name}` | 保留（输出角色名，正常可读） |
| 数字/状态标记 | `{target.isAre}` | 中文无需变位时可删除或改写 |

> 判定口诀：**这个标记在界面上会不会打出英文单词？会 → 处理掉；不会 → 保留。**

## 5. 本项目实测结论（重要）

### 5.1 各占位符在**中文包里**的实际输出

`source/Game/BaseCharacter.gd` 的代词字面量本身是词条，中文包里已译：

```
heShe() / hisHer() / hisHers() / himHer() / himselfHerself()
  -> 他 / 她 / TA / 它        ← 是中文，但**不带「的」「自己」等助词**
```

`source/Game/SexEngine/SexActivityBase.gd:2287` 的 `getNameHole()`、`getBodypartLewdDescriptionAndName()`
（`{x.penisShort}` / `{x.cum}` / `{x.foot}` / `{x.toes}` 等）候选词同样是词条，中文包里已输出
（小穴 / 肛门 / 嘴巴 / 肉棒 / 精液 / 脚 / 脚趾…）→ **占位符照原样保留，不要改成写死名词**。

`source/Util/GameParser.gd` 里的 `"you"` / `"your"` 也已译成「你」，但：

| 命令 | 中文输出 | 处理 |
|---|---|---|
| `{x.You}` `{x.you}` `{x.YouHe}` `{x.youHe}` `{x.youHim}` | 名字（玩家为「你」） | **保留** |
| `{x.yourHis}` `{x.your}` `{x.Your}` `{x.YourHis}` `{x.youHis}` | 他/她/你（NPC 的 `nameSOrYou` 还会带英文 `'s`） | **保留 + 补「的」**；`{x.your}` 建议改 `{x.youHis}的` 以免出现 `Avy's的` |
| `{x.yourself}` | 玩家=英文 `yourself`，NPC=他 | 改 `{x.youHim}自己` |
| `{x.youAre}` `{x.youAreHeIs}` `{x.isAre}` `{x.hasHave}` `{x.youWere}` … | 英文 `are/is/was` | **整段删掉**，中文不需要系动词 |
| `{x.youVerb('v')}` `{x.youHeVerb('v')}` | 英文屈折后的动词 | **连括号换成中文动词**（可保留 `RNG.pick(["猛顶","狠撞"])` 做变化），改完要再通读一遍 |

### 5.2 允许保留的

- `{x.name}`（角色名，本身可读）；
- `str(...)`、`getFlag(...)`、`RNG.pick([...])` 骨架（数组内的英文选项**可译**，但必须保持元素个数与引号）；
- `[b]`、`[/b]`、`[/say]` 等标记；
- `#` 注释里的英文（注释不译，实测 SexActivityBase 里还有 8 处 `youVerb(` 在注释中，属正常）。

### 5.3 拼接文本的语序

`"{<TOP>.You} 把肉棒插进 " + getNameHole(...) + " 里！"` 这类拼接，中文语序应让被拼接段**自然嵌在句尾或句中**，
不要把 `+ 名词 +` 放在句首造成「穴 被塞满」这种生硬结构。

### 5.4 字体标记

`[font=res://Fonts/normalconsolefont.tres]`、`[font=res://Fonts/smallconsolefont.tres]`
在中文版中替换为 `[font=res://UI/FontResources/Normal/NormalFont.tres]`（等宽中文），
其余 `[font=...]` 一律原样保留。

## 6. 函数参数规则（来自项目指引）

| 函数 | 规则 |
|---|---|
| `addButton(【译】, 【译】, 【留】)` | 前两项译，第三项（id/回调）保留 |
| `saynn(【译】)` | 整句译 |
| `setLocationName(【译】)` | 译 |
| `addCharacter(【留】)` | 保留 |
| `playAnimation(【留】, 【留】, {npc=【留】})` | 全保留 |
| `addAction(【留】, 【译】, 【译】, 【留】)` | 中间两项译 |
| `checkCharacterBusy(_checkID, 【译】, 【译】)` | 后两项译 |
| `SAVE.loadVar(var, 【留】, bool)` | 变量名与 bool 保留 |
| `entries[xxx] = { name = "【译】", desc = "【译】", actions = [["【留】", "【译】"], …] }` | 只译 name/desc/按钮文本 |

## 7. 术语表（按仓库现有译法统计得出，保持一致）

| 原文 | 译 | 说明 |
|---|---|---|
| cock / dick | 肉棒 / 鸡巴 | 高频首选「肉棒」，口语/粗俗语境用「鸡巴」 |
| cunt / pussy / slit | 穴 / 小穴 | 粗俗语境可「逼」 |
| ass / butt | 屁股 | 后穴 = tailhole / anus |
| tits / breasts | 奶子 / 乳房 | 口语「奶子」 |
| buttplug | 肛塞 | |
| strapon | 穿戴式假阳具 | |
| knot | 结 | 兽交语境专用，不译成"绳结" |
| cum / seed / jizz / semen | 精液 / 浓精 | 随机池中出现时可用「精液/浓精/白浊」保持多样性 |
| milked (verb) | 挤 / 榨 | 乳房→挤奶；睾丸→榨精 |
| womb | 子宫 | |
| orgasm | 高潮 | |
| edging | 憋着 / 悬在高潮边缘 | |
| Furry 相关 | 兽耳 / 尾巴 / 发情 | 圈内通行说法 |

## 8. 检查与验收流程

1. 改完写回 `trans/`（先备份）；
2. `bash pipeline.sh` → 必须 `parse success`（GDScript 语法校验）；
3. `check/identifier_check.txt` → danger 必须为 0；
4. BBCode 差分 → 缺失必须为 0（多出需逐条确认是有意为之）；
5. 包内抽查：`python -c "zipfile …"` 查关键词确实进包；
6. 上传 Paratranz（`--only trans --file <单文件> --force-translation`），回读核对条数与 stage。

## 9. 已知限制 / 待办

- `youVerb()` / `youHeVerb()` 依赖英文动词表，补代码无法解决，只能按 §5.1 在文本侧换成中文动词，
  换完必须通读一遍（脚本硬替容易出现"他 rams 他的结"这类语病）。
- `{x.yourself}` 对玩家会输出英文 `yourself`（`GameParser.gd` 里的字面量未译），文本侧统一改
  `{x.youHim}自己`。若以后把该字面量译成「你自己」，此规则可简化。
- `SexActivityBase` 里 6 条 `Log.printerr` 报错串（`Sex activity with ID …`、`getResistScore: …`）
  属开发者可见信息，保持英文，不译。
