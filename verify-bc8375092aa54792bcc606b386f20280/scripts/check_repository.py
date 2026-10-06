"""Read-only snapshot and source checks; never contacts collection platforms."""
import ast
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))


def check(root=ROOT):
    for folder in ('Ctrip_Spider', 'Dianping_Spider', 'tests', 'scripts'):
        for path in (root / folder).rglob('*.py'):
            ast.parse(path.read_text('utf-8'), filename=path.name, feature_version=(3, 10))
    ctrip = read_csv(root / 'Datasets/ctrip_province_top350.csv')
    require(len(ctrip) == 11900, '携程快照行数与记录不一致')
    require(set(Counter(x['省份'] for x in ctrip).values()) == {350}, '携程省份数量异常')
    require(len({x['省份'] for x in ctrip}) == 34, '携程省级范围异常')
    require(len({(x['省份'], x['景点名称']) for x in ctrip}) == len(ctrip), '携程地区内名称重复')
    dp_root = root / 'Datasets/dianping_national'
    restaurants = read_csv(dp_root / 'restaurants.csv')
    report = json.loads((dp_root / 'quality_report.json').read_text('utf-8'))
    require(len(restaurants) == report['餐馆数量'], '点评CSV与质量报告行数不一致')
    require(len({x['店铺ID'] for x in restaurants}) == len(restaurants), '点评店铺ID重复')
    counts = Counter(x['城市'] for x in restaurants)
    require(len(counts) == report['榜单城市数量'], '点评城市数不一致')
    require(max(counts.values()) <= 20, '点评每城超过20家')
    require(len({x['省份'] for x in restaurants}) == report['省级地区数量'], '点评省级范围不一致')
    for row in restaurants:
        require(all(row[k] for k in ('店铺名', '店铺具体地点', '评分', '人均消费（元/人）', '店铺特色菜')), '点评主要字段为空')
        require(0 <= float(row['评分']) <= 5, '点评评分超出范围')
        require(float(row['人均消费（元/人）']) >= 0, '点评人均消费为负')
    coverage = read_csv(dp_root / 'city_coverage.csv')
    require(sum(int(x['已获取数量']) for x in coverage) == len(restaurants), '覆盖报告数量不守恒')
    data = json.loads((dp_root / 'restaurants.json').read_text('utf-8'))['餐馆']
    require(len(data) == len(restaurants), '点评JSON与CSV行数不一致')
    require({str(x['店铺ID']) for x in data} == {x['店铺ID'] for x in restaurants}, '点评JSON/CSV身份不一致')
    require(sum(not x['原始地址'] for x in data) == report['街道地址缺失数量'], '地址缺失统计不一致')
    require(sum(not x['区县'] and x['城市'] not in ('东莞市', '中山市') for x in data) == report['区县未核实数量'], '地区缺失统计不一致')
    manifest_path = root / 'Datasets/manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text('utf-8'))
        for record in manifest['files']:
            path = root / record['path']
            require(path.is_file(), '数据清单文件不存在：' + record['path'])
            require(hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'], '数据快照SHA-256不一致：' + record['path'])
    return {'ctrip_attractions': len(ctrip), 'dianping_restaurants': len(restaurants),
            'dianping_cities': len(counts), 'coverage_rows': len(coverage), 'district_unverified': report['区县未核实数量']}


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, indent=2))
