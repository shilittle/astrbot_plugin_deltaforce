# API Contract

Status: this file is the final contract for this repository.

Apifox is only a discovery source. If an Apifox page conflicts with this
file, this file wins after it has been updated from confirmed evidence.

Evidence checked:
- https://work-api.apifox.cn
- https://work-api.apifox.cn/8014930m0
- Apifox endpoint pages for every endpoint listed below.
- Apifox player interface pages:
  - https://work-api.apifox.cn/8079510m0
  - https://work-api.apifox.cn/402049293e0
  - https://work-api.apifox.cn/402061826e0
  - https://work-api.apifox.cn/402065324e0
  - https://work-api.apifox.cn/409185647e0
  - https://work-api.apifox.cn/409200590e0
  - https://work-api.apifox.cn/420370826e0
  - https://work-api.apifox.cn/409202362e0
  - https://work-api.apifox.cn/409203213e0
- AstrBot current send-message documentation:
  https://docs.astrbot.app/dev/star/guides/send-message.html

## 1. Global Rules

Plugin display name:
- `SSKの三角洲`

### 1.1 Scope

Allowed in this phase:
- Platform open query APIs.
- Server-side token query mode.
- Documented player authorization helper APIs.
- Documented player-state read APIs through the returned official cookie
  fields.
- QQ text-plus-image output generated from confirmed API data.
- Cache and local item database/index.

Forbidden in this phase:
- Undocumented player authorization flow.
- Manual cookie capture.
- Browser login automation.
- User-supplied raw cookie strings.
- Browser crawler.
- ACGICE page screenshot extraction.
- Entertainment features.
- TTS.
- Login-state management.
- Push jobs.

### 1.2 No-Guess Rule

These items must stay as `TODO` unless confirmed by this contract:
- Request parameter names.
- Response field names.
- JSON wrapper layers.
- Headers.
- Cookies.
- Base URL.
- Auth model and auth parameter location.
- Exact refresh/update cadence.
- Business sorting semantics.

### 1.3 Output Boundary

- Successful command output is sent as one QQ message containing concise text
  plus a locally rendered image.
- The text portion should summarize what was queried and how to read the image,
  without duplicating the full payload.
- The rendered image must include:
  - Page header text: `sskの三角洲`.
  - A title.
  - For every API item that has confirmed `pic` and name fields, render the
    item image from `pic` together with the item name.
- Rendered images may be cached locally for reuse.
- QQ-facing errors must be one Chinese line.
- Do not return raw JSON.
- Do not return full upstream payloads.
- Do not return token values.
- Do not return player authorization cookie values.
- Do not return raw callback URLs after binding.
- Do not send debug logs to QQ messages.

### 1.4 Image Cache Boundary

- Image rendering cache is a local optimization only; it must not change API
  cache validity.
- Image cache keys must be derived from rendered content, not from token values.
- Public item image URLs from confirmed API `pic` fields may be cached locally.
- Rendering must prefer the local item database image record for matching
  items, then fall back to confirmed `pic` from the command response.
- If an item image cannot be fetched, render a local placeholder instead of
  failing the whole command.

## 2. Base URL and Auth

### 2.1 Base URL

Confirmed base URL:
- `https://orzice.com/workApi`

Confirmed endpoint prefix:
- `/v1/sjz_api/...`

### 2.2 Auth Injection

Confirmed auth model:
- Query parameter: `token`
- Type: string
- Description in Apifox: `密钥`
- Required by all open query endpoints in this contract.

Confirmed not used by these open query endpoints:
- Headers.
- Cookies.

Implementation rule:
- Read token only from local server-side configuration or local secret file.
- Never expose token in QQ output, docs examples, exceptions, or logs.

### 2.3 Player Authorization Helper APIs

These endpoints are on the same open-platform base URL and still use the
server-side open-platform `token` query parameter.

#### 2.3.1 Get authorization URL

Endpoint:
- Method: `GET`
- Path: `/v1/sjz_api_ex/z_GetOauthUrl`
- Full URL: `https://orzice.com/workApi/v1/sjz_api_ex/z_GetOauthUrl`

