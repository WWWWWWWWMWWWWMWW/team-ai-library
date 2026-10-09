#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}


ARCHETYPE_RULES = [
    ("pass", re.compile(r"pass|通行证", re.I)),
    ("competition", re.compile(r"1v1|2v2|排行|赛跑|段位|合作|比赛|大赛|篮球|race|rank|match", re.I)),
    ("collection", re.compile(r"相册|bingo|收集|勋章|collection|cardseason|赛季相册", re.I)),
    ("objective", re.compile(r"冲刺|订单|任务|客流|chooseorder|orderware|gymsprint|7日", re.I)),
    ("map", re.compile(r"梦幻岛|浮空岛|丛林|地图|闯关|冒险", re.I)),
    ("minigame", re.compile(r"弹珠|面具|魔药|螺丝|挖宝|下潜|悬空|爬塔|开宝箱|小火车|摸鱼|chessboard|challenge|tower|openbox|digname|screw|pinball", re.I)),
]


def rels(path: Path) -> dict[str, str]:
    root = ET.parse(path).getroot()
    return {rel.attrib["Id"]: rel.attrib["Target"] for rel in root.findall("pkg:Relationship", NS)}


def load_shared_strings(root: Path) -> list[str]:
    shared = root / "xl" / "sharedStrings.xml"
    if not shared.exists():
        return []
    return ["".join(t.text or "" for t in si.findall(".//main:t", NS)) for si in ET.parse(shared).getroot().findall("main:si", NS)]


def sheet_labels(sheet_path: Path, shared: list[str]) -> dict[int, str]:
    labels: dict[int, str] = {}
    root = ET.parse(sheet_path).getroot()
    for cell in root.findall(".//main:c", NS):
        ref = cell.attrib.get("r", "")
        if not ref.startswith("A"):
            continue
        digits = "".join(ch for ch in ref if ch.isdigit())
        if not digits:
            continue
        row = int(digits) - 1
        kind = cell.attrib.get("t")
        if kind == "inlineStr":
            value = "".join(t.text or "" for t in cell.findall(".//main:t", NS))
        else:
            node = cell.find("main:v", NS)
            if node is None:
                value = ""
            elif kind == "s":
                value = shared[int(node.text or 0)]
            else:
                value = node.text or ""
        labels[row] = value.strip() or f"第{row + 1}行"
    return labels


def perceptual_hash(image: Image.Image) -> str:
    gray = ImageOps.grayscale(ImageOps.exif_transpose(image)).resize((9, 8), Image.Resampling.LANCZOS)
    pixels = np.asarray(gray, dtype=np.int16)
    bits = pixels[:, 1:] > pixels[:, :-1]
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def image_metrics(path: Path) -> dict[str, float | int | str | bool]:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        width, height = image.size
        thumb = ImageOps.contain(image, (512, 512), Image.Resampling.LANCZOS)
        gray = np.asarray(ImageOps.grayscale(thumb), dtype=np.float32)
        center = gray[1:-1, 1:-1]
        lap = -4 * center + gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:]
        blur_variance = float(lap.var())
        brightness = float(gray.mean())
        dark_fraction = float((gray < 45).mean())
        light_fraction = float((gray > 245).mean())
        hist = np.bincount(gray.astype(np.uint8).ravel(), minlength=256).astype(np.float64)
        probs = hist / max(1, hist.sum())
        entropy = float(-(probs[probs > 0] * np.log2(probs[probs > 0])).sum())
        phash = perceptual_hash(image)

    ratio = height / max(1, width)
    full_page = width >= 700 and height >= 1200 and 1.35 <= ratio <= 2.4
    overlay_risk = dark_fraction > 0.48 or brightness < 72
    dim_score = min(width / 950, 1.0) * 16 + min(height / 1700, 1.0) * 16
    sharp_score = min(math.log1p(blur_variance) / 7.0, 1.0) * 22
    brightness_score = max(0.0, 1.0 - abs(brightness - 145) / 115) * 18
    entropy_score = min(entropy / 7.5, 1.0) * 16
    penalty = (22 if overlay_risk else 0) + (8 if light_fraction > 0.35 else 0)
    quality = max(0.0, min(100.0, dim_score + sharp_score + brightness_score + entropy_score + (12 if full_page else -25) - penalty))
    role = "full_page_candidate" if full_page and not overlay_risk else "overlay_or_dimmed" if full_page else "thumbnail_or_crop"
    return {
        "width": width,
        "height": height,
        "aspect_ratio": round(ratio, 4),
        "blur_variance": round(blur_variance, 3),
        "brightness": round(brightness, 3),
        "dark_fraction": round(dark_fraction, 4),
        "entropy": round(entropy, 4),
        "phash": phash,
        "full_page": full_page,
        "overlay_risk": overlay_risk,
        "role": role,
        "quality_score": round(quality, 2),
    }


