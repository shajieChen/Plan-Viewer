# R-001: Dashboard 可视化方案调研

## 调研目标

为 project-state-tracker 的 Research → Decision → Plan → LandingPrompt → TestPrompt 流程寻找可视化方案参考。

## 调研结论

**没有找到直接针对 AI agent 项目状态管理流程的现成可视化工具**，但找到了多个可组合的技术方案。

## 参考方案

### 1. visual-explainer（GitHub 8.2k stars）

- 地址：https://github.com/nicobailon/visual-explainer
- 定位：Agent skill，把复杂终端输出转成自包含 HTML 页面
- 支持 `/plan-review`、`/project-recap`、`/generate-visual-plan`
- 用 Mermaid.js 画流程图/依赖图，CSS Grid 做架构概览
- 输出自包含 HTML，浏览器直接打开
- **局限**：按需生成快照，不是持久化 dashboard

### 2. Stately.ai / XState Visualizer

- 地址：https://stately.ai/
- 专做状态机可视化编辑和模拟
- Stately Sketch：左边写状态机代码，右边实时看交互式图
- 9-state artifact 状态枚举天然适合 statechart 表达
- **局限**：SaaS 产品，不适合嵌入本地工具链

### 3. Microsoft Prompt Flow

- 地址：https://microsoft.github.io/promptflow/
- YAML 定义的 DAG 流程，VS Code 扩展提供可视化编辑器
- flow.dag.yaml 描述节点依赖，工具自动渲染 DAG 图
- **局限**：专为 LLM pipeline 设计，不通用

### 4. yml2dot

- 地址：https://github.com/lucasepe/yml2dot
- 直接把 YAML 结构转成 Graphviz DOT 图
- **局限**：静态输出，无交互

### 5. 依赖图可视化工具

- Azure Boards Delivery Plans：跨团队依赖可视化
- VisualBacklog.app（Jira 插件）：交互式依赖图
- TaskView.tech：任务依赖图
- **局限**：都是 SaaS，不适合本地集成

### 6. Mermaid.js

- 地址：https://mermaid.js.org/
- 支持 Flowchart、State Diagram、Kanban 等多种图表
- CDN 引入，浏览器端渲染
- **适合**：作为 DAG 和状态机视图的渲染引擎

## 技术选型结论

| 需求 | 选用技术 |
|------|---------|
| DAG 依赖图 | Mermaid.js flowchart |
| 状态机视图 | Mermaid.js stateDiagram-v2 |
| 泳道图 | CSS Grid + React 组件 |
| Markdown 预览 | marked.js |
| UI 框架 | React 18 CDN + Babel standalone |
| 输出形式 | 单文件 HTML，集成到 render_status.py |

## 调研日期

2026-05-14
