# Codex 小说导入

把用户合法持有的现有小说重建为可续写工程。默认交付完整工程；用户只要分析时改走长篇或短篇拆文，不创建续写结构。

## 1. 获取与保护源稿

1. 接受单个 `.txt` / `.md` 文件、按章节命名的目录，或用户直接提供的文本。
2. 自动识别书名、章节边界、总章数、字符数、最后一章是否完整和编码异常。
3. 让用户确认会改变分流的结果：长篇/短篇、书名、残章处理方式。题材与平台无法自动判断且后续需要时再问。
4. 在工程中保留原文备份；不移动、重命名或覆盖用户源文件。

篇幅路由使用 [篇幅判定](modules/story-import/references/length-routing.md)，优先级为用户声明、结构信号、字数兜底。

## 2. 拆解原稿

- 长篇读取 [长篇拆文工作流](modules/story-long-analyze/workflow.md)，完整执行其 Stage 0–6；导入任务不在黄金三章预览处停下。
- 短篇读取 [短篇拆文工作流](modules/story-short-analyze/workflow.md)，完整执行其拆解阶段。
- 章节很多时分批处理并维护进度文件；默认当前 Codex 串行完成。用户明确要求并行代理后，才按章节范围拆分无重叠任务。
- 每条设定、关系和状态尽量保留章节证据；无法确定的内容标记“待确认”，不要补写成事实。

## 3. 映射为写作工程

按 [Codex 写作工程](codex-workspace.md)创建或合并目录，并使用：

- [长篇结构映射](modules/story-import/references/structure-mapping-long.md)
- [短篇结构映射](modules/story-import/references/structure-mapping-short.md)
- [角色状态逆向](modules/story-import/references/character-state-reverse.md)
- [状态追踪](modules/story-import/references/state-tracking.md)
- [格式与结构](modules/story-import/references/format-and-structure.md)

长篇至少生成或更新：

- `作品信息.md`
- `设定/题材定位.md`、核心角色、世界观、关系与文风
- `大纲/大纲.md`、当前卷纲、已写章节的细纲
- `正文/` 中的原章节
- `追踪/角色状态.md`、`时间线.md`、`伏笔.md`、`上下文.md`
- `拆文库/` 或 `对标/` 中可追溯的分析资产

短篇只建立必要的作品信息、结构、角色、正文和写作手法文件，不套用长篇追踪模板。

## 4. 连续性校验

交付前检查：

1. 源章节与工程正文数量、顺序、标题和正文内容一致。
2. 最后一章结束状态与 `追踪/上下文.md` 一致。
3. 角色状态、时间线和伏笔能追溯到原文章节。
4. 大纲描述已发生剧情，不把模型推测写成作者既定计划。
5. 下一章入口明确：当前地点、人物状态、未决冲突、最近钩子和残章状态。

## 5. 交付

报告导入范围、识别结果、生成/更新的文件、待确认事实和建议续写起点。用户要求立即续写时，直接进入长篇或短篇写作工作流，不要求安装 hooks、agents 或重开会话。
