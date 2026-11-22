# BDCC 汉化发布流程

面向维护者。构建侧细节见 `pipeline.md`，文本规范见 `translation-guide.md`。
本文只讲**怎么把一个可玩包发出去，以及发之前必须核对什么**。

---

## 0. 现状速览

| 项 | 现状 |
|---|---|
| 正式发布触发 | 推 `v*` 形式的 tag（如 `v0.4.2-chs-1.0.0a`） |
| 预发布触发 | 每周一 12:30 UTC 定时 + Actions 手动 dispatch → tag `bdcc.YY.MM.DD`（prerelease） |
| 构建机 | `translate` 在 windows-latest（dotnet 8 + python 3.11）；各平台构建在 `barichello/godot-ci:3.6` 容器 |
| 发布产物 | `BDCC-Windows.zip` / `BDCC-Linux.zip` / `BDCC-Macos.zip` / `BDCC-WEB.zip` / `BDCC-Android.apk` / `source-code-for-test.zip` |
| release 说明 | `release.md`：README「更新日志」列表**第一条** + `CHANGELOG.zh-CN.md` **第一个**版本小节 |
| 发布后 | Jekyll（GitHub Pages）自动部署 |
| 最新正式版 | `v0.3.2-chs-1.0.0a`（2026-08-25） |
| 当前上游 | BDCC `chinese` = `9e0eecbe`，`git describe` = `0.4.2-20-g9e0eecbe` → 下次正式版按规则**重置**为 `v0.4.2-chs-1.0.0a` |

需要的仓库 Secrets：`PARATRANZ_TOKEN`、`PARATRANZ_PROJECT`、`ANDROID_KEYSTORE_FILE`、`ANDROID_KEYSTORE_PASSWORD`。

---

## 1. 版本号规则（摘自 README，发版照此推算）

- 结构：`{游戏版本}-chs-{汉化版本}`，汉化版本 `x.y.z` + 后缀 `a/b/r`
  - `a` 100% 翻译、可能有漏提取、未充分润色
  - `b` 100% 翻译、无漏提取、未充分润色
  - `r` 100% 翻译、无漏提取、已充分润色
- 游戏大版本变更（0.4.9→0.4.10 / 0.4→0.5）→ 汉化版本**重置** `1.0.0a`
- 游戏小修（0.4.10.6→0.4.10.7）→ 汉化版本**首位 +1**（`1.0.0a`→`2.0.0a`）
- 常规更新 → **第二位 +1**（`1.6.0a`→`1.7.0a`）
- 恶性问题热修 → **末位 +1**（`1.7.0a`→`1.7.1a`）

本次（游戏 0.3.2 → 0.4.2，属大版本变更）：`v0.4.2-chs-1.0.0a`。

---

## 2. 发版前必须对齐的三处指针（最易翻车）

CI 用的是**仓库里提交的记录**，不是本地工作树：

| # | 对象 | 检查 | 没对齐的后果 |
|---|---|---|---|
| 1 | `BDCC` 子模块 | `git -C BDCC status -sb` 必须 `## chinese...origin/chinese` 且无本地提交；发布库内 `git status` 不能出现 `M BDCC` | CI 用**旧游戏代码**构建，发出去的包落后于上游 |
| 2 | 工具库子模块 | 有脚本改动时：先在工具库 `main` 提交并 push 到 `HCPTangHY/BDCC-Localization-Replacer`；再在发布库提交指针 | CI 拉的是 `HCPTangHY ... @main`，本地 detached 的指针改了也没用 |
| 3 | 发布库本身 | `git status` 只剩预期改动（更新日志、子模块指针） | 漏提交 → CI 构建出来的内容与本地不一致 |

> 实测（2026-11-22）：发布库停在 `7a8c915`，`BDCC` 指针为 `M`（本地已到 `9e0eecbe`，仓库记录仍是旧 commit）。
> **不先提交这个指针就发版，包会是旧游戏版本。**

---

## 3. 发版步骤

### 3.1 准备

```bash
cd E:/Projects/Games/BDCC/BDCCChineseLocalization
export PARATRANZ_TOKEN=...            # 必需
git -C BDCC fetch origin && git -C BDCC log --oneline -3 origin/chinese
git submodule update --init --recursive
```

### 3.2 质量门禁（全绿才继续）

```bash
TRANSLATION_VERSION=0.4.2-chs-1.0.0a bash pipeline.sh   # 版本号会写进主菜单
```

| 门禁 | 通过标准 |
|---|---|
| 构建 | 日志出现 `parse success` + `Translation complete!`，退出码 0 |
| 标识符 | `check/identifier_check.txt`：`必须回退(danger)=0`、`空白污染=0`；`待人工` 逐条确认 |
| BBCode | 扫描缺失 = 0；多出逐条确认（是否为刻意加粗）；参数差异逐条确认（字体替换属正常） |
| 未译 | 除 `stage=-1` 隐藏条目外为 0；开发者日志串可保留 |
| 导出快照 | Paratranz「最新导出」的 `id`/`createdAt` 必须是**本轮刚生成**的（`pipeline.sh` 不会触发导出） |
| 包内容 | `BdccChineseLocalization.zip` 抽查：主菜单 `版本：` 已替换、几处标志性译文存在、文件数约 9980 |

### 3.3 写更新日志（release 说明的来源）

1. `README.md` →「## 更新日志」列表**最前面**新增一条，格式照现有条目：

```
- 2026.M.D
  - 发布 `v0.4.2-chs-1.0.0a` 版
    - 同步上游 `0.4.2`
    - 本轮要点（1~3 条短句）
```

