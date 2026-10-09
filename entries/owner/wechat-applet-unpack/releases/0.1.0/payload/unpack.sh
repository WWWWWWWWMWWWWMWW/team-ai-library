#!/usr/bin/env bash

set -euo pipefail

usage() {
	echo "Usage: $0 <app_id> <package_dir>" >&2
	echo "Example: $0 wx8d5d32e5505a18b0 wx8d5d32e5505a18b0/36" >&2
}

if [[ $# -ne 2 ]]; then
	usage
	exit 1
fi

app_id="$1"
package_dir="$2"
script_dir=$(cd "$(dirname "$0")" && pwd)
decrypt_tool="$script_dir/pc_wxapkg_decrypt/pc_wxapkg_decrypt"
unpacker_dir="$script_dir/wxappUnpacker"

if [[ ! -d "$package_dir" ]]; then
	echo "Package directory does not exist: $package_dir" >&2
	exit 1
fi

if [[ $(uname -s) != "Darwin" ]]; then
	echo "This script supports macOS only." >&2
	exit 1
fi

if [[ ! -x "$decrypt_tool" ]]; then
	echo "Decrypt tool is missing or not executable: $decrypt_tool" >&2
	exit 1
fi

if [[ ! -f "$unpacker_dir/bingo.sh" ]]; then
	echo "wxappUnpacker is missing: $unpacker_dir" >&2
	exit 1
fi

if ! command -v node >/dev/null 2>&1; then
	echo "Node.js is required to run wxappUnpacker." >&2
	exit 1
fi

package_dir=$(cd "$package_dir" && pwd)

unpack_package() {
	in_path="$1"
	file_name=$(basename "$in_path")
	out_path="$package_dir/unpack_$file_name"
	log_path="$package_dir/unpack_$file_name.log"
	echo "$in_path"
	echo "out,$out_path"

	"$decrypt_tool" -wxid "$app_id" -in "$in_path" --out "$out_path"
	if [[ "$file_name" != "__WITHOUT_MULTI_PLUGINCODE__.wxapkg" ]]; then
		if ! (
			cd "$unpacker_dir"
			node wuWxapkg.js -s="$package_dir/unpack___WITHOUT_MULTI_PLUGINCODE__" "$out_path"
		) >"$log_path" 2>&1; then
			report_partial_unpack "$out_path" "$log_path"
		fi
	else
		if ! (
			cd "$unpacker_dir"
			node wuWxapkg.js "$out_path"
		) >"$log_path" 2>&1; then
			report_partial_unpack "$out_path" "$log_path"
		fi
	fi
	echo "Source directory: ${out_path%.wxapkg}"
	echo "Unpack log: $log_path"
}

report_partial_unpack() {
	decrypted_path="$1"
	unpack_log="$2"
	extracted_dir="${decrypted_path%.wxapkg}"
	if [[ -d "$extracted_dir" ]] && find "$extracted_dir" -type f -print -quit | grep -q .; then
		echo "Warning: the base package was extracted, but wxappUnpacker could not fully restore some generated files." >&2
		echo "Partial source is available in: $extracted_dir" >&2
		echo "See the full diagnostic log: $unpack_log" >&2
		return 0
	fi

	echo "wxappUnpacker failed before producing source files. See: $unpack_log" >&2
	return 1
}

special_package="$package_dir/__WITHOUT_MULTI_PLUGINCODE__.wxapkg"
if [[ -f "$special_package" ]]; then
	unpack_package "$special_package"
fi

package_count=0
for in_path in "$package_dir"/*.wxapkg; do
	[[ -f "$in_path" ]] || continue
	file_name=$(basename "$in_path")
	[[ "$file_name" == unpack_* ]] && continue
	[[ "$file_name" == "__WITHOUT_MULTI_PLUGINCODE__.wxapkg" ]] && continue
	package_count=$((package_count + 1))
	unpack_package "$in_path"
done

if [[ $package_count -eq 0 && ! -f "$special_package" ]]; then
	echo "No .wxapkg files found in: $package_dir" >&2
	exit 1
fi