def infer_archetype(activity: str) -> str:
    for archetype, pattern in ARCHETYPE_RULES:
        if pattern.search(activity):
            return archetype
    return "landing"


def tags_for(activity: str, archetype: str) -> list[str]:
    tags = {archetype}
    for token in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2,}", activity.lower()):
        tags.add(token)
    return sorted(tags)


def extract_records(root: Path) -> list[dict]:
    shared = load_shared_strings(root)
    workbook = ET.parse(root / "xl" / "workbook.xml").getroot()
    workbook_rels = rels(root / "xl" / "_rels" / "workbook.xml.rels")
    sheets = []
    for sheet in workbook.findall("main:sheets/main:sheet", NS):
        rid = sheet.attrib[f"{{{NS['r']}}}id"]
        target = workbook_rels[rid].lstrip("/")
        path = root / target if target.startswith("xl/") else root / "xl" / target
        sheets.append((sheet.attrib["name"], path))

    records = []
    for sheet_name, sheet_path in sheets:
        rel_path = sheet_path.parent / "_rels" / f"{sheet_path.name}.rels"
        if not rel_path.exists():
            continue
        labels = sheet_labels(sheet_path, shared)
        sheet_rels = rels(rel_path)
        sheet_root = ET.parse(sheet_path).getroot()
        drawing = sheet_root.find("main:drawing", NS)
        if drawing is None:
            continue
        target = sheet_rels[drawing.attrib[f"{{{NS['r']}}}id"]]
        drawing_path = (sheet_path.parent / target).resolve()
        drawing_rels = rels(drawing_path.parent / "_rels" / f"{drawing_path.name}.rels")
        drawing_root = ET.parse(drawing_path).getroot()
        for anchor in list(drawing_root):
            from_node = anchor.find("xdr:from", NS)
            blip = anchor.find(".//a:blip", NS)
            if from_node is None or blip is None:
                continue
            row = int(from_node.findtext("xdr:row", default="0", namespaces=NS))
            col = int(from_node.findtext("xdr:col", default="0", namespaces=NS))
            embed = blip.attrib.get(f"{{{NS['r']}}}embed")
            if not embed or embed not in drawing_rels:
                continue
            media_path = (drawing_path.parent / drawing_rels[embed]).resolve()
            raw = media_path.read_bytes()
            metrics = image_metrics(media_path)
            records.append({
                "sheet": sheet_name,
                "row": row + 1,
                "col": col + 1,
                "activity": labels.get(row, f"第{row + 1}行"),
                "source_file": media_path.name,
                "source_path": str(media_path),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                **metrics,
            })
    records.sort(key=lambda item: (item["sheet"], item["row"], item["col"], item["source_file"]))
    return records


def annotate_near_duplicates(records: list[dict]) -> int:
    grouped = defaultdict(list)
    for item in records:
        grouped[(item["sheet"], item["activity"])].append(item)
    duplicate_refs = 0
    for (sheet, _activity), group in grouped.items():
        leaders: list[tuple[str, str, str]] = []
        assigned_by_sha: dict[str, str] = {}
        unique_members = defaultdict(set)
        for index, item in enumerate(group, start=1):
            match = assigned_by_sha.get(item["sha256"])
            if match is None:
                match = next(
                    (
                        group_id
                        for phash, _sha256, group_id in leaders
                        if (int(phash, 16) ^ int(item["phash"], 16)).bit_count() <= 4
                    ),
                    None,
                )
                if match is None:
                    match = f"{sheet}:{item['row']}:{index}"
                    leaders.append((item["phash"], item["sha256"], match))
                else:
                    duplicate_refs += 1
                assigned_by_sha[item["sha256"]] = match
            item["near_duplicate_group"] = match
            unique_members[match].add(item["sha256"])
        for item in group:
            item["near_duplicate_count"] = len(unique_members[item["near_duplicate_group"]])
    return duplicate_refs


def choose_representatives(records: list[dict], overrides: dict[str, str], archetype_overrides: dict[str, str]) -> list[dict]:
    activity_records = defaultdict(list)
    for record in records:
        if record["sheet"] == "活动截图":
            activity_records[record["activity"]].append(record)

    selected = []
    for activity, group in activity_records.items():
        pool = [item for item in group if item["role"] == "full_page_candidate"]
        if not pool:
            pool = [item for item in group if item["full_page"]]
        if not pool:
            pool = group
        pool.sort(key=lambda item: (-item["quality_score"], -item["bytes"], item["source_file"]))
        override_name = overrides.get(activity)
        override_match = next((item for item in group if item["source_file"] == override_name), None)
        winner = dict(override_match or pool[0])
        archetype = archetype_overrides.get(activity, infer_archetype(activity))
        winner["archetype"] = archetype
        winner["tags"] = tags_for(activity, archetype)
        if override_match:
            winner["selection_reason"] = "manual visual override: representative main activity page"
        else:
            winner["selection_reason"] = "highest quality complete-page candidate in activity" if winner["full_page"] else "fallback: no complete-page candidate"
        selected.append(winner)
    selected.sort(key=lambda item: item["row"])
    return selected


