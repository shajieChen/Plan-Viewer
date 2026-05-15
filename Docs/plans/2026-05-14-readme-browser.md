# README 浏览器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 dashboard 中增加 README 浏览功能，点击项目名进入 README 渲染面板，支持面包屑导航和嵌套 markdown 文件跳转。

**Architecture:** 在 `dashboard_template.html` 中新增 `ReadmeViewer` React 组件（含 `BreadcrumbBar` 子组件），通过 `/api/file` API 实时加载 markdown 文件，用已有的 `marked.js` 渲染。App 组件新增 `readmeMode` 状态控制视图切换。

**Tech Stack:** React 18 (CDN), marked.js (已加载), Tailwind CSS (已加载), 现有 `/api/file` API

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `dashboard_template.html` | Modify | 新增 ReadmeViewer 组件、修改 App 组件状态和渲染逻辑 |

单文件修改。所有变更都在 `<script type="text/babel">` 块内。

---

## Task 1: 添加 ReadmeViewer 组件骨架和 App 状态

**Files:**
- Modify: `dashboard_template.html` (JSX 区域)

- [ ] **Step 1: 在 App 组件中添加 README 模式状态**

在 App 组件的状态声明区域（`const [showProjectManager, setShowProjectManager] = useState(false);` 之后）添加：

```jsx
            // README browser state
            const [readmeMode, setReadmeMode] = useState(false);
            const [readmePath, setReadmePath] = useState('README.md');
            const [readmeHistory, setReadmeHistory] = useState(['README.md']);
```

- [ ] **Step 2: 添加进入 README 模式的 handler**

在 `handleRefresh` 之后添加：

```jsx
            // Handle entering README mode
            const handleEnterReadme = useCallback(() => {
                setReadmeMode(true);
                setReadmePath('README.md');
                setReadmeHistory(['README.md']);
            }, []);

            // Handle exiting README mode (when clicking a view tab)
            const handleViewChange = useCallback((viewId) => {
                setActiveView(viewId);
                setReadmeMode(false);
            }, []);
```

- [ ] **Step 3: 修改项目名为可点击按钮**

在 App 的 return JSX 中，找到：

```jsx
                        <span className="text-lg font-semibold text-slate-800 mr-2">
                            {selectedProject || 'Dashboard'}
                        </span>
```

替换为：

```jsx
                        <span
                            className="text-lg font-semibold text-slate-800 mr-2 cursor-pointer hover:text-blue-600 transition-colors"
                            onClick={selectedProject ? handleEnterReadme : undefined}
                            title={selectedProject ? '查看项目 README' : ''}
                        >
                            {selectedProject || 'Dashboard'}
                        </span>
```

- [ ] **Step 4: 修改 view tab 的 onClick 使用 handleViewChange**

找到 view tabs 的 button：

```jsx
                                    onClick={() => setActiveView(view.id)}
```

替换为：

```jsx
                                    onClick={() => handleViewChange(view.id)}
```

- [ ] **Step 5: 验证页面正常加载**

刷新页面，确认项目名可点击（hover 变蓝），tab 切换正常。

---

## Task 2: 实现 ReadmeViewer 组件

**Files:**
- Modify: `dashboard_template.html` (在 ProjectManager 组件之前插入)

- [ ] **Step 1: 添加 ReadmeViewer 组件**

在 `ProjectManager` 组件定义之前（`// ProjectManager component` 注释之前），插入完整的 ReadmeViewer 组件：

