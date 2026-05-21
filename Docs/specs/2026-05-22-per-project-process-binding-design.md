# Per-Project Process Binding with Persistence

## 概述

将进程聚焦功能从"全局单绑定"升级为"每项目独立绑定 + 本地持久化"。每个项目各自记住自己绑定的进程，切换项目时 🎯 按钮自动显示对应绑定状态。绑定关系持久化到本地 JSON 文件，应用重启后自动恢复。

## 当前状态

- `boundProcess` 是 App.jsx 中的单一 state，所有项目共享
- 绑定纯内存，重启即丢失
- 切换项目不影响绑定状态

## 目标状态

- 每个项目独立维护自己的进程绑定
- 绑定关系持久化到 `process_bindings.json`
- 切换项目时自动加载该项目的绑定
- 懒检查：只在用户点击 🎯 时检测进程存活

## 数据模型

### process_bindings.json（Tauri app_data_dir）

```json
{
  "ProjectA": {
    "pid": 1234,
    "hwnd": 5678,
    "process_name": "devenv.exe",
    "window_title": "MyProject - Visual Studio"
  },
  "ProjectB": {
    "pid": 9012,
    "hwnd": 3456,
    "process_name": "code.exe",
    "window_title": "index.ts - VSCode"
  }
}
```

字段说明：
- key = 项目名（与 projects dict 中的 key 一致）
- pid/hwnd = 绑定时记录的进程标识
- process_name/window_title = 用于 UI 显示

## Rust 后端变更

新增三个 Tauri 命令：

### `read_process_bindings() -> HashMap<String, ProcessBinding>`
- 读取 `app_data_dir/process_bindings.json`
- 文件不存在返回空 HashMap
- 解析失败返回空 HashMap（不报错，容错处理）

### `write_process_binding(project_name: String, binding: ProcessBinding)`
- 读取现有文件 → 更新指定 key → 写回
- 文件不存在则创建

### `remove_process_binding(project_name: String)`
- 读取现有文件 → 删除指定 key → 写回
- key 不存在时静默成功

数据结构：
```rust
#[derive(Serialize, Deserialize, Clone)]
pub struct ProcessBinding {
    pub pid: u32,
    pub hwnd: isize,
    pub process_name: String,
    pub window_title: String,
}
```

## 前端变更

### App.jsx 状态变更

```
// 旧
const [boundProcess, setBoundProcess] = useState(null);

// 新
const [processBindings, setProcessBindings] = useState({});
// 当前项目的绑定 = processBindings[selectedProject] || null
```

### 启动流程

1. App 挂载时调用 `read_process_bindings` 加载全部绑定到 `processBindings` state
2. 根据 `selectedProject` 从 map 中取当前绑定
3. TitleBar 的 🎯 按钮根据当前绑定显示 bound/unbound 状态

### 切换项目

- 切换 `selectedProject` 时，`boundProcess` 自动变为 `processBindings[newProject] || null`
- 不做存活检查，不弹选择器
- 按钮立即反映新项目的绑定状态

### 点击 🎯（聚焦）

- 如果当前项目无绑定 → 打开 ProcessSelector
- 如果有绑定 → 调用 `focus_bound_window`
  - 成功 → 窗口聚焦
  - 返回 `process_terminated` → 清除该项目绑定（内存 + 持久化），弹出选择器

### 绑定成功

1. 更新 `processBindings[selectedProject]` 内存
2. 调用 `write_process_binding(selectedProject, binding)` 持久化
3. 关闭选择器

### 解绑

1. 删除 `processBindings[selectedProject]` 内存
2. 调用 `remove_process_binding(selectedProject)` 持久化
3. 按钮变为 unbound

## 不变的部分

- ProcessSelector 组件（UI、搜索、选择逻辑）
- TitleBar 的按钮外观和交互模式
- `enumerate_processes` / `bind_process` / `focus_bound_window` 后端命令
- 进程枚举和聚焦的 Win32 API 逻辑

## 边界情况

| 场景 | 行为 |
|------|------|
| 应用启动，绑定文件不存在 | 所有项目显示未绑定 |
| 应用启动，绑定文件损坏 | 忽略，当作空文件 |
| 项目被删除但绑定还在文件中 | 无影响，孤儿条目不显示也不报错 |
| 同一进程被多个项目绑定 | 允许，每个项目独立管理 |
| 绑定写入失败（磁盘满等） | 内存状态正常，下次启动丢失该绑定 |

## 测试策略

### 属性测试
- 绑定映射一致性：对任意项目序列的绑定/解绑操作，`processBindings[project]` 始终等于最后一次成功绑定的值或 null
- 切换项目不修改其他项目的绑定

### 单元测试
- 启动加载绑定后，切换项目显示正确的 bound/unbound 状态
- 绑定成功后调用 `write_process_binding`
- 解绑后调用 `remove_process_binding`
- 进程死亡后清除绑定并调用 `remove_process_binding`
- Rust 端 read/write/remove 的文件操作正确性
