# 🧰 Personal-SKILL (个人 AI Agent 技能库)

[![GitHub Repo](https://img.shields.io/badge/GitHub-Scholar--52HZ%2FPersonal--SKILL-181717.svg?logo=github)](https://github.com/Scholar-52HZ/Personal-SKILL)
[![Skills Count](https://img.shields.io/badge/Skills-1%20Ready-brightgreen.svg)](#-技能清单-skills-catalog)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Antigravity%20%7C%20Claude%20Code%20%7C%20Cursor%20%7C%20Codex-purple.svg)](#-多平台生态适配)

> 专为现代 Agentic AI 编码助手（Google Antigravity、Claude Code、Cursor、OpenAI Codex 等）打造的高性能、模块化、即插即用型自用技能库。  
> 统一收纳自研与精选的 AI 工作流规范、自动化工具链与开发脚手架，实现跨设备快速同步与一键部署。

---

## 📑 目录

- [一、仓库介绍与设计理念](#一仓库介绍与设计理念)
- [二、技能清单 (Skills Catalog)](#二技能清单-skills-catalog)
- [三、仓库目录结构](#三仓库目录结构)
- [四、快速安装与同步指南](#四快速安装与同步指南)
  - [4.1 使用一键脚本安装 (推荐)](#41-使用一键脚本安装-推荐)
  - [4.2 手动复制安装](#42-手动复制安装)
  - [4.3 多平台生态适配](#43-多平台生态适配)
- [五、新增 Skill 规范与模板](#五新增-skill-规范与模板)
- [六、维护与贡献准则](#六维护与贡献准则)
- [七、开源协议](#七开源协议)

---

## 一、仓库介绍与设计理念

随着 AI 结对编程走向“深度智能体化 (Agentic Coding)”，AI 助手不再只是代码补全工具，而是承担端到端任务规划、架构设计、自动化测试与版本交付的数字工程师。

本仓库 **`Personal-SKILL`** 致力于建立标准化的自用技能资产体系：
- **自包含与模块化**：每个技能均拥有专属独立目录，内嵌清晰的 `SKILL.md`（供 AI 识别）与详细的 `README.md`（供人类与 AI 阅读）；
- **真实物理证据链**：倡导所有技能必须具备清晰的验收标准、执行边界与必要的测试验证套件；
- **跨平台兼容**：核心指令兼容 Antigravity，并可无缝迁移至 Claude Code、Cursor 与 Codex 等主流工具；
- **一键分发**：提供自动化脚本，支持一键安装至全局环境或任意工程工作区。

---

## 二、技能清单 (Skills Catalog)

| 技能名称 (Skill) | 目录与文档 | 核心版本 | 分类标签 | 功能简介 | 状态 |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **`agent-handoff-workflow`** | [📖 详细文档](skills/agent-handoff-workflow/README.md) | `v2.2.0` | 工程流 / Git 规范 | **AI 项目连续性与 Git 原生交接工作流**<br>彻底解决 AI 会话失忆、跨设备进度丢失与乱建分支问题，提供双长期分支模型与门禁式微快照 | 🟢 生产就绪 |

*(未来新增的自用技能将持续同步登记至上表)*

---

## 三、仓库目录结构

本仓库采用清晰的模块化多 Skill 架构组织：

```text
Personal-SKILL/
├── README.md                           # 仓库总览文档与技能索引
├── LICENSE                             # MIT 开源许可证
├── .gitignore                          # 过滤 Python 缓存、IDE 配置与临时资产
├── install-skill.ps1                   # 一键安装/同步技能至本地或项目的 PowerShell 脚本
├── templates/                          # 规范模板库（方便未来扩展）
│   └── skill-template/                 # 标准 Skill 脚手架模板
│       ├── SKILL.md                    # 规范元数据与指令模版
│       └── README.md                   # 技能独立说明文档模版
└── skills/                             # 核心技能集合目录
    └── agent-handoff-workflow/         # 【技能】项目连续性与交接工作流
        ├── README.md                   # 该技能的专属深度解析与使用文档
        ├── SKILL.md                    # AI 读取的入口指令与工作流契约
        ├── assets/
        │   └── templates/              # 初始化项目所需的基础模板
        │       ├── AGENTS.md           # AI 顶级行为规范
        │       ├── PROJECT_STATUS.md   # 宏观状态与工单索引
        │       ├── DECISIONS.md        # 架构决策记录 (ADR)
        │       └── TASK-TEMPLATE.md    # 细粒度单任务工单
        ├── references/                 # 进阶技术与策略参考手册
        │   ├── continuity.md           # 初始化与异常接续细则
        │   └── git-lifecycle.md        # Git 完整操作细则与恢复表
        └── scripts/                    # 工具脚本与测试套件
            ├── inspect_handoff.py      # 只读接手检查与环境校验工具
            └── tests/
                └── test_inspect_handoff.py  # 11 项全自动回归单测
```

---

## 四、快速安装与同步指南

### 4.1 使用一键脚本安装 (推荐)

仓库根目录下内置了轻量易用的 PowerShell 工具脚本 [`install-skill.ps1`](install-skill.ps1)：

```powershell
# 1. 查看当前仓库中所有可用技能
.\install-skill.ps1 -List

# 2. 全局安装指定技能到 Google Antigravity (~/.gemini/config/skills/)
.\install-skill.ps1 -Skill agent-handoff-workflow

# 3. 安装指定技能到特定项目工作区 (<project>/.gemini/skills/)
.\install-skill.ps1 -Skill agent-handoff-workflow -ProjectPath "E:\DevelopProject\MyProject"
```

### 4.2 手动复制安装

若希望手动管理，只需将 `skills/<skill-name>` 目录直接拷贝至目标路径：

```powershell
# Windows PowerShell 手动复制到全局配置
Copy-Item -Path "skills\agent-handoff-workflow" -Destination "$HOME\.gemini\config\skills\agent-handoff-workflow" -Recurse -Force
```

### 4.3 多平台生态适配

- **Google Antigravity**：安装到全局 `$HOME/.gemini/config/skills/` 后，在任意对话中输入 `/agent-handoff-workflow` 即可激活；
- **Claude Code**：在项目根目录 `CLAUDE.md` 中引用技能规范，或将 `SKILL.md` 指令复制至系统提示词；
- **Cursor / Codex**：将相关模板（如 `assets/templates/AGENTS.md`）挂载至 `.cursorrules` 或工作区顶级规范中。

---

## 五、新增 Skill 规范与模板

当您需要为本仓库添加新的自用 Skill 时，请遵循以下四步标准流程：

1. **复制脚手架模板**：
   ```powershell
   Copy-Item -Path "templates\skill-template" -Destination "skills\your-new-skill" -Recurse
   ```
2. **编写 `SKILL.md`**：
   - 顶部必须包含规范的 YAML Frontmatter（包含 `name`、`description` 和 `version`）；
   - 正文清晰定义：何时使用、执行流程、边界条件与安全门禁。
3. **编写专属 `README.md`**：
   - 详细记录该技能要解决的核心痛点、目录组成、参数说明与命令行示例；
   - 确保即使在跨工具、跨平台或人类查阅时也能一目了然。
4. **登记索引**：
   - 在本根目录 `README.md` 的 [技能清单](#二技能清单-skills-catalog) 中追加一行记录，标明版本与功能简介。

---

## 六、维护与贡献准则

1. **零污染原则**：严禁提交 `.pyc`、虚拟环境目录（`.venv`）、模型大权重（`*.bin`, `*.onnx`）或私有密钥（`.env`）；
2. **测试门禁**：若技能包含独立脚本，必须在 `scripts/tests/` 中配套自动化单测，确保测试通过后再入库；
3. **文档与代码同步**：功能迭代时，必须同步更新 `SKILL.md` 的版本号与对应 `README.md`。

---

## 七、开源协议

本项目遵循 [MIT License](LICENSE) 开源协议。
