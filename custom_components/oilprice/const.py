"""Constants for the OilPrice integration."""

DOMAIN = "oilprice"
PLATFORMS = ["sensor", "button"]

CONF_CITY = "city"
CONF_FINAL_QUERY_CODE = "final_query_code"
CONF_UPDATE_SCHEDULE_MODE = "update_schedule_mode"

SCHEDULE_MODE_DAILY = "daily_midnight"
SCHEDULE_MODE_WINDOW = "adjust_window"
DEFAULT_SCHEDULE_MODE = SCHEDULE_MODE_WINDOW

DEFAULT_REGION = "beijing"
ICON = "mdi:gas-station"

FUEL_KEY_TO_ATTR = {
    "92": "gas92",
    "95": "gas95",
    "98": "gas98",
    "0": "die0",
}

SENSOR_STATE_KEYS = (
    "gas92",
    "gas95",
    "gas98",
    "die0",
    "time",
    "tips",
    "trend",
    "next_adjust_date",
    "update_time",
    "friendly_name",
)

REGIONS: dict[str, str] = {
    "anhui": "安徽",
    "beijing": "北京",
    "chongqing": "重庆",
    "fujian": "福建",
    "gansu": "甘肃",
    "guangdong": "广东",
    "guangxi": "广西",
    "guizhou": "贵州",
    "hainan": "海南",
    "hebei": "河北",
    "heilongjiang": "黑龙江",
    "henan": "河南",
    "hubei": "湖北",
    "hunan": "湖南",
    "jiangsu": "江苏",
    "jiangxi": "江西",
    "jilin": "吉林",
    "liaoning": "辽宁",
    "neimenggu": "内蒙古",
    "ningxia": "宁夏",
    "qinghai": "青海",
    "shandong": "山东",
    "shanghai": "上海",
    "shanxi": "山西",
    "shanxisheng": "陕西",
    "sichuan": "四川",
    "tianjin": "天津",
    "xinjiang": "新疆",
    "xizang": "西藏",
    "yunnan": "云南",
    "zhejiang": "浙江",
}

CITY_MAP: dict[str, dict[str, str]] = {
    "guizhou": {
        "guiyang": "贵阳",
        "anshun": "安顺",
        "qingzhen": "清镇",
        "kaiyangxian": "开阳县",
        "xifengxian": "息烽县",
        "xiuwenxian": "修文县",
        "qiannan": "黔南",
        "liupanshui": "六盘水",
        "tongren": "铜仁",
        "qianxinan": "黔西南",
        "qiandongnan": "黔东南",
        "zunyi": "遵义",
        "bijie": "毕节",
    },
    "heilongjiang": {
        "haerbin": "哈尔滨",
        "mudanjiang": "牡丹江",
        "jixi": "鸡西",
        "qitaihe": "七台河",
        "daqing": "大庆",
        "qiqihaer": "齐齐哈尔",
        "jiamusi": "佳木斯",
        "suihua": "绥化",
        "heihe": "黑河",
        "hegang": "鹤岗",
        "shuangyashan": "双鸭山",
        "yichun": "伊春",
        "daxinganling": "大兴安岭",
    },
    "yunnan": {
        "kunming": "昆明",
        "qujing": "曲靖",
        "chuxiong": "楚雄",
        "yuxi": "玉溪",
        "honghe": "红河",
        "zhaotong": "昭通",
        "wenshan": "文山",
        "dalishi": "大理",
        "puershi": "普洱",
        "baoshanshi": "保山",
        "lijiang": "丽江",
        "dehong": "德宏",
        "nujiang": "怒江",
        "diqing": "迪庆",
        "xishuangbanna": "西双版纳",
        "lincang": "临沧",
    },
    "xizang": {
        "lasa": "拉萨",
        "rikaze": "日喀则",
        "shannan": "山南",
        "linzhi": "林芝",
        "naqu": "那曲",
        "changdu": "昌都",
        "ali": "阿里",
    },
    "xinjiang": {
        "wulumuqi": "乌鲁木齐",
        "changji": "昌吉",
        "kuerle": "库尔勒",
        "hami": "哈密",
        "kashi": "喀什",
        "akesu": "阿克苏",
        "tulufan": "吐鲁番",
        "dushanzi": "独山子",
        "kelamayi": "克拉玛依",
        "aletai": "阿勒泰",
        "tacheng": "塔城",
        "bole": "博乐",
        "shawan": "沙湾",
        "shihezi": "石河子",
        "yili": "伊犁",
        "hetian": "和田",
    },
    "sichuan": {
        "chengdu": "成都",
        "zigong": "自贡",
        "luzhou": "泸州",
        "deyang": "德阳",
        "mianyang": "绵阳",
        "guangyuanshi": "广元",
        "suining": "遂宁",
        "neijiang": "内江",
        "leshan": "乐山",
        "nanchong": "南充",
        "meishan": "眉山",
        "yibin": "宜宾",
        "guangan": "广安",
        "dazhou": "达州",
        "yaanshi": "雅安",
        "bazhongshi": "巴中",
        "ziyangshi": "资阳",
        "abazhou": "阿坝",
        "liangshanzhou": "凉山州",
        "panzhihua": "攀枝花",
    },
    "shanxisheng": {
        "xianshi": "西安",
        "tongchuan": "铜川",
        "xianyang": "咸阳",
        "baoji": "宝鸡",
        "weinan": "渭南",
        "yulinshi": "榆林",
        "yanan": "延安",
        "hanzhong": "汉中",
        "shangluo": "商洛",
        "ankang": "安康",
    },
    "qinghai": {
        "xining": "西宁",
        "haidong": "海东",
        "geermu": "格尔木(除唐古拉地区)",
        "haixizhou": "海西州(除格尔木市)",
        "haibeizhou": "海北州",
    },
    "neimenggu": {
        "huhehaote": "呼和浩特",
        "baotou": "包头",
        "eerduosi": "鄂尔多斯",
        "bayannaoer": "巴彦淖尔",
        "wuhai": "乌海",
        "alashanmeng": "阿拉善盟",
        "hulunbeier": "呼伦贝尔",
        "xinganmeng": "兴安盟",
        "tongliao": "通辽",
        "chifeng": "赤峰",
        "xilinguole": "锡林郭勒",
    },
}
REGION_SELECTOR_OPTIONS = [
    {"value": code, "label": name} for code, name in REGIONS.items()
]

SCHEDULE_MODE_SELECTOR_OPTIONS = [
    {"value": SCHEDULE_MODE_WINDOW, "label": "随调价窗口期更新 (推荐)"},
    {"value": SCHEDULE_MODE_DAILY, "label": "每日 00:05 更新"},
]


def region_name(region_code: str) -> str:
    """Return a friendly province or city name."""
    if not region_code:
        return ""

    if region_code in REGIONS:
        return REGIONS[region_code]

    for province_cities in CITY_MAP.values():
        if region_code in province_cities:
            return province_cities[region_code]

    return region_code


def location_key(province: str, city: str | None = None) -> str:
    """Return a stable key for a province/city selection."""
    if city:
        return f"{province}_{city}"
    return province


def location_slug(province: str, city: str | None = None) -> str:
    """Return an ASCII-friendly slug for entity IDs."""
    return location_key(province, city)
