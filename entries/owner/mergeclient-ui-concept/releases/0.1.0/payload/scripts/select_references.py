#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ARCHETYPE_SYNONYMS = {
    "landing": ["开始", "报名", "介绍", "主题", "开场", "landing"],
    "objective": ["冲刺", "订单", "收集", "任务", "进度", "7日", "objective"],
    "pass": ["pass", "通行证", "赛季", "等级", "奖励轨道"],
    "competition": ["排行", "赛跑", "对战", "1v1", "2v2", "段位", "合作", "双人", "比赛", "竞赛", "竞技", "登山"],
    "minigame": ["弹珠", "挑战", "挖宝", "爬塔", "开箱", "冒险", "小游戏", "棋盘"],
    "collection": ["相册", "收集", "bingo", "棋盘", "勋章", "套组"],
    "map": ["岛", "冒险", "地图", "闯关", "章节", "路径"],
    "shop": ["商店", "兑换", "刷新", "限购", "shop"],
}


def terms(text: str) -> set[str]:
    normalized = text.lower().replace("_", " ").replace("/", " ")
    latin = set(re.findall(r"[a-z0-9]+", normalized))
    chinese = set(re.findall(r"[\u4e00-\u9fff]{2,}", normalized))
    substrings = {
        word
        for words in ARCHETYPE_SYNONYMS.values()
        for word in words
        if word.lower() in normalized
    }
    return latin | chinese | substrings


def main() -> int:
    parser = argparse.ArgumentParser(description="Select diverse mergeclient UI references.")
    parser.add_argument("--brief", required=True, help="Activity UI request in Chinese or English.")
    parser.add_argument("--archetype", choices=sorted(ARCHETYPE_SYNONYMS), help="Optional page archetype.")
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    skill_dir = script_dir.parent
    manifest_path = args.manifest or skill_dir / "references" / "reference-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    brief_terms = terms(args.brief)
    inferred = args.archetype
    if not inferred:
        candidates = []
        lower = args.brief.lower()
        for archetype, words in ARCHETYPE_SYNONYMS.items():
            hits = sum(1 for word in words if word.lower() in lower)
            candidates.append((hits, archetype))
        if max(candidates)[0] > 0:
            inferred = max(candidates)[1]

    ranked = []
    for item in payload["selected"]:
        item_text = " ".join([
            item.get("activity", ""),
            item.get("archetype", ""),
            " ".join(item.get("tags", [])),
        ])
        item_terms = terms(item_text)
        overlap = len(brief_terms & item_terms)
        archetype_bonus = 5 if inferred and item.get("archetype") == inferred else 0
        score = overlap * 3 + archetype_bonus + float(item.get("quality_score", 0)) / 100
        ranked.append((score, item))

    limit = max(1, min(args.limit, 6))
    ranked.sort(key=lambda pair: (-pair[0], -float(pair[1].get("quality_score", 0)), pair[1]["activity"]))
    chosen = ranked[:limit]
    result = {
        "brief": args.brief,
        "inferred_archetype": inferred,
        "references": [
            {
                "activity": item["activity"],
                "archetype": item.get("archetype"),
                "role_hint": "structure/style reference",
                "path": str((skill_dir / item["asset_path"]).resolve()),
                "quality_score": item.get("quality_score"),
                "match_score": round(score, 3),
            }
            for score, item in chosen
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
