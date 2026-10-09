#!/usr/bin/env bash

set -euo pipefail

usage() {
	echo "Usage: $0 [--dry-run] <app_id> [output_root]" >&2
	echo "Example: $0 wx8d5d32e5505a18b0 \"$PWD\"" >&2
}

dry_run=0
if [[ ${1:-} == "--dry-run" ]]; then
	dry_run=1
	shift
fi

if [[ $# -lt 1 || $# -gt 2 ]]; then
	usage
	exit 1
fi

if [[ $(uname -s) != "Darwin" ]]; then
	echo "This skill supports macOS only." >&2
	exit 1
fi

app_id="$1"
output_root="${2:-$PWD}"

if [[ ! "$app_id" =~ ^wx[0-9a-fA-F]{16}$ ]]; then
	echo "Invalid app ID: $app_id" >&2
	echo "Expected wx followed by 16 hexadecimal characters." >&2
	exit 1
fi

applet_root="$HOME/Library/Containers/com.tencent.xinWeChat/Data/Documents/app_data/radium/Applet"
packages_root="$applet_root/packages"
package_source="$packages_root/$app_id"
skill_dir=$(cd "$(dirname "$0")/.." && pwd)

if [[ ! -d "$applet_root" ]]; then
	echo "WeChat Applet directory not found: $applet_root" >&2
	exit 1
fi

if [[ ! -d "$package_source" ]]; then
	echo "No cached package found for $app_id in $packages_root" >&2
	exit 1
fi

package_versions=()
while IFS= read -r version_dir; do
	package_versions+=("$version_dir")
done < <(find "$package_source" -mindepth 1 -maxdepth 1 -type d -print | sort)

if [[ ${#package_versions[@]} -eq 0 ]]; then
	echo "No package-version directory found under: $package_source" >&2
	exit 1
fi

runtime_sources=()
while IFS= read -r runtime_dir; do
	runtime_sources+=("$runtime_dir")
done < <(find "$applet_root" -mindepth 2 -maxdepth 5 -type d -name "$app_id" ! -path "$packages_root/*" -print | sort)

if [[ ${#runtime_sources[@]} -eq 0 ]]; then
	echo "No runtime-data directory named $app_id was found beside packages." >&2
	exit 1
fi

echo "Package versions:"
for version_dir in "${package_versions[@]}"; do
	echo "  $version_dir"
done

echo "Runtime-data directories:"
for runtime_dir in "${runtime_sources[@]}"; do
	echo "  $runtime_dir"
done

if [[ $dry_run -eq 1 ]]; then
	echo "Dry run complete; no files were copied or unpacked."
	exit 0
fi

mkdir -p "$output_root"
output_root=$(cd "$output_root" && pwd)
result_dir="$output_root/wechat-applet-$app_id"

if [[ -e "$result_dir" ]]; then
	echo "Result directory already exists; refusing to overwrite: $result_dir" >&2
	exit 1
fi

mkdir -p "$result_dir/packages"
cp -R "$package_source" "$result_dir/packages/$app_id"

for runtime_dir in "${runtime_sources[@]}"; do
	relative_path="${runtime_dir#"$applet_root"/}"
	runtime_target="$result_dir/runtime-data/$relative_path"
	mkdir -p "$(dirname "$runtime_target")"
	cp -R "$runtime_dir" "$runtime_target"
done

for version_dir in "${package_versions[@]}"; do
	version_name=$(basename "$version_dir")
	bash "$skill_dir/unpack.sh" "$app_id" "$result_dir/packages/$app_id/$version_name"
done

bash "$skill_dir/scripts/decompile-unity-lua.sh" "$result_dir"

echo "Completed: $result_dir"
