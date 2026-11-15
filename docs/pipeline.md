# BDCC 汉化流水线维护手册

面向维护者。玩家向说明见发布库 `README.md`。

流程固定为：**同步上游 → 提取 → 合并旧译 → 上传 Paratranz → 替换 → 校验 → 打包 → 发版**。
顺序不要调换：替换必须在「拿到最新译文」之后，校验必须在「打包」之前。

---

## 1. 仓库与环境

| 位置 | 角色 | 远端 |
|---|---|---|
| `BDCCChineseLocalization` | 发布库：子模块 + C# 编排器 + GitHub Actions | `chinese-liliths-throne/BDCCChineseLocalization` |
| └ `BDCC` | 游戏源码 fork（分支 `chinese`） | `CKRainbow/BDCC`，`upstream = Alexofp/BDCC` |
| └ `BDCC-Localization-Replacer` | Python 提取/合并/替换工具 | `HCPTangHY/BDCC-Localization-Replacer` |
| └ `Paratranz.NET` | Paratranz API 客户端（只用下载导出包） | `Mochacola500/Paratranz.NET` |

本机常用路径：

- 发布库：`E:\Projects\Games\BDCC\BDCCChineseLocalization`
- 源码 fork：`E:\Projects\Games\BDCC\BDCC`
- 工具（独立开发副本）：`E:\Projects\Games\BDCC\BDCC-Localization-Replacer`

依赖：Python 3.11（`ujson / loguru / json5 / gdtoolkit==3.*`，`setuptools<81`）、.NET 8 SDK、Godot 3.6（仅打包需要）、`git`、Paratranz API Token。

```bash
# 工具仓库建虚拟环境
cd BDCC-Localization-Replacer
python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -r requirements.txt

# Paratranz Token 只从环境变量取（pipeline.sh 已改为强制 env）
export PARATRANZ_TOKEN=xxxxxxxx
```

---

## 2. 目录语义

`src/consts.py` 定义全部路径，`ROOT` 为工具仓库根。

| 目录 | 内容 | 谁生成 | 进 git |
|---|---|---|---|
| `source/` | `BDCC` 源码整树拷贝 | 手工 / `Program.cs` | 否 |
| `fetch/` | Paratranz 导出包（`utf8/`）的拷贝 = 线上当前译文 | `Program.cs` / 手工 | 否 |
| `trans/` | 本次全量提取结果（Paratranz 词条格式） | `extract()` | 否 |
| `change/` | 与 `fetch/` 有差异的文件 → **要上传 Paratranz 的只有这些** | `update()` | 否 |
| `deprecated/` | 源码中已消失但有译文的词条（`stage=9`） | `update()` | 否 |
| `check/` | 标识符误译报告 | `check_identifier()` | 否 |
| `output/` | 替换完成、可直接打包的源码 | `replace_translation()` | 否 |
| `Artifact/` | Paratranz 导出 zip 及解包结果（发布库内） | `Program.cs` | 否 |

词条字段（与 Paratranz 一致）：

```json
{"key": "(1234, 1256)", "original": "原文", "translation": "译文", "stage": 1, "context": "所在语句 / [node ...] 头"}
```

`key` 是**位置型**标识（`.gd` 为字符偏移 `(start,end)`，`.tscn` 为行号 `(start_line,end_line)`），源码一改就全变。
因此**译文只能按 `original` 文本对齐**，`key` 不能当主键、也不能用来做增量上传。

`stage` 语义（`src/replace.py: is_replacable`）：

| stage | 含义 | 替换行为 |
|---|---|---|
| `0` | 未翻译 | 不替换，保留英文 |
| `1` | 已确认 | 无条件替换（即使译文为空） |
| `9` | 过时 | 进 `deprecated/`，不替换 |
| 其他 | 已翻译未确认等 | 译文非空才替换 |

`__NEWLINE__` 占位符：存储期把 `\n` 换成它，替换时按目标文件类型还原（脚本字符串 vs 场景文本属性）。

---

## 3. 同步上游

```bash
# 1) 源码 fork 合并上游
cd E:\Projects\Games\BDCC\BDCC
git fetch upstream
git checkout chinese
git merge upstream/main     # 冲突多为文本/场景行号

# 2) 发布库子模块指向最新
cd E:\Projects\Games\BDCC\BDCCChineseLocalization
git submodule update --remote
```

