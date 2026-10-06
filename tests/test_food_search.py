"""Offline tests; fixtures are synthetic, not collected restaurant facts."""
import unittest
from Ctrip_Spider.food_search import normalize_restaurants


def store(store_id=1, name="示例餐厅(一店)", **extra):
    return {"type": "food", "id": store_id, "poiId": store_id + 100,
            "word": name, "url": f"https://you.ctrip.com/food/beijing1/{store_id}.html",
            "districtName": "北京美食林臻选", "productScore": 0.98, **extra}


class FoodSearchTests(unittest.TestCase):
    def test_normal_store(self):
        row = normalize_restaurants({"data": [store(lat=39.9, lon=116.4)]})[0]
        self.assertEqual(row["城市"], "北京")
        self.assertEqual((row["纬度"], row["经度"]), (39.9, 116.4))

    def test_mixed_types(self):
        self.assertEqual(len(normalize_restaurants({"data": [store(),
            {"type": "sight"}, {"type": "hotel"}, {"type": "huodong"}, None]})), 1)

    def test_duplicate_poi(self):
        self.assertEqual(len(normalize_restaurants({"data": [store(), store(2, poiId=101)]})), 1)

    def test_branches_preserved(self):
        self.assertEqual(len(normalize_restaurants({"data": [store(), store(2)]})), 2)

    def test_missing_fields_not_free_or_search_score(self):
        row = normalize_restaurants({"data": [store()]})[0]
        for field in ("用户评分", "人均消费", "详细地址", "商圈"):
            self.assertIsNone(row[field])

    def test_invalid_store(self):
        self.assertEqual(normalize_restaurants({"data": [store(word=""), store(url="https://example.com/food/1")]}), [])

    def test_invalid_response(self):
        for response in ({}, {"data": None}, {"data": {}}):
            with self.assertRaises(ValueError):
                normalize_restaurants(response)


if __name__ == "__main__":
    unittest.main()
