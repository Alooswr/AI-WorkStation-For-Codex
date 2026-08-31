---
name: oh-story-codex
description: 用于中文网文创作与维护：选题拆解、设定人物、大纲正文、续写日更、旧稿导入、连续性审查、去 AI 味及封面。用户提到写网文、开书、续写、审稿或设定冲突时使用。
---

# Oh Story for Codex

把本 skill 当作工作流路由器。先识别任务，再只读取对应模块；不要一次加载全部参考资料。

上游模块保留了成熟的网文方法论，但其中的 Claude/OpenCode/ZCode 命令只作为历史语义。执行任何模块前，先遵守 [Codex 适配层](references/codex-adapter.md)；若模块与适配层冲突，以适配层为准。

## 路由任务

| 用户目标 | 必读工作流 | 按需补充 |
|---|---|---|
| 模糊地说“想写小说/网文” | 本文件 | 只问长篇或短篇等会改变路线的关键选择 |
| 长篇选题、榜单、市场判断 | [Codex 市场扫榜](references/codex-market-scan.md) | 长篇模块内的趋势、读者与决策方法 |
| 长篇拆文、黄金三章、深度分析 | [长篇拆文](references/modules/story-long-analyze/workflow.md) | 输出模板、素材拆解、文风协议 |
| 长篇开书、大纲、正文、续写、返工 | [长篇写作](references/modules/story-long-write/workflow.md) | 仅加载当前阶段点名的题材、角色、钩子、节奏或日更资料 |
| 短篇选题、平台风口 | [Codex 市场扫榜](references/codex-market-scan.md) | 短篇模块内的跨平台方法资料 |
| 短篇拆文 | [短篇拆文](references/modules/story-short-analyze/workflow.md) | 输出模板、题材公式、结构材料 |
| 短篇构思、写作、投稿定稿 | [短篇写作](references/modules/story-short-write/workflow.md) | 短篇格式、情绪、反转、投稿层资料 |
| 导入旧稿并建立可续写工程 | [Codex 小说导入](references/codex-import.md) | [Codex 写作工程](references/codex-workspace.md) |
| 审查结构、人物、连续性和文风 | [小说审查](references/modules/story-review/workflow.md) | 质量 rubric 与对应题材资料 |
| 去 AI 味、自然化润色 | [去 AI 味](references/modules/story-deslop/workflow.md) | 反模式、禁用表达与确定性检查脚本 |
| 新建或整理长期写作项目 | [Codex 写作工程](references/codex-workspace.md) | 先检查现有文件，合并而非覆盖 |
| 制作小说封面 | [Codex 封面流程](references/codex-cover.md) | 使用当前环境的图像生成能力 |

## 执行主线

1. 读取用户已提供的设定、正文、选择和明确禁忌；若存在写作工程，再按需检索项目文件。
2. 确认当前阶段与本次交付边界。只有缺失信息会实质改变结果时才提问；其余用清楚标注的合理假设继续。
3. 读取一个主工作流及它明确点名的少量参考文件。不要为了“全面”吞入整个资料库。
4. 先产出结构或修改判断，再写正文；已有明确大纲时不要重复让用户确认已确认事项。
5. 对正文执行情节功能、角色一致性、时间线、伏笔、字数和 AI 痕迹检查。机器检查只判断确定性模式，不替代读感。
6. 若在文件工程中工作，同步更新必要的设定、大纲和追踪文件；保留用户原稿，避免无提示覆盖。
7. 先交付用户要看的内容，再简短说明假设、检查结果或下一处待决项。

## 通用写作约束

- 把情绪满足、人物选择和可验证的情节变化放在解释之前。
- 保持人物语言差异；不要用旁白替人物总结情绪或主题。
- 让段尾形成行动、信息、关系或代价上的变化，少用预告式总结。
- 续写前先对齐最近正文、当前细纲、角色状态、时间线和未回收伏笔。
- 修改时保留用户指定的事件、视角、关系、语气和篇幅目标；不要借“去 AI 味”擅自改剧情。
- 分析第三方作品时做转化性的结构与技法分析，不大段复现原文。

## 工具与协作边界

- 市场扫榜和事实核查使用当前网页检索能力，并标出数据日期与来源；不要把包内静态市场材料冒充最新数据。
- 封面使用图像生成 skill/tool；不要要求用户配置上游脚本中的 API key。
- 除非用户明确要求多代理、并行审查或委派，不启动子代理；直接完成模块任务。用户明确要求后，才按适配层拆成有边界的并行角色。
- 需要生成长期文件时遵守当前运行环境的持久化规则；仅在用户明确指定本地项目时写工作区。

## 来源

本适配基于 `worldwonderer/oh-story-claudecode` v0.7.0（MIT）。查看 [适配说明](references/upstream.md) 与 [上游许可](references/upstream-license.txt)。
