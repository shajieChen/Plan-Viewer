import { invoke } from '@tauri-apps/api/core';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { open } from '@tauri-apps/plugin-dialog';
import { useState } from 'preact/hooks';
import huskyIcon from '../assets/husky-icon.png';

export function TitleBar({ autoShrink = true, onToggleAutoShrink, showReadme = false, onToggleReadme, onAddProject, boundProcess = null, onFocusClick, onUnbind, focusBtnRef }) {
  const [pinned, setPinned] = useState(true);

  const togglePin = async () => {
    const newState = !pinned;
    await invoke('set_always_on_top', { enabled: newState });
    setPinned(newState);
  };

  const hideWindow = async () => {
    const win = getCurrentWindow();
    await win.hide();
  };

  const handleAddProject = async () => {
    const selected = await open({ directory: true, title: '选择工程目录' });
    if (selected) {
      onAddProject(selected);
    }
  };

  return (
    <div class="title-bar" data-tauri-drag-region>
      <img src={huskyIcon} alt="Plan Viewer" class="app-logo" width="20" height="20" />
      <button onClick={togglePin} title={pinned ? '取消置顶' : '置顶'}>
        {pinned ? '📌' : '📍'}
      </button>
      <button
        onClick={onToggleAutoShrink}
        title={autoShrink ? '禁用自动缩小' : '启用自动缩小'}
        class={`auto-shrink-toggle ${autoShrink ? 'enabled' : 'disabled'}`}
      >
        {autoShrink ? '⇲' : '⇱'}
      </button>
      <button
        onClick={onToggleReadme}
        title="项目导读"
        class={`readme-toggle ${showReadme ? 'active' : ''}`}
      >
        📖
      </button>
      <button onClick={handleAddProject} title="添加工程">
        📂
      </button>
      <button
        ref={focusBtnRef}
        onClick={onFocusClick}
        title={boundProcess ? `聚焦: ${boundProcess.processName}` : '未绑定进程'}
        class={`focus-btn ${boundProcess ? 'bound' : 'unbound'}`}
      >
        🎯
      </button>
      {boundProcess && (
        <button onClick={onUnbind} title="取消绑定" class="unbind-btn">
          ✖
        </button>
      )}
      <button onClick={hideWindow} title="最小化到托盘">
        ✕
      </button>
    </div>
  );
}
