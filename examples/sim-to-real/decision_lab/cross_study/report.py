"""Generate an offline preparation report; never present pilots as effect evidence."""
import json,html
from .registry import OUT,ROWS,SPEC

def load(name):return json.loads((OUT/name).read_text())
def main():
 inventory=load('source-inventory.json');matching=load('matching-candidate.json');persona=load('persona-audit.json');pilot=load('participant-pilot-result.json');p= json.loads((SPEC/'participant-pilot.json').read_text())
 n=sum(x['status']=='complete' for x in pilot['rows']);tokens_in=sum(r['usage'].get('prompt_tokens',0) for r in pilot['rows']);tokens_out=sum(r['usage'].get('completion_tokens',0) for r in pilot['rows']);cost=(tokens_in*1.32+tokens_out*3.96)/1e6
 status={s:('已完成单人格式试跑','继续核对抽样权重、分群精度和完整画像；尚未正式准入') for s in matching['studies']}
 status.update({
 'origin':('待接入本轮','已有任务适配；需重新从原表读年龄学历，不能直接沿用历史分层标签'),
 'packaging':('待接入本轮','已有拒买及选择卡适配；复核信息组、完整背景匹配和评分单位'),
 'pew111':('待接入本轮','已有原题与跳题适配；重新读原始学历编码与权重'),
 'shoes':('待接入本轮','购买意愿属于七档评分；需冻结原题转为选项的适配，不能写成实际购买'),
 'amazon':('行为结果单列','没有未购买商品的完整备选集；需要独立的行为目标与评价标准，不加入商品二选一总分'),
 'vegetables':('关键材料待补','目前仍缺完整24组选择设计，不凭数据列名补造备选商品'),
 'swiss_six':('限定候选','既有审查发现1,837个数值编号与家电面板重叠；核对编号空间、筛选与题面后再定独立性'),
 'german':('用途边界待澄清','原受访者告知与公开许可范围存在不一致；尚未批准逐人关联云端实验'),
 'tshirt':('关键材料待补','逐商品图片映射与第二波样本差异仍未解释；文字版不能冒称完整原实验'),
 'radiant':('待完成材料核验','已找到部分干预原文；仍需逐工作簿核对说明、选择卡与样本差异'),
 'supermarket':('行为结果单列','原始数据可读，但实际商品备选集尚未还原，不能虚构单品选择任务'),
 'cius':('待制定购物题组','原始数据包与问卷齐全；购物题、资格、权重和匹配字段尚未冻结'),
 'drone':('结构已重建','3,715人、36,297次配送选择，编码无异常；缺学历实测，应明确只匹配可用背景，待冻结分块和指标')})
 rows=[]
 for ident,title,tier,files,task,gap in ROWS:
  s,detail=status[ident];rows.append({'id':ident,'name':title,'evidence':'历史复验' if tier=='historical' else '外部候选（尚未确认独立性）','status':s,'scope':task,'remaining':detail,'formal_admitted':False,'formal_budget_approved':False})
 doc={'status':'preflight_in_progress_not_effect_report','studies':rows,'completed_format_checks':n,'planned_format_checks':len(pilot['rows']),
 'pilot_peak_price_estimate_usd':cost,'pilot_input_tokens':tokens_in,'pilot_output_tokens':tokens_out,
 'formal_effects_available':False,'formal_run_authorized':False,
 'budget_note':'One-person pilot is not a reliable estimate for every full profile. Formal request, retry and fee caps remain unapproved; no final budget requested yet.'}
 (OUT/'admission.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
 e=html.escape
 tab=''.join(f'<tr><th>{e(r["name"])}</th><td>{e(r["evidence"])}</td><td>{e(r["status"])}</td><td>{e(r["remaining"])}</td></tr>' for r in rows)
 bars=''.join(f'<div class="bar"><strong>{e(next(r[1] for r in ROWS if r[0]==s))}</strong><meter min="0" max="{v["selected"]}" value="{v["matched"]}"></meter><span>{v["matched"]}/{v["selected"]}；不同画像 {v["unique_release_profiles"]} 个</span></div>' for s,v in matching['studies'].items())
 fields=''.join(f'<tr><th>{e(next(r[1] for r in ROWS if r[0]==s))}</th><td>{v["questions"]}</td><td>{v["canonical_profile_dimensions"]}</td><td>{v["omitted_noncanonical_or_null"]}</td></tr>' for s,v in p['studies'].items())
 text=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MatrAIx 跨研究验证：开跑准备</title>
<style>body{{margin:0;background:#f5f6f2;color:#20352d;font:17px/1.75 system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:30px 24px 80px}}h1{{font-size:36px;line-height:1.3}}h2{{margin-top:42px}}.notice,section,.card{{background:white;border:1px solid #d4dfd8;border-radius:12px;padding:22px;margin:18px 0}}.notice{{border-left:6px solid #ba8420}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.card strong{{font-size:30px;display:block}}table{{width:100%;border-collapse:collapse;font-size:15px}}th,td{{padding:14px 10px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}}thead{{background:#e8eee9}}.scroll{{overflow:auto}}.bar{{display:grid;grid-template-columns:150px 1fr 240px;gap:18px;align-items:center;margin:15px 0}}meter{{width:100%;height:26px}}small{{color:#566b62}}a{{color:#145b82}}@media(max-width:700px){{.grid{{grid-template-columns:1fr}}.bar{{grid-template-columns:1fr;gap:2px}}h1{{font-size:28px}}main{{padding:16px}}}}</style><main>
<p>2026-11-12 · 新一轮验证 · 开跑准备记录</p><h1>这次要检验：优化能否在新研究中继续有效？</h1>
<div class="notice"><b>目前还没有本轮效果结论。</b>已完成19套源文件清点、完整画像发行版校验及首批格式试跑。正式准入、全部适配、完整预算与评分实现仍在准备。以下数字衡量准备状态，不表示优化提升。</div>
<div class="grid"><div class="card"><strong>19 套</strong>11套历史复验＋8套外部候选。候选不等于独立新证据。</div><div class="card"><strong>{persona['rows']:,} 条</strong>发行版画像；10个分片均已校验内容哈希。</div><div class="card"><strong>{n}/{len(pilot['rows'])} 次</strong>首批格式试跑通过；另有4次完全虚构题目的接口检查。</div></div>
<h2>先把比较说清楚</h2><section>同一个模型、同一批画像、同一份问卷，只改两件事：怎样要求模型作答，以及是否保留每个选项的概率。
<div class="scroll"><table><thead><tr><th>比较方案</th><th>提示</th><th>交出的答案</th></tr></thead><tbody><tr><td>原流程参照</td><td>当前 MatrAIx 问卷指令</td><td>选一个答案</td></tr><tr><td>只改输出</td><td>相同原指令</td><td>每个选项各占多少概率</td></tr><tr><td>只改提示</td><td>预测对应受访者的选择</td><td>选一个答案</td></tr><tr><td>优化组合</td><td>预测对应受访者的选择</td><td>每个选项各占多少概率</td></tr></tbody></table></div>
<p>主要看“优化组合”能否改善原流程；另外两组帮助解释改进来自哪里。全部使用 DeepSeek Pro，所以结论不是对官方8B模型权重的排名。</p></section>
<h2>已经发现并处理的问题</h2><section><p><b>原流程会修补无效答案。</b>当前实现遇到缺答或无效选项时可能填入默认值，其中单选可被替换成第一个选项。本轮四组统一保留失败、不自动填答案。因此称“原生提示参照”，并公开这一执行差异；不能据此断言旧实验的全票现象就是由它造成。</p>
<p><b>不能只看40万条纯合成子集。</b>已检查完整发行版。其他来源能提供更多北美、西欧候选，但公开资料推断的人格不等于真人实测。Amazon来源及来源不明记录有单独隔离规则。</p>
<p><b>地区不是国家。</b>北美画像不自动等于美国居民。国家是题目的共同情境；匹配能精确到哪里，报告就写到哪里。</p>
<p><b>发现并修正国家缩写映射。</b>烘干机的加拿大、爱尔兰缩写现已识别。修正发生在任何效果评分之前，旧候选快照保留审计。</p></section>
<h2>首批六套：候选背景匹配到了多少？</h2><section><p>每套152名候选包含8名预留试跑、48名筛查、96名留出人员。已试跑的每套1人来自试跑集合。图中的匹配仅指当前人口字段约束，不能说明画像就是对应真人。</p>{bars}<p><small>烘干机未匹配的3人分别在筛查集合1人、留出集合2人；尚未放宽约束或补答案。原生生成器补充须另轨记录。画像重复、收入口径、分层覆盖和抽样权重仍需最终验收。</small></p></section>
<h2>同一发行版的“画像厚薄”差别很大</h2><section><div class="scroll"><table><thead><tr><th>试跑研究</th><th>完整题组题数</th><th>该试跑画像可用字段</th><th>空缺或非规范字段未发送</th></tr></thead><tbody>{fields}</tbody></table></div><p>这是每套一人的格式试跑，不能当作总体完整度估计。四组共享这些字段；非规范自由文字、姓名、来源编号、真人答案没有进入请求。完整正式队列还要报告字段覆盖分布。</p><p>24次试跑共输入 {tokens_in:,}、输出 {tokens_out:,} token。按已核对的高峰公开单价估计约 ${cost:.4f}，不是账单。未查看效果分数。</p></section>
<h2>19套数据逐项去向</h2><p>“文件齐全、能打开”不等于“已可用于有效对照”。所有数据保留；没有为凑数量补造任务。</p><div class="scroll"><table><thead><tr><th>研究</th><th>证据身份</th><th>当前进度</th><th>剩余条件／限定范围</th></tr></thead><tbody>{tab}</tbody></table></div>
<h2>什么结果才算支持优化？</h2><section><p>每项研究分别报告总体选项比例、对应人群差异、拒买与少数选择，以及费用和失败。总体误差下降至少2个百分点，且按受访者重抽样2,000次得到的95%区间高于零，才称该研究支持改善。</p><p>至少三套新的独立研究通过、覆盖两类任务和两个地区，并完整呈现其他研究的失败与不确定性，才支持较广适用。如果只有总体比例变准，分群没有改善，就只称“更好的群体比例估计”，不称“更懂对应真人”。</p></section>
<h2>接下来与当前边界</h2><section><p>先完成剩余任务适配、画像来源及覆盖审查，再冻结抽样、评价单位和每套预算。正式请求、重试与费用上限按批准方案提交确认；目前没有正式批量运行授权，也没有正式效果分数。</p><p>此前认可的总报告和真人源数据保持完整。本页不替代旧报告，不提前把优化写成成功。</p></section>
<p>核查材料：<a href="source-inventory.json">19套文件哈希</a> · <a href="persona-audit.json">发行版全量审计</a> · <a href="matching-candidate.json">候选匹配</a> · <a href="participant-pilot-result.json">24次格式检查</a> · <a href="admission.json">逐套准入进度</a> · <a href="drone-audit.json">配送任务结构审查</a> · <a href="../../specs/cross-study-v1/native-runtime.json">原生执行路径快照</a></p>
<p>外部来源：<a href="https://api-docs.deepseek.com/quick_start/pricing/">DeepSeek官方计费说明</a> · <a href="https://github.com/aberke/drones-consumer-privacy">无人机配送作者原件</a>。其他源数据路径与版本见文件清单。</p></main></html>'''
 (OUT/'index.html').write_text(text)
 print('Updated preflight report; effects_scored=false')
if __name__=='__main__':main()
