import json
from pathlib import Path
rows=[]
for line in Path('data/agent_metrics.jsonl').read_text(encoding='utf-8').splitlines():
    try: rows.append(json.loads(line))
    except Exception: pass
last=rows[-16:]
out={}
for agent in ('policy_agent','decision_agent'):
    x=[r for r in last if r.get('agent')==agent]
    times=[r['elapsed_seconds'] for r in x]
    tokens=[r.get('eval_count') for r in x]
    out[agent]={'count':len(x),'min_seconds':min(times),'max_seconds':max(times),'avg_seconds':sum(times)/len(times),'tokens':tokens,'token_min':min(tokens),'token_max':max(tokens),'prompt_chars':[r['prompt_chars'] for r in x],'json_metrics_present':all(r.get('eval_count') is not None for r in x)}
Path('section1_metrics_compact.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
