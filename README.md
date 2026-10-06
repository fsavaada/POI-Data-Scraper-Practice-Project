# LifeLens：携程与大众点评数据采集

本仓库包含可运行的采集代码、已采集的结果数据和离线回归测试。当前实现为携程景点采集、携程餐馆搜索适配、大众点评全国必吃榜餐馆采集；不包含酒店采集、情感分析或可视化模型。

## 当前结果

| 数据 | 数量 | 说明 |
| --- | ---: | --- |
| 携程全国景点 | 11900条 | 34个省级地区，每地区350条，含地点字段 |
| 大众点评全国必吃榜 | 2571家 | 34个省级地区、218个榜单城市，每城最多20家 |
| 携程早期景点样本 | 676条 | 历史每地区最多20条版本，字段较少 |
| 大众点评广州早期样本 | 10家 | 历史试采结果，全国表中广州已扩展为20家 |

以上为已有快照，不是实时数据。大众点评全部取得街道地址，105家区县仍未核实；阿坝、桂林、眉山各有1家上榜店铺资料未返回。未列入当前榜单的城市和抓取失败分别记录，不补造餐馆。

## 目录与模块

```text
Ctrip_Spider/
  collect_province_top20.py  # 全国景点主入口，历史名称；默认每地区350条
  food_search.py            # 餐馆搜索清洗，不提供完整详情
  sight_id.py              # 原有景点ID搜索
  sight_list.py            # 原有景点列表
  sight_detail.py          # 原有景点详情
  sight_comments.py        # 原有景点评论
  log.py                   # 轮转日志
  request_optimizer.py     # 原有延迟/代理工具，主流程未调用代理
Dianping_Spider/
  run.py                   # 全国餐馆完整流水线
  collect_national.py       # 城市目录、榜单、地址、限速缓存
  retry_missing.py          # 缺资料上榜店铺的公开单店重试
  enrich_districts.py       # 县级城市入口同店铺ID核验
  finalize.py               # 离线合并、校验、CSV/JSON导出
Datasets/                   # 结果及精选参考元数据
tests/                      # 不联网的相关回归测试
scripts/                    # 仓库检查、发布包构建
docs/                       # 数据流和发布说明
```

## 环境与安装

Python 3.10及以上。从项目根目录执行：

```bash
python -m venv .venv
# Windows PowerShell：.\.venv\Scripts\Activate.ps1
# Linux/macOS：source .venv/bin/activate
python -m pip install -r requirements.txt
```

全国携程和大众点评采集器只使用标准库；Requests、BeautifulSoup用于原有携程模块。无需浏览器驱动、Codex运行时或Node.js。可选 `python -m pip install -e .` 安装命令行入口；保持可编辑安装，以便结果目录仍位于本项目。

## 携程采集

```bash
python -m Ctrip_Spider.collect_province_top20 --top 350 --output Datasets/ctrip_province_top350.csv
```

流程：目的地搜索 → 省级地区ID → 景点分页 → POI类型/关键词过滤 → 地区内ID与名称去重 → CSV。

- 输出：景点名称、省份、市区、详细地点、景点门票价格、评分。
- 缺价格标为“免费”是按原需求采用的规则，不保证景点实际上免票。
- 使用启发式过滤排除演出等类别，仍需按业务抽查。
- 扩充数量时依次使用多个排序模式，并非官方统一Top350排名。
- `市区`和`详细地点`来自卡片展示字段，可能是商圈，不保证细到行政区县或门牌。
- 原有模块用 `python -m Ctrip_Spider.sight_detail` 等方式运行，勿直接执行文件路径。

餐馆搜索适配器仅发现真实餐馆候选；搜索接口未提供的评分、人均、地址保留为空，不使用搜索相关度冒充用户评分。

## 大众点评采集

```bash
python -m Dianping_Spider --workers 3
```

完整流水线依次采集、缺资料重试、县级地区核验、最终导出。线程共用每秒最多3次请求的限速；允许1至6个线程，默认3个。

- 结果目录：`Datasets/dianping_national/`，不依赖启动时的工作目录。
- 字段：店铺名、具体地点、评分、人均消费、特色菜，另保留省市区、缺失状态和来源。
- 每城最多20家，按综合展示顺序，不代表官方名次；顺德归佛山。
- 仅跟进公开榜单及店铺/城市入口，不绕过登录或验证码。
- 网页仅存本地，Git和发布ZIP不包含原始页面。首次运行会重新采集页面。

分步执行与离线复核见 [模块与数据流](docs/ARCHITECTURE.md) 和 [大众点评数据说明](Datasets/dianping_national/README.md)。不要同时运行多个进程，限速锁是进程内的。

## 测试和检查

```bash
python -m unittest discover -s tests -v
python scripts/check_repository.py
```

测试使用标为合成的夹具，不联网、不生成伪造采集数据。平台接口可能变化，离线测试通过不等于实时接口始终可用。

## 打包和上传 Git

```bash
python scripts/build_release.py
```

生成 `dist/lifelens-crawlers-source-data.zip`，只含代码、相关测试、文档、配置、结果和参考元数据，不含网页缓存、环境依赖、日志、备份或`.git`。包内附文件SHA-256和结果行数。

当前未初始化Git、未创建远程仓库。上传操作见 [发布说明](docs/PUBLISHING.md)。忽略规则允许精选CSV/JSON提交，排除缓存及私密配置。

## 来源与发布注意

尊重平台条款、访问限制、隐私和数据使用范围，发布数据前核对授权。未擅自为原项目或第三方数据指定开源许可证，参考来源见 [第三方来源说明](THIRD_PARTY_NOTICES.md)。
