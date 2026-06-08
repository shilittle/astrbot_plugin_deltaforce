from __future__ import annotations

from ..renderer import RenderDocument, RenderItem, RenderSection


def _cmd(name: str, desc: str) -> RenderItem:
    return RenderItem(name=name, fields=(("说明", desc),))


def render() -> RenderDocument:
    return RenderDocument(
        title="SSKの三角洲",
        summary="SSKの三角洲使用指南已生成，图片内按分组整理查询命令。",
        sections=(
            RenderSection(
                title="基础查询",
                items=(
                    _cmd("三角洲帮助", "查看本指南和所有开放查询入口"),
                    _cmd("每日密码 / 今日密码 / 地图密码", "查询每日地图密码"),
                    _cmd("卡战备 0", "查看卡战备档位和参数说明"),
                    _cmd("卡战备 1~6 [均衡|枪优先|胸挂优先]", "查询对应档位套装"),
                ),
            ),
            RenderSection(
                title="交易行",
                items=(
                    _cmd("交易行价格 <物品名>", "查询物品价格曲线摘要"),
                    _cmd("价格 / 物价 / 价格曲线 <物品名>", "价格查询的短命令别名"),
                    _cmd("交易行价格 总览", "查看物品总览筛选项"),
                    _cmd("交易行价格 总览 <一级分类> [二级分类] [排序] [等级]", "查询指定分类的交易行总览"),
                    _cmd("交易行总览 / 物品总览 <一级分类> [二级分类] [排序] [等级]", "总览查询的短命令入口"),
                    _cmd("示例：交易行价格 总览 钥匙 零号大坝 2-2 6", "按地图钥匙、排序和等级筛选"),
                ),
            ),
            RenderSection(
                title="收益分析",
                items=(
                    _cmd("特勤处制造 0", "查看制造参数"),
                    _cmd("特勤处制造 <t> [l] [小时收益|总收益]", "查询制造收益，t=1技术中心/2工作台/3制药台/4防具台，l默认3"),
                    _cmd("钥匙卡分析 0", "查看钥匙卡分析模式"),
                    _cmd("钥匙卡分析 1 / 2", "今日或明日钥匙卡低价预测"),
                    _cmd("子弹分析 0", "查看子弹分析模式"),
                    _cmd("子弹分析 1", "子弹自选包收益"),
                    _cmd("子弹分析 2 / 3", "今日低价预测或昨日最高收益"),
                ),
            ),
            RenderSection(
                title="玩家数据",
                items=(
                    _cmd("三角洲授权 qq / 微信", "获取玩家授权登录链接，建议私聊使用"),
                    _cmd("三角洲绑定 <回调链接>", "保存登录后的404/白屏回调链接"),
                    _cmd("三角洲刷新授权", "刷新已绑定玩家授权"),
                    _cmd("玩家数据 [烽火|战场] [赛季ID]", "查询角色、战绩统计和哈夫币"),
                    _cmd("玩家战绩 [烽火|全面] [页码]", "查询近期对局列表"),
                    _cmd("对局详情 <房间号>", "查询战绩中的单局详情"),
                ),
            ),
        ),
    )
