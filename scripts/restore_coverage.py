"""Recover a missing coverage export from saved metadata without changing shops."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'Datasets/dianping_national'


def main():
    target = ROOT / 'city_coverage.csv'
    if target.exists():
        raise FileExistsError('Refusing to overwrite existing coverage CSV')
    coverage = json.loads((ROOT / 'coverage.json').read_text('utf-8'))
    admin = json.loads((ROOT / 'administrative_divisions.json').read_text('utf-8'))
    report = json.loads((ROOT / 'quality_report.json').read_text('utf-8'))
    observed = {x['城市'] for x in coverage}
    absent = []
    for province in admin:
        for city in province.get('children', []):
            name = province['name'] if city['name'] == '市辖区' else city['name']
            candidates = city.get('children', []) if '直辖' in city['name'] else [{'name': name}]
            if city['name'] == '县':
                continue
            for candidate in candidates:
                if candidate['name'] not in observed:
                    status = '未列入当前必吃榜城市目录'
                    if '直辖' in city['name']:
                        status += '（省直辖县级地区）'
                    absent.append({'省份': province['name'], '城市': candidate['name'],
                                   '城市ID': '', '目录上榜数量': '', '已获取数量': 0,
                                   '状态': status, '错误': ''})
    for entry in coverage:
        count, error = entry['已获取数量'], entry['错误']
        entry['状态'] = ('部分资料未获取' if count else '获取失败') if error else (
            '已获取前20家' if count == 20 else '不足20家，按实际榜单保留')
        if count != min(20, entry['目录上榜数量']) and not error:
            entry['状态'] = '目录数量与实际可见数量不一致'
    if len(absent) != report['未列入目录的地级或省直辖县级地区数量']:
        raise ValueError('Missing-city count disagrees with saved quality report')
    if sum(x['已获取数量'] for x in coverage) != report['餐馆数量']:
        raise ValueError('Restaurant count disagrees with saved quality report')
    coverage += absent
    with target.open('x', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(coverage[0]))
        writer.writeheader()
        writer.writerows(coverage)
    print(f'Restored coverage rows: {len(coverage)}')


if __name__ == '__main__':
    main()
