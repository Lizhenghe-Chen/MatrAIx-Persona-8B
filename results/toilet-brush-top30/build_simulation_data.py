# -*- coding: utf-8 -*-
"""
MatrAIx 人群模拟 · Amazon美国站马桶刷 TOP30 —— 模拟输入数据构建脚本
================================================================
用途：把「Amazon美国站马桶刷_TOP30_全字段明细_202609.xlsx」整理为可供
      MatrAIx-Persona-8B 用户模拟（虚拟消费者选品）使用的去偏数据集。

处理原则：
  1. 泄漏剔除：排名/月销量/月销售额/BSR 等真实销量标签移出模拟输入，
     单独落盘为 ground_truth 供模拟后对比。
  2. 背书偏差剔除：品牌匿名化为 P01–P30（原品牌仅作受控变量存档）；
     徽章（Amazon's Choice 等）、卖家名称/国籍全部移除。
  3. 营销词剥离：商品标题与图片吊牌中的营销文案（NEW / STRONG POWER /
     360° DEEP CLEANING 等）不进入模拟输入；只保留客观属性与客观外观描述。
  4. 统计可信度标记：评分保留但按评价数打「评价可信度」标记，
     <500 评价的产品评分标注为低可信，避免误导模拟人格。
  5. 图片识别：30 张主图逐张识别，产出客观外观描述作为产品考虑维度之一。

输出：
  toilet_brush_top30_simulation.json   —— 模拟输入（去偏后）
  toilet_brush_top30_simulation.csv    —— 模拟输入（同内容 CSV）
  toilet_brush_top30_ground_truth.csv  —— 事实对照（真实排名/销量，模拟后对比用）
  toilet_brush_top30_review.xlsx       —— 审查工作簿（模拟输入表 / 干扰项处理说明 /
                                         主观信息清单 / 图片识别描述）
"""
import json, csv, os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 30 款产品结构化数据（客观属性由 Excel 明细 + 主图识别共同构建）
# ---------------------------------------------------------------------------
# rating_credibility: 高 = 评价数>=5000；中 = 500–4999；低 = <500
PRODUCTS = [
 dict(id="P01", asin="B00R55CIRQ", brand="Clorox", price=8.99, ptype="单刷套装",
      head="尼龙刷毛（抗菌，含边缘下方专用刷头）", pack=1, refill=None, color="白色（深灰部件）",
      handle="加长防滑手柄", holder="角落收纳杯状底座（敞口）",
      features=["角落收纳省空间", "可清洁马桶边缘下方", "抗菌刷毛", "防滑手柄"],
      size_note="约16×5×5in", rating=4.6, reviews=5865,
      image_desc="白色主体配深灰防滑握区与底座边缘；圆形鬃毛刷头；修长刷柄；敞口杯状底座；纯白背景，无营销吊牌。"),
 dict(id="P02", asin="B0FMRH81TB", brand="FORASTO", price=14.99, ptype="刷+搋2合1套装",
      head="白色尼龙刷头+黑色橡胶搋头", pack=1, refill=None, color="浅灰",
      handle="加长手柄", holder="一体式立式收纳底座",
      features=["二合一节省空间", "公寓/小浴室适用"],
      size_note="立式套装（约1.57磅）", rating=4.3, reviews=7628,
      image_desc="浅灰立式收纳底座插黑色橡胶搋头与白色刷杆；侧印品牌；挂蓝白吊牌（NEW/2IN1/STRONG POWER 营销文案已剥离）。"),
 dict(id="P03", asin="B07XGKZ2RC", brand="MR.SIGA", price=23.99, ptype="刷+搋2合1套装",
      head="黑色橡胶搋头+清洁刷", pack=1, refill=None, color="黑色哑光",
      handle="加长手柄", holder="黑色一体式收纳底座",
      features=["重型搋子", "二合一", "哑光黑外观"],
      size_note="约6.3×8.3×18.1in", rating=4.4, reviews=78059,
      image_desc="黑色哑光质感，搋子与细长清洁刷收纳于同一黑色底座支架；底座侧面有品牌标签；纯白背景。"),
 dict(id="P04", asin="B08TM8F2WH", brand="MR.SIGA", price=19.99, ptype="单刷套装",
      head="灰白相间尼龙刷毛", pack=1, refill=None, color="黑色（蓝色装饰）",
      handle="坚固长柄", holder="圆柱形刷座（支撑卡扣）",
      features=["坚固长柄", "圆柱底座稳固"],
      size_note="约5.1×5.1×17.1in", rating=4.5, reviews=18880,
      image_desc="黑色带蓝色装饰的圆柱刷座与长柄刷；刷柄斜靠在刷座支撑卡扣上；灰白相间刷毛；白底。"),
 dict(id="P05", asin="B09TL4MLZ3", brand="oshang", price=9.99, ptype="一次性刷系统",
      head="一次性海绵刷头（蓝条纹）", pack=1, refill=14, color="白/灰/蓝",
      handle="标准手柄（灰色握区）", holder="白色收纳底座（带盖插槽）",
      features=["一次性可抛刷头", "卫生免清洗", "深层清洁", "含14替换头"],
      size_note="约3.4×3.4×16in", rating=4.5, reviews=4881,
      image_desc="白杆灰握柄、蓝条纹海绵刷头；中间白色带灰盖收纳底座；右侧两摞替换刷头；白底。"),
 dict(id="P06", asin="B0B8C3D68Y", brand="HAMITOR", price=12.73, ptype="单刷套装",
      head="黑色刷毛（S形死角刷毛）", pack=1, refill=None, color="灰色",
      handle="长柄", holder="浅灰镂空收纳底座",
      features=["死角S形刷毛", "镂空底座通风", "防溅"],
      size_note="约16.5×4.5×15in", rating=4.6, reviews=2620,
      image_desc="浅灰镂空收纳底座内置深灰长柄刷；刷头为黑色刷毛结构；简约设计；纯白背景。"),
 dict(id="P07", asin="B003M8GMRW", brand="OXO", price=19.90, ptype="单刷套装（紧凑型）",
      head="蓝色尼龙刷毛", pack=1, refill=None, color="白色",
      handle="Good Grips 防滑手柄", holder="自动开盖罐式底座",
      features=["自动开关盖", "紧凑收纳", "防滑手柄"],
      size_note="约4.3×4×17in", rating=4.7, reviews=18325,
      image_desc="白色立式底座配蓝色刷毛刷头；整体简约；纯白背景，无多余装饰。"),
 dict(id="P08", asin="B099DYL32J", brand="FAZMoss", price=8.99, ptype="浮石清洁棒（非传统刷）",
      head="浮石材质", pack=2, refill=None, color="灰色",
      handle="超长手柄", holder="无（独立长柄浮石棒）",
      features=["去除硬水渍/水垢", "不伤瓷面", "超长手柄"],
      size_note="约1.8×3.7×14.2in", rating=4.6, reviews=6171,
      image_desc="两支带长柄的浮石清洁刷；旁立蓝白包装纸盒（盒面功能文案 REMOVES HARD WATER STAINS / PUMICE POWER 已剥离）；白底网格纹。"),
 dict(id="P09", asin="B0DYJKB7GB", brand="Holaloha", price=8.99, ptype="单刷套装",
      head="蓬松球状尼龙刷毛", pack=2, refill=None, color="白色（灰防滑握柄）",
      handle="防滑握柄", holder="镂空收纳底座",
      features=["省空间", "密毛360°清洁", "2件装"],
      size_note="约4.1×3.3×15.7in", rating=4.2, reviews=1436,
      image_desc="两套白色刷（灰色防滑握柄）；左刷头蓬松球状，右刷收纳于镂空底座；蓝红吊牌（NEW 2 PACK 已剥离）。"),
 dict(id="P10", asin="B0D8J1KF6X", brand="Holaloha", price=12.99, ptype="单刷套装",
      head="尼龙刷毛", pack=3, refill=3, color="白色（灰手柄）",
      handle="标准手柄", holder="镂空收纳底座",
      features=["省空间", "3件装+3替换刷头"],
      size_note="约3.4×4.2×15.7in", rating=4.5, reviews=2204,
      image_desc="三套带底座的白色马桶刷（灰手柄）配三个替换刷头；蓝红吊牌（NEW 3 PACK WITH 3 REPLACEMENT 已剥离）。"),
 dict(id="P11", asin="B0D2C9BC6N", brand="SetSail", price=29.99, ptype="刷+搋2合1套装",
      head="黑色搋头+刷", pack=2, refill=None, color="黑色亮面",
      handle="加长手柄", holder="圆润弧形一体收纳底座",
      features=["半隐藏搋子", "2套装", "一体收纳"],
      size_note="约9.3×17.7×20.8in（大套装）", rating=4.4, reviews=7796,
      image_desc="两个外观一致的黑色亮面立式收纳底座并排；上方竖立细长柱杆；圆润弧形设计；纯白背景。"),
 dict(id="P12", asin="B0CGDHB2FC", brand="LOVLOY", price=15.29, ptype="刷+搋2合1套装",
      head="黑色橡胶搋头+刷", pack=1, refill=None, color="灰色",
      handle="加长手柄", holder="通风式收纳底座",
      features=["通风底座", "重型搋子", "适配5.3英寸排水口"],
      size_note="约8.6×7.2×6.1in", rating=4.7, reviews=1475,
      image_desc="灰黑配色收纳式底座，双杆（橡胶搋头杆+清洁刷位）；蓝白吊牌（NEW/2IN1/UPGRADED DESIGN 已剥离）。"),
 dict(id="P13", asin="B07TNHWFXJ", brand="Sellemer", price=11.99, ptype="硅胶刷套装",
      head="硅胶刷头", pack=1, refill=None, color="珍珠白",
      handle="白色长柄", holder="通风槽收纳盒（黑底白壳）",
      features=["硅胶不伤马桶", "通风快干"],
      size_note="约4×2×16in", rating=4.0, reviews=36538,
      image_desc="白色长柄硅胶刷头配白色收纳盒（黑色底座）；盒身印品牌 SELLEMER；纯白背景。"),
 dict(id="P14", asin="B0FCY9Y3JP", brand="AONEZ", price=29.99, ptype="单刷套装（紧凑型）",
      head="黑色海绵刷头", pack=3, refill=None, color="黑色",
      handle="不锈钢长柄（黑色手柄）", holder="深灰圆柱收纳底座",
      features=["紧凑小尺寸", "不锈钢手柄", "易隐藏", "防滴漏"],
      size_note="约4×4×16in", rating=4.3, reviews=10656,
      image_desc="三支套装；一支斜放（银色金属杆+黑手柄、黑色海绵头）；两支直立收纳于深灰圆柱底座；红吊牌（3 PACK 已剥离）。"),
 dict(id="P15", asin="B0CPXV2K34", brand="HAMITOR", price=11.99, ptype="单刷套装（弧形）",
      head="黑色密集刷毛", pack=1, refill=None, color="白色（灰环带底座）",
      handle="弧形手柄（防滑纹理）", holder="镂空圆柱收纳底座",
      features=["弧形柄死角清洁", "紧凑隐藏", "RV适用"],
      size_note="约3.9×3.9×16.6in", rating=4.4, reviews=7393,
      image_desc="灰白配色；弧形刷柄带防滑纹理、黑色密集刷毛；白底灰环带镂空圆柱底座，刷可斜靠收纳。"),
 dict(id="P16", asin="B0995KL5K4", brand="uptronic", price=19.99, ptype="单刷套装（加长柄）",
      head="尼龙刷毛", pack=2, refill=None, color="青铜/深棕",
      handle="加长手柄", holder="带盖圆柱收纳筒",
      features=["加长手柄", "带盖收纳", "深层清洁"],
      size_note="约17×4.5×4.5in", rating=4.5, reviews=4627,
      image_desc="两个同款深棕色（哑光青铜）圆柱收纳筒配长柄刷并排；筒底弧形底座；哑光质感。"),
 dict(id="P17", asin="B0GJPRYJLY", brand="Holaloha", price=6.99, ptype="单刷套装（含缝隙刷）",
      head="密集尼龙刷毛", pack=1, refill=None, color="白色（灰部件）",
      handle="标准手柄", holder="白色收纳底座",
      features=["省空间", "附缝隙小刷", "密毛360°清洁"],
      size_note="约4.1×3.3×15.7in", rating=4.3, reviews=173,
      image_desc="白色主体灰部件；长柄主刷+两个不同样式小清洁刷+白色底座；蓝红吊牌（NEW TOILET BRUSH SET with CREVICE BRUSH 已剥离）。"),
 dict(id="P18", asin="B088K29VNZ", brand="MR.SIGA", price=38.99, ptype="刷+搋2合1套装",
      head="黑色橡胶搋头+刷", pack=2, refill=None, color="黑色亮面",
      handle="加长手柄", holder="黑色底座收纳架",
      features=["重型搋子", "2套装"],
      size_note="约18.1×6.3×8.2in", rating=4.5, reviews=11972,
      image_desc="两个外观一致的黑色亮面搋子套装并排；每套装含长柄搋头与配套黑色底座收纳架。"),
 dict(id="P19", asin="B0FLYCVSTQ", brand="SetSail", price=33.99, ptype="单刷套装（自动关盖）",
      head="尼龙刷毛", pack=4, refill=None, color="纯白",
      handle="加长手柄（金属连接杆）", holder="方形自动关盖收纳盒",
      features=["自动关盖", "加长手柄", "通风设计", "4件装"],
      size_note="约5×5×17.5in", rating=4.5, reviews=5202,
      image_desc="四套白色刷套装；金属连接杆长柄+方形底座收纳盒；左侧盒盖打开露出内部结构，其余闭合；盒侧印品牌。"),
 dict(id="P20", asin="B09JVFPZXK", brand="uptronic", price=11.69, ptype="单刷套装（加长柄）",
      head="尼龙刷毛", pack=1, refill=None, color="深棕色",
      handle="加长手柄", holder="圆柱收纳筒（带盖）",
      features=["加长手柄", "耐用刷毛", "带盖收纳"],
      size_note="约8×1×2in", rating=4.4, reviews=4780,
      image_desc="深棕色圆柱收纳筒与配套长柄刷；刷头收纳于筒内；简约现代；纯白背景。"),
 dict(id="P21", asin="B0GT4YY6XV", brand="OSAMEDA", price=20.99, ptype="刷+搋3合1套装（含缝隙刷）",
      head="黑色橡胶搋头+刷", pack=2, refill=None, color="亮黑",
      handle="长杆手柄", holder="收纳底座",
      features=["3合1", "含缝隙刷", "2套装"],
      size_note="大套装（约3.19磅）", rating=4.4, reviews=740,
      image_desc="两套黑色搋子组合（长杆+收纳底座）并排；右侧另摆两把同款细长金属杆配件（缝隙刷）；亮面黑。"),
 dict(id="P22", asin="B09BX6ZW69", brand="Clorox", price=22.40, ptype="刷+搋2合1套装",
      head="黑色橡胶搋头+刷", pack=2, refill=None, color="白/灰",
      handle="白色手柄（黑色握区）", holder="独立收纳 caddy",
      features=["重型搋子", "自由站立 caddy", "2套装"],
      size_note="约17.3×16.1×14.4in", rating=4.5, reviews=7722,
      image_desc="两组同款套装并排；每组白柄黑握区搋子+白色收纳底座；黑色橡胶搋头；纯白背景。"),
 dict(id="P23", asin="B08RCJR77R", brand="Wsedor", price=29.99, ptype="单刷套装（不锈钢柄）",
      head="尼龙刷毛", pack=2, refill=None, color="银色",
      handle="304不锈钢长柄", holder="不锈钢圆柱筒身",
      features=["304不锈钢手柄", "人体工学", "耐用"],
      size_note="约4.1×4.1×15.7in", rating=4.4, reviews=272,
      image_desc="两个外观一致的不锈钢圆柱筒身并排；顶部细长金属刷杆延伸；哑光银质感；底部轻微反光。"),
 dict(id="P24", asin="B0GS645WC5", brand="Dealsgogo", price=9.99, ptype="壁挂式硅胶刷",
      head="硅胶刷头", pack=1, refill=None, color="灰色",
      handle="长柄（顶部挂孔）", holder="壁挂式一体底座",
      features=["硅胶不伤瓷", "壁挂收纳", "防滚防滴", "RV/房车适用"],
      size_note="约3.9×1.7×14.4in", rating=4.3, reviews=978,
      image_desc="浅灰长柄刷配一体式收纳底座；杆顶有挂孔；左侧圆形放大图标示杆身螺纹拼接结构；右侧牛皮纸包装盒。"),
 dict(id="P25", asin="B0G4QL1MJF", brand="FORASTO", price=26.99, ptype="刷+搋2合1套装",
      head="黑色橡胶搋头+刷", pack=2, refill=None, color="奶油白",
      handle="加长手柄", holder="一体式收纳底座",
      features=["加长柄搋子", "赠清洁手套2双", "2套装"],
      size_note="大套装（约2.99磅）", rating=4.4, reviews=1335,
      image_desc="两套白色底座黑搋头的一体式组合；左侧吊牌（NEW 2PACK STRONG POWER 已剥离）；右侧两双蓝色橡胶手套为赠品展示。"),
 dict(id="P26", asin="B09G6D4GXP", brand="HAMITOR", price=23.99, ptype="单刷套装（现代设计）",
      head="黑色海绵刷头", pack=2, refill=None, color="白色",
      handle="白色塑料杆（带圆形防溅挡板）", holder="白色圆柱收纳底座",
      features=["现代设计", "防溅挡板", "2套装"],
      size_note="约4.1×4.1×16.5in", rating=4.4, reviews=1648,
      image_desc="三态展示：取出状态的刷（黑海绵头+白杆+圆形防溅挡板）、空圆柱底座、插入后的完整收纳状态。"),
 dict(id="P27", asin="B0D28YKSC8", brand="Hohoky", price=26.99, ptype="一次性刷系统",
      head="一次性海绵头（蓝白条纹）", pack=1, refill=50, color="白色+蓝",
      handle="标准手柄", holder="壁挂式收纳底座",
      features=["一次性可抛", "50片替换头", "壁挂", "卫生"],
      size_note="约5.9×3.5×15.7in", rating=4.7, reviews=1725,
      image_desc="白色手柄与收纳底座；中间与右侧堆叠蓝白条纹一次性替换头；前景两个拆开刷头；背景蓝色包装盒（印 OHOKY Toilet Brush）。"),
 dict(id="P28", asin="B00BZP66HK", brand="simplehuman", price=34.99, ptype="单刷套装（不锈钢 caddy）",
      head="灰色尼龙刷毛", pack=1, refill=None, color="白+银",
      handle="加长手柄", holder="不锈钢弧形底座收纳架",
      features=["不锈钢 caddy", "经典设计"],
      size_note="约7.3×3.7×18.6in", rating=4.4, reviews=5347,
      image_desc="白色主体配银色金属部件；长柄刷+弧形底座收纳架；灰色刷毛；简洁现代；纯白背景。"),
 dict(id="P29", asin="B0H4ZJLGV4", brand="SAVEGA", price=24.99, ptype="刷+搋2合1套装（金色）",
      head="黑色橡胶搋头+刷", pack=1, refill=None, color="金/黑",
      handle="金属杆（黑色握柄）", holder="金色双孔收纳底座",
      features=["金色 caddy", "2合1", "轻奢设计"],
      size_note="约10.2×5.9×19.3in", rating=4.0, reviews=40,
      image_desc="深灰双孔底座配两根金属杆身与黑色握柄清洁棒；左侧青绿包装盒；三个圆形图标展示不同配色握柄。"),
 dict(id="P30", asin="B0GQZ24NXP", brand="HAMITOR", price=59.99, ptype="刷+搋2合1套装（不锈钢）",
      head="黑色密集刷毛+黑色橡胶搋头", pack=1, refill=None, color="金/黑",
      handle="黑黄分段手柄", holder="金色与黑色相间收纳底座",
      features=["不锈钢组合", "弧形刷毛", "重型疏通", "紧凑隐藏"],
      size_note="约6.8×6×9.9in", rating=4.4, reviews=1039,
      image_desc="金色与黑色相间收纳底座；带底座的搋子（黑黄分段手柄）与单支马桶刷（黑色密集刷毛）并置；简约轻奢风。"),
]

