---
name: wechat-applet-unpack
description: Collect and unpack locally cached WeChat Mini Program packages on macOS for authorized learning and research, including automatic Unity+xLua detection and Lua 5.3 bytecode decompilation. Use when the user provides a WeChat Mini Program or official-account app ID such as wx8d5d32e5505a18b0 and asks to locate its packages in the macOS WeChat Applet container, copy package and runtime files into the workspace, decrypt wxapkg files, recover source code, inspect __GAME_FILE_CACHE, or extract Lua from a Unity WeChat game.
---

# WeChat Applet Unpack

Extract a specified Mini Program's locally cached package and runtime data from macOS WeChat, then invoke the bundled `unpack.sh` to recover studyable code.

## Workflow

1. Obtain exactly one app ID from the user. Require the form `wx` followed by 16 hexadecimal characters.
2. Confirm the host is macOS. Do not attempt this workflow on Windows or Linux.
3. Treat the user's current working directory as the output root unless they explicitly choose another writable directory.
4. Run:

   ```bash
   bash <skill-dir>/scripts/collect-and-unpack.sh <app-id> <output-root>
   ```

5. Report the absolute result directory printed by the script. Point out:
   - `packages/<app-id>/<version>/` contains copied packages, decrypted wxapkg files, and recovered code.
   - `runtime-data/` contains all matching local WeChat runtime files with their original relative layout preserved.
   - `unpack_*.wxapkg.log` contains reconstruction diagnostics. If the script reports a partial-restoration warning, the base JavaScript, configuration, HTML, and resources are still available in the adjacent `unpack_*` source directory; tell the user which higher-level generated files could not be restored.
   - When Unity and Lua bundles are detected, `lua-source/cache-*/decompiled/` contains recovered Lua source, `luac/` contains extracted bytecode, `raw/` contains TextAsset payloads, and `_summary.json` records success, failure, and fallback-quality counts.
6. If macOS denies access to the WeChat container, tell the user to grant the Codex host application Full Disk Access and retry.
7. For Unity+Lua results, read every `lua-source/cache-*/_summary.json` and report bundle count, module count, hard failures, clean primary files (`success - primary_error_files`), fallback files, and `fallback_better_files`. Do not equate process success with clean decompilation.

## Guardrails

- Use only packages already present in the user's local WeChat container and only for code the user is authorized to inspect.
- Never broaden the search outside `~/Library/Containers/com.tencent.xinWeChat/Data/Documents/app_data/radium/Applet`.
- Never overwrite an existing result directory. The script intentionally stops if `<output-root>/wechat-applet-<app-id>` already exists; ask the user to rename it or select another output root.
- Do not omit runtime files. Copy every directory named exactly as the app ID outside `packages`, preserving its path relative to `Applet`.
- Process every cached package-version directory, not only the highest numeric version.
- Detect Unity by `unity-namespace.js`. For Unity results, search every copied `__GAME_FILE_CACHE` for Lua-named AssetBundles and run `scripts/decompile-unity-lua.sh`; skip this phase for non-Unity projects.
- Preserve all primary decompiler output. When `luadec` emits error markers, also generate `-a` fallback output and report quality counts from `_summary.json` rather than claiming every file is clean.
- Use the script-pinned `UnityPy==1.25.3` environment through `uv` to inspect Unity AssetBundles. If the sandbox blocks the user's uv cache or first-run package download, request the minimum required approval and retry the same Lua-decompilation command.

## Preflight discovery

When inspection is requested without copying or unpacking, run:

```bash
bash <skill-dir>/scripts/collect-and-unpack.sh --dry-run <app-id> <output-root>
```

This verifies the macOS layout and lists package versions and runtime-data locations without writing output.