Query parameters:
- `typs`: string. `0` means QQ account, `1` means WeChat account.
- `token`: open-platform server token.

Response contract:
- Wrapper: object with `code`, `message`, `msg`, `data`.
- `data`: authorization URL string.

Implementation rule:
- Do not cache longer than 60 seconds.
- Send the returned authorization URL only as the user-facing next step.

#### 2.3.2 Verify callback URL and get player authorization

Endpoint:
- Method: `GET`
- Path: `/v1/sjz_api_ex/z_OauthUrl`
- Full URL: `https://orzice.com/workApi/v1/sjz_api_ex/z_OauthUrl`

Query parameters:
- `url`: the callback URL copied after player login. The HTTP client may pass
  the raw URL as a query value and rely on normal query encoding.
- `token`: open-platform server token.

Response contract:
- Wrapper: object with `code`, `message`, `msg`, `data`.
- `data.expire`: authorization expiry timestamp.
- `data.pt`: account platform, such as `qq`.
- `data.quid`: refresh identifier. Documented validity is about seven days.
- `data.token`: object containing official cookie fields. Confirmed field
  names: `access_token`, `acctype`, `appid`, `openid`, `vopenid`.

Implementation rule:
- Do not cache this request.
- Store only per sender in a local secret file.
- Do not print, log, render, or return `data.token` values.
- Do not include raw callback URLs in cache keys or persisted files.

#### 2.3.3 Refresh latest player authorization by `quid`

Endpoint:
- Method: `GET`
- Path: `/v1/sjz_api_ex/z_GetOauthQuid`
- Full URL: `https://orzice.com/workApi/v1/sjz_api_ex/z_GetOauthQuid`

Query parameters:
- `quid`: login user identifier from the verify response.
- `token`: open-platform server token.

Response contract:
- Wrapper: object with `code`, `message`, `msg`, `data`.
- `data.token`: object containing official cookie fields. Confirmed field
  names: `access_token`, `acctype`, `appid`, `openid`, `vopenid`.

Implementation rule:
- Do not cache this request.
- Preserve previously stored `quid`, `pt`, and `expire` if the refresh response
  omits them.

### 2.4 Player Official Read APIs

Confirmed common request model:
- Method: `POST`
- URL: `https://comm.ams.game.qq.com/ide/`
- Request body: none.
- Parameters are sent as query parameters.
- Cookie fields are taken from the `data.token` object returned by the
  documented authorization helper APIs.

Confirmed shared output boundary:
- Do not return raw JSON.
- Do not expose official cookie values.
- Render only summarized player statistics and battle rows.
- Cache player reads with a short TTL keyed by sender and `quid`, never by
  cookie value.

#### 2.4.1 Get player role information

Endpoint:
- Method: `POST`
- URL: `https://comm.ams.game.qq.com/ide/`

Query parameters:
- `iChartId=317814`
- `iSubChartId=317814`
- `sIdeToken=QIRBwm`
- `seasonid=0`

Confirmed response fields:
- Top-level success fields: `ret`, `iRet`, `sMsg`.
- `jData.userData.picurl`: URL-encoded avatar URL.
- `jData.userData.charac_name`: URL-encoded character name.
- `jData.careerData.rankpoint`:烽火段位分。
- `jData.careerData.tdmrankpoint`:全面战场段位分。
- `jData.careerData.soltotalfght`:烽火对局数。
- `jData.careerData.solttotalescape`:烽火撤离数。
- `jData.careerData.solduration`:烽火时长。
- `jData.careerData.soltotalkill`:烽火击杀数。
- `jData.careerData.solescaperatio`:烽火撤离率。
- `jData.careerData.tdmduration`:全面战场时长。
- `jData.careerData.tdmsuccessratio`:全面战场胜率。
- `jData.careerData.tdmtotalfight`:全面战场对局数。
- `jData.careerData.totalwin`:全面战场胜场数。
- `jData.careerData.tdmtotalkill`:全面战场击杀数。

#### 2.4.2 Get player detailed data

Endpoint:
- Method: `POST`
- URL: `https://comm.ams.game.qq.com/ide/`

