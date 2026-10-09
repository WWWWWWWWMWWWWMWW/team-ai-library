#!/usr/bin/env python3
"""Reliable, explainable Super Lotto (大乐透) lookup and analysis.

The module deliberately uses only the Python standard library. Network access is
restricted to an explicit allow-list and is never triggered unless the caller
asks for a live fetch. Web responses are treated as data, not instructions.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import random
import re
import sys
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


OFFICIAL_API = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
OFFICIAL_PAGE = "https://www.lottery.gov.cn/kj/kjlb.html?dlt"
RULES_URL = "https://www.lottery.gov.cn/bzzx/yxgz/20191119/1002858.html"
SECONDARY_BASE = "https://datachart.500.com/dlt/history/newinc/history.php"
ALLOWED_HOSTS = {
    "webapi.sporttery.cn",
    "www.lottery.gov.cn",
    "datachart.500.com",
    "datachart.500star.com",
}
MAX_RESPONSE_BYTES = 2_000_000
USER_AGENT = "dlt-reliable-analysis/1.0 (+stdlib; no background tasks)"


class DataError(RuntimeError):
    """Raised when a source cannot provide trustworthy draw data."""


@dataclass(frozen=True)
class Draw:
    issue: str
    date: str
    front: tuple[int, ...]
    back: tuple[int, ...]
    source: str
    source_url: str
    fetched_at: str

    def to_json(self) -> dict[str, Any]:
        value = asdict(self)
        value["front"] = list(self.front)
        value["back"] = list(self.back)
        return value


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _issue_key(issue: str) -> int:
    if not re.fullmatch(r"\d{4,6}", str(issue)):
        raise DataError(f"期号格式非法：{issue!r}")
    return int(issue)


def validate_draw(
    issue: Any,
    date: Any,
    front: Iterable[Any],
    back: Iterable[Any],
    *,
    source: str,
    source_url: str,
    fetched_at: str | None = None,
) -> Draw:
    issue_text = str(issue).strip()
    _issue_key(issue_text)
    date_text = str(date).strip()
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError as exc:
        raise DataError(f"{issue_text} 的开奖日期非法：{date_text!r}") from exc

    try:
        front_values = tuple(sorted(int(value) for value in front))
        back_values = tuple(sorted(int(value) for value in back))
    except (TypeError, ValueError) as exc:
        raise DataError(f"{issue_text} 的开奖号码包含非整数") from exc

    if len(front_values) != 5 or len(set(front_values)) != 5:
        raise DataError(f"{issue_text} 前区必须是5个不重复号码")
    if len(back_values) != 2 or len(set(back_values)) != 2:
        raise DataError(f"{issue_text} 后区必须是2个不重复号码")
    if not all(1 <= value <= 35 for value in front_values):
        raise DataError(f"{issue_text} 前区号码超出01-35范围")
    if not all(1 <= value <= 12 for value in back_values):
        raise DataError(f"{issue_text} 后区号码超出01-12范围")

    return Draw(
        issue=issue_text,
        date=date_text,
        front=front_values,
        back=back_values,
        source=source,
        source_url=source_url,
        fetched_at=fetched_at or utc_now(),
    )


def validate_ticket(front: Iterable[Any], back: Iterable[Any]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Validate a user ticket using the same ranges as an official draw."""
    try:
        front_values = tuple(sorted(int(value) for value in front))
        back_values = tuple(sorted(int(value) for value in back))
    except (TypeError, ValueError) as exc:
        raise DataError("投注号码必须是整数") from exc
    if len(front_values) != 5 or len(set(front_values)) != 5:
        raise DataError("投注前区必须是5个不重复号码")
    if len(back_values) != 2 or len(set(back_values)) != 2:
        raise DataError("投注后区必须是2个不重复号码")
    if not all(1 <= value <= 35 for value in front_values):
        raise DataError("投注前区号码必须在01-35")
    if not all(1 <= value <= 12 for value in back_values):
        raise DataError("投注后区号码必须在01-12")
    return front_values, back_values


def _allowed_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise DataError(f"拒绝访问白名单之外的地址：{url}")


