"""One public single-shop focus retry for missing on-board records."""
import json
import re
from urllib.parse import urlencode
from Dianping_Spider.collect_national import ROOT, BOARD, cached, state_from_html, address_from_html


def main():
    rows = json.loads((ROOT / 'list_rows.json').read_text('utf-8'))
    coverage = json.loads((ROOT / 'coverage.json').read_text('utf-8'))
    for city in coverage:
        if not city['错误'].startswith('部分上榜店铺资料未获取：'):
            continue
        cid = city['城市ID']
        missing = city['错误'].split('：')[1].split(',')
        still_missing = []
        for sid in missing:
            try:
                state = state_from_html(cached(BOARD.format(cid) + '&' + urlencode({'topshopids': sid}), ROOT / 'boards' / f'{cid}_single_{sid}.html'))
                shops = state['shopInfo'].get('shopList', []) + state['shopInfo'].get('remainingShopList', [])
                shop = next((x for x in shops if str(x['shopId']) == sid), None)
                if shop is None:
                    still_missing.append(sid)
                    print('仍无资料', cid, sid, flush=True)
                    continue
                template = next(x for x in rows if x['榜单来源'] == BOARD.format(cid)).copy()
                template.update({'店铺名': shop['shopName'], '评分': shop.get('fiveScore'), '人均消费（元/人）': shop.get('price'),
                    '店铺特色菜': '；'.join(dish for tag in shop.get('shopTags', []) for dish in re.findall(r'["“]([^"”]+)["”]', tag)),
                    '店铺ID': sid, '商圈': shop.get('mainRegionName', ''), '区县': '', '区县依据': '区县未核实',
                    '详情来源': f'https://www.dianping.com/shop/{sid}/photos/album'})
                original = state_from_html((ROOT / 'boards' / f'{cid}.html').read_text('utf-8'))
                template['页面展示序号'] = list(map(str, original['shopInfo']['shopIds'])).index(sid) + 1
                body = cached(template['详情来源'], ROOT / 'shops' / f'{sid}.html')
                template['原始地址'], template['地址状态'] = address_from_html(body, sid)
                rows.append(template)
                city['已获取数量'] += 1
                print('已恢复', cid, sid, flush=True)
            except Exception as exc:
                still_missing.append(sid)
                print('恢复失败', cid, sid, str(exc), flush=True)
        city['错误'] = '部分上榜店铺资料未获取：' + ','.join(still_missing) if still_missing else ''
    rows.sort(key=lambda x: (int(x['榜单来源'].split('cityid=')[1].split('&')[0]), x['页面展示序号']))
    (ROOT / 'list_rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'coverage.json').write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