Query parameters:
- `iChartId=316969`
- `iSubChartId=316969`
- `sIdeToken=NoOapI`
- `method=dfm/center.person.resource`
- `source=2`
- `param`: JSON string. Confirmed fields:
  - `resourceType`: `sol` for烽火, `mp` for全面战场.
  - `seasonid`: array of season IDs.
  - `isAllSeason`: boolean.

Confirmed response fields:
- `jData.data.code=0`
- `jData.data.data.solDetail` or matching detail object for the requested
  resource type.
- Detail fields include `redTotalMoney`, `redTotalCount`, and `mapList`.
- `mapList[]` includes `mapID`, `totalCount`, and `leaveCount`.

#### 2.4.3 Get player Havoc coin count

Endpoint:
- Method: `POST`
- URL: `https://comm.ams.game.qq.com/ide/`

Query parameters:
- `iChartId=319386`
- `iSubChartId=319386`
- `sIdeToken=zMemOt`
- `item=17020000010`
- `type=3`

Confirmed response fields:
- `jData.data[0].totalMoney`: Havoc coin amount.

#### 2.4.4 Battle record V2

Endpoint:
- Method: `POST`
- URL: `https://comm.ams.game.qq.com/ide/`

Query parameters:
- `iChartId=450526`
- `iSubChartId=450526`
- `sIdeToken=PHq59Y`
- `type`: `4` for烽火, `5` for全面战场.
- `page`: page number.

Confirmed response fields:
- `jData.data[]`
- Battle row fields include `MapId`, `EscapeFailReason`, `FinalPrice`,
  `dtEventTime`, `ArmedForceId`, `DurationS`, `KillCount`,
  `KillPlayerAICount`, `KillAICount`, `RoomId`, and `flowCalGainedPrice`.
- `flowCalGainedPrice` is documented as battle net profit.

#### 2.4.5 Battle room detail V2

Endpoint:
- Method: `POST`
- URL: `https://comm.ams.game.qq.com/ide/`

Query parameters:
- `iChartId=450471`
- `iSubChartId=450471`
- `sIdeToken=ylP3eG`
- `type=2`
- `roomId`: room ID from battle record V2.

Confirmed response fields:
- `jData.data[]`
- Room row fields include `ArmedForceId`, `EscapeFailReason`, `dtEventTime`,
  `MapId`, `FinalPrice`, `vopenid`, `TeamId`, `DurationS`, `KillCount`,
  `KillAICount`, `KillPlayerAICount`, `Rescue`, and `nickName`.

## 3. Local Item Data Bootstrap

The plugin must initialize this layer before serving business commands.

### 3.1 `item_info_all`

Endpoint:
- Method: `GET`
- Path: `/v1/sjz_api/item_info_all`
- Full URL: `https://orzice.com/workApi/v1/sjz_api/item_info_all`

Query parameters:
- `token` string, required.

Response wrapper:
- `code` integer
- `msg` string
- `count` integer
- `data` array

Confirmed `data[]` fields:
- `desc` string
- `detail` string
- `grade` integer
- `id` integer
- `is_get` integer
- `length` integer
- `objectID` integer
- `objectName` string
- `oid` integer
- `pic` string
- `primaryClass` string
- `secondClass` string
- `secondClassCN` string
- `width` integer

Field notes confirmed by Apifox:
- `is_get`: whether the item is tradable, `0` means not tradable, `1` means tradable.
- `oid`: third-generation Data Emperor ID, normally used by other APIs. If the item is not tradable, it can be `0`.
- `id`: second-generation ID, currently kept only for mapping.
- `objectID`: official Delta Force mini-program data ID, used only for mapping.

Resource note:
- Normal request costs 1 resource unit for 1000+ items.

Local storage requirements:
- Keep at least `id`, `oid`, `objectID`, `objectName`, `pic`, `grade`,
  `primaryClass`, `secondClass`, `secondClassCN`, `is_get`.
- Build keyword lookup from confirmed name/class fields.

### 3.2 `item_price_all`

Endpoint:
- Method: `GET`
- Path: `/v1/sjz_api/item_price_all`
- Full URL: `https://orzice.com/workApi/v1/sjz_api/item_price_all`