def fetch_bytes(url: str, *, timeout: float = 15.0, retries: int = 2) -> bytes:
    """Fetch a bounded response from an allow-listed HTTPS endpoint."""
    _allowed_url(url)
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": OFFICIAL_PAGE,
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.1",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "identity",
            "Connection": "close",
        },
        method="GET",
    )
    last_error: Exception | None = None
    for attempt in range(max(1, retries + 1)):
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise DataError("数据源响应超过大小上限，已拒绝")
            return body
        except (HTTPError, URLError, TimeoutError, OSError, DataError) as exc:
            last_error = exc
            if attempt < retries:
                # Keep retries short and deterministic; never run a background loop.
                import time

                time.sleep(0.5 * (attempt + 1))
    raise DataError(f"数据源请求失败：{last_error}") from last_error


def official_url(page_no: int = 1, page_size: int = 100) -> str:
    params = {
        "gameNo": "85",
        "provinceId": "0",
        "pageSize": str(max(1, min(int(page_size), 100))),
        "isVerify": "1",
        "termLimits": "0",
        "pageNo": str(max(1, int(page_no))),
    }
    return f"{OFFICIAL_API}?{urlencode(params)}"


def parse_official_payload(payload: dict[str, Any], *, source_url: str, fetched_at: str | None = None) -> list[Draw]:
    if str(payload.get("errorCode", "")) != "0":
        raise DataError(f"中国体彩网接口错误：{payload.get('errorMessage', '未知错误')}")
    value = payload.get("value")
    records = value.get("list") if isinstance(value, dict) else None
    if not isinstance(records, list) or not records:
        raise DataError("中国体彩网响应缺少开奖列表")

    result: list[Draw] = []
    stamp = fetched_at or utc_now()
    for record in records:
        if not isinstance(record, dict):
            raise DataError("中国体彩网开奖记录不是对象")
        values = str(record.get("lotteryDrawResult", "")).split()
        if len(values) != 7:
            raise DataError(f"{record.get('lotteryDrawNum', '未知期号')} 开奖号码不是7个")
        result.append(
            validate_draw(
                record.get("lotteryDrawNum", ""),
                record.get("lotteryDrawTime", ""),
                values[:5],
                values[5:],
                source="中国体彩网官方接口",
                source_url=source_url,
                fetched_at=stamp,
            )
        )
    return _dedupe_draws(result)


def fetch_official(*, pages: int = 1, page_size: int = 100, timeout: float = 15.0) -> list[Draw]:
    """Fetch recent official draws. Pages are deliberately capped by the CLI."""
    if pages < 1 or pages > 20:
        raise DataError("pages 必须在1-20之间")
    result: list[Draw] = []
    for page_no in range(1, pages + 1):
        url = official_url(page_no, page_size)
        raw = fetch_bytes(url, timeout=timeout)
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DataError("中国体彩网返回不是有效 JSON") from exc
        if not isinstance(payload, dict):
            raise DataError("中国体彩网 JSON 根节点不是对象")
        page = parse_official_payload(payload, source_url=url)
        result.extend(page)
        if len(page) < page_size:
            break
    return _dedupe_draws(result)


def parse_secondary_html(raw: bytes, *, source_url: str, source_name: str = "500.com镜像") -> list[Draw]:
    """Parse only the tabular draw fields from the 500.com/500star mirror."""
    text = raw.decode("gb18030", errors="replace")
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", text, flags=re.I | re.S)
    result: list[Draw] = []
    for row in rows:
        row = re.sub(r"<!--.*?-->", "", row, flags=re.S)
        cells = [html.unescape(re.sub(r"<[^>]+>", " ", cell)).strip() for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.I | re.S)]
        if not cells:
            continue
        issue_match = re.fullmatch(r"\d{4,6}", cells[0])
        date_match = next(
            (match for cell in cells if (match := re.search(r"\d{4}-\d{2}-\d{2}", cell))),
            None,
        )
        numeric_cells = [cell for cell in cells[1:] if re.fullmatch(r"\d{1,2}", cell)]
        if not issue_match or not date_match or len(numeric_cells) < 7:
            continue
        try:
            result.append(
                validate_draw(
                    cells[0],
                    date_match.group(0),
                    numeric_cells[:5],
                    numeric_cells[5:7],
                    source=source_name,
                    source_url=source_url,
                )
            )
        except DataError:
            continue
    if not result:
        raise DataError("500.com镜像未解析出合法开奖记录")
    return _dedupe_draws(result)


