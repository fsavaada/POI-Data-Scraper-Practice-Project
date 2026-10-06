"""Prove county-level membership using city links exposed by the board."""
import json
from collections import defaultdict
from Dianping_Spider.collect_national import ROOT, BOARD, cached, state_from_html, admin_index


def main():
    rows = json.loads((ROOT / 'list_rows.json').read_text('utf-8'))
    city_dir = {x['cityId']: x for x in json.loads((ROOT / 'city_directory.json').read_text('utf-8'))['cityList']}
    index = admin_index(json.loads((ROOT / 'administrative_divisions.json').read_text('utf-8')))
    unresolved = {int(x['榜单来源'].split('cityid=')[1].split('&')[0]) for x in rows if not x['区县']}
    evidence = defaultdict(list)
    requests = []
    for cid in sorted(unresolved):
        state = state_from_html((ROOT / 'boards' / f'{cid}.html').read_text('utf-8'))
        allowed = {x['name'] for x in index[city_dir[cid]['cityName']][2]}
        for group in state.get('filterState', {}).get('regionList', []):
            for district in group.get('list', []):
                if district.get('type') != 999:
                    continue
                name = district.get('regionName', '')
                matches = [x for x in allowed if x == name or x.removesuffix('市').removesuffix('县').removesuffix('区') == name]
                if len(matches) == 1:
                    requests.append((cid, int(district['regionId']), matches[0]))
    for parent, child, district in requests:
        url = BOARD.format(child)
        try:
            state = state_from_html(cached(url, ROOT / 'child_boards' / f'{child}.html'))
            base = state['baseInfo']
            if int(base.get('cityId', -1)) != parent or int(base.get('originCityId', -1)) != child:
                raise ValueError('城市归属返回不匹配')
            source_name = base.get('originCityName', '')
            short_name = district.removesuffix('市').removesuffix('县').removesuffix('区')
            if source_name not in (district, short_name):
                raise ValueError('来源县级城市名称与行政区参考不一致')
            for sid in state['shopInfo'].get('shopIds', []):
                evidence[f'{parent}:{sid}'].append({'区县': district, '来源': url})
            print(json.dumps({'parent': parent, 'district': district, 'ids': len(state['shopInfo'].get('shopIds', []))}, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({'district': district, 'error': str(exc)}, ensure_ascii=False), flush=True)
    (ROOT / 'district_evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('DISTRICT_EVIDENCE_COMPLETE', len(evidence), flush=True)


if __name__ == '__main__':
    main()
