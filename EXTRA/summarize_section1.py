import json
from pathlib import Path

path = Path('data/agent_metrics.jsonl')
rows = []
for line in path.read_text(encoding='utf-8').splitlines():
    try:
        rows.append(json.loads(line))
    except json.JSONDecodeError:
        continue
last = rows[-16:]
for i, row in enumerate(last, 1):
    print(json.dumps({'metric_index': i, **row}, ensure_ascii=False))
for agent in ('policy_agent', 'decision_agent'):
    values = [float(r['elapsed_seconds']) for r in last if r.get('agent') == agent]
    evals = [int(r.get('eval_count') or 0) for r in last if r.get('agent') == agent]
    print(f'{agent}: count={len(values)} min={min(values):.3f} max={max(values):.3f} avg={sum(values)/len(values):.3f} eval_count_min={min(evals)} eval_count_max={max(evals)} eval_count_avg={sum(evals)/len(evals):.2f}')
