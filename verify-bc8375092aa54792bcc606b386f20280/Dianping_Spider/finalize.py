"""Offline QA/export from cached source responses; never invent missing fields."""
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from Dianping_Spider.collect_national import ROOT, BOARD, ADMIN_URL, admin_index, address_from_html, state_from_html, district_from_regions


def main():
    rows = json.loads((ROOT / 'list_rows.json').read_text('utf-8'))
    admin = json.loads((ROOT / 'administrative_divisions.json').read_text('utf-8'))
    index = admin_index(admin)
    city_dir = json.loads((ROOT / 'city_directory.json').read_text('utf-8'))['cityList']
    cities = {x['cityId']: x for x in city_dir}
    states = {}
    evidence_path = ROOT / 'district_evidence.json'
    evidence = json.loads(evidence_path.read_text('utf-8')) if evidence_path.exists() else {}
    coverage = json.loads((ROOT / 'coverage.json').read_text('utf-8'))
    for row in rows:
        cid = int(row['榜单来源'].split('cityid=')[1].split('&')[0])
        city = cities[cid]
        if cid not in states:
            states[cid] = state_from_html((ROOT / 'boards' / f'{cid}.html').read_text('utf-8'))
        state = states[cid]
        province, city_name, districts = index[city['cityName']]
        row['省份'], row['城市'] = province, city_name
        path = ROOT / 'shops' / f"{row['店铺ID']}.html"
        if path.exists():
            row['原始地址'], row['地址状态'] = address_from_html(path.read_text('utf-8'), row['店铺ID'])
        else:
            row['原始地址'], row['地址状态'] = '', '详情请求未成功，无缓存'
        address_hint = row['原始地址']
        for prefix_name in (province, city_name):
            if address_hint.startswith(prefix_name):
                address_hint = address_hint[len(prefix_name):].lstrip()
        row['区县'], row['区县依据'] = district_from_regions(state, row['商圈'], districts, address_hint)
        proof = evidence.get(f"{cid}:{row['店铺ID']}", [])
        proof_names = {x['区县'] for x in proof}
        if not row['区县'] and row['区县依据'] == '区县未核实' and len(proof_names) == 1:
            row['区县'] = proof_names.pop()
            row['区县依据'] = '同店铺ID出现在榜单县级城市入口'
            row['区县来源'] = proof[0]['来源']
        else:
            row['区县来源'] = row['榜单来源']
        # County-level destinations have no additional county level.
        if city_name in ('陵水黎族自治县', '文昌市', '万宁市'):
            row['区县'], row['区县依据'] = city_name, '省直辖县级目的地，无更下一级区县'
        prefix = province + ('' if province == city_name else city_name)
        if row['区县'] and row['区县'] != city_name and not row['原始地址'].startswith(row['区县']):
            prefix += row['区县']
        raw = row['原始地址']
        # Avoid doubled full-address prefixes when the source already has them.
        row['店铺具体地点'] = raw if raw.startswith(province) else (province + raw if raw.startswith(city_name) else prefix + raw)
        row['地址完整性'] = '省市区及街道已获取' if province and row['区县'] and raw else '区县或街道未核实'
        if city_name in ('东莞市', '中山市') and raw and row['区县']:
            row['地址完整性'] = '省市及直管镇街/门牌已获取，无区县'
        if city_name in ('东莞市', '中山市') and raw and not row['区县']:
            row['地址完整性'] = '省市及街道已获取，地级市直管镇街无区县'
            row['区县依据'] = '不虚构行政区：地级市直管镇街'
    observed = {x['城市'] for x in coverage}
    absent = []
    for province in admin:
        for city in province.get('children', []):
            name = province['name'] if city['name'] == '市辖区' else city['name']
            if '直辖' in city['name']:
                for county in city.get('children', []):
                    if county['name'] not in observed:
                        absent.append({'省份': province['name'], '城市': county['name'], '城市ID': '', '目录上榜数量': '',
                                       '已获取数量': 0, '状态': '未列入当前必吃榜城市目录（省直辖县级地区）', '错误': ''})
                continue
            if city['name'] == '县' or name in observed:
                continue
            absent.append({'省份': province['name'], '城市': name, '城市ID': '', '目录上榜数量': '',
                           '已获取数量': 0, '状态': '未列入当前必吃榜城市目录', '错误': ''})
    for entry in coverage:
        expected = min(20, entry['目录上榜数量'])
        entry['状态'] = '部分资料未获取' if entry['错误'] and entry['已获取数量'] else ('获取失败' if entry['错误'] else ('已获取前20家' if entry['已获取数量'] == 20 else '不足20家，按实际榜单保留'))
        if entry['已获取数量'] != expected and not entry['错误']:
            entry['状态'] = '目录数量与实际可见数量不一致'
    coverage += absent
    keys = [(x['城市'], x['店铺ID']) for x in rows]
    assert len(set(keys)) == len(rows), '城市内店铺ID重复'
    counts = Counter(x['城市'] for x in rows)
    assert all(x <= 20 for x in counts.values()), '每城上限超过20'
    assert all(x['省份'] and x['城市'] and x['店铺名'] for x in rows), '必需身份字段缺失'
    assert all(x['评分'] is None or 0 <= float(x['评分']) <= 5 for x in rows), '评分超出5分制'
    assert all(x['人均消费（元/人）'] is None or float(x['人均消费（元/人）']) >= 0 for x in rows), '消费值异常'
    stats = {'餐馆数量': len(rows), '榜单城市数量': len(counts), '省级地区数量': len({x['省份'] for x in rows}),
             '未列入目录的地级或省直辖县级地区数量': len(absent), '每城20家的城市数量': sum(x == 20 for x in counts.values()),
             '少于20家的城市数量': sum(x < 20 for x in counts.values()),
             '街道地址缺失数量': sum(not x['原始地址'] for x in rows),
             '区县未核实数量': sum(not x['区县'] and x['城市'] not in ('东莞市', '中山市') for x in rows),
             '榜单资料未完整获取的城市数量': sum(bool(x['错误']) for x in coverage),
             '评分缺失数量': sum(x['评分'] in (None, '') for x in rows),
             '人均缺失数量': sum(x['人均消费（元/人）'] in (None, '') for x in rows),
             '特色菜缺失数量': sum(not x['店铺特色菜'] for x in rows),
             '采集完成时间UTC': datetime.now(timezone.utc).isoformat()}
    fields = ['省份', '城市', '区县', '店铺名', '店铺具体地点', '评分', '人均消费（元/人）', '店铺特色菜', '地址完整性', '地址状态', '区县依据', '店铺ID', '榜单来源', '详情来源', '区县来源']
    for filename, data, headers in [('restaurants.csv', rows, fields), ('city_coverage.csv', coverage, list(coverage[0]))]:
        with (ROOT / filename).open('w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
    (ROOT / 'restaurants.json').write_text(json.dumps({'统计': stats, '行政区参考来源': ADMIN_URL, '餐馆': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'quality_report.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