`pipeline.sh` 的前两步就是上面这两条，并额外做下一步。

### 3.1 把子模块工作树拉回与远程一致（必须先做）

`git submodule update --remote` 只移动指针，**不会清掉子模块里的脏文件**。而 Godot（.NET）打开过项目就会自动改 `.import`、`.tres`、`project.godot`（`[mono] assembly_name`）等，这些改动会被当成源码提取，实测产生过「原文是中文」的词条。所以提取前必须：

```bash
cd E:\Projects\Games\BDCC\BDCCChineseLocalization
git submodule update --init --recursive --remote
git -C BDCC fetch --quiet origin
git -C BDCC reset --hard origin/chinese     # 分支名可用 SUBMODULE_BRANCH 覆盖
git -C BDCC status --porcelain              # 必须为空，否则停下处理
```

注意：`reset --hard` 会丢弃 BDCC 工作树里**所有**未提交改动。汉化侧需要的代码补丁（字体、场景、版本号占位符等）必须提交在 `chinese` 分支上，不能只留在工作树里，否则这一步会把它清掉。

**同步后检查 `source/` 是否与 fork 一致**，否则提取的是旧源码：

```bash
cd E:\Projects\Games\BDCC
robocopy "BDCC" "BDCC-Localization-Replacer\source" /MIR /XD ".git" /NFL /NDL /NJH /NP
diff -q BDCC\UI\MainMenu\MainMenu.gd BDCC-Localization-Replacer\source\UI\MainMenu\MainMenu.gd
```

不要用 `shutil.copytree` 拷整个 `BDCC`：本地是完整克隆，`.git` 有 GB 级；CI 里子模块的 `.git` 是文件所以无所谓。

---

## 4. 提取（`src/extract.py`）

```bash
cd BDCC-Localization-Replacer
PYTHONPATH= ./.venv/Scripts/python.exe -c "from src.extract import extract; from src.consts import DIR_SOURCE, DIR_TRANS; extract(DIR_SOURCE, DIR_TRANS)"
```

- `.gd`：gdtoolkit 解析语法树，取字符串字面量的**字符区间**；跳过 `get_node / get_node_or_null / has / Color / preload / load / playAnimation` 的参数，`emit_signal` 参数 ≤1、`connect` 参数 ≤3 也跳过；`context` 记录所在语句（函数内会加 `Function Name: xxx`）。
- `.tscn`：逐行扫 `text / Text / Name / Description / tooltip / title / Message / Desc` 等属性，取引号内的值，`context` 为 `[node ...]` 头。
- 没有可提取字符串的文件**不产出 json**——所以 `fetch` 里有、`trans` 里没有的文件会被 `update()` 判为「整个文件消失」，见第 9 节。
- 耗时参考：3300 个 `.gd` + 653 个 `.tscn` ≈ 63 s。

---

## 5. 合并旧译（`src/update.py`）

```bash
PYTHONPATH= ./.venv/Scripts/python.exe -c "from src.update import update; from src.consts import *; update(DIR_TRANS, DIR_FETCH, DIR_DEPRECATED, DIR_CHANGE)"
```

`update(trans, fetch, deprecated, change)` 以 `original` 为键：

1. 同一 `original` 在 `fetch` 与 `trans` 中出现次数相同 → 逐条搬运译文与 `stage`；
2. 次数不同 → 按出现序复用已有译文，全部标 `stage=1`；
3. `fetch` 有、`trans` 无 → 原文≠译文的词条进 `deprecated/` 并标 `stage=9`；
4. `fetch` 有该文件、`trans` 没有 → 整个文件拷进 `deprecated/`（源码删文件或该文件已无可提取文本）；
5. 自动填原文：无译文且原文含 `_`（疑似 id / 枚举值）或不含 `__NEWLINE__` 的 `res://` 路径 → 填原文并置 `stage=1`，防止译者翻掉；
6. 判定有差异（`is_diff`、或 `key`/`original` 集合变化）→ 复制到 `change/`；`trans` 中新增的文件也进 `change/`。

