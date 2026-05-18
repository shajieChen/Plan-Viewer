# Requirements Document

## Introduction

当鼠标离开应用窗口（失去 hover）时，窗口自动缩小到 tauri.conf.json 中配置的初始大小（400×300），同时进入透明化状态。当鼠标重新 hover 到窗口上时，窗口恢复到缩小前的尺寸。此功能增强了 Plan Viewer 作为桌面浮动小组件的体验——不使用时占用最小屏幕空间，需要时立即恢复完整视图。

## Glossary

- **Window_Manager**: 负责窗口尺寸管理的前端模块，通过 Tauri window API 控制窗口的缩放和恢复
- **Hover_Detector**: 检测鼠标是否在窗口区域内的前端模块（现有 `useWindowHover` hook 的扩展）
- **Initial_Size**: tauri.conf.json 中配置的窗口初始尺寸，当前为 400×300 像素
- **Saved_Size**: 窗口在缩小前记录的用户调整后的尺寸（宽度和高度）
- **Idle_State**: 鼠标离开窗口后经过延迟时间进入的状态，窗口处于缩小和透明化状态
- **Active_State**: 鼠标在窗口区域内时的状态，窗口处于完整尺寸和不透明状态
- **Shrink_Delay**: 鼠标离开窗口后到窗口开始缩小的等待时间（即 Shrink_Dwell_Delay，1500ms）
- **Restore_Dwell_Delay**: 鼠标进入缩小窗口后，需持续停留的时间（1500ms），超过此时间才触发窗口放大恢复
- **Shrink_Dwell_Delay**: 鼠标离开窗口后，需持续在窗口外停留的时间（1500ms），超过此时间才触发窗口缩小
- **Auto_Shrink_Toggle**: 标题栏中的开关按钮，用于启用或禁用自动缩小功能
- **TitleBar**: 窗口顶部的标题栏组件，包含 Pin 按钮、Auto-Shrink 开关和关闭按钮

## Requirements

### Requirement 1: 窗口缩小触发

**User Story:** As a 用户, I want 窗口在鼠标离开后自动缩小, so that 不使用时占用最小屏幕空间。

#### Acceptance Criteria

1. WHEN the mouse leaves the window area and remains outside for the duration of the Shrink_Dwell_Delay (1500ms), THE Window_Manager SHALL save the current window size as Saved_Size and resize the window to Initial_Size (400×300).
2. WHILE the window is already at Initial_Size or smaller, WHEN the mouse leaves the window area, THE Window_Manager SHALL not perform any resize operation.
3. THE Window_Manager SHALL apply a CSS transition animation during the shrink operation with a duration of 300ms.
4. WHEN the mouse re-enters the window area before the Shrink_Dwell_Delay elapses, THE Window_Manager SHALL cancel the pending shrink and keep the window at its current (enlarged) size — symmetric with how a leave during the Restore_Dwell_Delay cancels the pending restore.
5. WHEN a second mouse-leave event fires while a Shrink_Dwell_Delay timer is already pending, THE Window_Manager SHALL reset the timer (cancel and restart with full Shrink_Dwell_Delay) rather than stack multiple timers.

### Requirement 2: 窗口恢复触发

**User Story:** As a 用户, I want 窗口在鼠标 hover 回来时恢复到之前的大小, so that 我可以立即继续查看完整内容。

#### Acceptance Criteria

1. WHEN the mouse enters the window area and remains for the duration of the Restore_Dwell_Delay (1500ms), THE Window_Manager SHALL resize the window to the Saved_Size.
2. IF no Saved_Size exists (first launch or window was never resized beyond Initial_Size), THEN THE Window_Manager SHALL keep the window at its current size without resizing.
3. THE Window_Manager SHALL apply a CSS transition animation during the restore operation with a duration of 300ms.

### Requirement 3: 缩小延迟

**User Story:** As a 用户, I want 窗口缩小有一个短暂延迟, so that 鼠标意外移出窗口时不会立即触发缩小。

#### Acceptance Criteria

