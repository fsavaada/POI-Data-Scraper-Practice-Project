"""Collect public must-eat listings, at most 20 unique shops per city.

No login, captcha bypass or invented values. Resume with local response cache.
"""
import argparse
import csv
import html
import json
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1] / 'Datasets' / 'dianping_national'
BOARD = 'https://plat.dianping.com/app/femember-musteat-web/musteat-rank?cityid={}&notitlebar=1&ranktype=3'
CITY_URL = 'https://plat.dianping.com/mapi/shoprank/mustseriescitylist.bin?rankId=136&platform=1&pageCityId=4'
ADMIN_URL = 'https://raw.githubusercontent.com/modood/Administrative-divisions-of-China/master/dist/pca-code.json'
REQUEST_LOCK = threading.Lock()
LAST_REQUEST = 0.0


def cached(url, path):
    if path.exists():
        return path.read_text('utf-8')
    last = None
    for attempt in range(2):
        try:
            global LAST_REQUEST
            # Shared ceiling of three request starts/second, regardless of workers.
            with REQUEST_LOCK:
                time.sleep(max(0, 1 / 3 - (time.monotonic() - LAST_REQUEST)))
                LAST_REQUEST = time.monotonic()
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'zh-CN,zh;q=0.9'})
            with urlopen(req, timeout=20) as response:
                body = response.read().decode('utf-8', 'replace')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding='utf-8')
            time.sleep(0.3)
            return body
        except Exception as exc:
            last = exc
            time.sleep(1 + attempt)
    raise RuntimeError(str(last))


def state_from_html(body):
    marker = 'window.__K2_INITIAL_STATE__='
    if marker not in body:
        raise ValueError('榜单状态缺失，可能要求验证')
    return json.JSONDecoder().raw_decode(body.split(marker, 1)[1])[0]


def clean(value):
    return html.unescape(re.sub(r'<[^>]+>', '', value)).strip()


def address_from_html(body, shop_id):
    # Require a linked identity, not an unrelated occurrence of the ID.
    if not re.search(r'href=["\x27]/shop/' + re.escape(str(shop_id)) + r'["\x27]', body):
        return '', '店铺身份未核验或页面要求验证'
    match = re.search(r'<p\s+class="address"[^>]*>.*?<a[^>]*>(.*?)</a>', body, re.S)
    address = clean(match.group(1)) if match else ''
    return address, '已获取' if address else '公开页无地址'


def admin_index(admin):
    index = {}
    for province in admin:
        for city in province.get('children', []):
            entry = (province['name'], city['name'], city.get('children', []))
            if city['name'] == '市辖区':
                children = [county for group in province.get('children', []) for county in group.get('children', [])]
                if province['name'] == '重庆市':
                    # Official 2025 update, verified against Chongqing Civil Affairs:
                    # https://mzj.cq.gov.cn/zwgk_218/zfxxgkml/tzgg/202512/t20251205_15215632.html
                    children = [x for x in children if x['name'] not in ('江北区', '渝北区')]
                    children.append({'name': '两江新区', 'code': '500157'})
                index[province['name'].removesuffix('市')] = (province['name'], province['name'], children)
            else:
                index[city['name']] = entry
                index[city['name'].removesuffix('市')] = entry
    aliases = {'阿坝': '阿坝藏族羌族自治州', '大理州': '大理白族自治州', '甘孜州': '甘孜藏族自治州',
               '迪庆': '迪庆藏族自治州', '凉山': '凉山彝族自治州', '恩施': '恩施土家族苗族自治州',
               '红河': '红河哈尼族彝族自治州', '黔东南': '黔东南苗族侗族自治州',
               '黔南': '黔南布依族苗族自治州', '黔西南': '黔西南布依族苗族自治州',
               '锡林郭勒': '锡林郭勒盟', '西双版纳': '西双版纳傣族自治州',
               '延边': '延边朝鲜族自治州', '伊犁': '伊犁哈萨克自治州', '陵水': '陵水黎族自治县',
               '文昌': '文昌市', '万宁': '万宁市'}
    for province in admin:
        # Province-administered county-level cities appear under this container.
        for city in province.get('children', []):
            if '直辖' in city['name']:
                for county in city.get('children', []):
                    index[county['name']] = (province['name'], county['name'], [county])
    for alias, name in aliases.items():
        if name in index:
            index[alias] = index[name]
    index['香港'] = ('香港特别行政区', '香港', [])
    index['澳门'] = ('澳门特别行政区', '澳门', [])
    index['台北'] = ('台湾省', '台北市', [])
    return index