`translate_old()` 用 `update_deprecated()`：只写 `deprecated/`，不产出 `change/`，用于「我没打算回传 Paratranz」的场合。

耗时参考：3406 个 json ≈ 57 s。

---

## 6. 标识符检查（`src/check_identifier.py`）

```bash
PYTHONPATH= ./.venv/Scripts/python.exe -c "from src.check_identifier import check_identifier; check_identifier()"
```

扫 `trans/`，把「原文形如 PascalCase / camelCase / snake_case / kebab-case **且译文≠原文**」的词条列到控制台并写 `check/identifier_check.txt`。
这类原文通常是 id、类名、枚举值、标签，翻译了会崩游戏或让逻辑失效。
`stage=1` 且译文=原文的自动填充条目不算（它们本来就不该翻）。

已知误报：连字符自然词（`Self-fuck`、`average-sized`、`Power-trip`）会被 kebab 规则抓到，需人工判断，不要盲改。

---

## 7. 上传 Paratranz（项目 ID `10958`）

只有 `change/` 需要上传。下载侧是自动的（`ParatranzClient.DownloadArtifactAsync`），上传侧目前靠 MCP 或网页。

```bash
# 取最新导出（Program.cs 里 CI 做的同一步）
# MCP: generate_artifact(project_id=10958) → 等约 30–60 s → download_artifact(project_id=10958, dest_dir=<本地目录>)
# 解包后 utf8/ 就是 fetch/ 的内容
```

`paratranz` MCP 里四个相关工具，语义不同别混用：

| 工具 | 语义 | 用途 |
|---|---|---|
| `update_file(project_id, file_id, file_path, incremental=True)` | **只更新原文**，不动译文；`incremental=True` 时新文件里没有的词条不删；无变化返回 `hashMatched` | 把 `change/` 合并进项目（**主用**） |
| `create_file(project_id, path="UI/MainMenu/", file_path)` | 新建文件；`path` 是目录，文件名取 `file_path` 的 basename | 仅源码新增文件 |
| `upload_file_translation(project_id, file_id, file_path, force=False)` | 上传**译文**，默认只覆盖未被人工编辑的词条 | 本地/离线译文回填，**不是**新词条入库 |
| `list_files(project_id)` | 全量文件列表（含 `id`） | 取「路径 → file_id」映射 |

上传步骤：

1. `list_files(10958)` 建映射（约 3800 条，脚本处理，别整份拉进对话）；
2. 先分类：`change/` 中相对 `fetch/` 不存在的 → `create_file`；其余 → `update_file(..., incremental=True)`；
3. `deprecated/` 是核对清单，不自动上传；要不要在项目里挪进 `过时/` 由人工决定（`update()` 会跳过含「过时」的路径）；
4. **禁止整树重传**：`key` 是位置型，整树覆盖会重置译者进度与审校状态。

项目内的文件命名与工具产物一致（`UI/MainMenu/MainMenu.gd.json` / `*.tscn.json`），过时词条放在项目 `过时/` 目录。

### 7.1 `deprecated/` → 项目 `过时/` 目录（只增不覆盖）

`deprecated/` 是「源码里已不存在、但线上有译文」的词条（`stage=9`），归档到项目的 `过时/` 下，路径保持与导出包一致：`deprecated/UI/MainMenu/MainMenu.gd.json` → `过时/UI/MainMenu/MainMenu.gd.json`。

**硬规则：绝不覆盖 `过时/` 里已有的文件或词条。**

1. 先 `list_files(10958)` 取当前路径集合（含 `过时/` 下的）；
2. `过时/<相对路径>` **不存在** → `create_file(project_id=10958, path="过时/<目录>/", file_path=<deprecated 里的本地 json>)`；
3. `过时/<相对路径>` **已存在** → 不调用 `update_file`、不覆盖，改用带日期的文件名**另建**一个：`<原名>.<YYYYMMDD>.json`（如 `MainMenu.gd.20261114.json`）；该名字也存在时追加序号 `-2`、`-3`；
4. 禁止对 `过时/` 内文件做 `update_file`（会替换原文、冲掉归档）、删除或移动。

