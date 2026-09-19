# Claude Desktop 中文补丁

给 Claude Desktop 换上简体中文界面。支持 Windows 和 macOS，支持官方订阅和第三方 API，可完整卸载恢复原样。

补丁只修改本机 Claude Desktop 的界面资源文件，不触碰账号数据，也不改变推理请求的内容。

## 界面截图

![Claude Desktop 中文主界面](docs/images/claude-desktop-zh-cn-home.png)
![Claude Desktop 中文设置界面](docs/images/claude-desktop-zh-cn-settings.png)
![Claude Desktop 中文推理配置界面](docs/images/claude-desktop-zh-cn-gateway.png)

> 截图取自 Claude Desktop 2.2553.1。Claude 每次更新都可能新增文案，届时需要重跑补丁；更新后如果出现零星英文，见文末「Claude 更新后」。

## 汉化覆盖

Claude Desktop 的界面文案分两层，分别存放在两个互不相干的目录里：

| 界面层 | 对应文件 | 覆盖情况 |
|---|---|---|
| 主进程（菜单栏、托盘、系统对话框） | `resources/<语言>.json` | 705 / 705 |
| 渲染进程（应用内所有页面，**含设置界面**） | `ion-dist/i18n/<语言>.json` | 28,757 / 29,442 |

未覆盖的 685 条经扫描确认没有被任何代码引用，属于旧版本遗留的死数据，不会出现在界面上。也就是说，当前版本**所有可见文案都已汉化**。

## 安装模式

只需要做一个选择：

### [1] 标准汉化

不修改 `app.asar` 和 `Claude.exe`，保留 Claude 的代码签名。

- 菜单栏、托盘、系统对话框、应用内界面：中文
- 不含：在线页面汉化、模型选择器汉化、第三方模型名校验绕过
- 用第三方 API 时，需要在网关或 CC Switch 中把模型名映射成 `claude-*` 风格的名称，否则推理配置无法保存

### [2] 完整汉化

改写 `app.asar`，并重算 `Claude.exe` 内嵌的完整性哈希。

- 在 [1] 的基础上，额外汉化在线页面、主进程菜单、模型选择器
- 绕过第三方模型名校验，模型名可以直接写 `deepseek-v4-pro` 这类名称
- **Cowork 沙箱/工作区必不可用**（`Claude.exe` 签名失效）

拿不准就选 `[1]`——它的汉化范围覆盖日常会用到的全部界面，而且不动签名。

## Cowork 沙箱/工作区说明

Cowork 的 VM 沙箱要能用，必须**同时**满足两个条件，缺任何一个都不行：

### 条件一：系统本身支持 Hyper-V

Cowork 通过 `vmcompute.dll`（Hyper-V Host Compute Service）启动虚拟机。这个组件**只在 Windows 专业版 / 企业版 / 教育版提供，家庭版没有**。

如果 `C:\Windows\System32\vmcompute.dll` 不存在，Cowork 永远不可用，**和是否打补丁无关**。日志（`C:\ProgramData\Claude\Logs\cowork-service.log`）里表现为：

```
[HCS] Warning: Failed to load vmcompute.dll: The specified module could not be found.
[Cleanup] Warning: failed to enumerate HCN networks: HcnEnumerateNetworks failed with HRESULT 0x800706d9
[VM] Stale VM scan failed, continuing without cleanup: HCS not initialized
```

很多「Cowork 用不了」的反馈其实是这一条——家庭版系统本来就跑不了。

### 条件二：Claude 的签名未被破坏

`cowork-svc.exe` 启动时会做签名校验（日志里的 `Signature verification initialized ... Enforce: true`）。模式 `[2]` 改写了 `app.asar` 并重算了 `Claude.exe` 的哈希，Authenticode 签名变成 `HashMismatch`，服务会拒绝客户端，典型报错是 `RPC pipe closed`。

模式 `[1]` 不碰 `app.asar` 和 `Claude.exe`，这一条不会触发。

### 结论

想用 Cowork：系统要有 Hyper-V，并且用模式 `[1]`。

## 适用环境

- Windows 10/11，或 macOS
- 已安装 Claude Desktop
- macOS 需要 Python 3（优先用 `/usr/bin/python3`，没有则从 `PATH` 找 `python3`）
- Windows 需要系统自带的 Windows PowerShell（`powershell.exe`），批处理入口会自动请求管理员权限

## 使用方式

### Windows

