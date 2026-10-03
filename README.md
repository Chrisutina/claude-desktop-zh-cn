# Claude Desktop 简体中文补丁（Windows）

**源码修复版 1.4.11 · 更新日期：2026-10-03 · 核对客户端：Claude Desktop 2.19675.0**

本轮维护范围为 **Windows、简体中文、Claude 官方订阅账号登录**。使用 Claude 账号登录即可，安装本补丁无需配置第三方 API。

**[下载当前源码 ZIP](https://github.com/Chrisutina/claude-desktop-zh-cn/archive/refs/heads/main.zip)**，完整解压后运行 `install-windows.bat`，依次选择 **2：官方账号登录模式（完整汉化）→ 1：简体中文**。

1.4.11 是当前源码包的版本，与 `resources/release.json` 一致；本仓库目前尚未发布对应的 GitHub Release，下载入口为 `main` 分支源码包。Claude Desktop 的版本号与补丁版本号分别记录。

## 1.4.11 更新内容

- 补齐 Chrome 扩展设置、网站权限和默认策略文案，以及订阅用量、额度重置和用量余额页面的文案。
- 处理运行时生成的百分比、折扣、到期日、星期、12/24 小时重置时间及倒计时。
- 修复在线词表的大小写匹配，分别保留 `Extensions` 与 `EXTENSIONS`，避免词条被覆盖。
- 思考等级保留 `Low / Medium / High / Extra / Max`，标题保留 `Effort`；模型说明与帮助文字使用中文。其他语境的低、中、高仍按原意翻译。
- 补齐右键菜单中的复制链接、复制图片、添加到词典、检查元素等文案；保留拼写建议原文和 Windows 的 `Ctrl+B` 快捷键。
- 新增模型动态词库，并调整注入顺序，避免后续替换破坏在线词表的英文匹配项。

[修复细节与验证范围](https://github.com/Chrisutina/claude-desktop-zh-cn/blob/main/docs/windows-official-localization.md)。

## 安装与更新补丁

1. 保存工作，结束 Claude Code 等正在运行的任务，再退出 Claude Desktop。安装脚本会关闭并重新启动应用。
2. 下载上方源码 ZIP，**完整解压整个文件夹**。已有旧补丁时，也要重新下载当前源码包。
3. 双击 `install-windows.bat`，按 UAC 提示授予管理员权限。入口会将脚本和词库复制到本机临时目录再运行。
4. 第一层菜单选择 **2：官方账号登录模式（完整汉化）**。
5. 语言菜单选择 **1：简体中文**。
6. 等待安装完成和 Claude 重新打开；若语言未自动切换，在账号菜单的 `Language` 中选择简体中文。
7. 检查思考等级、输入框右键菜单、Chrome 设置和订阅用量页。

**仅重启 Claude 不会写入新词库。** 修改补丁源码或下载新版后，需要重新运行安装入口。需要保留当前任务时，等任务结束再安装。

Windows 需要系统自带的 `powershell.exe`，并提前安装 Claude Desktop；普通安装无需额外安装 Python、Node.js 或配置 API 密钥。资源已按上述客户端版本核对，其他版本仍需检查实际安装结果。

## Windows 菜单说明

| 选项 | 用途 |
| --- | --- |
| `1` 标准汉化 | 写入语言资源及前端文本补丁，保留 `app.asar` 与 `Claude.exe` 原有签名；不含在线页面和模型选择器补丁。 |
| **`2` 官方账号登录模式（完整汉化）** | 在标准汉化基础上补充在线账号页面、主进程菜单与模型选择器翻译；官方订阅账号本轮修复使用此项。 |
| `3` Frida 运行时汉化 | 实验模式，需要额外运行时和注入条件，普通安装无需选择。 |
| `4` 恢复原样 / 卸载补丁 | 使用备份恢复应用文件、移除补丁语言注册，并将语言设置切回英文。 |
| `5` 自动更新设置 | `y` 禁止 Claude 自动更新，`n` 允许。 |
| `6` 同步 CC Switch skills | 可选的本地技能同步，官方账号登录和界面翻译无需启用。 |

模式 `2` 会改写 `app.asar` 并同步 `Claude.exe` 内嵌的完整性哈希，使 EXE 的 Authenticode 校验显示 `HashMismatch`。Cowork VM 服务可能因此拒绝连接；需要保留签名时选择模式 `1`，其翻译范围见上表。

## 翻译范围与文件

| 文件 | 用途 |
| --- | --- |
| `install-windows.bat` | Windows 安装入口与管理员启动。 |
| `scripts/install_windows.ps1` | 查找安装目录、备份、安装、卸载和在线页面补丁。 |
| `resources/frontend-zh-CN.json` | 应用页面和设置的键值翻译。 |
| `resources/desktop-zh-CN.json` | 菜单、托盘和系统对话框翻译。 |
| `resources/dynamic-zh-CN.json` | 模型说明与思考选项动态词库。 |
| `resources/frontend-hardcoded-zh-CN.json` | 硬编码文本与在线页面翻译映射。 |
| `resources/statsig-zh-CN.json` | Statsig 文案资源。 |
| `resources/manifest.json` | 简体中文资源信息与当前词条数量。 |
| `resources/release.json` | 源码包版本及安装入口的 GitHub Release 更新检查来源。 |

安装时将中文词库与目标客户端当前的英文词库按键合并：已有译文使用中文，新键回退英文，当前版本不再使用的旧键不写入应用。随包词条数量见 `resources/manifest.json`，不能据此推算所有在线页面的翻译覆盖率。

在线翻译会跳过用户消息、输入内容和代码区域。翻译网站权限和余额文案不会改变权限策略，也不会开启付费余额、购买额度或重置用量。

## 卸载与 Claude 更新

运行 `install-windows.bat`，选择 **4：恢复原样 / 卸载补丁**，完成后手动启动 Claude。应用文件的备份位于安装目录的 `resources\.zh-cn-backups\`，请保留该目录以便恢复。

Claude Desktop 更新可能覆盖补丁或新增文案。更新前可先选择 `4` 恢复原样；更新完成后，下载本项目当前源码包，重新选择 **2 → 1** 安装，并核对实际界面。

## 常见问题

**下载新版本后，界面还是旧翻译？**

确认运行的是新解压目录中的 `install-windows.bat`，整个 `scripts` 与 `resources` 文件夹均来自同一源码包。旧安装入口会继续使用旁边的旧词库；只替换 README、单个脚本或重启 Claude 都不会更新完整补丁。

**设置菜单中文了，Chrome 设置和用量正文仍是英文？**

先确认安装时选了第一层菜单的 **2：官方账号登录模式**，再选语言 **1：简体中文**，并检查本次安装是否完成。模式 `1` 不包含在线页面翻译。完成安装后仍有漏翻时，请记录页面路径、英文原文和客户端版本，反馈截图前隐去账号与聊天内容。

**为什么 `Max` 仍然是英文？**

思考等级沿用原界面的 `Low / Medium / High / Extra / Max`，便于与 Claude Code 和英文文档对照；说明文字使用中文。

**截图为什么与当前界面不同？**

`docs/images/` 内现有截图来自旧版客户端，只能参考旧版效果。此次修复核对的客户端版本为 **2.19675.0**，旧截图不作为本轮实际界面的验收证据。

## 验证与维护范围

仓库的 [自动测试](https://github.com/Chrisutina/claude-desktop-zh-cn/actions/workflows/tests.yml) 覆盖 DOM 翻译保护、Windows 语言合并、大小写匹配、动态文案、英文思考等级，以及临时目录中的备份与卸载行为。脚本测试通过后，仍需在安装后的真实界面检查思考选项、右键菜单和设置页；本轮源码验证不能替代这些界面的重装验收。

仓库保留原项目的 macOS、其他中文变体及实验工具。本轮修复与验证范围为 Windows 简体中文官方账号模式，其他平台和登录方式沿用已有实现。

## 来源与许可

本项目基于 [javaht/claude-desktop-zh-cn](https://github.com/javaht/claude-desktop-zh-cn) 的补丁框架继续维护，是非官方本地化补丁，与 Anthropic 无关。许可为 MIT，见 [LICENSE](LICENSE)。
