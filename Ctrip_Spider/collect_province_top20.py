"""采集携程全国省级行政区景点榜单，并保存为 CSV。"""

from __future__ import annotations

import argparse
import csv
from http.client import RemoteDisconnected
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "香港",
    "澳门", "台湾",
]

SEARCH_URL = "https://m.ctrip.com/restapi/soa2/26872/search"
ATTRACTION_API_URL = "https://m.ctrip.com/restapi/soa2/18109/json/getAttractionList"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)



def _request(url: str, payload: dict | None = None, retries: int = 3) -> bytes:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"}
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = Request(url, data=body, headers=headers)
            with urlopen(request, timeout=30) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError, RemoteDisconnected, ConnectionResetError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * attempt + random.uniform(0.2, 0.8))
    raise RuntimeError(f"请求失败（重试 {retries} 次）: {url}: {last_error}")


def find_province_id(province: str) -> int:
    payload = {
        "action": "online",
        "source": "globalonline",
        "keyword": province,
        "pagenum": 1,
        "pagesize": 20,
    }
    data = json.loads(_request(SEARCH_URL, payload).decode("utf-8"))
    candidates = [item for item in data.get("data", []) if item.get("type") == "district"]

    for item in candidates:
        if item.get("word") == province:
            return int(item["id"])
    for item in candidates:
        if province in str(item.get("word", "")):
            return int(item["id"])
    raise ValueError(f"未找到省级目的地 ID: {province}")


EXCLUDED_KEYWORDS = (
    "演出", "演唱会", "音乐会", "脱口秀", "相声", "戏曲", "话剧", "舞台剧",
    "演艺", "剧场", "剧院", "电影院", "影城电影", "LiveHouse", "LIVEHOUSE",
    "酒吧", "KTV", "密室逃脱", "剧本杀", "网吧", "电竞馆", "足浴", "按摩",
    "赛事", "展览", "水疗", "汤泉", "洗浴", "采耳", "棋牌", "轰趴", "电玩",
    "桌游", "台球", "派对", "生日会",
    "音乐剧", "儿童剧", "巡演", "开放麦", "音乐节", "艺术节", "影院", "电影院",
    "SPA", "比赛", "发布会",
)


def _is_attraction(card: dict) -> bool:
    """只保留景点类 POI，并排除演出、娱乐场所等非景点。"""
    poi_type = card.get("poiType")
    if poi_type not in (3, 66):
        return False
    if poi_type == 66 and " · " in str(card.get("poiName", "")):
        return False
    searchable = " ".join(
        [
            str(card.get("poiName", "")),
            str(card.get("sightCategoryInfo", "")),
            " ".join(str(tag) for tag in card.get("tagNameList", [])),
        ]
    )
    return not any(keyword.lower() in searchable.lower() for keyword in EXCLUDED_KEYWORDS)


def _fetch_attraction_page(
    district_id: int,
    index: int,
    count: int = 20,
    token: str = "",
    sort_type: int = 1,
) -> dict:
    cid = "090310" + "".join(str(random.randrange(10)) for _ in range(14))
    payload = {
        "scene": "online",
        "districtId": district_id,
        "index": index,
        "sortType": sort_type,
        "count": count,
        "filter": {"filterItems": []},
        "returnModuleType": "product",
        "token": token,
        "head": {
            "auth": "",
            "cid": cid,
            "ctok": "",
            "cver": "1.0",
            "extension": [{"name": "tecode", "value": "h5"}],
            "lang": "01",
            "sid": "8888",
            "syscode": "09",
            "xsid": "",
        },
    }
    return json.loads(_request(ATTRACTION_API_URL, payload).decode("utf-8"))


def fetch_top_attractions(district_id: int, province: str, limit: int) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    seen_names: set[str] = set()
    for sort_type in (1, 9, 4, 5):
        token = ""
        stagnant_pages = 0
        for page in range(1, 31):
            before = len(rows)
            data = _fetch_attraction_page(
                district_id, page, token=token, sort_type=sort_type
            )
            items = data.get("attractionList", [])
            if not items:
                break
            for item in items:
                card = item.get("card") or {}
                if not _is_attraction(card):
                    continue
                unique_id = str(
                    card.get("poiId") or card.get("businessId") or card.get("poiName")
                )
                if unique_id in seen:
                    continue
                name = str(card.get("poiName", "")).strip()
                normalized_name = re.sub(r"\s+", "", name).casefold()
                if not name or normalized_name in seen_names:
                    continue
                seen.add(unique_id)
                seen_names.add(normalized_name)
                city = str(card.get("districtName", "")).strip() or "暂无"
                detail_location = str(card.get("displayField", "")).strip() or city
                raw_price = card.get("price")
                price: str | float = (
                    "免费" if raw_price in (None, "", 0, 0.0) else raw_price
                )
                rows.append(
                    {
                        "景点名称": name,
                        "省份": province,
                        "市区": city,
                        "详细地点": detail_location,
                        "景点门票价格": price,
                        "评分": card.get("commentScore") or "暂无评分",
                    }
                )
                if len(rows) >= limit:
                    return rows[:limit]
            stagnant_pages = stagnant_pages + 1 if len(rows) == before else 0
            if not data.get("hasMore", False) or stagnant_pages >= 3:
                break
            token = str(data.get("token", ""))
            time.sleep(random.uniform(0.25, 0.55))

    return rows[:limit]


def collect(provinces: Iterable[str], limit: int, delay: tuple[float, float]) -> list[dict]:
    all_rows: list[dict] = []
    province_list = list(provinces)
    for index, province in enumerate(province_list, 1):
        try:
            district_id = find_province_id(province)
            rows = fetch_top_attractions(district_id, province, limit)
            if not rows:
                raise ValueError("榜单页面未解析到景点卡片")
            all_rows.extend(rows)
            logging.info("[%d/%d] %s: %d 条", index, len(province_list), province, len(rows))
        except Exception as exc:  # 单省失败不终止全国任务
            logging.error("[%d/%d] %s: %s", index, len(province_list), province, exc)
        if index < len(province_list):
            time.sleep(random.uniform(*delay))
    return all_rows


def write_csv(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["景点名称", "省份", "市区", "详细地点", "景点门票价格", "评分"]
    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=350, help="每省采集条数，默认 350")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Datasets/ctrip_province_top350.csv"),
        help="CSV 输出路径",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    rows = collect(PROVINCES, max(1, args.top), (3.0, 6.0))
    write_csv(rows, args.output)
    logging.info("采集完成：%d 条，保存至 %s", len(rows), args.output.resolve())
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