1. 退出 Claude Desktop。
2. 下载或克隆本项目。
3. 双击 `install-windows.bat`，按 UAC 提示授权；脚本会先把安装文件复制到临时目录再以管理员身份运行。
4. 选择安装模式（`1` 标准汉化 / `2` 完整汉化），详见上文「安装模式」。
5. 选择语言：`1` 简体中文、`2` 繁体中文（中国台湾）、`3` 繁体中文（中国香港）。
6. 脚本会先尝试从旧备份恢复以清理上一轮汉化；没有旧备份时跳过并继续。
7. 脚本会备份被修改的文件、写入中文资源并重启 Claude Desktop。
8. 如果没有自动切换，打开左下角账号菜单，选择 `Language` → 对应的中文选项。

其他菜单项：

- `3` Frida 运行时汉化（实验）：不修改磁盘上的 `app.asar` / `Claude.exe`，用 Frida 内存补丁加 CDP 注入在线页面 DOM 翻译。若本机缺 Python + frida，会提示下载便携运行时到 `%LOCALAPPDATA%\claude-zh\runtime`。需要本机允许 Frida 注入，**不适合当普通安装方式**。
- `4` 恢复原样 / 卸载补丁。
- `5` 自动更新设置：`y` 禁止自动更新，`n` 允许。
- `6` CC Switch skills 同步：`y` 把 `%USERPROFILE%\.cc-switch\skills` 中缺失的 skill 软链接进 Claude Desktop 的本地 skills 目录；`n` 只删除之前同步产生的软链接和记录，不动 CC Switch 源目录。

### macOS

1. 退出 Claude Desktop。
2. 下载或克隆本项目。
3. 双击 `install-mac.command`，选择安装模式（`1` 标准汉化 / `2` 完整汉化）。
4. 选择语言：`1` 简体中文、`2` 繁体中文（中国台湾）、`3` 繁体中文（中国香港）。
5. 按提示输入登录密码（选项 `1`/`2`/`4`/`5` 需要）。
6. 安装完成后 Claude 会自动重新打开。
7. 如果没有自动切换，打开左下角账号菜单，选择 `Language` → 对应的中文选项。

其他菜单项与 Windows 相同（`3` Frida、`4` 恢复、`5` 自动更新、`6` CC Switch skills）。

**macOS 的自动更新**：补丁会对应用做本机 ad-hoc 重签名。从 2026-08 版本起，重签时显式写入 `identifier` 级别的 designated requirement（替代默认的 cdhash 级别），因此 Claude Desktop 的官方自动更新下载后可以正常安装，不会再卡在「下载完成但版本不变」。

- 更新安装成功后，`/Applications/Claude.app` 会被官方英文版覆盖，重跑本补丁即可恢复中文。
- 如果之前打过旧版补丁（默认 ad-hoc DR），需要重打一次才能获得新的签名行为。

## 文件说明

- `install-windows.bat` / `install-mac.command`：两个平台的安装入口。
- `scripts/install_windows.ps1`：Windows 汉化安装和卸载脚本。
- `scripts/patch_claude_zh_cn.py`：macOS 上真正执行补丁的 Python 脚本。
- `scripts/translate_missing.py`：词表维护工具，用于补齐 Claude 更新后新增的文案，见「补齐词表」。
- `scripts/experimental/`：Frida 实验模式相关文件（便携运行时自举、启动器、注入 Agent、常驻计划任务）。
- `resources/manifest.json` / `manifest-zh-TW.json` / `manifest-zh-HK.json`：语言包信息。
- `resources/frontend-<语言>.json`：应用内界面翻译。
- `resources/frontend-hardcoded-<语言>.json`：未走 i18n key 的硬编码文本映射，同时用于在线页面的 DOM 翻译表。
- `resources/desktop-<语言>.json`：主进程壳层（菜单栏、托盘、对话框）翻译。
- `resources/statsig-<语言>.json`：statsig i18n 兜底资源。
- `resources/Localizable*.strings`：macOS 原生菜单资源。
- `resources/release.json`：安装入口用来检查 GitHub Releases 是否有新版。

## 脚本会做什么

两个平台的共同流程：