def district_from_regions(state, region, admin_districts, address=''):
    candidates = set()
    allowed = {x['name'] for x in admin_districts}
    def canonical(label):
        if label in allowed:
            return label
        matches = [x for x in allowed if x.removesuffix('区').removesuffix('县').removesuffix('市') == label]
        return matches[0] if len(matches) == 1 else ''
    for group in state.get('filterState', {}).get('regionList', []):
        for district in group.get('list', []):
            raw_name = district.get('regionName', '')
            name = canonical(raw_name)
            if not name:
                continue
            subs = district.get('subRegions', district.get('list', []))
            if region in (raw_name, name) or any(x.get('regionName') == region for x in subs):
                candidates.add(name)
    explicit = {x for x in allowed if address.startswith(x)}
    if len(explicit) == 1:
        value = explicit.pop()
        if len(candidates) == 1 and value not in candidates:
            return '', '原始地址与榜单区县冲突，待核实'
        return value, '原始地址行政区'
    if len(candidates) == 1:
        return candidates.pop(), '榜单行政区/商圈归属'
    return '', '区县未核实'


def collect_city(city):
    cid = city['cityId']
    url = BOARD.format(cid)
    try:
        state = state_from_html(cached(url, ROOT / 'boards' / f'{cid}.html'))
        base = state.get('baseInfo', {})
        if int(base.get('cityId', -1)) != cid:
            raise ValueError('返回城市不匹配')
        if base.get('showBlank') or state.get('pageError'):
            raise ValueError('页面为空或错误，不据此判断无上榜餐馆')
        info = state.get('shopInfo', {})
        found = {}
        for shop in info.get('shopList', []) + info.get('remainingShopList', []):
            if shop.get('shopId') and shop.get('shopName'):
                found.setdefault(str(shop['shopId']), shop)
        # First-screen IDs give the authoritative order; the public navigation
        # parameter focuses known on-board IDs without requesting a protected API.
        target_ids = list(dict.fromkeys(map(str, info.get('shopIds', []))))[:20]
        missing = [sid for sid in target_ids if sid not in found]
        more_error = ''
        if missing:
            try:
                focus_url = url + '&' + urlencode({'topshopids': ','.join(missing)})
                focus = state_from_html(cached(focus_url, ROOT / 'boards' / f'{cid}_more.html'))
                if int(focus['baseInfo']['cityId']) != cid:
                    raise ValueError('补充页面城市不匹配')
                for shop in focus['shopInfo'].get('shopList', []) + focus['shopInfo'].get('remainingShopList', []):
                    sid = str(shop.get('shopId', ''))
                    if sid in target_ids:
                        found.setdefault(sid, shop)
                missing = [sid for sid in target_ids if sid not in found]
                if missing:
                    more_error = '部分上榜店铺资料未获取：' + ','.join(missing)
            except Exception as exc:
                more_error = '补充公开页面失败：' + str(exc)
        shops = [found[sid] for sid in target_ids if sid in found] if target_ids else list(found.values())[:20]
        return city, state, shops, more_error
    except Exception as exc:
        return city, {}, [], str(exc)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['lists', 'details', 'all'], default='all')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 6:
        parser.error('workers必须为1至6；所有线程共享每秒最多3次请求的限速')
    ROOT.mkdir(parents=True, exist_ok=True)
    city_data = json.loads(cached(CITY_URL, ROOT / 'city_directory.json'))
    admin = json.loads(cached(ADMIN_URL, ROOT / 'administrative_divisions.json'))
    index = admin_index(admin)
    cities = [x for x in city_data['cityList'] if not x['isOverseas'] or x['cityName'] in ('香港', '澳门', '台北')]
    # Shunde is a Foshan district, not a separate prefecture-level city.
    cities = [x for x in cities if x['cityName'] != '顺德区']
    print(json.dumps({'cities': len(cities), 'unmapped': [x['cityName'] for x in cities if x['cityName'] not in index]}, ensure_ascii=False), flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(collect_city, city) for city in cities]
        for future in as_completed(jobs):
            city, state, shops, error = future.result()
            results.append((city, state, shops, error))
            print(json.dumps({'city': city['cityName'], 'shops': len(shops), 'error': error}, ensure_ascii=False), flush=True)
    results.sort(key=lambda x: x[0]['cityId'])
    rows, coverage = [], []
    for city, state, shops, error in results:
        province, city_name, districts = index.get(city['cityName'], ('', city['cityName'], []))
        coverage.append({'省份': province, '城市': city_name, '城市ID': city['cityId'], '目录上榜数量': city['itemAmount'],
                         '已获取数量': len(shops), '状态': '获取失败' if error else ('已获取前20家' if len(shops) == 20 else '已获取页面可见餐馆'), '错误': error})
        for order, shop in enumerate(shops, 1):
            district, reason = district_from_regions(state, shop.get('mainRegionName', ''), districts)
            dishes = []
            for tag in shop.get('shopTags', []):
                dishes.extend(re.findall(r'["“]([^"”]+)["”]', tag))
            rows.append({'省份': province, '城市': city_name, '区县': district, '店铺名': shop['shopName'],
                         '原始地址': '', '评分': shop.get('fiveScore'), '人均消费（元/人）': shop.get('price'),
                         '店铺特色菜': '；'.join(dict.fromkeys(dishes)), '店铺ID': str(shop['shopId']),
                         '商圈': shop.get('mainRegionName', ''), '区县依据': reason, '地址状态': '尚未获取',
                         '榜单来源': BOARD.format(city['cityId']), '详情来源': f"https://www.dianping.com/shop/{shop['shopId']}/photos/album",
                         '页面展示序号': order, '榜单年份': state.get('baseInfo', {}).get('year')})
    (ROOT / 'list_rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'coverage.json').write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.phase == 'lists':
        print('LISTS_COMPLETE', len(rows), flush=True)
        return
    def detail(row):
        try:
            body = cached(row['详情来源'], ROOT / 'shops' / f"{row['店铺ID']}.html")
            row['原始地址'], row['地址状态'] = address_from_html(body, row['店铺ID'])
        except Exception as exc:
            row['地址状态'] = str(exc)
        return row
    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(detail, rows):
            completed += 1
            if completed % 25 == 0:
                print('DETAIL_PROGRESS', completed, '/', len(rows), flush=True)
    for row in rows:
        city = next(x for x in results if BOARD.format(x[0]['cityId']) == row['榜单来源'])
        districts = index.get(city[0]['cityName'], ('', '', []))[2]
        row['区县'], row['区县依据'] = district_from_regions(city[1], row['商圈'], districts, row['原始地址'])
        prefix = row['省份'] + ('' if row['省份'] == row['城市'] else row['城市'])
        if row['区县'] and row['区县'] != row['城市'] and not row['原始地址'].startswith(row['区县']):
            prefix += row['区县']
        row['店铺具体地点'] = prefix + row['原始地址']
        row['地址完整性'] = '省市区及街道已获取' if row['省份'] and row['区县'] and row['原始地址'] else '存在缺失，见区县/地址状态'
    (ROOT / 'restaurants.json').write_text(json.dumps({'采集时间': datetime.now(timezone.utc).isoformat(),
        '口径': '2026必吃榜综合展示顺序每城最多20家，非官方名次；未上榜城市不从普通餐馆补齐；顺德归佛山',
        '行政区参考来源': ADMIN_URL, '餐馆': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    fields = ['省份', '城市', '区县', '店铺名', '店铺具体地点', '评分', '人均消费（元/人）', '店铺特色菜', '地址完整性', '地址状态', '区县依据', '店铺ID', '榜单来源', '详情来源']
    with (ROOT / 'restaurants.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    with (ROOT / 'city_coverage.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(coverage[0]))
        writer.writeheader()
        writer.writerows(coverage)
    print(json.dumps({'rows': len(rows), 'cities': len(coverage), 'provinces': len({x['省份'] for x in rows}),
        'address_missing': sum(not x['原始地址'] for x in rows), 'district_missing': sum(not x['区县'] for x in rows),
        'city_failures': sum(bool(x['错误']) for x in coverage)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
