#!/usr/bin/env python3
"""
提取当前版本 Lua bundle 中的字节码并使用 luadec 反编译。

当前版本的 Lua 已拆分为多个 bundle，每个 bundle 内是一个包含多个模块的
大 TextAsset。脚本会先提取原始二进制，再扫描其中的 Lua 5.3/xLua 块并
逐个调用 luadec 反编译。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import UnityPy

GAME_CACHE_DIR: Path
LUA_BUNDLE_FILES: list[Path]
OUTPUT_DIR: Path
RAW_OUTPUT_DIR: Path
LUAC_OUTPUT_DIR: Path
DECOMPILED_OUTPUT_DIR: Path
DECOMPILED_FALLBACK_A_DIR: Path
LUADEC_PATH: Path
LUA_SIGNATURE = b"\x1bLuaS"
DECOMPILER_ERROR_MARKER = "DECOMPILER ERROR"
DECOMPILER_ALERTS = (
    "processing OP_JMP",
    "SIGSEGV",
    "assert",
    "panic",
)
UNSET_PENDING_PATTERN = re.compile(
    r"^\s*-- DECOMPILER ERROR at PC\d+: Confused about usage of register: R\d+ in 'UnsetPending'\s*$",
    re.M,
)


def sanitize_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unnamed"


def get_textasset_bytes(obj) -> bytes:
    data = obj.read()
    script = getattr(data, "m_Script", b"")
    if isinstance(script, str):
        return script.encode("utf-8", errors="surrogateescape")
    return bytes(script)


def extract_raw_bundles() -> list[dict]:
    print(f"扫描 __GAME_FILE_CACHE: {GAME_CACHE_DIR}")
    print(f"候选 Lua bundle: {len(LUA_BUNDLE_FILES)} 个")
    if not LUA_BUNDLE_FILES:
        raise FileNotFoundError(f"未在 __GAME_FILE_CACHE 中找到 Lua bundle: {GAME_CACHE_DIR}")

    RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    extracted = []
    for bundle in LUA_BUNDLE_FILES:
        environment = UnityPy.load(str(bundle))
        for obj in environment.objects:
            if obj.type.name != "TextAsset":
                continue
            data = obj.read()
            asset_name = str(getattr(data, "m_Name", bundle.stem))
            raw = get_textasset_bytes(obj)
            target = RAW_OUTPUT_DIR / f"{sanitize_name(asset_name)}.bin"
            if target.exists():
                target = RAW_OUTPUT_DIR / (
                    f"{sanitize_name(bundle.stem)}_{sanitize_name(asset_name)}.bin"
                )
            target.write_bytes(raw)
            print(f"{bundle.name}\t{asset_name}\t{len(raw)}\t{target.name}")
            extracted.append(
                {
                    "bundle_name": bundle.name,
                    "asset_name": asset_name,
                    "size": len(raw),
                    "path": target,
                }
            )
    print(f"提取完成，共 {len(extracted)} 个原始 Lua 包")
    return extracted


def find_lua_chunks(data: bytes) -> list[int]:
    positions = []
    start = 0
    while True:
        pos = data.find(LUA_SIGNATURE, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1
    return positions


class ChunkReader:
    def __init__(self, data: bytes, pos: int):
        self.data = data
        self.pos = pos

    def read(self, size: int) -> bytes:
        chunk = self.data[self.pos:self.pos + size]
        if len(chunk) != size:
            raise EOFError(f"unexpected eof at {self.pos}, need {size} bytes")
        self.pos += size
        return chunk

    def byte(self) -> int:
        return self.read(1)[0]

    def int32(self) -> int:
        return int.from_bytes(self.read(4), "little", signed=True)

    def uint(self, size: int) -> int:
        return int.from_bytes(self.read(size), "little")


def parse_chunk_size(data: bytes, start: int) -> int:
    reader = ChunkReader(data, start)
    if reader.read(4) != b"\x1bLua":
        raise ValueError(f"invalid lua signature at offset {start}")

    version = reader.byte()
    fmt = reader.byte()
    if version != 0x53:
        raise ValueError(f"unsupported lua version: {version:#x}")

    reader.read(6)  # LUAC_DATA
    int_size = reader.byte()
    size_t_size = reader.byte()
    reader.byte()  # instruction size in file header; xLua may report 8
    int64_size = reader.byte()
    if fmt != 1:
        reader.byte()  # lua_Number size

    if int_size != 4:
        raise ValueError(f"unexpected int size: {int_size}")
    if size_t_size not in (4, 8):
        raise ValueError(f"unexpected size_t size: {size_t_size}")
    if int64_size != 8:
        raise ValueError(f"unexpected lua_Integer size: {int64_size}")

    reader.read(8)  # LUAC_INT
    reader.read(8)  # LUAC_NUM
    reader.byte()   # top-level upvalue count

    def load_size() -> int:
        first = reader.byte()
        if first == 0xFF:
            return reader.uint(size_t_size)
        return first

    def load_string() -> None:
        size = load_size()
        if size == 0:
            return
        reader.read(size - 1)  # dumped string excludes trailing '\0'

    def load_function() -> None:
        load_string()
        reader.int32()
        reader.int32()
        reader.byte()
        reader.byte()
        reader.byte()

        code_count = reader.int32()
        reader.read(code_count * 4)  # luadec patch still reads 4-byte instructions

        const_count = reader.int32()
        for _ in range(const_count):
            const_type = reader.byte()
            if const_type == 0:
                continue
            if const_type == 1:
                reader.read(1)
                continue
            if const_type == 3:
                reader.read(8)
                continue
            if const_type == 19:
                reader.read(8)
                continue
            if const_type in (4, 20):
                load_string()
                continue
            raise ValueError(f"unknown const type {const_type} at {reader.pos}")

        upvalue_count = reader.int32()
        reader.read(upvalue_count * 2)

        proto_count = reader.int32()
        for _ in range(proto_count):
            load_function()

        lineinfo_count = reader.int32()
        reader.read(lineinfo_count * 4)

        locvar_count = reader.int32()
        for _ in range(locvar_count):
            load_string()
            reader.int32()
            reader.int32()

        upname_count = reader.int32()
        for _ in range(upname_count):
            load_string()

    load_function()
    return reader.pos - start


def extract_module_name(data: bytes, chunk_pos: int) -> str | None:
    search_start = max(0, chunk_pos - 160)
    prefix = data[search_start:chunk_pos]

    matches = re.findall(
        rb"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+",
        prefix,
    )
    if matches:
        return matches[-1].decode("utf-8", errors="replace")

    try:
        chunk_data = data[chunk_pos:chunk_pos + 256]
        lua_match = re.search(
            rb"@?([A-Za-z_][A-Za-z0-9_./]*\.lua)",
            chunk_data,
        )
        if lua_match:
            return (
                lua_match.group(1)
                .decode("utf-8", errors="replace")
                .replace("/", ".")
                .replace(".lua", "")
            )
    except Exception:
        pass

    return None


def extract_chunks(raw_files: list[dict]) -> list[dict]:
    LUAC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    extracted = []

    for raw_file in raw_files:
        data = raw_file["path"].read_bytes()
        positions = find_lua_chunks(data)
        print(f"{raw_file['asset_name']}: 找到 {len(positions)} 个 Lua 块")

        asset_dir = LUAC_OUTPUT_DIR / sanitize_name(raw_file["asset_name"])
        asset_dir.mkdir(parents=True, exist_ok=True)

        for i, pos in enumerate(positions):
            chunk_size = parse_chunk_size(data, pos)
            end_pos = pos + chunk_size
            chunk_data = data[pos:end_pos]
            module_name = extract_module_name(data, pos)

            if module_name:
                filename = module_name.replace(".", "_") + ".luac"
            else:
                filename = f"chunk_{i:04d}.luac"

            output_path = asset_dir / filename
            output_path.write_bytes(chunk_data)

            extracted.append(
                {
                    "bundle_name": raw_file["bundle_name"],
                    "asset_name": raw_file["asset_name"],
                    "index": i,
                    "module_name": module_name,
                    "filename": filename,
                    "path": output_path,
                    "size": len(chunk_data),
                    "offset": pos,
                }
            )

            if (i + 1) % 200 == 0:
                print(f"  {raw_file['asset_name']} 已提取 {i + 1}/{len(positions)}")

    print(f"字节码提取完成，共 {len(extracted)} 个模块")
    return extracted


def analyze_decompile_output(stdout: bytes, stderr: bytes) -> dict:
    text = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
    return {
        "text": text,
        "error_markers": text.count(DECOMPILER_ERROR_MARKER),
        "alerts": sum(1 for item in DECOMPILER_ALERTS if item in text),
    }


def clean_decompiled_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = UNSET_PENDING_PATTERN.sub("", text)
    text = re.sub(r"^\s*;\s*$", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def run_luadec(input_path: Path, extra_args: list[str]) -> dict:
    result = subprocess.run(
        [str(LUADEC_PATH), *extra_args, "-se", "UTF8", str(input_path)],
        capture_output=True,
        timeout=30,
    )
    metrics = analyze_decompile_output(result.stdout, result.stderr)
    return {
        "args": extra_args,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        **metrics,
    }


def candidate_rank(candidate: dict) -> tuple:
    return (
        0 if candidate["returncode"] == 0 and candidate["stdout"] else 1,
        candidate["error_markers"],
        candidate["alerts"],
        0 if not candidate["args"] else 1,
    )


def build_output_path(base_dir: Path, chunk: dict) -> Path:
    asset_root = base_dir / sanitize_name(chunk["asset_name"])
    module_name = chunk.get("module_name")

    if module_name:
        parts = module_name.split(".")
        if len(parts) > 1:
            return asset_root.joinpath(*parts[:-1], parts[-1] + ".lua")
        return asset_root / f"{module_name}.lua"
    return asset_root / f"chunk_{chunk['index']:04d}.lua"


def decompile_chunks(extracted: list[dict]) -> dict:
    DECOMPILED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DECOMPILED_FALLBACK_A_DIR.mkdir(parents=True, exist_ok=True)
    results = {
        "success": 0,
        "failed": 0,
        "errors": [],
        "fallback_generated": 0,
        "fallback_better_files": 0,
        "primary_error_files": 0,
        "primary_error_markers": 0,
        "fallback_error_files": 0,
        "fallback_error_markers": 0,
    }

    for i, chunk in enumerate(extracted, start=1):
        module_name = chunk.get("module_name")
        primary_output_file = build_output_path(DECOMPILED_OUTPUT_DIR, chunk)
        fallback_output_file = build_output_path(DECOMPILED_FALLBACK_A_DIR, chunk)
        primary_output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            primary = run_luadec(chunk["path"], [])
            fallback = None

            if primary["error_markers"] > 0 or primary["alerts"] > 0:
                fallback = run_luadec(chunk["path"], ["-a"])

            if primary["returncode"] == 0 and primary["stdout"]:
                primary_output_file.write_text(
                    clean_decompiled_text(
                        primary["stdout"].decode("utf-8", errors="replace")
                    ),
                    encoding="utf-8",
                )
                results["success"] += 1
                if primary["error_markers"] > 0:
                    results["primary_error_files"] += 1
                    results["primary_error_markers"] += primary["error_markers"]

                if fallback and fallback["returncode"] == 0 and fallback["stdout"]:
                    fallback_output_file.parent.mkdir(parents=True, exist_ok=True)
                    fallback_output_file.write_text(
                        clean_decompiled_text(
                            fallback["stdout"].decode("utf-8", errors="replace")
                        ),
                        encoding="utf-8",
                    )
                    results["fallback_generated"] += 1
                    if fallback["error_markers"] > 0:
                        results["fallback_error_files"] += 1
                        results["fallback_error_markers"] += fallback["error_markers"]
                    if candidate_rank(fallback) < candidate_rank(primary):
                        results["fallback_better_files"] += 1
            else:
                error_msg = (
                    primary["stderr"].decode("utf-8", errors="replace")
                    if primary["stderr"]
                    else "Unknown error"
                )
                results["failed"] += 1
                results["errors"].append(
                    {
                        "asset": chunk["asset_name"],
                        "module": module_name or chunk["filename"],
                        "args": " ".join(primary["args"]),
                        "error": error_msg,
                    }
                )
                primary_output_file.with_suffix(primary_output_file.suffix + ".error").write_text(
                    f"-- Decompilation failed\n-- Error: {error_msg}\n",
                    encoding="utf-8",
                )
        except subprocess.TimeoutExpired:
            results["failed"] += 1
            results["errors"].append(
                {
                    "asset": chunk["asset_name"],
                    "module": module_name or chunk["filename"],
                    "error": "Timeout",
                }
            )
        except Exception as exc:
            results["failed"] += 1
            results["errors"].append(
                {
                    "asset": chunk["asset_name"],
                    "module": module_name or chunk["filename"],
                    "error": str(exc),
                }
            )

        if i % 200 == 0:
            print(
                f"已反编译 {i}/{len(extracted)} "
                f"(成功: {results['success']}, 失败: {results['failed']}, "
                f"fallback产物: {results['fallback_generated']}, "
                f"主输出错误文件: {results['primary_error_files']})"
            )

    if results["errors"]:
        error_log = DECOMPILED_OUTPUT_DIR / "_errors.log"
        with error_log.open("w", encoding="utf-8") as handle:
            for err in results["errors"]:
                handle.write(
                    f"{err['asset']} | {err['module']} | {err.get('args', '')}: {err['error']}\n"
                )
        print(f"错误日志已保存到: {error_log}")

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract and decompile Lua 5.3/xLua bytecode from a Unity game cache."
    )
    parser.add_argument("game_cache_dir", type=Path, help="Path to __GAME_FILE_CACHE")
    parser.add_argument("output_dir", type=Path, help="New directory for extracted Lua")
    parser.add_argument("--luadec", required=True, type=Path, help="Path to luadec")
    return parser.parse_args()


def configure(args: argparse.Namespace) -> None:
    global GAME_CACHE_DIR, LUA_BUNDLE_FILES, OUTPUT_DIR
    global RAW_OUTPUT_DIR, LUAC_OUTPUT_DIR, DECOMPILED_OUTPUT_DIR
    global DECOMPILED_FALLBACK_A_DIR, LUADEC_PATH

    GAME_CACHE_DIR = args.game_cache_dir.expanduser().resolve()
    OUTPUT_DIR = args.output_dir.expanduser().resolve()
    LUADEC_PATH = args.luadec.expanduser().resolve()
    LUA_BUNDLE_FILES = sorted(
        path
        for path in GAME_CACHE_DIR.rglob("*.bundle")
        if "lua" in path.relative_to(GAME_CACHE_DIR).as_posix().lower()
    )
    RAW_OUTPUT_DIR = OUTPUT_DIR / "raw"
    LUAC_OUTPUT_DIR = OUTPUT_DIR / "luac"
    DECOMPILED_OUTPUT_DIR = OUTPUT_DIR / "decompiled"
    DECOMPILED_FALLBACK_A_DIR = OUTPUT_DIR / "decompiled_fallback_a"


def main() -> None:
    args = parse_args()
    configure(args)

    print("=" * 60)
    print("Lua 字节码提取与反编译工具")
    print("=" * 60)

    if GAME_CACHE_DIR.name != "__GAME_FILE_CACHE" or not GAME_CACHE_DIR.is_dir():
        raise FileNotFoundError(f"无效的 __GAME_FILE_CACHE 目录: {GAME_CACHE_DIR}")

    if not LUADEC_PATH.exists():
        raise FileNotFoundError(f"找不到 luadec: {LUADEC_PATH}")

    if OUTPUT_DIR.exists():
        raise FileExistsError(f"输出目录已存在，拒绝覆盖: {OUTPUT_DIR}")

    print("\n[步骤 1] 提取原始 Lua 包...")
    raw_files = extract_raw_bundles()

    print("\n[步骤 2] 提取 Lua 字节码...")
    extracted = extract_chunks(raw_files)
    if not extracted:
        raise RuntimeError("找到了 Lua bundle，但未提取到 Lua 5.3/xLua 字节码")

    print("\n[步骤 3] 反编译字节码...")
    results = decompile_chunks(extracted)

    summary = {
        "game_cache": str(GAME_CACHE_DIR),
        "lua_bundle_files": len(LUA_BUNDLE_FILES),
        "raw_lua_packages": len(raw_files),
        "lua_chunks": len(extracted),
        **results,
    }
    (OUTPUT_DIR / "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("处理完成!")
    print(f"原始 Lua 包: {RAW_OUTPUT_DIR}")
    print(f"字节码文件: {LUAC_OUTPUT_DIR}")
    print(f"反编译结果: {DECOMPILED_OUTPUT_DIR}")
    print(f"-a 备用结果: {DECOMPILED_FALLBACK_A_DIR}")
    print(f"成功: {results['success']} 失败: {results['failed']}")
    print(
        f"生成 -a 备用文件: {results['fallback_generated']} "
        f"其中更优文件: {results['fallback_better_files']}"
    )
    print(
        f"主输出 DECOMPILER ERROR 文件: {results['primary_error_files']} "
        f"标记数: {results['primary_error_markers']}"
    )
    print(
        f"-a 备用 DECOMPILER ERROR 文件: {results['fallback_error_files']} "
        f"标记数: {results['fallback_error_markers']}"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
