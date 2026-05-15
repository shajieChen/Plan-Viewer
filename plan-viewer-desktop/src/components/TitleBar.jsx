import { invoke } from '@tauri-apps/api/core';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { useState } from 'preact/hooks';

export function TitleBar({ autoShrink = true, onToggleAutoShrink }) {
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

  return (
    <div class="title-bar" data-tauri-drag-region>
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
      <button onClick={hideWindow} title="最小化到托盘">
        ✕
      </button>
    </div>
  );
}
