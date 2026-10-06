# Git 发布与清理说明

## 本次整理

- 大众点评模块独立为 `Dianping_Spider`，携程仍位于 `Ctrip_Spider`。
- 临时探测、联网打印调试、旧样本生成及一次性前端检查脚本已移出有效目录。
- 相关离线回归测试统一到 `tests/`，CI不访问采集站点。
- 清理项在本地 `_cleanup_archive/20261006_repository_cleanup/` 可恢复，原README和忽略规则也有备份；此目录不提交、不打包。
- 全国原始网页保留本地，用于复核和断点续采，不提交、不打包。
- 未永久删除结果数据，未创建远程仓库，未提交或推送。

## 发布步骤

```bash
python -m unittest discover -s tests -v
python scripts/check_repository.py
python scripts/build_release.py
```

解压 `dist/lifelens-crawlers-source-data.zip` 到新目录。包内 `RELEASE_MANIFEST.json` 包含文件大小、SHA-256和CSV行数。核对代码、数据许可后执行：

```bash
git init -b main
git add .
git status --short
git diff --cached --stat
git commit -m "Prepare Ctrip and Dianping collectors with result snapshots"
git remote add origin <你的远程仓库URL>
git push -u origin main
```

也可直接在本工作区初始化Git，忽略规则已配置。暂存后仍应确认没有HTML、`node_modules`、环境文件、日志或备份。不要整体拖入带缓存的Datasets目录进行网页上传，推荐使用干净ZIP解压目录。

## 授权和复现

未擅自指定MIT等开源许可证。发布者应确认原代码许可及第三方数据的发布范围。最终数据可离线分析；重新采集依赖网络和仍可用的公开入口，可能与快照不同。
# 覆盖表恢复

本次从保留的 `coverage.json` 和行政区元数据恢复了缺失的城市覆盖 CSV，没有重新采集或修改餐馆、景点快照。`python scripts/restore_coverage.py` 仅用于本地保留这些源文件且覆盖表缺失的情况，拒绝覆盖已有 CSV。发布包不含原始 `coverage.json`，正常重新采集请运行大众点评完整流水线。

