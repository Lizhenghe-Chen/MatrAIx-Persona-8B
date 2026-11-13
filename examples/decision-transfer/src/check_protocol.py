"""Offline smoke check using fictional inputs; never sends requests."""
import hashlib,json
from protocol import build,parse,MODELS,ARMS

def main():
    common={'title':'Software fixture','context':'Fictional test only; no real participant.', 'questions':[{'id':'q1','prompt':'Choose one','options':{'a':'Example A','b':'Example B'}}]}
    rows=[]
    for model in MODELS:
        bodies=[]
        for arm in ARMS:
            p=dict(common)
            if arm=='matraix':p['persona_text']='Fictional placeholder; native persona integration pending.'
            else:
                p['basic']={'age':'35'}
                if arm!='basic':p['extra']={'attitude':'Concerned' if arm=='own' else None}
            body=build(p,arm,model,{'age':'Age'},{'attitude':'Measured attitude'},768)
            bodies.append(body)
            raw={'model':MODELS[model],'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'answers':[{'questionId':'q1','probabilities':{'a':.5,'b':.5}}]})}}]}
            parse(raw,common['questions'],model)
            rows.append({'model':model,'arm':arm,'request_sha256':hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()})
        assert all(x['messages'][1]==bodies[0]['messages'][1] for x in bodies)
    print(json.dumps({'status':'offline_fixture_pass','live_calls':0,'not_a_scientific_result':True,'requests':rows},indent=2))
if __name__=='__main__':main()
