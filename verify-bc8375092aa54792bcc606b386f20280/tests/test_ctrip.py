"""Synthetic fixtures and mocks only; no real HTTP calls or log output."""
import unittest
from unittest.mock import Mock, patch
from Ctrip_Spider.collect_province_top20 import _is_attraction
from Ctrip_Spider.sight_list import CtripAttractionScraper
from Ctrip_Spider.sight_comments import CtripCommentSpider
from Ctrip_Spider.sight_detail import AttractionDetailFetcher
from Ctrip_Spider.sight_id import SightId


class CtripTests(unittest.TestCase):
    def test_attraction_category(self):
        self.assertTrue(_is_attraction({'poiType': 3, 'poiName': '示例公园'}))
        self.assertFalse(_is_attraction({'poiType': 1, 'poiName': '示例酒店'}))

    def test_performance_excluded(self):
        for name in ('示例演唱会', '示例脱口秀剧场', '示例SPA'):
            self.assertFalse(_is_attraction({'poiType': 3, 'poiName': name}))

    def test_coordinates_not_swapped(self):
        scraper = CtripAttractionScraper(logger=Mock())
        row = scraper._parse_poi_basic_info({'name': '合成景点', 'coordInfo': {'gDLat': 23.1, 'gDLon': 113.3}})
        self.assertEqual((row['latitude'], row['longitude']), (23.1, 113.3))

    def test_comment_final_page_retained(self):
        with patch('Ctrip_Spider.sight_comments.os.makedirs'):
            spider = CtripCommentSpider(logger=Mock())
        for count, expected in [(0, 0), (1, 1), (10, 1), (11, 2), (21, 3)]:
            spider._make_request = Mock(return_value={'result': {'totalCount': count}})
            self.assertEqual(spider._get_total_pages('synthetic-id'), expected)

    def test_detail_timeout(self):
        with patch('Ctrip_Spider.sight_detail.post', return_value=Mock(status_code=403)) as request:
            result = AttractionDetailFetcher(logger=Mock()).get_detail(1)
        self.assertFalse(result['success'])
        self.assertEqual(request.call_args.kwargs['timeout'], 15)

    def test_id_search_timeout(self):
        response = Mock()
        response.json.return_value = {'data': []}
        with patch('Ctrip_Spider.sight_id.requests.post', return_value=response) as request:
            self.assertIsNone(SightId(logger=Mock()).search_sight_id('合成测试'))
        self.assertEqual(request.call_args.kwargs['timeout'], 15)