def fetch_secondary(issue: str, *, host: str = "datachart.500.com", timeout: float = 15.0) -> list[Draw]:
    _issue_key(issue)
    if host not in {"datachart.500.com", "datachart.500star.com"}:
        raise DataError("secondary host 不在允许的镜像白名单")
    url = f"https://{host}/dlt/history/newinc/history.php?{urlencode({'start': issue, 'end': issue})}"
    return parse_secondary_html(fetch_bytes(url, timeout=timeout), source_url=url, source_name=f"{host}镜像")


def _dedupe_draws(draws: Iterable[Draw]) -> list[Draw]:
    by_issue: dict[str, Draw] = {}
    for draw in draws:
        prior = by_issue.get(draw.issue)
        if prior is not None and (prior.date, prior.front, prior.back) != (draw.date, draw.front, draw.back):
            raise DataError(f"同一期数据冲突：{draw.issue}")
        by_issue[draw.issue] = draw
    return sorted(by_issue.values(), key=lambda item: _issue_key(item.issue), reverse=True)


def cross_validate(official: Draw, secondary: Draw) -> dict[str, Any]:
    same = (official.issue, official.date, official.front, official.back) == (
        secondary.issue,
        secondary.date,
        secondary.front,
        secondary.back,
    )
    if not same:
        raise DataError(
            f"来源冲突：官方={official.issue}/{official.date}/{official.front}/{official.back}; "
            f"镜像={secondary.issue}/{secondary.date}/{secondary.front}/{secondary.back}"
        )
    return {
        "matched": True,
        "issue": official.issue,
        "official_source": official.source_url,
        "secondary_source": secondary.source_url,
    }


def draw_from_json(value: dict[str, Any]) -> Draw:
    if not isinstance(value, dict):
        raise DataError("输入记录不是对象")
    return validate_draw(
        value.get("issue", ""),
        value.get("date", ""),
        value.get("front", []),
        value.get("back", []),
        source=str(value.get("source", "本地数据")),
        source_url=str(value.get("source_url", "")),
        fetched_at=str(value.get("fetched_at", utc_now())),
    )


def load_draws(path: Path) -> list[Draw]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError(f"无法读取输入 JSON：{path}") from exc
    records = payload.get("draws") if isinstance(payload, dict) else payload
    if not isinstance(records, list) or not records:
        raise DataError("输入 JSON 必须是非空数组，或包含 draws 数组")
    return _dedupe_draws(draw_from_json(record) for record in records)


def save_draws(path: Path, draws: Iterable[Draw]) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"saved_at": utc_now(), "draws": [draw.to_json() for draw in _dedupe_draws(draws)]}
    # Atomic replacement avoids leaving a half-written cache after interruption.
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _window(draws: list[Draw], size: int) -> list[Draw]:
    if not draws:
        raise DataError("没有可分析的开奖数据")
    if size < 1:
        raise DataError("window 必须大于0")
    return sorted(draws, key=lambda item: _issue_key(item.issue), reverse=True)[:size]


def _omission(draws: list[Draw], pool: range, attr: str) -> dict[str, int]:
    values = [set(getattr(draw, attr)) for draw in draws]
    result: dict[str, int] = {}
    for number in pool:
        result[f"{number:02d}"] = next((index for index, current in enumerate(values) if number in current), len(values))
    return result


