# 上游与适配说明

- 上游：`https://github.com/worldwonderer/oh-story-claudecode`
- 基线：v0.7.0，commit `964d6bfdb7b78b225591e4b35bfa00d245d4f9a2`
- 许可：MIT，全文见 `upstream-license.txt`

本版本把上游 13-skill、多 CLI、hooks/custom agents 的发行形态收为一个 Codex 个人 skill。保留长短篇写作、扫榜、拆文、导入、审查、去 AI 味的方法论与确定性脚本；删除 Claude 项目部署、登录态 CDP 和独立 API key 依赖，改用 Codex 当前的文件、网页、结构化提问、图像生成与可选协作能力。

更新上游时，先比较工作流和参考资料，再人工合并；不要直接覆盖 `SKILL.md`、`codex-adapter.md`、`codex-workspace.md` 或 `codex-cover.md`。
