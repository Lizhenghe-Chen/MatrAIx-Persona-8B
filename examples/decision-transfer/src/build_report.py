"""Build a self-contained preparation page using only public audit summaries."""
import json,html
from freeze import HERE

def main():
 frozen=json.loads((HERE/'archive/frozen-history.json').read_text());data=json.loads((HERE/'data/candidates.json').read_text());swiss=data['candidates'][1]
 backup=frozen['recovery_bundle']['bytes']/1024**2
 page=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>下一阶段｜不提前知道答案，能否预测新选择？</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f4ee;color:#213e35;font:17px/1.8 system-ui,-apple-system,"PingFang SC",sans-serif}}main{{max-width:1080px;margin:auto;padding:42px 24px 70px}}h1{{font-size:38px;line-height:1.35;max-width:850px}}h2{{font-size:25px;margin-top:36px}}h3{{margin-top:0;font-size:21px}}.eyebrow,small{{color:#5b6c65}}.notice{{padding:20px 24px;background:#e4eee8;border-left:5px solid #257461;border-radius:5px;margin:24px 0}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.card{{background:white;border:1px solid #d7ded7;border-radius:12px;padding:22px}}.big{{display:block;font-size:30px;font-weight:700}}a{{color:#176c65;text-underline-offset:3px}}li{{margin:10px 0}}.steps{{counter-reset:step}}.step{{background:white;border-bottom:1px solid #ddd;padding:16px 20px}}.step b{{display:block}}.warn{{background:#f7ead8;border-color:#a97432}}.links a{{display:inline-block;margin:8px 16px 8px 0}}code{{overflow-wrap:anywhere}}footer{{margin-top:38px;font-size:14px;color:#5b6c65}}@media(max-width:700px){{.grid{{grid-template-columns:1fr}}h1{{font-size:29px}}main{{padding:25px 18px}}}}
</style></head><body><main><div class="eyebrow">2026-11-13 · 独立新阶段 · 准备说明</div><h1>不提前告诉AI答案，<br>它能否预测新商品的选择？</h1>
<p>旧实验已经告诉我们：保留概率比只选一个答案更合理，但还没有证明合成人格能可靠代表对应真人。下一阶段希望检验：<strong>一次了解人，能否用于预测多个没有提前知道答案的问题。</strong></p>
<div class="notice"><strong>当前进度：旧实验已冻结，新阶段已建好。</strong><br>现在只有数据检查和方案草案，没有新模型调用、没有新效果分数，也没有承诺达到70分。</div>
<h2>旧资料保护好了什么？</h2><div class="grid"><div class="card"><span class="big">原位保留</span>旧报告、代码、实验记录和真人源数据均未改动或删除。</div><div class="card"><span class="big">约{backup:.0f} MiB</span>本机私有材料恢复包，包内文件逐个核验；代码与报告另有Git固定版本。</div><div class="card"><span class="big">7.1 GiB</span>共享盘源数据完成内容校验，留在原位，没有再复制一套大文件。</div></div>
<p><small>这是版本和校验保护，不是磁盘强制锁定。备份仍在本机，不是异地灾难备份。<a href="../archive/README.md">查看冻结与恢复说明</a>。</small></p>
<h2>下一步不再反复绕圈</h2><div class="steps"><div class="step"><b>第一步：确认手里真的有“了解人的信息”</b>核对真实需求、约束或偏好字段的来源和测量时间。不能把收入当预算，也不能让模型编造购物经历。</div><div class="step"><b>第二步：只做一个小对照</b>比较“只有基础资料”“加本人的真实资料”“加可比别人的资料”。看看额外信息有没有帮助，以及是否必须对应到本人。</div><div class="step"><b>第三步：有帮助，再换商品品类考试</b>方法先固定，再看没有参与方法选择的品类。不把旧数据换个文件夹就当成新证据。</div><div class="step"><b>第四步：结果决定是否继续</b>没有明显收益就停止这一改法；不靠不断加调用、换提示把旧题刷到好看。</div></div>
<h2>这与“先拿真人答案再混合”有什么不同？</h2><div class="card"><p>这次允许使用的是了解人的资料和商品说明；<strong>不给目标商品的真人选择答案或比例</strong>。真人答案只放在本机判卷。举例：知道顾客的真实家庭情况，不等于已经知道他会选哪台洗衣机。</p><p>首轮固定DeepSeek Pro和完整概率，不比较模型，不微调，不喂本人选择例子。它先检验“真实信息有没有额外价值”，不是重新给整个MatrAIx打总分。</p></div>
<h2>候选数据检查到哪一步？</h2><div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(240px,1fr))"><div class="card"><h3>美国商品产地</h3><p>原表有人口信息和第一波态度字段。可以用于开发与核对流程；由于早已看过实验成绩，不能作为全新外部验证。</p></div><div class="card"><h3>瑞士六品类</h3><p>已确认{swiss['people']:,}人、{swiss['tasks']:,}次选择。整体涵盖六品类，<strong>每个人实际只回答两个品类</strong>。原题、字段时点和旧面板重叠还需核验。</p></div></div>
<div class="notice warn"><strong>暂时不能开跑正式实验。</strong>目前没有冻结合格的新独立验证集，也没有确认候选表中存在足够的真实购买约束。如果材料不支持，就报告缺口，不为凑实验编造信息。</div>
<h2>规模与费用怎么控制？</h2><p>首轮目标最多两套研究、每套48人、三个条件。若每人一份请求能完成，就是288份筛查请求，另有少量格式试跑；原题分块可能改变数量。<strong>实际题组、调用上限和费用估算准备好后再提交确认。</strong>本次准备调用模型为0。</p>
<h2>从哪里查看？</h2><div class="links"><a href="../README.md">新阶段导航</a><a href="../docs/下一阶段方案.md">完整方案草案</a><a href="../data/candidates.json">候选结构检查</a><a href="../docs/旧证据使用注意事项.md">旧证据的局限与勘误</a><a href="../../sim-to-real/reports/story.html">已冻结的旧故事报告</a></div>
<footer>本页是准备报告。旧实验结果保留原版本，新阶段成绩以后另行发布，不混合计算。文件夹：examples/decision-transfer。</footer></main></body></html>'''
 (HERE/'reports/index.html').write_text(page)
 print('Built new preparation page; no historical files written.')
if __name__=='__main__':main()