```jsx
        // ReadmeViewer component - displays markdown files with breadcrumb navigation
        function ReadmeViewer({ currentPath, history, onNavigate, onBreadcrumbClick }) {
            const [content, setContent] = useState('');
            const [loading, setLoading] = useState(true);
            const [error, setError] = useState(null);
            const contentRef = useRef(null);

            // Fetch markdown file content
            useEffect(() => {
                setLoading(true);
                setError(null);
                fetch(`/api/file?path=${encodeURIComponent(currentPath)}`)
                    .then(res => {
                        if (!res.ok) throw new Error(`文件未找到: ${currentPath}`);
                        return res.text();
                    })
                    .then(text => {
                        setContent(text);
                        setLoading(false);
                    })
                    .catch(err => {
                        setError(err.message);
                        setLoading(false);
                    });
            }, [currentPath]);

            // Render markdown and intercept links
            useEffect(() => {
                if (!contentRef.current || !content) return;

                // Render markdown with marked.js
                const html = marked.parse(content);
                contentRef.current.innerHTML = html;

                // Intercept clicks on links
                const handleClick = (e) => {
                    const link = e.target.closest('a');
                    if (!link) return;

                    const href = link.getAttribute('href');
                    if (!href) return;

                    // Absolute URLs - open in new tab
                    if (href.startsWith('http://') || href.startsWith('https://')) {
                        link.setAttribute('target', '_blank');
                        link.setAttribute('rel', 'noopener noreferrer');
                        return;
                    }

                    // Anchor links - scroll within page
                    if (href.startsWith('#')) {
                        const target = contentRef.current.querySelector(href);
                        if (target) target.scrollIntoView({ behavior: 'smooth' });
                        e.preventDefault();
                        return;
                    }

                    // Relative .md links - navigate within viewer
                    if (href.endsWith('.md') || href.includes('.md#')) {
                        e.preventDefault();
                        const mdPath = href.split('#')[0];
                        // Resolve relative path
                        const basePath = currentPath.substring(0, currentPath.lastIndexOf('/') + 1);
                        const resolvedPath = resolvePath(basePath + mdPath);
                        onNavigate(resolvedPath);
                        return;
                    }

                    // Other relative files - open via API in new tab
                    e.preventDefault();
                    const basePath = currentPath.substring(0, currentPath.lastIndexOf('/') + 1);
                    const resolvedPath = resolvePath(basePath + href);
                    window.open(`/api/file?path=${encodeURIComponent(resolvedPath)}`, '_blank');
                };

                contentRef.current.addEventListener('click', handleClick);
                return () => {
                    if (contentRef.current) {
                        contentRef.current.removeEventListener('click', handleClick);
                    }
                };
            }, [content, currentPath, onNavigate]);

            // Build breadcrumb items from history
            const breadcrumbs = useMemo(() => {
                return history.map((path, index) => {
                    const parts = path.split('/');
                    const label = index === 0 ? '📄 README.md' : parts[parts.length - 1];
                    const isLast = index === history.length - 1;
                    return { path, label, isLast, fullParts: parts };
                });
            }, [history]);

            // Expanded breadcrumb with directory segments
            const expandedBreadcrumbs = useMemo(() => {
                if (history.length <= 1) return breadcrumbs;
                const lastPath = history[history.length - 1];
                const parts = lastPath.split('/');
                const items = [{ label: '📄 README.md', path: history[0], isLast: false }];
                // Add intermediate directory segments
                for (let i = 0; i < parts.length - 1; i++) {
                    items.push({ label: parts[i], path: null, isLast: false });
                }
                // Add current file
                items.push({ label: parts[parts.length - 1], path: lastPath, isLast: true });
                return items;
            }, [history, breadcrumbs]);

            return (
                <div className="flex-1 flex flex-col overflow-hidden bg-white/60 backdrop-blur-xl rounded-2xl border border-[#8EABC9]">
                    {/* Breadcrumb bar */}
                    <div className="px-4 py-2.5 border-b border-[#8EABC9] bg-white/80 backdrop-blur-sm rounded-t-2xl flex items-center gap-1 flex-wrap text-sm">
                        {expandedBreadcrumbs.map((item, index) => (
                            <React.Fragment key={index}>
                                {index > 0 && <span className="text-slate-400 mx-1">&gt;</span>}
                                {item.isLast ? (
                                    <span className="text-slate-600 font-medium">{item.label}</span>
                                ) : item.path ? (
                                    <button
                                        className="text-blue-600 hover:text-blue-800 hover:underline cursor-pointer bg-transparent border-none text-sm transition-colors"
                                        onClick={() => onBreadcrumbClick(item.path)}
                                    >
                                        {item.label}
                                    </button>
                                ) : (
                                    <span className="text-slate-500">{item.label}</span>
                                )}
                            </React.Fragment>
                        ))}
                    </div>

                    {/* Content area */}
                    <div className="flex-1 overflow-auto p-6">
                        {loading && (
                            <div className="text-center text-slate-400 py-10">加载中...</div>
                        )}
                        {error && (
                            <div className="text-center text-red-500 py-10">{error}</div>
                        )}
                        {!loading && !error && (
                            <div
                                ref={contentRef}
                                className="prose prose-slate max-w-none prose-headings:text-slate-800 prose-a:text-blue-600 prose-code:text-slate-700 prose-code:bg-slate-100 prose-code:px-1 prose-code:rounded prose-pre:bg-slate-100 prose-pre:border prose-pre:border-slate-200"
                            />
                        )}
                    </div>
                </div>
            );
        }

        // Utility: resolve relative path (handle .. and .)
        function resolvePath(path) {
            const parts = path.split('/');
            const resolved = [];
            for (const part of parts) {
                if (part === '.' || part === '') continue;
                if (part === '..') {
                    resolved.pop();
                } else {
                    resolved.push(part);
                }
            }
            return resolved.join('/');
        }
```

