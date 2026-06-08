# SSKの三角洲

适用于 AstrBot 的三角洲行动数据查询插件。

作者：CodeX

本插件调用 Orzice 数据 API（https://orzice.com ）。使用前需要先在 Orzice 购买并开通数据 API，取得可用的 API Token；本插件不提供 Orzice 账号、Token 或数据接口授权。

## 功能

- 每日地图密码查询
- 交易行价格、价格曲线和物品总览查询
- 卡战备配置查询
- 特勤处制造收益查询
- 钥匙卡和子弹低价分析
- 玩家授权、玩家数据、玩家战绩和对局详情查询
- 文本加本地渲染图片的消息回复

## 安装

### 通过 AstrBot WebUI 安装

1. 打开 AstrBot WebUI。
2. 进入「插件」页面。
3. 点击右下角「+」按钮。
4. 选择通过 URL 安装，填写：

```text
https://github.com/shilittle/astrbot_plugin_deltaforce.git
```

5. 安装完成后重载插件，或重启 AstrBot。

AstrBot 会根据仓库中的 `requirements.txt` 安装依赖。如果依赖安装失败，请在 AstrBot WebUI 的依赖安装入口或当前运行环境中手动安装：

```bash
pip install -r requirements.txt
```

### 手动安装

进入 AstrBot 的插件目录后克隆仓库：

```bash
cd /path/to/AstrBot/data/plugins
git clone https://github.com/shilittle/astrbot_plugin_deltaforce.git
```

然后重启 AstrBot，或在 WebUI 插件页面重载插件。

## 配置

插件支持通过 AstrBot WebUI 配置项填写 API Token：

- `api_token`：Orzice 数据 API Token。推荐使用 WebUI 填写。
- `key_file`：本地 Token 文件路径，默认 `key.txt`。当 `api_token` 为空时才会读取该文件。

如果使用本地文件方式，可以在插件目录创建 `key.txt`：

```bash
cp key.txt.example key.txt
```

然后把 Orzice API Token 写入 `key.txt`，文件内容只保留一行 Token。

请不要把 `key.txt`、玩家授权缓存或任何 Token 发到群聊，也不要提交到公开仓库。

## 常用命令

| 命令 | 用途 |
| --- | --- |
| `三角洲帮助` | 查看插件帮助 |
| `每日密码` | 查询各地图每日密码 |
| `交易行价格 <物品名>` | 查询交易行价格摘要 |
| `交易行总览 [筛选项]` | 查询交易行物品总览 |
| `卡战备 <等级> [偏好]` | 查询卡战备配置 |
| `特勤处制造 <类型> [等级] [排序]` | 查询制造收益 |
| `钥匙卡分析 <数量>` | 查询钥匙卡低价分析 |
| `子弹分析 <数量>` | 查询子弹收益和低价分析 |
| `三角洲授权 <qq|微信>` | 获取玩家授权链接 |
| `三角洲绑定 <回调链接>` | 保存玩家授权回调 |
| `三角洲刷新授权` | 刷新玩家授权 |
| `玩家数据 [烽火|战场] [赛季ID]` | 查询已绑定玩家数据 |
| `玩家战绩 [烽火|全面] [页码]` | 查询已绑定玩家战绩 |
| `对局详情 <房间号>` | 查询对局详情 |

命令参数不确定时，可以先发送 `三角洲帮助`。

## 实现框架

- `main.py`：AstrBot Star 插件入口，注册所有聊天命令。
- `metadata.yaml`：AstrBot 插件元数据，供插件列表和插件市场识别。
- `_conf_schema.json`：AstrBot WebUI 配置项定义。
- `requirements.txt`：插件运行依赖。
- `deltaforce_openapi/`：Orzice API 客户端、缓存、物品索引、玩家授权、本地图片渲染和命令实现。

插件使用异步 HTTP 请求访问上游 API，并使用本地缓存减少重复请求。玩家授权数据和渲染图片默认保存在插件本地缓存目录中。
