from collections import Counter, defaultdict
from pathlib import Path
import hashlib, json, math, re, urllib.parse, urllib.request

ROOT = Path(__file__).resolve().parent
MASTERS = json.loads((ROOT/'vocabulary.json').read_text(encoding='utf-8'))
PROMPT = (ROOT/'prompt.txt').read_text(encoding='utf-8')
OPTIONS = {'num_ctx':8192, 'num_predict':1800, 'temperature':0, 'seed':20260930}

def normalize(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())

def check_endpoint(endpoint):
    u=urllib.parse.urlsplit(endpoint)
    if u.scheme!='http' or u.hostname not in {'127.0.0.1','localhost','::1'} or u.username or u.password or u.query or u.fragment or u.path not in {'','/'}:
        raise ValueError('Only a loopback HTTP Ollama endpoint is supported.')
    return endpoint.rstrip('/')

def api(endpoint,path,payload=None):
    endpoint=check_endpoint(endpoint)
    req=urllib.request.Request(endpoint+'/api/'+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    # Do not follow redirects from localhost to any other service.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):
            raise ValueError('Ollama redirect refused')
    with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect).open(req,timeout=600) as r:
        return json.load(r)

def laterality_conflict(name,master):
    tokens=set(re.findall(r'[a-z]+',name.lower()))
    left=bool(tokens & {'left','links','linke','linker','li','lt'}) or bool(re.search(r'(?:^|[_ .-])l(?:$|[_ .-])',name,re.I))
    right=bool(tokens & {'right','rechts','rechte','rechter','re','rt'}) or bool(re.search(r'(?:^|[_ .-])r(?:$|[_ .-])',name,re.I))
    target_left=master in {'Lung Left','H_Chambers_Atrium_L','H_Chambers_Ventricle_L'}
    target_right=master in {'Lung Right','H_Chambers_Atrium_R','H_Chambers_Ventricle_R'}
    return bool((right and target_left) or (left and target_right))

def exact_proposals(rows):
    vocabulary={normalize(m):m for m in MASTERS}
    return {r['name']:(vocabulary.get(normalize(r['name']),'x'),2 if normalize(r['name']) in vocabulary else 0) for r in rows}

def enforce_unique(rows,proposals):
    """Do not infer anatomy from volume or use any reference assignments."""
    result=[]; candidates=defaultdict(list)
    for r in rows:
        master,certainty=proposals.get(r['name'],('x',0))
        if master not in MASTERS and master!='x':raise ValueError('Unknown proposed master')
        item={**r,'llm_master':master,'certainty':certainty,'automatic_master':'x','reason':'No name match'}
        if master!='x':
            if master in {'CardTV','Target_ITV','Target_PTV'} and re.search(r'(?<![a-z])(?:gtv|ctv|itv|ptv|tv)[_ -]*[1-9](?=$|[_ -])',r['name'],re.I):item['reason']='Numbered target component'
            elif certainty!=2:item['reason']='Uncertain name'
            elif laterality_conflict(r['name'],master):item['reason']='Laterality conflict'
            else:
                item['reason']='Duplicate candidates'
                candidates[(r['case'],master)].append(len(result))
        result.append(item)
    for (case,master),indices in candidates.items():
        exact=[i for i in indices if normalize(result[i]['name'])==normalize(master)]
        chosen=indices[0] if len(indices)==1 else exact[0] if len(exact)==1 else None
        if chosen is not None:
            result[chosen].update(automatic_master=master,reason='Single candidate' if len(indices)==1 else 'Sole exact-name candidate')
    used=[(r['case'],r['automatic_master']) for r in result if r['automatic_master']!='x']
    assert len(used)==len(set(used)), 'Duplicate master assignment'
    assert len({r['key'] for r in result})==len(result), 'Duplicate ROI key'
    return result

def predict_names(names,model,cache,endpoint='http://127.0.0.1:11434',batch_size=32):
    if not 1<=batch_size<=32:raise ValueError('batch_size must be 1..32')
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    tags=api(endpoint,'tags')['models'];metadata=next((m for m in tags if m['name']==model),None)
    if metadata is None:raise ValueError(f'Model not installed locally: {model}')
    names=sorted(set(names)); proposals={}
    schema={'type':'object','properties':{'matches':{'type':'array','items':{'type':'array','items':{'type':'integer'},'minItems':3,'maxItems':3}}},'required':['matches'],'additionalProperties':False}
    for start in range(0,len(names),batch_size):
        batch=names[start:start+batch_size]
        payload={'model':model,'messages':[{'role':'system','content':PROMPT},{'role':'user','content':json.dumps(list(enumerate(batch)),ensure_ascii=False)}],'format':schema,'stream':False,'think':False,'options':OPTIONS,'keep_alive':'10m'}
        key=hashlib.sha256(json.dumps({'digest':metadata['digest'],'request':payload},sort_keys=True).encode()).hexdigest()
        path=cache/(key+'.json'); errors=[]
        for attempt in range(3):
            try:
                response=json.loads(path.read_text()) if path.exists() else api(endpoint,'chat',payload)
                matches=json.loads(response['message']['content'])['matches']
                if len(matches)!=len(batch) or {x[0] for x in matches}!=set(range(len(batch))):raise ValueError('Missing, duplicate or extra input IDs')
                if not all(len(x)==3 and all(type(v) is int for v in x) and 0<=x[1]<=len(MASTERS) and 0<=x[2]<=2 for x in matches):raise ValueError('Invalid output schema')
                for i,m,c in matches:proposals[batch[i]]=(MASTERS[m-1] if m else 'x',c)
                if not path.exists():path.write_text(json.dumps(response,ensure_ascii=False),encoding='utf-8')
                break
            except (ValueError,KeyError,IndexError,TypeError) as exc:
                errors.append(str(exc))
                if path.exists():raise ValueError(f'Invalid cached response {path.name}') from exc
        else:raise ValueError(f'Invalid model output after retries: {errors}')
        print(f'{start+len(batch)}/{len(names)} names',flush=True)
    return proposals,metadata
