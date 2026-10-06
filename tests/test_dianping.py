import unittest
from Dianping_Spider.collect_national import address_from_html, district_from_regions, admin_index, state_from_html


class DianpingTests(unittest.TestCase):
    def test_identity_and_html_address(self):
        body = '<a href="/shop/123">店</a><p class="address"><a>东路1号&amp;2号</a></p>'
        self.assertEqual(address_from_html(body, 123), ('东路1号&2号', '已获取'))
        self.assertEqual(address_from_html(body, 124)[0], '')

    def test_validation_page_is_not_an_address(self):
        self.assertEqual(address_from_html('<title>验证中心</title>', 123)[0], '')

    def test_unique_business_area_mapping(self):
        state = {'filterState': {'regionList': [{'list': [
            {'regionName': '越秀区', 'subRegions': [{'regionName': '东山口'}]}]}]}}
        self.assertEqual(district_from_regions(state, '东山口', [{'name': '越秀区'}])[0], '越秀区')

    def test_ambiguous_business_area_not_guessed(self):
        state = {'filterState': {'regionList': [{'list': [
            {'regionName': '甲区', 'subRegions': [{'regionName': '中心'}]},
            {'regionName': '乙区', 'subRegions': [{'regionName': '中心'}]}]}]}}
        self.assertEqual(district_from_regions(state, '中心', [{'name': '甲区'}, {'name': '乙区'}])[0], '')

    def test_explicit_address_district(self):
        self.assertEqual(district_from_regions({}, '', [{'name': '天河区'}], '天河区东路1号')[0], '天河区')

    def test_county_city_short_name(self):
        state = {'filterState': {'regionList': [{'list': [
            {'regionName': '昆山', 'subRegions': [{'regionName': '亭林路'}]}]}]}}
        self.assertEqual(district_from_regions(state, '亭林路', [{'name': '昆山市'}])[0], '昆山市')

    def test_address_conflict_not_hidden(self):
        state = {'filterState': {'regionList': [{'list': [
            {'regionName': '甲区', 'subRegions': [{'regionName': '中心'}]}]}]}}
        self.assertEqual(district_from_regions(state, '中心', [{'name': '甲区'}, {'name': '乙区'}], '乙区东路1号')[0], '')

    def test_municipality(self):
        idx = admin_index([{'name': '北京市', 'children': [{'name': '市辖区', 'children': [{'name': '东城区'}]}]}])
        self.assertEqual(idx['北京'][:2], ('北京市', '北京市'))

    def test_state_parser(self):
        self.assertEqual(state_from_html('window.__K2_INITIAL_STATE__={"x":1};rest'), {'x': 1})


if __name__ == '__main__':
    unittest.main()