Query parameters:
- `isZb` integer, required. Confirmed description: `0为普通  1为战备数据 【暂不开放】`.
- `token` string, required.

Allowed phase-1 usage:
- Use `isZb=0`.
- Do not depend on `isZb=1`; it is marked not open.

Response wrapper:
- `code` integer
- `msg` string
- `count` integer
- `data` array

Confirmed `data[]` fields:
- `bl` number or integer
- `day_30_bl` number or integer
- `day_30_price` integer
- `day_3_bl` number or integer
- `day_3_price` integer
- `day_7_bl` number or integer
- `day_7_price` integer
- `id` integer
- `is_get_time` integer
- `price` integer
- `price_start` integer
- `tid` integer

Field notes confirmed by Apifox:
- `tid`: second-generation data ID, same as `item_info_all.id`.
- `id`: third-generation data ID, normally used by other APIs.
- `price`: price.
- `is_get_time`: price update timestamp.
- `price_start`: first price today.
- `bl`: daily change ratio.
- `day_3_price`, `day_3_bl`: 3-day price and change ratio.
- `day_7_price`, `day_7_bl`: 7-day price and change ratio.
- `day_30_price`, `day_30_bl`: 30-day price and change ratio.
- `zb_price`: mentioned in prose as battle-prep value, updated manually every Tuesday before 10:00, but not present in the confirmed `isZb=0` schema.

Update notes confirmed by Apifox:
- High-frequency items: 1 minute.
- Medium-frequency items: 5 minutes.
- Low-frequency items: 10 minutes.
- Battle-prep data: marked not open and manually updated every Tuesday before 10:00.

Local merge rules:
- Join `item_price_all.tid` to `item_info_all.id`.
- Use `item_price_all.id` as the confirmed third-generation market ID for APIs that require this ID.
- Search and price lookup must prefer the local merged index.

### 3.3 `item_list_pro_key`

Endpoint:
- Method: `GET`
- Path: `/v1/sjz_api/item_list_pro_key`
- Full URL: `https://orzice.com/workApi/v1/sjz_api/item_list_pro_key`

Query parameters:
- `token` string, required by the repository auth rule.

Response wrapper:
- `code` integer
- `msg` string
- `count` integer
- `data` array

Confirmed `data[]` fields:
- `children` array
- `extra` integer
- `label` string
- `value` integer

Confirmed `children[]` fields:
- `extra` integer
- `label` string
- `value` integer

Field notes confirmed by Apifox:
- This endpoint is used to get associated filter properties for
  `item_list_pro`.
- It does not consume resource count.
- The documentation recommends requesting it once.

Local storage requirements:
- Fetch lazily when the item overview feature is queried.
- Cache for a long period and record local update time.

### 3.4 `item_list_pro`

Endpoint:
- Method: `GET`
- Path: `/v1/sjz_api/item_list_pro`
- Full URL: `https://orzice.com/workApi/v1/sjz_api/item_list_pro`

Query parameters:
- `key1` string, optional in implementation. Confirmed prose example:
  `key1=钥匙`.
- `key2` string, optional in implementation. Confirmed prose example:
  `key2=零号大坝`.
- `sort` string, optional in implementation. Confirmed values:
  - `1` and `1-1`: 今日涨跌从小到大
  - `1-2`: 今日涨跌从大到小
  - `2-1`: 金额从小到大
  - `2-2`: 金额从大到小
  - `3-1`: 价值从小到大
  - `3-2`: 价值从大到小
  - `5-1`, `5-2`: 3天涨跌排序, exact direction TODO
  - `7-1`, `7-2`: 7天涨跌排序, exact direction TODO
  - `30-1`, `30-2`: 30天涨跌排序, exact direction TODO
- `grade` integer, optional in implementation. Confirmed range: `0~6`.
- `token` string, required by the repository auth rule.

Confirmed implementation note:
- `key1` and `key2` are sent as filter labels such as `钥匙` and `零号大坝`,
  not numeric `value` ids.

Response wrapper:
- `code` integer
- `msg` string
- `count` integer
- `data` array

