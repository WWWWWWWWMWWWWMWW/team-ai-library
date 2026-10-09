#!/usr/bin/env bash

set -euo pipefail

usage() {
	echo "Usage: $0 <unpacked_result_dir>" >&2
}

if [[ $# -ne 1 ]]; then
	usage
	exit 1
fi

result_dir="$1"
script_dir=$(cd "$(dirname "$0")" && pwd)
skill_dir=$(cd "$script_dir/.." && pwd)
luadec_path="$skill_dir/luadec/luadec/luadec"

if [[ ! -d "$result_dir/packages" || ! -d "$result_dir/runtime-data" ]]; then
	echo "Invalid unpack result directory: $result_dir" >&2
	exit 1
fi

result_dir=$(cd "$result_dir" && pwd)

unity_marker=$(find "$result_dir/packages" -type f -name unity-namespace.js -print -quit)
if [[ -z "$unity_marker" ]]; then
	echo "Unity project not detected; skipping Lua decompilation."
	exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
	echo "uv is required to load UnityPy for Unity Lua extraction." >&2
	exit 1
fi

if [[ ! -x "$luadec_path" ]]; then
	echo "luadec is missing or not executable: $luadec_path" >&2
	exit 1
fi

game_caches=()
while IFS= read -r cache_dir; do
	game_caches+=("$cache_dir")
done < <(find "$result_dir/runtime-data" -type d -name __GAME_FILE_CACHE -print | sort)

if [[ ${#game_caches[@]} -eq 0 ]]; then
	echo "Unity project detected, but no __GAME_FILE_CACHE directory was found."
	exit 0
fi

processed=0
for cache_dir in "${game_caches[@]}"; do
	lua_bundle=$(find "$cache_dir" -type f -name '*.bundle' -ipath '*lua*' -print -quit)
	if [[ -z "$lua_bundle" ]]; then
		continue
	fi

	processed=$((processed + 1))
	output_dir="$result_dir/lua-source/cache-$processed"
	echo "Unity + Lua detected in: $cache_dir"
	uv run --with 'UnityPy==1.25.3' python "$script_dir/extract-and-decompile-lua.py" \
		"$cache_dir" "$output_dir" --luadec "$luadec_path"
	echo "UNITY_LUA_RESULT=$output_dir"
done

if [[ $processed -eq 0 ]]; then
	echo "Unity project detected, but no Lua AssetBundle was found under __GAME_FILE_CACHE."
fi