def credibility(reviews):
    if reviews >= 5000: return "高"
    if reviews >= 500: return "中"
    return "低（样本不足，评分仅供参考）"

for p in PRODUCTS:
    p["rating_credibility"] = credibility(p["reviews"])
    p["brand_anonymized"] = p["id"]

# ---------------------------------------------------------------------------
# 事实对照（ground truth）：真实销量标签，仅用于模拟后对比，绝不进入模拟输入
# ---------------------------------------------------------------------------
GROUND_TRUTH = [
 # id, asin, brand, rank, monthly_sales, monthly_revenue_usd, sales_growth_pct, cat_rank, bsr
 ("P01","B00R55CIRQ","Clorox",1,40482,None,22.0,"Toilet Brushes & Holders #1",229),
 ("P02","B0FMRH81TB","FORASTO",2,34024,None,None,"Bathroom Accessory Sets #1",261),
 ("P03","B07XGKZ2RC","MR.SIGA",3,25415,None,17.0,"Toilet Plungers & Holders #2",706),
 ("P04","B08TM8F2WH","MR.SIGA",4,23513,None,24.0,"Toilet Brushes & Holders #2",515),
 ("P05","B09TL4MLZ3","oshang",5,18600,None,16.0,"Toilet Brushes & Holders #5",814),
 ("P06","B0B8C3D68Y","HAMITOR",6,15311,None,-4.0,"Toilet Brushes & Holders #4",735),
 ("P07","B003M8GMRW","OXO",7,14249,None,25.0,"Toilet Brushes & Holders #7",1139),
 ("P08","B099DYL32J","FAZMoss",8,13438,None,34.0,"Toilet Brushes & Holders #6",1069),
 ("P09","B0DYJKB7GB","Holaloha",9,12576,None,44.0,"Toilet Brushes & Holders #10",1764),
 ("P10","B0D8J1KF6X","Holaloha",10,11183,None,46.0,"Toilet Brushes & Holders #10",1657),
 ("P11","B0D2C9BC6N","SetSail",11,10184,None,None,"Toilet Brushes & Holders #19",3210),
 ("P12","B0CGDHB2FC","LOVLOY",12,9882,None,None,"Toilet Brushes & Holders #8",1453),
 ("P13","B07TNHWFXJ","Sellemer",13,9749,None,7.0,"Toilet Brushes & Holders #14",2597),
 ("P14","B0FCY9Y3JP","AONEZ",14,9584,None,None,"Toilet Brushes & Holders #12",2217),
 ("P15","B0CPXV2K34","HAMITOR",15,9504,None,60.0,"Toilet Brushes & Holders #14",2905),
 ("P16","B0995KL5K4","uptronic",16,9270,None,None,"Toilet Brushes & Holders #16",3064),
 ("P17","B0GJPRYJLY","Holaloha",17,7550,None,66.0,"Toilet Brushes & Holders #13",2566),
 ("P18","B088K29VNZ","MR.SIGA",18,7475,None,17.0,"Toilet Brushes & Holders #23",3285),
 ("P19","B0FLYCVSTQ","SetSail",19,7045,None,None,"Toilet Brushes & Holders #24",3027),
 ("P20","B09JVFPZXK","uptronic",20,6614,None,None,"Toilet Brushes & Holders #11",2543),
 ("P21","B0GT4YY6XV","OSAMEDA",21,5160,None,None,"Toilet Brushes & Holders #23",3811),
 ("P22","B09BX6ZW69","Clorox",22,5023,None,None,"Toilet Brushes & Holders #18",4593),
 ("P23","B08RCJR77R","Wsedor",23,4874,None,None,"Toilet Brushes & Holders #27",7818),
 ("P24","B0GS645WC5","Dealsgogo",24,4581,None,None,"Toilet Brushes & Holders #24",5945),
 ("P25","B0G4QL1MJF","FORASTO",25,4559,None,None,"Toilet Brushes & Holders #27",8067),
 ("P26","B09G6D4GXP","HAMITOR",26,4185,None,None,"Toilet Brushes & Holders #21",5027),
 ("P27","B0D28YKSC8","Hohoky",27,3805,None,0.0,"Toilet Brushes & Holders #33",10173),
 ("P28","B00BZP66HK","simplehuman",28,3342,None,27.0,"Toilet Brushes & Holders #37",8225),
 ("P29","B0H4ZJLGV4","SAVEGA",29,2880,None,1441.0,"Toilet Brushes & Holders #36",13264),
 ("P30","B0GQZ24NXP","HAMITOR",30,2768,None,None,"Toilet Plungers & Holders #14",10919),
]