Confirmed `data[]` fields:
- `ShopSellType` array
- `bl` number or integer
- `day_30_bl` number or integer
- `day_30_price` integer
- `day_7_bl` number or integer
- `day_7_price` integer
- `grade` integer
- `id` integer
- `isGet` string
- `length` integer
- `name` string
- `oid` integer
- `pic` string
- `price` integer
- `width` integer

Field notes confirmed by Apifox:
- `oid`: third-generation Data Emperor ID used by other APIs; `0` if not tradable.
- `id`: second-generation ID, kept for mapping.
- `ShopSellType`: recommended sell method, with fee/listing/quick-sell effects
  already considered. The second element is a recommendation grade. The third
  element is the instant-sale price one market bar forward.

Update and resource notes confirmed by Apifox:
- High-frequency items: 1 minute.
- Medium-frequency items: 5 minutes.
- Low-frequency items: 10 minutes.
- Request costs 1 resource unit.

Local storage requirements:
- Do not bulk load this endpoint at startup.
- Fetch only the requested filter option when the user queries item overview.
- Cache each requested option and record local update time.
- For low-cost operation, default item overview cache should be conservative
  and no shorter than 20 minutes unless explicitly configured lower in local
  development.

TODO:
- Exact request parameter required/optional status.
- Exact direction for `5-*`, `7-*`, and `30-*` sort variants. The Apifox prose
  repeats "从大到小" for both variants.

### 3.5 Local Item Database Rules

- Build the base table and index at plugin startup.
- Persist the merged item database locally, including confirmed item image URL
  fields.
- Store locally fetched item image paths in the same database so later renders
  can load item images through the database.
- Refresh prices through the cache layer.
- Prefer local data for item search, name suggestions, and price lookup.
- Do not treat upstream APIs as a per-message database scan.

## 4. Product Command Contract

### 4.1 每日密码

Commands:
- `每日密码`
- `今日密码`
- `地图密码`

Endpoint:
- Method: `GET`
- Path: `/v1/sjz_api/map_pwd`
- Full URL: `https://orzice.com/workApi/v1/sjz_api/map_pwd`

Query parameters:
- `token` string, required.

Response wrapper:
- `code` integer
- `message` string
- `msg` string
- `data` object

Confirmed `data` fields:
- `a`: array of strings, `[password, date]`, map: 零号大坝
- `b`: array of strings, `[password, date]`, map: 长弓溪谷
- `c`: array of strings, `[password, date]`, map: 巴克什
- `d`: array of strings, `[password, date]`, map: 航天基地
- `e`: array of strings, `[password, date]`, map: 潮汐监狱

Output target:
- 零号大坝：密码（日期）
- 长弓溪谷：密码（日期）
- 巴克什：密码（日期）
- 航天基地：密码（日期）
- 潮汐监狱：密码（日期）

Special rule:
- If the password value is `-`, output `未更新`.

Cache strategy:
- Cache until the next daily refresh window.

Confirmed update cadence:
- Updates every day at 00:05, then data is unchanged for the day.

### 4.2 卡战备

Command:
- `卡战备 <n> [均衡|枪优先|胸挂优先]`

Endpoint:
- Method: `GET`
- Path: `/v1/sjz_api/jzv3_zb_plus`
- Full URL: `https://orzice.com/workApi/v1/sjz_api/jzv3_zb_plus`

Query parameters:
- `lv` integer, optional in schema, used by this command.
- `token` string, required.

Command mapping:
- `0`: output help.
- `1`: `lv=0`, `11W 机密配置`
- `2`: `lv=1`, `18W 机密配置`
- `3`: `lv=2`, `55W 绝密巴克什`
- `4`: `lv=3`, `60W 绝密航天`
- `5`: `lv=4`, `24W 适应监狱`
- `6`: `lv=5`, `78W 绝密监狱`

Confirmed Apifox `lv` prose:
- `0`: `11W` 机密配置
- `1`: `18W` 机密配置
- `2`: `55W` 绝密巴克什
- `3`: `60W` 绝密航天
- `4`: `24W` 适应监狱, only calculated during Friday 12:00 to Monday 00:00.
- `5`: `78W` 绝密监狱