`deprecated/` 里的条目带着原有译文和 `stage=9`，作用是存档「已下线文本」；`src/update.py` 在后续运行时跳过路径含「过时」的文件，因此归档不会回流进 `fetch/`、也不会被当成本次提取结果。

上传顺序：先 `change/`（`update_file` / `create_file`），再 `deprecated/` 归档，最后再考虑更新项目 `extra.version`。归档这一步**只增不删**，多传不会破坏任何东西，漏传只会少一份存档。

本轮 0.4.0 的 `deprecated/`：42 个文件（1 个整文件拷贝 + 41 个含 `stage=9` 的部分词条），共 147 条 `stage=9`。

---

## 8. 替换、校验、打包、发版

```bash
# 替换 + 语法校验（translate_new 的后半段）
PYTHONPATH= ./.venv/Scripts/python.exe -c "
from src.replace import replace_translation
from src.parse import lint_check
from src.consts import DIR_SOURCE, DIR_TRANS, DIR_OUTPUT
replace_translation(DIR_SOURCE, DIR_TRANS, DIR_OUTPUT)
lint_check(DIR_OUTPUT)"
```

- `replace_translation`：整树拷贝 `source/ → output/`，按 `key` 拼接译文；`.tscn` 用原文子串替换；`GameUI*` 的斜体字体统一改指粗体（Godot 3.5 中文斜体不显示）；字体文件替换为 `SourceHanSansCN-Regular/Bold.otf → Titillium-Regular/Bold.otf`、`Bailu_Qiaoli.ttf → Chocolate Covered Raindrops BOLD.ttf`。
- `lint_check`：gdtoolkit 对每个 `.gd` 做语法校验，`UnexpectedInput` 直接抛异常——**宁可不发版，也不发起不来的包**。

一键跑完整条（本地等价于 CI 的 translate 阶段，**不含上传**）：

```bash
cd BDCCChineseLocalization
export PARATRANZ_TOKEN=xxx     # 必填，脚本会校验
# 可选: PARATRANZ_PROJECT(默认 10958)、TRANSLATION_VERSION(默认 1.0.0)、SUBMODULE_BRANCH(默认 chinese)、PYTHON
bash pipeline.sh
```

`pipeline.sh` 四步：① `git submodule update --init --recursive --remote`；② `BDCC` 执行 `reset --hard origin/chinese` 并校验工作树干净（`.mono/ .import/ .godot/` 除外）；③ 挑 Python 解释器——子模块里有 `BDCC-Localization-Replacer/.venv` 就用它（用 `cygpath -w` 转成 Windows 原生路径，.NET 起进程认不了 `/e/...`），否则用 `$PYTHON` / 系统 `python`；④ `dotnet run … -- Translate`。

本地前提：子模块里的 `.venv` 要先建好并装依赖（`python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt`）；CI 里是 `pip install -r requirements.txt` 装到系统 python。

`Program.cs Translate` 做的事：删/重建 `Artifact/` → 下载导出包 → 解到 `Artifact/utf8` → 拷成工具侧 `fetch/`、拷 `BDCC` 成 `source/` → `python main.py` → 把 `output/UI/MainMenu/MainMenu.gd` 里的 `TRANSLATION_VERSION_HERE` 换成 `-v` 版本 → 压 `BdccChineseLocalization.zip`。

CI（`.github/workflows/runner.yml`）：

- 触发：`schedule`（每周一 `30 12 * * 1`；每 6 小时的 `30 0/6 * * *` 已在 `afa98b1` 注释掉）、`workflow_dispatch`、推送 `v*` tag；
- `translate`（windows-latest，dotnet 8 + Python 3.11）→ 五个 Godot 3.6 构建 job（Windows / Linux / MacOS / Web(可失败) / Android）→ `release`；
- 发布：定时/手动 → 预发布 `tag: bdcc.YY.MM.DD`；`v*` tag → 正式版，release note 由 `marko` 从 `README.md` 最后一段列表抽最新条目生成，并触发 Jekyll 发布页。

版本号：`chs-x.y.z` + `a/b/r`；完整版号 `{游戏版本}-chs-{汉化版本}`，如 `v0.3.2-chs-1.0.0a`。破坏性更新归零 `1.0.0a`，小修小补第一位 +1，常规更新第二位 +1，恶性问题热修末位 +1。