def _max_run(values: Iterable[int]) -> int:
    current = longest = 1
    ordered = sorted(values)
    for left, right in zip(ordered, ordered[1:]):
        if right == left + 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def analyze(draws: list[Draw], *, window: int = 100) -> dict[str, Any]:
    selected = _window(draws, window)
    front_counts = Counter(number for draw in selected for number in draw.front)
    back_counts = Counter(number for draw in selected for number in draw.back)
    sums = [sum(draw.front) for draw in selected]
    front_total = math.comb(35, 5)
    back_total = math.comb(12, 2)
    return {
        "window": len(selected),
        "latest_issue": selected[0].issue,
        "latest_date": selected[0].date,
        "sources": sorted({draw.source for draw in selected}),
        "front_frequency": {f"{n:02d}": front_counts[n] for n in range(1, 36)},
        "back_frequency": {f"{n:02d}": back_counts[n] for n in range(1, 13)},
        "front_omission_draws": _omission(selected, range(1, 36), "front"),
        "back_omission_draws": _omission(selected, range(1, 13), "back"),
        "odd_front_histogram": dict(sorted(Counter(sum(number % 2 for number in draw.front) for draw in selected).items())),
        "front_sum": {
            "min": min(sums),
            "max": max(sums),
            "average": round(sum(sums) / len(sums), 2),
        },
        "max_consecutive_front": max(_max_run(draw.front) for draw in selected),
        "random_baseline": {
            "front_combinations": front_total,
            "back_combinations": back_total,
            "single_ticket_combinations": front_total * back_total,
            "jackpot_probability": f"1/{front_total * back_total}",
            "interpretation": "历史频率不会改变下一期任一合法组合的数学概率",
        },
    }


def _weighted_sample(pool: list[int], weights: list[float], count: int, rng: random.Random) -> tuple[int, ...]:
    available = list(pool)
    remaining = list(weights)
    picked: list[int] = []
    for _ in range(count):
        total = sum(remaining)
        if total <= 0:
            index = rng.randrange(len(available))
        else:
            target = rng.random() * total
            index = 0
            for index, weight in enumerate(remaining):
                target -= weight
                if target <= 0:
                    break
        picked.append(available.pop(index))
        remaining.pop(index)
    return tuple(sorted(picked))


def recommend(draws: list[Draw], *, count: int = 5, window: int = 100, seed: int = 20260825) -> dict[str, Any]:
    if count < 1 or count > 100:
        raise DataError("count 必须在1-100之间")
    selected = _window(draws, window)
    front_counts = Counter(number for draw in selected for number in draw.front)
    back_counts = Counter(number for draw in selected for number in draw.back)
    # Blend empirical frequency with uniform weights. This is a reproducible
    # sample generator, not a probability model or prediction claim.
    front_avg = sum(front_counts.values()) / 35
    back_avg = sum(back_counts.values()) / 12
    front_weights = [0.5 + 0.5 * (front_counts[n] / front_avg if front_avg else 1.0) for n in range(1, 36)]
    back_weights = [0.5 + 0.5 * (back_counts[n] / back_avg if back_avg else 1.0) for n in range(1, 13)]
    rng = random.Random(seed)
    tickets: list[dict[str, Any]] = []
    seen: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    attempts = 0
    while len(tickets) < count and attempts < count * 100:
        attempts += 1
        front = _weighted_sample(list(range(1, 36)), front_weights, 5, rng)
        back = _weighted_sample(list(range(1, 13)), back_weights, 2, rng)
        key = (front, back)
        if key in seen:
            continue
        seen.add(key)
        tickets.append({"front": [f"{n:02d}" for n in front], "back": [f"{n:02d}" for n in back]})
    if len(tickets) != count:
        raise DataError("无法生成足够的不重复统计样本")
    return {
        "window": len(selected),
        "latest_issue": selected[0].issue,
        "seed": seed,
        "tickets": tickets,
        "method": "频率与均匀基线50/50混合的可复现抽样",
        "claim_boundary": "这些是娱乐性统计样本，不代表预测、优势或更高中奖概率",
    }


def prize_grade(front_hits: int, back_hits: int) -> int | None:
    rules = {
        (5, 2): 1,
        (5, 1): 2,
        (5, 0): 3,
        (4, 2): 3,
        (4, 1): 4,
        (4, 0): 5,
        (3, 2): 5,
        (3, 1): 6,
        (2, 2): 6,
        (3, 0): 7,
        (2, 1): 7,
        (1, 2): 7,
        (0, 2): 7,
    }
    return rules.get((front_hits, back_hits))