Response wrapper:
- `code` integer
- `message` string
- `msg` string
- `data` object

Confirmed `data` fields:
- `data.data[]`: result list.
- `data.time`: string.

Confirmed result fields in `data.data[]`:
- `cz` integer
- `data` array
- `jz` integer
- `name` string
- `price` integer

Confirmed item fields in each result `data[]`:
- `bl` integer
- `exchange` string
- `exchange_plus` object or null
- `grade` integer
- `id` integer
- `jiazhang` integer
- `jz` integer
- `name` string
- `pic` string
- `price` integer
- `type` string

Confirmed `exchange_plus` fields:
- `perCount` integer
- `purchaseCount` string
- `purchaseDuration` string

Output requirements:
- First output the selected level name.
- A single upstream request returns up to three result rows. Render all three
  rows into local cached images.
- Reply with only the image matching the selected preference.
- Do not truncate the selected result row item list.
- Render result `cz` as `节省`, using positive green values when cost is lower
  than battle value.
- Render each item with:
  - `战备值`, calculated from `price - jz` for the current API shape.
  - A `兑换` cost column when `exchange` is non-empty. Include `价格`, `节省`,
    `限购<purchaseCount>`, and `刷新<purchaseDuration>` when available.
  - A `购买` cost column when `exchange` is empty. Include `价格` and `节省`.
- Do not render item `type`; item type is only used as upstream context.

Cache strategy:
- 120 seconds.

Confirmed update cadence:
- Every 5 minutes, at minute 2, 7, 12, 17, and so on.

TODO:
- Business sorting semantics beyond preserving API order.

### 4.3 交易行价格

Commands:
- `交易行价格 <keyword>`
- `价格 <keyword>`
- `物价 <keyword>`
- `价格曲线 <keyword>`
- `交易行价格 总览`
- `交易行价格 总览 <key1> [key2] [sort] [grade]`
- `交易行总览`
- `物品总览`

Endpoint:
- Method: `GET`
- Path: `/v1/sjz_api/minute`
- Full URL: `https://orzice.com/workApi/v1/sjz_api/minute`

Query parameters:
- `id` integer, required. Confirmed description: Data Emperor internal third-generation ID.
- `isZb` integer, optional. Confirmed description: default `0`; `1` includes battle-prep data.
- `token` string, required.

Command parameter rules:
- `0`: output help.
- Other content is item keyword.
- Resolve keyword through the local item index, then call `/minute` with the confirmed third-generation ID.

Response wrapper:
- `code` integer
- `message` string
- `msg` string
- `data` object

Confirmed `data` fields:
- `a`: array of strings, time labels.
- `b`: array of integers, prices.
- `zb`: array of integers, battle-prep values when available.

Output requirements:
- Item name.
- Item image from local base index `pic` if available.
- Latest price.
- Latest time label.
- Battle-prep value if available.
- Optional 24h trend summary derived from confirmed `a` and `b`.
- In image output, do not invent chart fields beyond confirmed `a`, `b`, and
  `zb`.

Cache strategy:
- Short cache only.

Confirmed update cadence:
- Up to 1440 rows for 24 hours.
- Minute or 10-minute cadence depending on item class.

TODO:
- Exact meaning of `zb` when the array is absent, empty, or shorter than price data.

### 4.3.1 交易行物品总览

Command:
- `交易行价格 总览`
- `交易行价格 总览 <key1> [key2] [sort] [grade]`
- `交易行总览`
- `物品总览`

Endpoints:
- `GET /v1/sjz_api/item_list_pro_key`
- `GET /v1/sjz_api/item_list_pro`

Command parameter rules:
- `交易行价格 总览`: output available top-level filter options and local filter
  update time.
- `交易行价格 总览 <key1> [key2] [sort] [grade]`: query only the requested
  filter option.
- `key1` and `key2` are filter labels from `item_list_pro_key`.
- Default `key2`: `全部` when the selected filter contains that child.
- Default `sort`: `2-2`.
- `grade` must be `0..6` when provided.

