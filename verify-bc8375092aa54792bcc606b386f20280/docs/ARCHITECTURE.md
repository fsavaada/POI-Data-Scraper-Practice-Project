# 模块、数据流与限制

## 携程

全国入口 `Ctrip_Spider.collect_province_top20` 使用标准库请求，获取目的地ID和景点分页。请求具备超时、有限重试及间隔。分页token来自公开响应，不是用户登录凭据。地区内按ID和名称去重，结合POI类型和关键词排除非景点，导出UTF-8 BOM CSV。

原有类模块使用Requests，详情文本另使用BeautifulSoup。日志为控制台和轮转文件。延迟/代理选择工具未接入全国主入口。餐馆搜索仅识别 `food` 项及官方链接，不补造详情字段。

整理修复了包内日志导入、列表经纬度颠倒、评论总页数向下取整及搜索/详情请求缺少超时。没有重采或改写已有结果CSV。

## 大众点评

```text
公开城市目录
  → 榜单HTML初始状态与shopIds原始顺序
  → 公开店铺定位链接补充第11至20家
  → 同店铺ID相册页的街道地址
  → 缺资料单店重试、县级城市入口ID归属证据
  → 行政区参考与明确地址前缀核验
  → 去重、每城上限、数值检查
  → CSV、JSON及质量报告
```

分步命令：

```bash
python -m Dianping_Spider.collect_national --phase lists --workers 3
python -m Dianping_Spider.collect_national --phase all --workers 3
python -m Dianping_Spider.retry_missing
python -m Dianping_Spider.enrich_districts
python -m Dianping_Spider.finalize
```

`lists`只取列表；`details`和`all`均取/复用列表后补地址。建议使用完整入口 `python -m Dianping_Spider`，避免遗漏后处理。

`finalize`不联网，但需本次的 `list_rows.json`、`coverage.json`、`boards/`和`shops/`缓存。发布包不含这些运行中间文件，从发布包首次运行需先采集，不能直接重建原网页。

缓存用于断点续采。刷新批次前将缓存和中间文件归档，避免混合新旧快照，不会自动删除旧结果。

## 限制

- 本批对应2026年，城市目录默认 `rankId=136`。年份变化时需核查接口和页面结构。
- `topshopids`取自页面支持的导航参数，不是承诺长期稳定的API。
- 参考区划可能滞后，重庆两江新区已单独补充；未知地区留空。
- 台湾仅包含当前目录中的台北入口，不代表全部城市。
- 特色菜是推荐标签，不是完整菜单；门票与人均是不同指标。
- 不使用账号轮换或验证码绕过，访问受限时保留失败状态。
