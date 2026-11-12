"""All nineteen studies; audit status is deliberately separate from admission."""
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/cross-study-v1'
SPEC=ROOT/'specs/cross-study-v1'
DATA=Path(os.environ.get('MATRAIX_DATA_ROOT','/Volumes/元宇宙联合创新实验室/实验数据/MatrAIx多地区选品源数据'))
# id, title, history/external candidate, files, task scope, outstanding checks
ROWS=[
('shed','美国消费调整','historical',['00_历史通用问卷/shed.zip'],'7道涨价应对题','复用题面；复核插补排除、年龄学历权重与新画像覆盖'),
('pew168','美国诈骗风险','historical',['00_历史通用问卷/Pew-W168.zip'],'5道风险题','复用题面；复核拒答与调查权重'),
('anes','美国公共支出','historical',['00_历史通用问卷/anes.zip'],'6道三档支出题','固定选前新招募网络样本；排除纸质与GSS回访样本'),
('origin','美国商品产地','historical',['06_历史北美电商/origin-original.tab','06_历史北美电商/origin.csv','06_历史北美电商/origin-appendix.docx'],'商品二选一与四项属性取舍','保留文化态度时点；随机位置映射不冒称原位置'),
('packaging','美国包装与拒买','historical',['06_历史北美电商/packaging.csv'],'两款啤酒与都不买','复核选择卡说明、包装标签与拒买编码'),
('pew111','美国网购与达人购物','historical',['06_历史北美电商/Pew-W111.zip'],'6道设备及购物题','跳题仅决定展示资格，不向画像添加目标答案'),
('shoes','美国运动鞋意愿','historical',['08_购物研究与候选/Horiuchi2021_Conjoint_SDB/ReplicationPackage_v2.tar.gz','08_购物研究与候选/shoes.csv.gz'],'七档购买意愿','保留十项商品属性和随机设计；意愿不等于成交'),
('pew13','美国购物看法','historical',['08_购物研究与候选/Pew_Wave13/American-Trends-Panel-Wave-13-Dec-15.zip'],'13道购物题','保留网络样本资格及逐题权重'),
('amazon','美国真实购买','historical',['08_购物研究与候选/Open_eCommerce_1.0/amazon-purchases.csv.gz','08_购物研究与候选/Open_eCommerce_1.0/survey.csv.gz'],'价格构成、类别与复购','行为指标另列；剔除amazon来源画像，不能编造未购买备选集'),
('vegetables','中国日本有机蔬菜','external_candidate',['01_中国日本有机蔬菜/Raw_data_China.xlsx','01_中国日本有机蔬菜/Raw_data_Japan.xlsx','01_中国日本有机蔬菜/论文补充材料.docx'],'含拒选的蔬菜选择','旧审查缺完整24组设计；需新材料或限定可还原部分'),
('swiss_six','瑞士六品类','external_candidate',['02_瑞士六品类/w14_conjoint.RData','02_瑞士六品类/SEP_w14_reduced.RData','02_瑞士六品类/Dragons_ReplicationCode_Gomm.R'],'二选一与购买意愿分开','同面板重叠、样本筛选和题面仍需核验；不是天然独立研究'),
('german','德国番茄包装','external_candidate',['03_德国番茄包装/data_valid.sav','03_德国番茄包装/survey_original.pdf','03_德国番茄包装/XLSTAT_V4_final.xlsm','03_德国番茄包装/BOKU_2024_012_ethical_statement.pdf'],'包装选择及拒买','按原同意用途审查必要匿名背景的云端使用；不扩大既有授权解释'),
('dryer','四国烘干机','historical',['04_四国烘干机/Tumbledrier_DCE_wide.dta'],'8次商品选择及拒买','仅既有可还原信息条件；不能恢复未经确认的价格电费图形条件'),
('swiss','瑞士家电规格','historical',['05_瑞士家电规格/w8_conjoint.csv','05_瑞士家电规格/w7_w8_subgroups.csv'],'4次家电二选一','同面板跨研究重叠；英文文字重建限制沿用'),
('tshirt','美国T恤','external_candidate',['07_美国T恤/CFTF_usa.dta','07_美国T恤/CTFTF_usa_w1_demos.dta','07_美国T恤/论文与补充材料/gini_a_2089133_sm6766.docx'],'三款商品选择','缺逐商品图片映射及样本差异说明；不可冒称完整同信息重现'),
('radiant','欧洲新品食品','external_candidate',['11_欧洲新品食品/COESHT.xlsx','11_欧洲新品食品/COSCBB.xlsx','11_欧洲新品食品/COITPR.xlsx','11_欧洲新品食品/COITYP.xlsx','11_欧洲新品食品/COBGID.xlsx'],'多地食品选择','干预文本、原指令与选择卡映射；子项目不能当成独立研究凑数量'),
('supermarket','美国模拟网超','external_candidate',['14_美国模拟网超/ICPSR_198165-V2.1.zip','14_美国模拟网超/解压材料/Data_upload.dta','14_美国模拟网超/解压材料/Code_upload.do'],'选购篮或类别行为','实际备选集与标签干预还原；无备选集则不做单品选择准确率'),
('cius','加拿大互联网使用','external_candidate',['08_购物研究与候选/cius-2022.zip','08_购物研究与候选/CIUS2022_Codebook_PUMF.pdf','08_购物研究与候选/CIUS2022_Quest_E.pdf'],'购物行为问卷候选','尚需固定购物题、资格规则、人口字段与调查权重'),
('drone','美国无人机配送','external_candidate',['08_购物研究与候选/drone-survey.csv.gz','08_购物研究与候选/drone-fields.csv.gz','08_购物研究与候选/drone-attributes.py.gz','08_购物研究与候选/drone-codebook.py.gz'],'配送服务偏好候选','先确认是问卷态度还是商品选择及原题编码，不凭名称定义任务'),
]
assert len(ROWS)==19 and len({r[0] for r in ROWS})==19