Output requirements:
- Show item overview title.
- Show the requested filter and local update time.
- For every displayed item, render `pic` plus `name`.
- Include at least confirmed `grade`, `price`, `bl`, `day_7_price`,
  `day_30_price`, and `ShopSellType` when present.

Cache strategy:
- Filter options: long cache, because the API says it should normally be
  requested once.
- Item overview query results: 20 minutes by default for low-cost operation.
- Do not refresh any overview option unless that exact option is queried or its
  local cache has expired.

### 4.4 特勤处制造

Command:
- `特勤处制造 <t> [l] [小时收益|总收益]`
- `特勤制造 <t> [l] [小时收益|总收益]` as compatibility alias.

Endpoint:
- Method: `GET`
- Path: `/v1/sjz_api/manufacturePro`
- Full URL: `https://orzice.com/workApi/v1/sjz_api/manufacturePro`

Query parameters:
- `t` integer, optional in schema, used by this command.
- `l` integer, optional in schema, used by this command.
- `token` string, required.

Command help:
- `特勤处制造 0`: output parameter help.

Parameter mapping:
- `t=1`: 技术中心
- `t=2`: 工作台
- `t=3`: 制药台
- `t=4`: 防具台
- `l=1`: 等级1
- `l=2`: 等级2
- `l=3`: 等级3
- Default `l`: `3`
- Sort option:
  - `小时收益`: local sort by confirmed field `price_hour` descending.
  - `总收益`: local sort by confirmed field `price` descending.
- Default sort option: `小时收益`.
- The Apifox page confirms only `t` and `l` request parameters. Do not send an
  upstream sort parameter.

Response wrapper:
- `code` integer
- `message` string
- `msg` string
- `data` array

Confirmed `data[]` fields:
- `grade` integer
- `id` integer
- `isGet` integer
- `is_pay` integer
- `name` string
- `objectID` integer
- `oid` integer
- `period` number or integer
- `pic` string
- `price` integer
- `priceMax` integer
- `price_hour` integer
- `primaryClass` string
- `secondClass` string
- `secondClassCN` string
- `sxf` integer
- `unlockLevel` integer

Confirmed field notes:
- `unlockLevel`: unlock level.
- `period`: minimum manufacture duration.
- `priceMax`: price before fees.
- `sxf`: fee, including fee and listing fee.
- `price`: real received price after fees.
- `price_hour`: hourly income after fees.

Output requirements:
- Sort by selected local sort field.
- Show at least:
  - Name.
  - Hourly income.
  - Real received price.
  - Fee.
  - Manufacture duration.
  - Unlock level.

Cache strategy:
- 10 minutes.

Confirmed update cadence:
- Every 10 minutes.

### 4.5 钥匙卡分析

Command:
- `钥匙卡分析 <n>`

Command mapping:
- `0`: output help.
- `1`: 今日钥匙卡低价预测.
- `2`: 明日钥匙卡低价预测.

Endpoints:
- `n=1`: `GET /v1/sjz_api/keys_day`
- `n=2`: `GET /v1/sjz_api/keys_day_yc`

Full URLs:
- `https://orzice.com/workApi/v1/sjz_api/keys_day`
- `https://orzice.com/workApi/v1/sjz_api/keys_day_yc`

Query parameters:
- `mid` integer, required. Confirmed map data: `1` 大坝, `2` 航天, `3` 长弓, `4` 巴克什, `5` 监狱.
- `token` string, required.

Command-level query rule:
- The command has no map argument in phase 1. To output by map, request documented `mid` values `1..5` and group results by map.

`keys_day` response wrapper:
- `code` integer
- `message` string
- `msg` string
- `data` array

Confirmed `keys_day data[]` fields:
- `data` array
- `hour` integer

Confirmed `keys_day data[].data[]` fields:
- `grade` integer
- `id` integer
- `mid` integer
- `name` string
- `oid` integer
- `pic` string
- `price` integer

`keys_day_yc` confirmed wrapper:
- `code` integer
- `message` string
- `msg` string
- `data` array

Output requirements:
- Group by map.
- Show a small number of card entries per map.
- Include at least:
  - `name`
  - `grade`
  - `price`