- [ ] **Step 2: 验证组件语法正确**

刷新页面，确认无 JS 错误（组件已定义但尚未被渲染）。

---

## Task 3: 在 App 中集成 ReadmeViewer 渲染

**Files:**
- Modify: `dashboard_template.html` (App 组件的 return JSX)

- [ ] **Step 1: 在主内容区添加 README 模式渲染**

在 App 的主内容区 `<div className="p-4 overflow-hidden flex flex-col" style={{gridArea: 'main'}}>` 内部，在 `{hasNoProjects && ...}` 之后、`{!hasNoProjects && activeView === 'dag' ...}` 之前，插入：

```jsx
                        {!hasNoProjects && readmeMode && (
                            <ReadmeViewer
                                currentPath={readmePath}
                                history={readmeHistory}
                                onNavigate={(newPath) => {
                                    setReadmePath(newPath);
                                    setReadmeHistory(prev => [...prev, newPath]);
                                }}
                                onBreadcrumbClick={(path) => {
                                    const index = readmeHistory.indexOf(path);
                                    if (index >= 0) {
                                        setReadmeHistory(prev => prev.slice(0, index + 1));
                                        setReadmePath(path);
                                    } else {
                                        // Root README click
                                        setReadmePath('README.md');
                                        setReadmeHistory(['README.md']);
                                    }
                                }}
                            />
                        )}
```

- [ ] **Step 2: 修改其他视图的渲染条件，加上 `!readmeMode`**

将所有 4 个视图的条件从：
```jsx
{!hasNoProjects && activeView === 'dag' && currentProjectData && (
```

改为：
```jsx
{!hasNoProjects && !readmeMode && activeView === 'dag' && currentProjectData && (
```

对 `swimlane`、`statemachine`、`hotspots` 同样添加 `!readmeMode &&`。

- [ ] **Step 3: 在 toolbar 中给 tab 添加 README 模式下的视觉反馈**

修改 view tab 的 active 判断，当 `readmeMode` 为 true 时所有 tab 都不高亮：

```jsx
                                    className={`px-4 py-1.5 rounded-lg text-sm transition-all duration-200 ${
                                        !readmeMode && activeView === view.id
                                            ? 'bg-blue-500/20 border border-blue-400/40 text-blue-700 shadow-lg shadow-blue-500/20'
                                            : 'border border-transparent text-slate-500 hover:bg-white/90 hover:text-slate-800'
                                    }`}
```

- [ ] **Step 4: 验证完整功能**

1. 刷新页面
2. 点击左上角项目名 → 应进入 README 浏览模式，显示面包屑和 README 内容
3. 点击 README 中的 .md 链接 → 应在面板内跳转，面包屑更新
4. 点击面包屑中的 "📄 README.md" → 应跳回根 README
5. 点击任意 view tab → 应退出 README 模式，回到正常视图

---

## Task 4: 添加 Tailwind Typography 支持和 Markdown 样式微调

**Files:**
- Modify: `dashboard_template.html` (style 块和 Tailwind config)

- [ ] **Step 1: 在 Tailwind config 中启用 typography 插件**

由于使用 Tailwind Play CDN，`prose` class 已内置支持。但需要在 `<style>` 块中添加一些针对暗色面板的 markdown 渲染微调：

在 `<style>` 块的 `@keyframes fadeSlideUp` 之后添加：

