"""Restaurant discovery adapter. Search results are not restaurant detail data."""
from __future__ import annotations

import json
from urllib.parse import urlparse
from Ctrip_Spider.collect_province_top20 import SEARCH_URL, _request


def normalize_restaurants(response: dict) -> list[dict]:
    items = response.get("data")
    if not isinstance(items, list):
        raise ValueError("搜索响应 data 必须是列表")
    rows, seen = [], set()
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "food":
            continue
        name = str(item.get("word") or "").strip()
        store_id = item.get("id")
        url = str(item.get("url") or "")
        parsed = urlparse(url)
        if not name or not store_id or parsed.hostname != "you.ctrip.com" or not parsed.path.startswith("/food/"):
            continue
        key = str(item.get("poiId") or store_id)
        if key in seen:
            continue
        seen.add(key)
        city = str(item.get("cityName") or item.get("districtName") or "")
        city = city.split("美食林", 1)[0].strip()
        rows.append({
            "店铺ID": str(store_id), "POI_ID": str(item.get("poiId") or ""),
            "店铺名称": name, "城市": city, "商圈": item.get("zoneName") or None,
            "纬度": item.get("lat"), "经度": item.get("lon"), "来源链接": url,
            "用户评分": None, "人均消费": None, "详细地址": None,
        })
    return rows


def search_restaurants(keyword: str, page: int = 1) -> list[dict]:
    if not keyword.strip() or page < 1:
        raise ValueError("关键词不能为空，页码必须大于零")
    response = json.loads(_request(SEARCH_URL, {
        "action": "online", "source": "globalonline", "keyword": keyword,
        "pagenum": page, "pagesize": 10,
    }).decode("utf-8"))
    return normalize_restaurants(response)