def check_ticket(draw: Draw, front: Iterable[Any], back: Iterable[Any]) -> dict[str, Any]:
    front_values, back_values = validate_ticket(front, back)
    front_hits = len(set(front_values) & set(draw.front))
    back_hits = len(set(back_values) & set(draw.back))
    grade = prize_grade(front_hits, back_hits)
    return {
        "issue": draw.issue,
        "date": draw.date,
        "draw_front": [f"{n:02d}" for n in draw.front],
        "draw_back": [f"{n:02d}" for n in draw.back],
        "ticket_front": [f"{n:02d}" for n in front_values],
        "ticket_back": [f"{n:02d}" for n in back_values],
        "front_hits": front_hits,
        "back_hits": back_hits,
        "prize_grade": grade,
        "rules_source": RULES_URL,
    }


def _parse_numbers(value: str) -> list[int]:
    parts = [part for part in re.split(r"[\s,，|]+", value.strip()) if part]
    try:
        return [int(part) for part in parts]
    except ValueError as exc:
        raise DataError(f"号码格式非法：{value!r}") from exc


def _load_for_command(args: argparse.Namespace) -> list[Draw]:
    if args.input:
        return load_draws(Path(args.input))
    if not args.live:
        raise DataError("请提供 --input <JSON>，或明确指定 --live 获取真实数据")
    draws = fetch_official(pages=args.pages, page_size=args.page_size, timeout=args.timeout)
    if args.secondary:
        latest = draws[0]
        mirrors = fetch_secondary(latest.issue, host=args.secondary_host, timeout=args.timeout)
        mirror = next((item for item in mirrors if item.issue == latest.issue), None)
        if mirror is None:
            raise DataError(f"镜像源没有返回官方最新期 {latest.issue}")
        args._verification = cross_validate(latest, mirror)
    if args.cache:
        save_draws(Path(args.cache), draws)
    return draws


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="可靠、可解释的大乐透查询与统计分析")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in {
        "analyze": "输出历史统计和随机基线",
        "recommend": "生成可复现的娱乐性统计样本",
        "check": "核验一组号码与指定开奖",
        "fetch": "获取并可选保存真实开奖数据",
    }.items():
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--input", help="本地 JSON 文件；不提供时不会使用本地默认缓存")
        command.add_argument("--live", action="store_true", help="明确允许联网获取中国体彩网数据")
        command.add_argument("--secondary", action="store_true", help="同时核验500.com镜像的最新期")
        command.add_argument("--secondary-host", default="datachart.500.com", choices=["datachart.500.com", "datachart.500star.com"])
        command.add_argument("--pages", type=int, default=1, help="官方接口页数，1-20")
        command.add_argument("--page-size", type=int, default=100, help="每页记录数，1-100")
        command.add_argument("--timeout", type=float, default=15.0)
        command.add_argument("--cache", help="显式指定 JSON 缓存输出路径")
    sub.choices["analyze"].add_argument("--window", type=int, default=100)
    sub.choices["recommend"].add_argument("--window", type=int, default=100)
    sub.choices["recommend"].add_argument("--count", type=int, default=5)
    sub.choices["recommend"].add_argument("--seed", type=int, default=20260825)
    check = sub.choices["check"]
    check.add_argument("--front", required=True, help="5个前区号码，空格或逗号分隔")
    check.add_argument("--back", required=True, help="2个后区号码，空格或逗号分隔")
    check.add_argument("--issue", help="要核验的期号，默认最新期")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        draws = _load_for_command(args)
        if args.command == "fetch":
            output = {"draw_count": len(draws), "draws": [draw.to_json() for draw in draws]}
        elif args.command == "analyze":
            output = analyze(draws, window=args.window)
        elif args.command == "recommend":
            output = recommend(draws, count=args.count, window=args.window, seed=args.seed)
        else:
            target = next((draw for draw in draws if not args.issue or draw.issue == args.issue), None)
            if target is None:
                raise DataError(f"找不到期号：{args.issue}")
            output = check_ticket(target, _parse_numbers(args.front), _parse_numbers(args.back))
        if getattr(args, "_verification", None):
            output["source_verification"] = args._verification
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except DataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