---

## 9. 坑与检查清单

- **`BDCC` 工作树里的改动基本都是 Godot（.NET）打开编辑器自动产生的**：`.import`、`.mono/`、`project.godot` 的 `[mono] assembly_name`、`.tres` 重写等，不用提交，也不必当成源码污染——但**提取前要按 3.1 节把它们清掉**（`reset --hard origin/chinese` + `status --porcelain` 必须为空）。真正要盯的是文本改动：实测 `UI/LaunchScreen/LaunchScreen.tscn` 曾多出一行 `window_title = "请确认..."`，会被提取成「原文是中文」的新词条；撤销后 `change/` 从 2 个文件降到 1 个。
- **`fetch/` 必须是最新导出**。用手工留存的旧 zip 当基线，`change/` 会虚高（实测旧基线 190 个文件 → 换最新导出后只剩 2 个）。
- **`fetch` 有、`trans` 没文件的条目会整文件进 `deprecated/`**，多数是源码删文件，也可能是该文件已无可提取文本——上传前人工看一眼。
- **不要用 `key` 做主键或增量依据**：位置型，每次提取都变；只按 `original` 对齐。
- **版本号占位符在译文里，不在源码里**：原文 `"Version: "+GlobalRegistry.getGameVersionString()` 在 Paratranz 的译文是 `"版本：TRANSLATION_VERSION_HERE"`（`stage=1`），`replace_translation` 写进 `output/` 后由 `Program.cs` 把这个字面量换成 `-v` 传入的版本。因此 **`-v` 必须传真实版本号**；不传（默认 `1.0.0`）包里就会写死 `1.0.0`，漏替换时则会出现字面量 `TRANSLATION_VERSION_HERE`。验证方式：`grep -n versionLabel.text output/UI/MainMenu/MainMenu.gd`。
- **Token 只从环境变量取**；历史上 `pipeline.sh` 明文提交过 token，应视为已泄露并在 Paratranz 侧轮换。
- **工具改动要回推子模块指针**：`BDCC-Localization-Replacer` 提交并推送后，发布库要 `git add BDCC-Localization-Replacer` 更新 commit，否则 CI 跑的还是旧代码。
- **本地跑完的 `output/` 不要打包上传**：若 `source/` 里混了 `.git` 会让 zip 暴涨（CI 里是文件不是目录，所以 CI 没这问题）。

---

## 10. 2026-11-14 实跑记录（到上传前为止）

环境：Windows、Python 3.11.15（`.venv`）、`BDCC@0b976728`（`chinese`）、Paratranz 项目 10958。

| 阶段 | 结果 | 耗时 |
|---|---|---|
| 准备 `source/` | 3300 `.gd` + 653 `.tscn`（robocopy /MIR，排除 `.git`） | 58 s |
| 准备 `fetch/` | `generate_artifact` + `download_artifact` → 3821 个 json（415 在 `过时/`），32.8 MB | ~60 s |
| `extract` | `trans/` 3406 文件 / 174,341 词条 | 62.9 s |
| `update` | `change/` 2 文件（新增 1 条，来自本地误改）、`deprecated/` 1 文件（`stage=9` 1 条）、已译 174,258 条 | 57.1 s |
| `update`（撤销误改后重跑） | `change/` **1 文件**（新增 0 条，仅条目数变化）、`deprecated/` 1 文件（1 条） | 100.4 s |
| `check_identifier` | 标识符形态 31,428 条，已译 31,426 条，译文≠原文 151 条 | 31.7 s |
| 整条 `pipeline.sh` | 成功：`BdccChineseLocalization.zip` 244,575,910 B / 9818 文件，`change/` 1 文件，`deprecated/` 1 文件，lint `parse success` | replace 101 s、lint 86 s、zip ≈1 min |

结论：源码与项目已基本同步——撤销那条误改后只剩 `Game/Datapacks/UI/CrotchCode/VisualSlots/CrotchBigTextEditWindow.gd.json` 一个文件有差异（条目数变化、新增 0 条），本轮**没有要上传的新词条**。

Paratranz 侧现状（`get_project`）：3821 文件 / 177,115 词条 / 已译 176,846 / `extra.version = 0.3.2`。
