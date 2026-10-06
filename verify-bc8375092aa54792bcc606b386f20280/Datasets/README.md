# 结果数据

精选结果及必要参考元数据参与Git提交。已有CSV保持原始字节不变，不因代码整理重写。

| 文件 | 行数 | 用途 |
| --- | ---: | --- |
| `ctrip_province_top350.csv` | 11900 | 主要携程结果，含省份、地区、地点、门票与评分 |
| `ctrip_province_top20.csv` | 676 | 早期景点样本，未使用现版本全部规则 |
| `dianping_guangzhou_10_shops.csv` | 10 | 历史广州试采样本，非官方名次榜 |
| `dianping_national/restaurants.csv` | 2571 | 全国餐馆明细与来源 |
| `dianping_national/city_coverage.csv` | 372 | 218个榜单城市及154个未列入目录的参考地区 |

`restaurants.json`保留原始地址、商圈和依据；`quality_report.json`为本批缺失统计；城市目录、区划参考、地区证据JSON为公开参考快照。

`manifest.json`由 `python scripts/build_release.py` 生成，记录精选文件的SHA-256、字节数和CSV行数。不能核实的历史采集日期不依据文件修改时间猜测。

原始HTML、`list_rows.json`和`coverage.json`是运行缓存，只存本地、不发布。