# ---------------------------------------------------------------------------
# 写出 JSON / CSV
# ---------------------------------------------------------------------------
sim_json = {
    "category": "toilet brush - Amazon US TOP30 (202609)",
    "data_month": "202609",
    "price_currency": "USD",
    "scope": "Amazon US 类目月销 TOP30 父体（Toilet Brushes & Holders 及其兄弟节点）",
    "debiasing_notes": [
        "品牌已匿名化为 P01–P30（原品牌作为受控变量存档，可单变量恢复）",
        "徽章（Amazon's Choice 等）已全部移除",
        "排名/月销量/月销售额/BSR 等真实销量标签已移出（泄漏），见 ground_truth",
        "卖家名称/卖家国籍/配送方式/在售卖家数/FBA费/profit 已移除",
        "商品标题与图片吊牌营销文案已剥离，仅保留客观属性",
        "评分保留并按评价数打可信度标记；<500 评价标为低可信",
    ],
    "products": PRODUCTS,
}
with open(os.path.join(HERE, "toilet_brush_top30_simulation.json"), "w", encoding="utf-8") as f:
    json.dump(sim_json, f, ensure_ascii=False, indent=2)

csv_cols = ["id","asin","brand_anonymized","brand_original","price_usd","product_type",
            "brush_head_material","pack_count","refill","color","handle","holder",
            "key_features","size_note","rating","review_count","rating_credibility","image_description"]
