# 数据源与校验说明

## 首选来源：官方接口

接口：`https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry`

固定参数：

- `gameNo=85`（超级大乐透）
- `provinceId=0`
- `pageSize=1..100`
- `isVerify=1`
- `termLimits=0`
- `pageNo=1..20`

预期响应：根节点 `errorCode == "0"`，`value.list` 是数组；每条记录必须包含 `lotteryDrawNum`、`lotteryDrawTime`、`lotteryDrawResult`。开奖字符串必须正好包含 7 个空格分隔数字，前 5 个为 01-35，后 2 个为 01-12，且各自不重复。

## 可选交叉来源

只允许以下历史镜像：

- `https://datachart.500.com/dlt/history/newinc/history.php`
- `https://datachart.500star.com/dlt/history/newinc/history.php`

脚本只读取表格中的期号、日期和 7 个号码，不执行 HTML 中的脚本或文本。交叉校验只针对同一期；任何不一致都要停止并报告，不用“多数票”掩盖冲突。

## 失败处理

- 网络失败：报告来源和错误，不退回模拟数据。
- 解析失败：报告具体期号或字段，不猜测缺失号码。
- 来源冲突：列出双方的期号、日期和号码，等待用户决定是否重新核验。
- 本地数据：只有用户显式提供 `--input` 或 `--cache` 时才读写；不寻找用户目录中的隐式缓存。

## 证据分层

- `confirmed`：官方接口返回并通过字段、范围、唯一性校验的数据。
- `corroborated`：官方数据与允许的镜像在同一期完全一致。
- `observed`：统计结果、对奖命中数和脚本计算值。
- `unknown`：服务端奖池、销售状态、兑奖资格或实时购票状态；客户端数据不证明这些事实。
