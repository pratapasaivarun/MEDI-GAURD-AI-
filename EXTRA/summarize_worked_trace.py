import json
from pathlib import Path
raw = Path('worked_examples_trace.json').read_bytes()
text = raw.decode('utf-16') if raw.startswith(b'\xff\xfe') else raw.decode('utf-8')
data = json.loads(text[text.index('['):])
out=[]
for e in data:
    r=e['rule_engine_results']
    out.append({'example':e['example'],'title':e['title'],'bill_fields':{k:None if v is None else {'value':v['value'],'confidence':round(v['confidence'],2),'needs_review':v['needs_review'],'evidence':v['evidence']} for k,v in e['bill_raw_fields'].items()},'policy_terms':e['policy_terms'],'context':e['inputs']['context_not_extracted_from_fixture'],'rule_trace':e['rule_order_and_trace'],'engine_status':r['status'],'covered_amount':r['covered_amount'],'deductible':r['deductible'],'copayment':r['copayment'],'payable_amount':r['payable_amount'],'warnings':r['warnings'],'calculations':r['results']})
Path('WORKED_EXAMPLES_EXACT.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
for e in out:
    print(json.dumps({k:e[k] for k in ('example','title','engine_status','covered_amount','deductible','copayment','payable_amount','warnings')},ensure_ascii=False))
print('WORKED_EXACT_JSON_OK')