def load_font(size: int):
    for path in [Path("/System/Library/Fonts/PingFang.ttc"), Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")]:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def render_contact_sheet(selected: list[dict], output: Path) -> None:
    cols, card_w, card_h = 6, 300, 430
    rows = math.ceil(len(selected) / cols)
    canvas = Image.new("RGB", (cols * card_w, rows * card_h), "#F1F3F6")
    draw = ImageDraw.Draw(canvas)
    title_font, meta_font = load_font(20), load_font(15)
    for index, item in enumerate(selected):
        x, y = (index % cols) * card_w, (index // cols) * card_h
        with Image.open(item["source_path"]) as source:
            thumb = ImageOps.contain(ImageOps.exif_transpose(source).convert("RGB"), (270, 330), Image.Resampling.LANCZOS)
        px = x + (card_w - thumb.width) // 2
        canvas.paste(thumb, (px, y + 10))
        label = item["activity"].replace("\n", " ")[:19]
        draw.text((x + 12, y + 350), label, font=title_font, fill="#243247")
        draw.text((x + 12, y + 382), f"{item['archetype']} · {item['quality_score']}", font=meta_font, fill="#596A80")
        draw.text((x + 12, y + 405), item["source_file"], font=meta_font, fill="#7A8798")
    canvas.save(output, quality=90, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a curated mergeclient activity UI reference library.")
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--skill-dir", type=Path, required=True)
    args = parser.parse_args()
    workbook = args.workbook.resolve()
    skill_dir = args.skill_dir.resolve()
    if not workbook.is_file() or workbook.suffix.lower() != ".xlsx":
        raise SystemExit(f"Workbook not found or not .xlsx: {workbook}")
    asset_dir = skill_dir / "assets" / "references" / "activity"
    reference_dir = skill_dir / "references"
    asset_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mergeclient-ui-ref-") as temp:
        extracted = Path(temp) / "xlsx"
        with zipfile.ZipFile(workbook) as archive:
            archive.extractall(extracted)
        records = extract_records(extracted)
        exact_counts = Counter(item["sha256"] for item in records)
        for item in records:
            item["exact_duplicate_count"] = exact_counts[item["sha256"]]
        near_duplicate_references = annotate_near_duplicates(records)
        override_path = reference_dir / "selection-overrides.json"
        overrides = json.loads(override_path.read_text(encoding="utf-8")) if override_path.exists() else {}
        archetype_path = reference_dir / "archetype-overrides.json"
        archetype_overrides = json.loads(archetype_path.read_text(encoding="utf-8")) if archetype_path.exists() else {}
        selected = choose_representatives(records, overrides, archetype_overrides)

        for existing in asset_dir.glob("activity-*"):
            if existing.is_file():
                existing.unlink()
        for item in selected:
            source = Path(item["source_path"])
            suffix = source.suffix.lower() if source.suffix else ".jpg"
            asset_name = f"activity-{item['row']:02d}-{item['sha256'][:10]}{suffix}"
            target = asset_dir / asset_name
            shutil.copy2(source, target)
            item["asset_path"] = str(target.relative_to(skill_dir))
        render_contact_sheet(selected, skill_dir / "assets" / "reference-contact-sheet.jpg")

        public_selected = []
        for item in selected:
            public_selected.append({key: value for key, value in item.items() if key != "source_path"})
        manifest = {
            "source_workbook": workbook.name,
            "source_workbook_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
            "summary": {
                "image_references": len(records),
                "unique_binary_images": len(exact_counts),
                "exact_duplicate_references": sum(count - 1 for count in exact_counts.values()),
                "near_duplicate_references": near_duplicate_references,
                "activity_images": sum(1 for item in records if item["sheet"] == "活动截图"),
                "activity_types": len({item["activity"] for item in records if item["sheet"] == "活动截图"}),
                "selected_references": len(selected),
            },
            "selected": public_selected,
        }
        (reference_dir / "reference-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        with (reference_dir / "quality-audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            fields = ["sheet", "row", "activity", "source_file", "width", "height", "role", "quality_score", "brightness", "dark_fraction", "blur_variance", "entropy", "sha256", "phash", "exact_duplicate_count", "near_duplicate_group", "near_duplicate_count"]
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)

    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