1. WHEN the mouse leaves the window area, THE Window_Manager SHALL start a 1500ms Shrink_Dwell_Delay timer before performing the shrink operation.
2. WHEN the mouse re-enters the window area before the Shrink_Dwell_Delay elapses, THE Window_Manager SHALL cancel the pending shrink (symmetric with the Restore_Dwell_Delay cancellation rule); see Requirement 1, AC 4.
3. THE Shrink_Dwell_Delay (1500ms) is owned by the Window_Manager (the `useWindowAutoShrink` hook) and is independent of the Hover_Detector's transparency debounce.

### Requirement 4: 尺寸记忆

**User Story:** As a 用户, I want 窗口记住我调整过的大小, so that 每次恢复时都能回到我习惯的尺寸。

#### Acceptance Criteria

1. WHEN the user manually resizes the window while in Active_State, THE Window_Manager SHALL update the Saved_Size to reflect the new dimensions.
2. THE Window_Manager SHALL persist Saved_Size only in memory for the current application session.
3. WHEN the application starts, THE Window_Manager SHALL initialize with no Saved_Size (window starts at Initial_Size as configured in tauri.conf.json).

### Requirement 5: 透明化与缩小同步

**User Story:** As a 用户, I want 透明化和缩小同时发生, so that 状态切换感觉流畅自然。

#### Acceptance Criteria

1. WHEN transitioning to Idle_State, THE Window_Manager SHALL trigger the shrink operation simultaneously with the existing opacity transition.
2. WHEN transitioning to Active_State, THE Window_Manager SHALL trigger the restore operation simultaneously with the existing opacity transition.
3. THE Window_Manager SHALL coordinate with the Hover_Detector so that both size and opacity transitions use the same trigger event.

### Requirement 6: Auto-Shrink 开关

**User Story:** As a 用户, I want 在标题栏有一个开关来启用或禁用自动缩小功能, so that 我可以根据需要控制窗口是否自动缩小。

#### Acceptance Criteria

1. THE TitleBar SHALL display an Auto-Shrink toggle button adjacent to the Pin button.
2. WHEN the user clicks the Auto-Shrink toggle, THE Window_Manager SHALL enable or disable the auto-shrink behavior accordingly.
3. WHILE Auto-Shrink is disabled, WHEN the mouse leaves the window area, THE Window_Manager SHALL not perform any shrink operation (transparency transition still applies).
4. THE TitleBar SHALL visually indicate the current Auto-Shrink state using distinct icons or styling for enabled and disabled states.
5. WHEN the application starts, THE Auto-Shrink toggle SHALL default to enabled.

### Requirement 7: 窗口位置保持

**User Story:** As a 用户, I want 窗口缩小和恢复时保持在屏幕上的相对位置, so that 窗口不会跳到意外的位置。

#### Acceptance Criteria

1. WHEN the window shrinks, THE Window_Manager SHALL keep the window's top-left corner position unchanged.
2. WHEN the window restores, THE Window_Manager SHALL keep the window's top-left corner position unchanged.
3. IF the restored size would cause the window to extend beyond the screen boundary, THEN THE Window_Manager SHALL clamp the window size to fit within the visible screen area.


### Requirement 8: 恢复放大停留延迟

**User Story:** As a 用户, I want 鼠标需要在缩小窗口内停留一段时间才触发放大, so that 鼠标快速划过窗口时不会触发意外的放大抖动。

#### Acceptance Criteria

1. WHEN the mouse enters the window area while the window is in shrunk state, THE Window_Manager SHALL start a 1500ms dwell timer before performing the restore operation.
2. WHEN the mouse leaves the window area before the 1500ms dwell timer elapses, THE Window_Manager SHALL cancel the pending restore and keep the window at Initial_Size.
3. WHEN the mouse enters the window area while the window is in shrunk state, THE Window_Manager SHALL immediately restore opacity (via CSS class transition to Active_State) without waiting for the dwell timer.
4. THE Window_Manager SHALL reset the dwell timer on each new mouse-enter event (no accumulation from previous partial dwells).