with open(os.path.join(HERE, "toilet_brush_top30_simulation.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=csv_cols)
    w.writeheader()
    for p in PRODUCTS:
        w.writerow({
            "id": p["id"], "asin": p["asin"], "brand_anonymized": p["id"],
            "brand_original": p["brand"], "price_usd": p["price"],
            "product_type": p["ptype"], "brush_head_material": p["head"],
            "pack_count": p["pack"], "refill": p["refill"] if p["refill"] else "",
            "color": p["color"], "handle": p["handle"], "holder": p["holder"],
            "key_features": "；".join(p["features"]), "size_note": p["size_note"],
            "rating": p["rating"], "review_count": p["reviews"],
            "rating_credibility": p["rating_credibility"], "image_description": p["image_desc"],
        })

gt_cols = ["id","asin","brand","rank","monthly_sales","monthly_revenue_usd","sales_growth_pct","category_rank","bsr"]
with open(os.path.join(HERE, "toilet_brush_top30_ground_truth.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=gt_cols)
    w.writeheader()
    for row in GROUND_TRUTH:
        w.writerow(dict(zip(gt_cols, list(row) + [None]*(len(gt_cols)-len(row)))))

print("JSON/CSV 已写出：", len(PRODUCTS), "款产品")

# ---------------------------------------------------------------------------
# 审查工作簿（xlsx，本地交付）
# ---------------------------------------------------------------------------
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = Workbook()
HDR_FILL = PatternFill("solid", fgColor="1F4E79")
HDR_FONT = Font(color="FFFFFF", bold=True, size=11)
WARN_FILL = PatternFill("solid", fgColor="FFF2CC")
SEP_FILL = PatternFill("solid", fgColor="DDEBF7")
thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
WRAP = Alignment(wrap_text=True, vertical="top")

def style_header(ws, ncols, row=1):
    for c in range(1, ncols+1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HDR_FILL; cell.font = HDR_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        cell.border = BORDER

def autowidth(ws, widths):
    for i, wd in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = wd

# ---- Sheet 1: 模拟输入数据 ----
ws = wb.active
ws.title = "模拟输入数据"
s1_cols = ["编号","ASIN(追溯)","原品牌(受控变量)","价格USD","产品类型","刷头材质","套装件数","替换头",
           "颜色","手柄","底座/收纳","客观功能点","尺寸要点","评分","评价数","评价可信度","图片识别描述"]
ws.append(s1_cols); style_header(ws, len(s1_cols))
for p in PRODUCTS:
    ws.append([p["id"], p["asin"], p["brand"], p["price"], p["ptype"], p["head"], p["pack"],
               p["refill"] if p["refill"] else "—", p["color"], p["handle"], p["holder"],
               "；".join(p["features"]), p["size_note"], p["rating"], p["reviews"],
               p["rating_credibility"], p["image_desc"]])
for r in range(2, ws.max_row+1):
    for c in range(1, len(s1_cols)+1):
        cell = ws.cell(row=r, column=c); cell.border = BORDER; cell.alignment = WRAP
    if ws.cell(row=r, column=16).value.startswith("低"):
        for c in range(1, len(s1_cols)+1):
            ws.cell(row=r, column=c).fill = WARN_FILL
autowidth(ws, [6,13,13,9,18,26,8,7,16,16,22,34,13,6,8,16,55])
ws.freeze_panes = "A2"

# ---- Sheet 2: 干扰项处理说明 ----
ws2 = wb.create_sheet("干扰项处理说明")
s2_cols = ["序号","字段/项目","类别","问题说明（为何构成干扰）","处理方式"]
rows2 = [
 (1,"排名 / 月销量 / 月销售额","真值泄漏","真实销量标签；模拟输入若包含则人格可直接复现榜单，无法检验模拟质量","移出模拟输入；另存为 ground_truth.csv 供模拟后对比"),
 (2,"类目内排名 / 类目BSR / BSR变化 / BSR变化率","真值泄漏","销量与热度的代理变量，与月销量高度共线","同上，移出并仅作对照"),
 (3,"月销增速%","真值泄漏+噪声","部分缺失；存在异常值（P29 达 1441%，为新品起量噪声）","移出模拟输入"),
 (4,"第三方月销估算 / 估算更新日 / 月销售额-est","真值泄漏","与月销量重复的第三方估算口径","移出模拟输入"),
 (5,"品牌名称","背书偏差","Clorox/OXO/simplehuman 认知度与白牌差异巨大，会系统性放大选择偏向（前次 Top10 实验已证明背书类信息有放大效应）","匿名化为 P01–P30；原品牌作为受控变量存档，可单变量恢复做敏感性检验"),
 (6,"徽章（Amazon's Choice 等）","背书偏差","前次实验证实徽章会放大选择效应（OXO 81.3%→77.7%）；且本数据 17/30 带 Amazon's Choice，区分度低、干扰大","全部移除"),
 (7,"卖家名称 / 卖家国籍","产地偏见","'中国卖家'刻板印象会引入非产品因素偏好","移出模拟输入"),
 (8,"配送方式 / 在售卖家数 / 变体数 / FBA费 / profit","非消费者决策信息","卖家侧运营/履约/经济账，消费者购买时通常不可见或不作为决策依据","移出模拟输入"),
 (9,"商品标题","营销词干扰","含 STRONG POWER / 360° DEEP CLEANING / NEW 等营销话术与关键词堆砌，主观性极强","不直接使用标题；重新抽取客观属性（类型/件数/材质/功能）"),
 (10,"图片吊牌与包装营销文案","营销词干扰","图片中 NEW / 2IN1 STRONG POWER / PUMICE POWER 等吊牌属于卖家营销物料","图片描述仅描述客观外观；营销文案识别后剥离并注明"),
 (11,"LQS品质分","口径不透明","第三方专有模型分，消费者不可见、方法论不公开","移出模拟输入，仅在原明细可追溯"),
 (12,"评分增速 / 评价新增 / 评分增量","动量噪声","短期波动信号，多数行缺失，口径不一致","移出模拟输入"),
 (13,"评分（低评价数产品）","统计不可靠","P17 仅173评、P23 仅272评、P29 仅40评等，评分统计上不可靠，直接呈现会误导模拟人格","评分保留但强制配对评价数并打可信度标记；<500 评价标为'低（样本不足）'并高亮"),
 (14,"ASIN / 链接 / 类目节点 / 类目路径 / 数据月份 / 价格带窗口 / 首次可售日","内部标识","非消费者决策属性；含追踪与抽样信息","移出模拟输入；保留在审查表与原明细中做追溯"),
]
ws2.append(s2_cols); style_header(ws2, len(s2_cols))
for row in rows2: ws2.append(list(row))
for r in range(2, ws2.max_row+1):
    for c in range(1, len(s2_cols)+1):
        cell = ws2.cell(row=r, column=c); cell.border = BORDER; cell.alignment = WRAP
autowidth(ws2, [5,30,14,60,50])
ws2.freeze_panes = "A2"

# ---- Sheet 3: 主观信息清单 ----
ws3 = wb.create_sheet("主观信息清单")
s3_cols = ["序号","信息项","主观性说明","是否进入模拟","处理/使用方式"]
rows3 = [
 (1,"评分（星级）","用户主观评价的聚合；受评价样本构成影响，且新品/低销量产品评分失真","进入（带可信度标记）","按评价数分级：≥5000 高、500–4999 中、<500 低并高亮；低可信评分不作为强信号"),
 (2,"评价数","反映口碑规模，本身客观，但与评分合读时构成'社会证明'，会放大从众效应","进入（客观计数）","原样保留；与评分配对使用"),
 (3,"品牌印象","品牌认知/忠诚度属主观联想，模型可能把训练知识中的品牌印象代入模拟","不进入（匿名化）","匿名 P01–P30；如需检验品牌效应可恢复原品牌做对比实验"),
 (4,"营销话术（标题/吊牌）","'NEW''STRONG POWER''360° DEEP CLEANING'等为卖家自述，无第三方验证","不进入","已剥离；仅保留可客观核验的属性"),
 (5,"图片呈现（角度/打光/道具）","商品图为卖家自摄宣传物料，呈现方式带有美化意图","部分进入","图片识别聚焦客观外观（形态/配色/结构/组件）；吊牌营销文案与赠品展示已注明"),
 (6,"LQS品质分","第三方模型输出，方法论不透明，非市场可见信息","不进入","仅存档于原明细"),
 (7,"'Amazon's Choice'等徽章","平台推荐标签，已被证明会显著放大选择（前次实验）","不进入","全部移除"),
 (8,"价格本身","客观数值，但价格同时是质量锚点（贵=好的心理联想）","进入（客观数值）","原样保留；模拟后分析时可单独检验价格敏感度"),
]
ws3.append(s3_cols); style_header(ws3, len(s3_cols))
for row in rows3: ws3.append(list(row))
for r in range(2, ws3.max_row+1):
    for c in range(1, len(s3_cols)+1):
        cell = ws3.cell(row=r, column=c); cell.border = BORDER; cell.alignment = WRAP
autowidth(ws3, [5,22,52,18,52])
ws3.freeze_panes = "A2"

# ---- Sheet 4: 图片识别描述 ----
ws4 = wb.create_sheet("图片识别描述")
s4_cols = ["编号","ASIN","品牌(受控)","图片识别描述（客观外观）","已剥离的营销元素","图片文件"]
rows4 = []
img_map = {p["asin"]: f"{i+1:02d}_{p['asin']}.jpg" for i, p in enumerate(PRODUCTS)}
mkt_map = {
 "P02":"吊牌 NEW / 2IN1 TOILET PLUNGER & BRUSH SET / STRONG POWER；侧印品牌",
 "P05":"（无营销吊牌；吊牌处为品牌标识）",
 "P08":"包装盒面 REMOVES HARD WATER STAINS / EXTRA LONG / PUMICE POWER / 2 PACK",
 "P09":"吊牌 NEW / 2 PACK / TOILET BRUSH SET / 360° DEEP CLEANING WITH DENSE BRISTLE",
 "P10":"吊牌 NEW / 3 PACK / TOILET BRUSH SET WITH 3 REPLACEMENT CLEANING BRUSH",
 "P12":"吊牌 NEW / 2IN1 / TOILET PLUNGER & BRUSH SET / UPGRADED DESIGN",
 "P14":"红吊牌 3 PACK",
 "P17":"吊牌 NEW / TOILET BRUSH SET / with CREVICE BRUSH / 360° DEEP CLEANING with DENSE BRISTLE",
 "P21":"（无营销文案；产品+配件展示）",
 "P25":"吊牌 NEW / 2PACK / TOILET PLUNGER & BRUSH SET / STRONG POWER；赠蓝手套",
 "P27":"包装盒 OHOKY / Toilet Brush / NEW",
 "P29":"包装盒 SAVEGA 竖排品牌名；圆形图标展示配色",
 "P03":"底座侧面品牌标签 SIGA",
 "P04":"刷座印品牌 MR.SIGA",
 "P13":"盒身印品牌 SELLEMER",
 "P19":"盒侧印品牌 SetSail",
 "P02s":"—",
}
for p in PRODUCTS:
    rows4.append([p["id"], p["asin"], p["brand"], p["image_desc"],
                  mkt_map.get(p["id"], "无显著营销元素"), img_map[p["asin"]]])
ws4.append(s4_cols); style_header(ws4, len(s4_cols))
for row in rows4: ws4.append(row)
for r in range(2, ws4.max_row+1):
    for c in range(1, len(s4_cols)+1):
        cell = ws4.cell(row=r, column=c); cell.border = BORDER; cell.alignment = WRAP
autowidth(ws4, [6,13,13,60,50,20])
ws4.freeze_panes = "A2"

xlsx_path = os.path.join(HERE, "toilet_brush_top30_review.xlsx")
wb.save(xlsx_path)
print("审查工作簿已写出：", xlsx_path)
print("done.")
