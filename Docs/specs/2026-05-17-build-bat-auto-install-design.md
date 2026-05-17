# Design: build.bat Auto-Install Hardening

**Date**: 2026-05-17
**Status**: Approved
**Owner**: Plan-Viewer

## Problem

Original `build.bat` assumed Node.js + Rust were already installed and on PATH.
A clean machine ran into three blockers in sequence:

1. `cargo metadata` not found — Rust toolchain missing.
2. After installing rustup, `rustc -vV` reported "Missing manifest in toolchain
   stable-x86_64-pc-windows-msvc" — partially-installed toolchain.
3. After Rust compiled successfully, the build hung on a global timeout
   downloading `nsis-3.11.zip` from GitHub (slow CDN).

Each blocker required manual intervention. The script should self-heal.

## Goals

- Run on a clean Windows machine with zero manual setup.
- Survive partial installs / corrupted manifests.
- Avoid network-dependent steps by default.
- Keep advanced packaging (NSIS installer) available behind a flag.

## Non-Goals

- Support OS other than Windows (current `serve.bat` family is Windows-only).
- Auto-install Visual Studio Build Tools (rustup minimal profile pulls them in
  on first compile if needed; documenting this is out of scope).

## Approach

### Decisions

| Concern | Choice | Rationale |
|---|---|---|
| Missing Rust | Auto-install via rustup-init silent (`-y --profile minimal`) | Single-step, no user prompts |
| Missing Node.js | Auto-install via `winget install OpenJS.NodeJS.LTS --silent` | winget bundled in Win10 1809+ |
| PATH for cargo | In-session inject `%USERPROFILE%\.cargo\bin` | Works even right after install, no restart needed |
| PATH for node | Re-read user/system PATH from registry after winget | winget writes registry but current shell ignores it |
| Corrupted toolchain | If `rustup show` fails: uninstall + reinstall stable | Recovers from missing-manifest errors |
| Default packaging | `--bundles none` (only produce .exe) | Avoids NSIS download flakiness |
| Installer mode | `build.bat --installer` → `--bundles nsis` | Opt-in for distribution |

### Flow

```
[1/4] Check Node.js
      └── missing → winget install (silent) → refresh PATH from registry
[2/4] Check Rust
      ├── inject ~/.cargo/bin into PATH
      ├── cargo missing → download rustup-init.exe → run silent install
      └── `rustup show` fails → uninstall stable + reinstall stable
[3/4] npm install
[4/4] npm run tauri -- build --bundles {none|nsis}
      └── copy exe to project root
```

### tauri.conf.json

`bundle.active` stays `true` (default upstream behaviour). Bundle target
selection happens at the CLI via `--bundles` flag, not in config. This keeps
the config canonical and lets the script choose per-invocation.

## Components

### `build.bat`

Single Windows batch file. Sections:

- Argument parsing (`--installer` / `-i` flag)
- Node.js detection + winget install + PATH refresh
- Rust detection + rustup install + manifest healing + PATH inject
- npm install
- Tauri build with conditional `--bundles` flag
- Copy exe to project root

Uses `setlocal enabledelayedexpansion` so error codes inside `if` blocks
work correctly.

### `tauri.conf.json`

Reverted to `bundle.active: true`, `bundle.targets: ["nsis"]`. The bundle
behaviour is now controlled by CLI flag from `build.bat`.

### `README.md`

Updated "构建桌面版" section to document:

- One-click build (`build.bat`)
- Installer mode (`build.bat --installer`)
- Auto-install behaviour for Node.js / Rust
- PATH injection mechanism
- Why NSIS bundle is skipped by default

## Error Handling

| Failure | Behaviour |
|---|---|
| winget unavailable | Print manual install URL, exit 1 |
| rustup-init download fails | Print network hint, exit 1 |
| rustup install fails | Exit 1 with code from rustup-init |
| Toolchain still broken after reinstall | Exit 1 |
| `cargo --version` still fails | Exit 1 |
| npm install fails | Exit 1 |
| Tauri build fails | Exit 1 |
| `pause` before every exit | User can read the error before window closes |

## Testing

Manual test matrix (run on a clean Windows VM):

1. **Clean machine, no Node, no Rust** → expect both auto-install, build succeeds, exe at root.
2. **Node present, no Rust** → only Rust step runs, build succeeds.
3. **Both present** → both detection steps fast-pass, build succeeds.
4. **Corrupted Rust toolchain** → manifest healing kicks in, build succeeds.
5. **`build.bat --installer`** → NSIS package produced under `bundle\nsis\`.

No automated tests for this script (Windows VM matrix is out of scope for
this repo's pytest suite).

## Rollout

- One commit on `main`: build.bat rewrite + tauri.conf.json revert + README update + this spec.
- Push to `origin/main`.
- No version bump needed (build script change only).
