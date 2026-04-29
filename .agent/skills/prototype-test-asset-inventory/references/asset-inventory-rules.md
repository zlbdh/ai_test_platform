# Asset Inventory Rules

## 必盘点对象

- 技术入口页
- 平台壳页
- 模块列表页
- 详情/审核页
- 看板页
- 设置/配置页
- 可能承接弹窗的页面

## 重点标记

- `entry_page`
- `standalone_page`
- `embedded_candidate`
- `out_of_scope_asset`
- `missing_asset_risk`

## 常见误判

- 把登录页当作业务缺陷判定页，而用户只把它当技术入口。
- 把带某业务关键词的文件名直接当目标页面。
- 忽略详情页中的 Tab，导致嵌入式承接点漏记。