```css
        /* === Markdown Prose Overrides === */
        .prose h1 { font-size: 1.5rem; margin-bottom: 0.75rem; margin-top: 1.5rem; }
        .prose h2 { font-size: 1.25rem; margin-bottom: 0.5rem; margin-top: 1.25rem; }
        .prose h3 { font-size: 1.1rem; margin-bottom: 0.5rem; margin-top: 1rem; }
        .prose p { margin-bottom: 0.75rem; line-height: 1.7; }
        .prose ul, .prose ol { margin-bottom: 0.75rem; padding-left: 1.5rem; }
        .prose li { margin-bottom: 0.25rem; }
        .prose a { color: #2563eb; text-decoration: underline; }
        .prose a:hover { color: #1d4ed8; }
        .prose code { font-size: 0.85em; }
        .prose pre { padding: 1rem; overflow-x: auto; border-radius: 0.5rem; }
        .prose blockquote { border-left: 3px solid #8EABC9; padding-left: 1rem; color: #64748b; }
        .prose table { width: 100%; border-collapse: collapse; margin-bottom: 1rem; }
        .prose th, .prose td { border: 1px solid #e2e8f0; padding: 0.5rem 0.75rem; text-align: left; }
        .prose th { background: #f8fafc; font-weight: 600; }
        .prose img { max-width: 100%; border-radius: 0.5rem; }
```

- [ ] **Step 2: 验证 markdown 渲染样式**

进入 README 模式，确认标题、段落、代码块、链接、列表等元素样式正常。

---

## Task 5: 处理 handleProjectChange 时退出 README 模式

**Files:**
- Modify: `dashboard_template.html` (App 组件)

- [ ] **Step 1: 在 handleProjectChange 中重置 README 状态**

找到：
```jsx
            const handleProjectChange = useCallback((projectName) => {
                setSelectedProject(projectName);
                setActiveFilters({ plan: true, landing_prompt: true, test_prompt: true });
                setSelectedArtifact(null);
                setSidebarOpen(false);
            }, []);
```

替换为：
```jsx
            const handleProjectChange = useCallback((projectName) => {
                setSelectedProject(projectName);
                setActiveFilters({ plan: true, landing_prompt: true, test_prompt: true });
                setSelectedArtifact(null);
                setSidebarOpen(false);
                setReadmeMode(false);
            }, []);
```

- [ ] **Step 2: 同样修改 handleSelectProjectFromManager**

找到：
```jsx
            const handleSelectProjectFromManager = useCallback((projectName) => {
                setSelectedProject(projectName);
                setActiveFilters({ plan: true, landing_prompt: true, test_prompt: true });
                setSelectedArtifact(null);
                setSidebarOpen(false);
                setShowProjectManager(false);
            }, []);
```

替换为：
```jsx
            const handleSelectProjectFromManager = useCallback((projectName) => {
                setSelectedProject(projectName);
                setActiveFilters({ plan: true, landing_prompt: true, test_prompt: true });
                setSelectedArtifact(null);
                setSidebarOpen(false);
                setShowProjectManager(false);
                setReadmeMode(false);
            }, []);
```

- [ ] **Step 3: 验证切换项目时退出 README 模式**

在 README 模式下，通过项目选择器切换项目，确认回到正常视图。

---

## Task 6: 最终验收

**Files:**
- Modify: `dashboard_template.html` (如有微调)

- [ ] **Step 1: 完整功能测试**

测试清单：
1. 点击项目名 → 进入 README 模式，加载根 README
2. README 中的 `.md` 相对链接 → 面板内跳转，面包屑更新
3. 面包屑 "📄 README.md" → 跳回根
4. 面包屑中间层级 → 正确截断历史
5. 外部链接（http/https）→ 新标签页打开
6. 非 .md 文件链接 → 通过 API 新标签页打开
7. 点击任意 view tab → 退出 README 模式
8. 切换项目 → 退出 README 模式
9. README 不存在 → 显示错误提示
10. 页面刷新后 → 回到正常视图（README 模式不持久化）

- [ ] **Step 2: 运行现有测试**

```bash
python -m pytest tests/ -v
```

确认所有测试通过（纯前端变更不影响 Python 逻辑）。

---