2. 上游有新版本时，在 `CHANGELOG.zh-CN.md` 分隔线之后**紧跟**插入新的 `## [x.y.z] - YYYY-MM-DD` 小节
   （release job 只取第一个小节）。

### 3.4 提交与打 tag

```bash
# 工具库（仅在改了脚本时）
git -C BDCC-Localization-Replacer add -A && git -C BDCC-Localization-Replacer commit -m "..." \
  && git -C BDCC-Localization-Replacer push origin main

# 发布库：子模块指针 + 更新日志
git add BDCC BDCC-Localization-Replacer README.md CHANGELOG.zh-CN.md
git commit -m "release: v0.4.2-chs-1.0.0a"
git push origin master

git tag v0.4.2-chs-1.0.0a
git push origin v0.4.2-chs-1.0.0a
```

> `BdccChineseLocalization.zip` 已在 `.gitignore`，不需要也不应该提交。

### 3.5 盯 CI

`runner.yml` 顺序：`get-tag → translate → windows/linux/macos/web/android → release`。
- `translate` 失败：先看 Traceback（python）或 Paratranz 5xx，重跑即可
- `web-build` 允许失败（`continue-on-error`），但 `release` 仍会跑
- 任何 job 卡住时，用 Actions 的 re-run failed jobs 重试，不要重打 tag

### 3.6 发布后核对

| 项 | 核对方式 |
|---|---|
| release 资产 | 6 个文件齐全：Windows/Linux/Macos/WEB/Android/source-code |
| release 说明 | 是最新那条更新日志 + 上游改动小节 |
| Pages | 站点已更新（release 触发 Jekyll） |
| 游戏内版本 | 主菜单显示 `版本：<tag>`；设置/关于处同样 |
| 冒烟 | 下载 Windows 包，进主菜单 → 开新档 → 走一段对话 → 存/读档 |

---

## 4. 热修与回滚

**热修**：改完 → 走 §3 全流程，汉化版本末位 +1（`1.0.0a` → `1.0.1a`），打新 tag。
旧 release 保留即可（README 徽章指向 latest）。

**回滚**（发错了/构建坏了）：
```bash
# 方案 A：release 就地替换资产（allowUpdates=true 已开启）
#   本机未装 gh，用 API：
curl -X DELETE -H "Authorization: $GH_TOKEN" \
  https://api.github.com/repos/chinese-liliths-throne/BDCCChineseLocalization/releases/assets/<asset_id>
# 或用网页 Release 页面手动 Upload/Delete 资产

# 方案 B：把 tag 指向旧提交再重发
git tag -f v0.4.2-chs-1.0.0a <旧commit> && git push -f origin v0.4.2-chs-1.0.0a
```
⛔ 不要删除 release 后原地重打同名 tag 而不通知玩家——下载统计会丢。

---

## 5. 已知问题（发版时按此规避）

| 级别 | 问题 | 影响 | 建议 |
|---|---|---|---|
| P0 | `runner.yml:40` 用 `git tag -l "v*" --sort=-version:refname \| head -1` 取版本，而不是本次推送的 tag | 热修补丁的 tag 若比历史版本号小，会构建/发布成**最新版号** | 改为 `echo "RELEASE_VERSION=${{ github.ref_name }}"` |
| P0 | 发布库 `BDCC` 子模块指针未提交（当前 `M BDCC`） | CI 用旧游戏代码构建 | 每次发版前 §2 检查 |
| P1 | CI 无文本质量门禁（只有 python 退出码） | identifier 退回、BBCode 断裂等可以一路发出去 | 在 `translate` 后加一步跑 `check_identifier` + bbcode 扫描，danger≠0 直接 fail |
| P1 | 主菜单版本号丢了本体版本（译文把 `GlobalRegistry.getGameVersionString()` 删掉，只留 `版本：TRANSLATION_VERSION_HERE`） | 玩家无法从界面确认游戏本体版本，反馈问题难定位 | 译文改成 `"版本："+GlobalRegistry.getGameVersionString()+"　汉化：TRANSLATION_VERSION_HERE"` |
| P2 | 预发布 tag `bdcc.YY.MM.DD` 与正式 `v*` 命名不同，且预发布不触发 Pages | 预发布包无法从页面看到；tag 列表混杂 | 统一为 `v<游戏版本>-chs-nightly.YYMMDD` 或维持现状但在此登记 |
| P2 | README 更新日志里混用了 `2026.8.25` / `2026.5.17` 这类无前导零写法 | 排序/检索不便 | 新条目沿用现有写法即可，暂不统一 |

---

## 6. 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `translate` 报 `python script failed` | 替换阶段 5 个 `.gd` 解析失败（坏译文） | 看日志里的 key，回 Paratranz 修该条译文，重新 `generate_artifact` 后重跑 |
| 包里文本是旧的 | artifact 是旧快照 | 先 `generate_artifact`，确认 `artifacts/latest.createdAt` 是刚才 |
| 主菜单版本号是 `1.0.0` | 本地跑没传 `TRANSLATION_VERSION` | 用 `TRANSLATION_VERSION=<tag> bash pipeline.sh` |
| 构建成功但资产里少平台 | 对应 job 挂掉（android keystore / macos 模板） | 重跑该 job；android 检查 secret 是否过期 |
| 发布页说明为空 | README「更新日志」列表不是最后一个 List，或 CHANGELOG 缺首个小节 | 按 §3.3 修正后重发 |