Cache strategy:
- `keys_day`: cache until next daily refresh.
- `keys_day_yc`: conservative cache.

Confirmed update cadence:
- `keys_day`: updates at 00:00; data remains unchanged afterward.
- `keys_day_yc`: service starts after 15:00; after 23:00 data no longer changes.

TODO:
- Non-empty `keys_day_yc` item schema. The schema page only confirms that `data` is an array, and the visible example is empty.
- Business sorting semantics beyond preserving API order.

### 4.6 子弹分析

Command:
- `子弹分析 <n>`

Command mapping:
- `0`: output help.
- `1`: 子弹自选包收益.
- `2`: 今日倒子弹低价预测.
- `3`: 昨日倒子弹最高收益.

Endpoints:
- `n=1`: `GET /v1/sjz_api/ammo_pack`
- `n=2`: `GET /v1/sjz_api/ammo_day`
- `n=3`: `GET /v1/sjz_api/ammo_zr_yc`

Full URLs:
- `https://orzice.com/workApi/v1/sjz_api/ammo_pack`
- `https://orzice.com/workApi/v1/sjz_api/ammo_day`
- `https://orzice.com/workApi/v1/sjz_api/ammo_zr_yc`

Query parameters:
- `grade` integer, required. Confirmed description: quality grade `0~6`.
- `token` string, required.

Command-level query rule:
- The command has no grade argument in phase 1. Use documented `grade` values `0..6` and aggregate non-empty results.

`ammo_pack` response wrapper:
- `code` integer
- `message` string
- `msg` string
- `data` object

Confirmed `ammo_pack data` groups:
- `3级子弹自选包`
- `4级子弹自选包`
- `5级子弹自选包`
- `通行证基础子弹自选包`
- `通行证高级子弹自选包`

Confirmed `ammo_pack` item fields:
- `bl` number or integer
- `grade` integer
- `id` integer
- `name` string
- `num` integer
- `pic` string
- `price` integer
- `sy_price` integer

`ammo_day` response wrapper:
- `code` integer
- `message` string
- `msg` string
- `data` array

Confirmed `ammo_day data[]` fields:
- `data` array
- `hour` integer

Confirmed `ammo_day data[].data[]` fields:
- `grade` integer
- `id` integer
- `name` string
- `oid` integer
- `pic` string
- `price` integer

`ammo_zr_yc` confirmed response:
- Apifox example is `{}`.
- Structured schema is empty.

Output requirements:
- `n=1`: output top bullets grouped by pack name.
- `n=2`: output bullet entries from confirmed `ammo_day` fields.
- `n=3`: handle empty object/list safely; only output fields if the upstream response contains a confirmed compatible structure.
- Include at least confirmed `name`, `grade`, and `price` when those fields exist.

Cache strategy:
- Conservative cache for all `ammo_*` endpoints.

TODO:
- Exact update frequency for all `ammo_*` endpoints. Pages contain an update-frequency heading but no confirmed cadence.
- `ammo_zr_yc` non-empty response schema and item fields.
- Business sorting semantics beyond preserving API order.

## 5. Error Contract

Allowed QQ-facing one-line errors:
- `查询失败：上游接口暂时不可用`
- `参数错误：请使用“卡战备 0”查看帮助`
- `接口未完成：返回字段尚未在文档中确认`
- `配置错误：请先配置开放平台密钥`

Forbidden in QQ output:
- Raw JSON.
- Traceback.
- Token.
- Full payload dump.
- Debug logs.

## 6. Implementation Freeze Points

Do not implement behavior from any item below before this contract is updated:

1. Unconfirmed HTTP parameter names.
2. Unconfirmed response field names.
3. Unconfirmed auth header formats.
4. Unconfirmed cookies.
5. Unconfirmed base URL.
6. Any player-auth behavior not covered by section 2.3 and 2.4.
- Preference default: `均衡`.
- Preference mapping:
  - `枪优先`: select API result whose `name` is `枪械优先`.
  - `均衡`: select API result whose `name` is `均衡套装`.
  - `胸挂优先`: select API result whose `name` is `胸挂优先`.