1. 查找 Claude Desktop 安装目录。
2. 安装前先尝试从旧备份恢复，清理上一轮汉化；没有旧备份时跳过。
3. 备份本次实际会改动的文件（Windows 存到安装目录下的 `resources\.zh-cn-backups\<时间戳>\`，macOS 把整个 `Claude.app` 备份到同目录）。
4. 写入中文资源。
5. 把当前选择的中文变体加入前端语言白名单。
6. 汉化前端 bundle 中未走 i18n JSON 的硬编码界面文本（侧边栏入口、配置页标签、模型选择项等）。
7. 写入用户配置，把 `locale` 设为所选语言。
8. 重启 Claude Desktop。

**语言包合并**：两个平台都会把随包中文翻译与目标机器当前的 `en-US.json` 按 key 合并——已有译文用中文，Claude 新版新增而本包没有的 key 保留英文，本包里的过期 key 直接丢弃。这样界面永远不会因为缺字段而空白。

`★ Insight ─────────────────────────────────────`
这个合并步骤是补丁能跟上 Claude 快速迭代的关键。Claude 的界面文案 key 是 11 字符的 hash（如 `2GURQYNPp3`），每次更新都会新增和删除大量 key。如果直接把翻译文件覆盖过去，新版本里所有未翻译的 key 就会失去兜底；合并则保证「翻过的用中文、没翻过的用英文」，界面永远不会出现 hash 或空白。
`─────────────────────────────────────────────────`

**仅模式 `[2]` 会做的事**：

- 改写 `app.asar`：注入在线账号页面的 DOM 翻译、主进程菜单汉化、模型选择器汉化。
- 用等长替换关闭第三方网关的模型名校验。
- Windows 上同步改写 `Claude.exe` 内嵌的完整性哈希。

这三项都会改变被签名覆盖的文件内容，因此模式 `[2]` 必然导致签名失效。

## Claude 更新后

Claude Desktop 每次更新都可能改动界面结构，补丁也会被覆盖。推荐流程：

1. 先运行安装入口选 `[4]` 恢复原样。
2. 再更新 Claude Desktop。
3. 最后用本项目最新版本重新安装。

如果更新后你发现某些界面出现英文，那是新版本新增了本包还没有的文案。可以提 Issue 说明具体位置（界面路径 + 英文原文 + 截图），帮助补齐词表。

## 补齐词表（维护者向）

Claude 更新后新增的文案可以用仓库自带的脚本批量补齐：

```bash
python scripts/translate_missing.py --limit 1    # 预览一批，先看质量
python scripts/translate_missing.py --merge      # 全量翻译并写回词表
```

脚本的工作流程：

1. 自动探测已安装的 Claude Desktop（Windows 走 `Get-AppxPackage`，macOS 走 `/Applications/Claude.app`），读取它的 `en-US.json`；也可以用 `--app` 手动指定。
2. 与 `resources/frontend-zh-CN.json` 比对，找出缺失的 key。
3. 扫描应用的 JS bundle，**只保留被代码实际引用的 key**——没有任何代码引用的字符串永远不会出现在界面上，翻译它们是白费功夫。
4. 分批调用 Anthropic 兼容接口翻译，逐条校验 ICU 占位符、花括号结构和单引号。
5. 校验不通过的自动退回单条重译。
6. `--merge` 把通过校验的译文写回词表（原件备份为 `.bak`）。

结果会增量写入 `.translate-missing-results.jsonl`，中途中断后重跑会自动跳过已完成的部分。

**凭据**通过环境变量提供：

```bash
export TRANSLATE_API_BASE=https://api.deepseek.com/anthropic
export TRANSLATE_API_KEY=sk-...
```

如果本机已经用 cc-switch 配好了 Claude Desktop profile，脚本会自动复用其中的凭据，不需要额外设置。

只依赖 Python 3 标准库，无需安装第三方包。目前只支持 `zh-CN`；`zh-TW` / `zh-HK` 词表需要人工维护。

## 卸载 / 恢复

运行对应平台的安装入口，选择 `[4]`。

- Windows：恢复备份文件、删除中文资源、把用户语言设置改回 `en-US`。
- macOS：恢复 `/Applications` 下最早的 `Claude.backup-before-zh-CN-*.app`，并删除其他补丁备份。

## 常见问题

**装完还是英文？**

先确认 Claude Desktop 已经重启。如果只有部分界面是英文，多半是 Claude 更新后新增了文案，见「Claude 更新后」。

**Cowork 用不了？**

见上文「Cowork 沙箱/工作区说明」——先看你的 Windows 是家庭版还是专业版。家庭版没有 Hyper-V，Cowork 无论如何都用不了。

**第三方模型配置保存不了？**

模式 `[1]` 不带模型名校验绕过。要么改用模式 `[2]`，要么在网关 / CC Switch 里把模型名映射成 `claude-*` 风格。

**Windows 提示 `RPC pipe closed`？**

模式 `[2]` 造成签名失效，Cowork 服务拒绝连接。改用模式 `[1]`。

## 致谢

本项目基于 [javaht/claude-desktop-zh-cn](https://github.com/javaht/claude-desktop-zh-cn)（MIT）发展而来，感谢原作者搭建的补丁框架与安装流程。

## 免责声明

本项目为非官方中文补丁，与 Anthropic 无关，仅修改本机 Claude Desktop 的本地资源文件，不修改 Claude 服务端账号数据。Claude Desktop 更新后资源结构可能变化；如果补丁失败，请先恢复原版应用再更新本项目，不要在安装未完成的状态下反复运行脚本。

## 许可

MIT，见 [LICENSE](LICENSE)。
