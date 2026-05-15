# Design: README 浏览器（项目文档导航）

## 概述

在 dashboard 中增加 README 浏览功能。用户点击左上角项目名时，主内容区切换为 README 渲染面板，支持通过面包屑导航在嵌套的 markdown 文件之间跳转。

## 触发方式

- 点击 toolbar 左上角的项目名称（如 "UE_Iris"）进入 README 浏览模式
- 点击任意 view tab（DAG View / Swim Lane / State Machine / Hotspots）退出 README 模式，回到正常视图

## 交互流程

1. 用户点击项目名 → 主内容区替换为 README 面板
2. 通过 `GET /api/file?path=README.md` 从服务器加载项目根目录的 README.md
3. 用 `marked.js`（页面已加载）渲染 markdown 为 HTML
4. README 中的相对路径 `.md` 链接被拦截，点击后在同一面板内加载目标文件
5. 顶部面包屑显示当前浏览层级
6. 用户可随时点击面包屑跳回上级或根 README
7. 用户点击任意 view tab 退出 README 模式

## 面包屑导航

### 格式

```
📄 README.md > Research > UE_03-ReplicationSystem > README.md
```

### 规则

- 第一项始终是 `📄 README.md`（项目根），可点击，直接跳回根 README
- 中间项为路径中的目录名，可点击（跳转到对应层级的文件）
- 最后一项为当前文件名，不可点击（表示当前位置）
- 面包屑条固定在内容区顶部，README 内容区域独立滚动
- 各层级之间用 `>` 分隔

### 面包屑生成逻辑

从 `readmeHistory` 栈生成。例如浏览历史为 `['README.md', 'Research/UE_03-ReplicationSystem/README.md']`，则面包屑显示：

```
📄 README.md > Research > UE_03-ReplicationSystem > README.md
                                                      ↑ 当前（不可点击）
              ↑ 点击跳回 history[0]
```

## 链接处理规则

| 链接类型 | 行为 |
|---------|------|
| 相对路径 `.md` 文件（如 `./sub/README.md`） | 拦截，在面板内加载，push 到 history |
| 相对路径非 `.md` 文件（如 `./image.png`） | 用 `/api/file?path=...` 在新标签页打开 |
| 绝对 URL（http/https） | 新标签页打开（`target="_blank"`） |
| 锚点链接（`#section`） | 页内滚动到对应标题 |

### 相对路径解析

当前文件为 `Research/UE_03/README.md`，其中有链接 `../UE_04/README.md`，则解析为 `Research/UE_04/README.md`。使用标准路径解析逻辑（处理 `..` 和 `.`）。

## 数据获取

- 使用现有的 `GET /api/file?path=<relative_path>` 接口
- 服务器已实现该接口，会在所有已注册项目中搜索文件
- 返回原始文件内容（text/plain 或对应 MIME type）
- 前端拿到 markdown 文本后用 `marked.js` 渲染

## 状态管理

在 App 组件中新增状态：

```javascript
const [readmeMode, setReadmeMode] = useState(false);       // 是否处于 README 浏览模式
const [readmePath, setReadmePath] = useState('README.md');  // 当前显示的文件路径
const [readmeHistory, setReadmeHistory] = useState([]);     // 浏览历史栈
```

### 状态转换

- **进入 README 模式**：点击项目名 → `readmeMode=true, readmePath='README.md', readmeHistory=['README.md']`
- **跳转子文件**：点击 md 链接 → 解析完整路径，push 到 history，更新 readmePath
- **面包屑跳转**：点击面包屑某一级 → 截断 history 到该级，更新 readmePath
- **退出 README 模式**：点击任意 view tab → `readmeMode=false`

## UI 布局

### README 面板结构

```
┌─────────────────────────────────────────────┐
│ 📄 README.md > Research > UE_03 > README.md │  ← 面包屑（固定）
├─────────────────────────────────────────────┤
│                                             │
│  [渲染后的 Markdown 内容]                    │  ← 可滚动区域
│                                             │
│  ## 标题                                    │
│  正文内容...                                 │
│  [链接到子文档](./sub/README.md)  ← 可点击   │
│                                             │
└─────────────────────────────────────────────┘
```

### 样式

- 面包屑条：与当前 toolbar 风格一致（`bg-white/80 backdrop-blur` 等）
- 内容区：白色背景面板，与其他 view 的毛玻璃容器一致
- Markdown 渲染：使用 Tailwind typography 样式（`prose` class）或手写基础排版样式
- 链接：蓝色下划线，hover 加深

## 错误处理

| 场景 | 行为 |
|------|------|
| README.md 不存在 | 显示提示："该项目没有 README.md 文件" |
| 子链接目标文件不存在 | 显示提示："文件未找到: [path]"，保留面包屑可返回 |
| 网络请求失败 | 显示错误提示，保留面包屑可返回 |
| 文件内容为空 | 显示提示："文件为空" |

## 组件结构

新增一个 `ReadmeViewer` 组件：

```
ReadmeViewer
├── BreadcrumbBar (面包屑导航)
└── MarkdownContent (渲染区域)
```

在 App 的主内容区中，当 `readmeMode === true` 时渲染 `ReadmeViewer`，否则渲染原有的 view 组件。

## 不做的事情

- 不做全文搜索
- 不做目录树侧边栏
- 不做编辑功能
- 不缓存已加载的文件（每次点击都重新 fetch，保证内容最新）
- 不处理非 markdown 文件的内联预览（图片除外，marked.js 会自动处理 img 标签）
