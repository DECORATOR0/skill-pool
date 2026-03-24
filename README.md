# 项目入口

这个仓库已经按“长期维护”方式重新整理。后续默认从仓库根目录 `D:\skills-evo\project_skills` 开始看，不要先钻进 `project_skills/` 内层再找说明。

优先阅读顺序：

1. `项目文档/给AI先看_项目工作约定.md`
2. `项目文档/项目架构与工作流说明书.md`
3. `实验记录/实验总表.md`
4. `实验记录/观察与假设.md`
5. `待办/进行中.md`

目录分工：

- `项目文档/`：主说明书和 AI 工作约定
- `实验记录/`：每次 run 的总表、观察和维护规则
- `待办/`：进行中 / 已完成 / 历史 TODO
- `AI交互记录/`：需要长期记住的用户指令和关键对话
- `杂项归档/`：对方构建、旧聊天、API 说明、架构图、git 学习等非核心资料
- `project_skills/`：真正的代码、配置、prompt、skill、run 产物

运行命令的统一约束：

- 工作目录固定在外层根目录：`D:\skills-evo\project_skills`
- CLI 入口固定写成：`python -m project_skills.nlrl_skills.cli`
- 长跑不要从可见 `cmd.exe` 窗口拉起

实验表更新命令：

```powershell
python project_skills/scripts/generate_experiment_table.py
```
