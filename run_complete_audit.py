from pathlib import Path
import ast, json, sqlite3, subprocess, os, re
root=Path(r'C:\MediGaurd AI')
exclude={'.venv','.git','__pycache__','.pytest_cache','EXTRA'}
files=[]
for p in root.rglob('*'):
    if p.is_file() and not any(part in exclude for part in p.parts):
        files.append(p)
files.sort()
rows=[]
for p in files:
    rel=p.relative_to(root).as_posix(); size=p.stat().st_size
    ext=p.suffix.lower(); kind='other'
    if ext=='.py': kind='source' if not p.name.startswith('test_') and not p.name.startswith('verify_') and p.name not in {'run_full_audit_suite.py'} else 'test/tool'
    elif ext in {'.md','.txt'}: kind='documentation/report'
    elif ext in {'.pdf','.png','.jpg','.jpeg'}: kind='fixture/media'
    elif p.name.startswith('.env') or p.name in {'requirements.txt'}: kind='configuration'
    elif 'data' in p.parts: kind='runtime-data'
    try:
        text=p.read_text(encoding='utf-8', errors='ignore') if ext in {'.py','.md','.txt','.json','.env'} else ''
    except Exception as e: text=''
    rows.append({'file':rel,'kind':kind,'bytes':size,'lines':text.count('\n')+1 if text else None,'todos':len(re.findall(r'\bTODO\b|FIXME|not implemented|pass #',text,re.I)),'secrets':bool(re.search(r'(api[_-]?key|password|secret)\s*[=:]\s*["\'][^"\']{8,}',text,re.I)) if text else False})
source=[r for r in rows if r['kind']=='source']
tests=[r for r in rows if r['kind']=='test/tool']
compile_results=[]
for r in source+tests:
    path=root/r['file']
    if path.suffix=='.py':
        try: ast.parse(path.read_text(encoding='utf-8',errors='ignore')); status='PASS'
        except Exception as e: status='FAIL: '+str(e)
        compile_results.append((r['file'],status))
imports=[]
for r in source:
    try:
        tree=ast.parse((root/r['file']).read_text(encoding='utf-8',errors='ignore'))
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): imports += [(r['file'],a.name.split('.')[0]) for a in n.names]
            elif isinstance(n,ast.ImportFrom) and n.module: imports.append((r['file'],n.module.split('.')[0]))
    except: pass
root_py={p.stem for p in root.glob('*.py')}
missing=sorted({name for _,name in imports if name in {'app','agents','extraction','rules','policy_index','policy_terms','policy_compare','reports'} and name not in root_py})
db_info=[]
db=root/'data'/'mediguard.db'
if db.exists():
    try:
        con=sqlite3.connect(db); tables=con.execute("select name from sqlite_master where type='table' order by name").fetchall()
        for (name,) in tables:
            cols=[x[1] for x in con.execute(f'pragma table_info("{name}")').fetchall()]
            count=con.execute(f'select count(*) from "{name}"').fetchone()[0]
            db_info.append((name,count,cols))
        con.close()
    except Exception as e: db_info=[('ERROR',0,[str(e)])]
git=''
try: git=subprocess.check_output(['git','-C',str(root),'status','--short'],text=True,stderr=subprocess.STDOUT)
except Exception as e: git=str(e)
req=(root/'requirements.txt').read_text(encoding='utf-8',errors='ignore') if (root/'requirements.txt').exists() else 'MISSING'
report=[]
report += ['# Medi Gaurd AI — Complete File-by-File Audit','',f'**Audit path:** `{root}`  ','**Scope:** Project-owned files excluding `.venv`, `.git`, `__pycache__`, `.pytest_cache`, and `EXTRA` backup files.','']
report += ['## Executive conclusion','', '> The core claim-verification path is present and has previously passed the clean end-to-end fixture, but the repository is not cleanly release-ready. The main audit risks are missing tracked project hygiene files, a large unreviewed `EXTRA` backup folder, runtime data committed or mixed with source, and a security code defect requiring confirmation: `app.py` uses `base64` in password/MFA functions but the inspected import section does not import `base64`. Authentication is currently bypassed by core-demo mode and must not be used for real medical documents.','']
report += ['## Inventory summary','', '| Category | Count |','|---|---:|',f'| Total in-scope files | {len(rows)} |',f'| Python source files | {len(source)} |',f'| Python tests/tools | {len(tests)} |',f'| Documentation/reports | {sum(r["kind"]=="documentation/report" for r in rows)} |',f'| Fixtures/media | {sum(r["kind"]=="fixture/media" for r in rows)} |',f'| Runtime-data files | {sum(r["kind"]=="runtime-data" for r in rows)} |','']
report += ['## File-by-file register','', '| File | Category | Bytes | Lines | TODO/severity markers | Literal-secret pattern |','|---|---|---:|---:|---:|---|']
for r in rows: report.append(f'| `{r["file"]}` | {r["kind"]} | {r["bytes"]:,} | {r["lines"] or "—"} | {r["todos"]} | {"YES" if r["secrets"] else "No"} |')
report += ['','## Core-file assessment','', '| File | Responsibility | Audit assessment |','|---|---|---|']
assess={'app.py':'Main Streamlit UI, SQLite access, auth helpers, claim orchestration, policy screens, result rendering. Large high-risk integration file; inspect import/runtime paths and keep auth disabled only for demo.','agents.py':'Two-agent LangGraph/Ollama workflow. Must remain compact-evidence-only, strict JSON, bounded calls, and Manual Review fallback.','extraction.py':'PyMuPDF/Tesseract extraction and normalization. Verify confidence/provenance and image/PDF parity.','rules.py':'Deterministic financial rule engine. Authoritative calculation layer; protect with fixture matrix.','policy_terms.py':'Policy term extraction and normalization. Must avoid demonstration defaults when live policy terms are absent.','policy_index.py':'Persistent ChromaDB indexing/retrieval. Verify policy-number matching and persistence.','policy_compare.py':'Policy-edition comparison utility. Optional to core flow but imported by app.','reports.py':'Report/appeal generation. Optional/deferred feature but imported by app, so import failure can break startup.','requirements.txt':'Dependency manifest. Tesseract is correctly used instead of PaddleOCR for Python 3.13 Windows; versions are minimums rather than fully locked pins.'}
for f in ['app.py','agents.py','extraction.py','rules.py','policy_terms.py','policy_index.py','policy_compare.py','reports.py','requirements.txt']:
 report.append(f'| `{f}` | {assess.get(f,"Project file")} | Review required before production use. |')
report += ['','## Static verification','', '| Check | Result |','|---|---|']
for f,s in compile_results: report.append(f'| Python parse: `{f}` | {s} |')
report += [f'| Imported local modules missing from project root | {", ".join(missing) if missing else "None detected"} |',f'| `AGENTS.md` found | {"Yes" if list(root.rglob("AGENTS.md")) else "No"} |']
report += ['','## Database inventory','', '| Table | Rows | Columns |','|---|---:|---|']
for n,c,cols in db_info: report.append(f'| `{n}` | {c} | {", ".join(cols)} |')
report += ['','## Configuration review','', '```text',req.strip(),'```','', '- `requirements.txt` deliberately excludes PaddleOCR/PaddlePaddle and uses Tesseract, matching the Windows Python 3.13 decision.','- Dependency versions use `>=` ranges, so reproducibility is weaker than a lock file or exact pins.','- `.env.example` is absent from the current root inventory and is shown as deleted by Git status; restore a safe template before handoff.','- `.gitignore` is absent from the current root inventory and is shown as deleted by Git status; this can expose SQLite, uploads, ChromaDB, logs, and environment files.','']
report += ['## Repository hygiene and risks','', 'The Git status shows important tracked files deleted from the root, including `.env.example`, `.gitignore`, `README.md`, `SECURITY_OPERATIONS.md`, and several tests. Copies exist in `EXTRA`, but a backup folder is not a substitute for the live project structure. This should be repaired before any release or handoff.','', 'The root contains runtime state such as `data/mediguard.db`, ChromaDB directories, uploads, logs, and generated reports. These should be deliberately classified as local demo artifacts and excluded from version control unless there is a documented reason to keep them.','', 'The application contains authentication and MFA code, but `CORE_DEMO_MODE` defaults to `true`, meaning the core demo can bypass login. This is acceptable only for synthetic local testing and not for real patient documents.','', 'The inspected `app.py` import section calls `base64.urlsafe_b64encode` and `base64.urlsafe_b64decode` in password/MFA functions without showing an import for `base64`. This must be fixed or verified immediately because it would fail when those paths execute.','']
report += ['## Prioritized action plan','', '| Priority | Action | Reason |','|---|---|---|','| P0 | Restore `.gitignore`, `.env.example`, README, and required tracked tests; remove accidental root deletions or formally document them. | Prevents broken handoff and accidental sensitive-data commits. |','| P0 | Add/verify `import base64` in `app.py`; run authentication/MFA tests if those paths remain in code. | Potential runtime defect in password/MFA functionality. |','| P0 | Confirm the patched dark UI app compiles and starts on Windows after the latest change. | Final live frontend verification was interrupted by the disconnected sidecar. |','| P1 | Lock dependencies using a tested Windows requirements lock or constraints file. | Prevents environment drift. |','| P1 | Run the complete test matrix, not only the reduced root test subset. | Current root is missing many tests that remain in `EXTRA`. |','| P1 | Add explicit tests for covered, excluded, deductible, copayment, and claimant responsibility reconciliation. | Protects the user-facing financial explanation. |','| P2 | Separate demo runtime data from source and define retention/deletion rules. | Medical-document data needs controlled handling. |','| P2 | Keep authentication, MFA, authorization, encryption, audit, and retention work before real-user deployment. | Core demo mode is not production security. |']
report += ['','## Git status evidence','', '```text',git.strip() or '(clean)','```','', '## Overall rating','', '**Core MVP functionality:** conditionally working. **Automated evidence:** partial but positive. **Repository readiness:** not ready for release or real medical data until P0 hygiene, security-runtime, and final Windows UI checks are closed.','']
(root/'COMPLETE_FILE_BY_FILE_AUDIT.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
(root/'COMPLETE_FILE_BY_FILE_AUDIT.json').write_text(json.dumps({'files':rows,'compile':compile_results,'missing_local_imports':missing,'db':db_info,'git_status':git},indent=2),encoding='utf-8')
print('AUDIT_WRITTEN',len(rows),'files')
print('SOURCE',len(source),'TESTS_TOOLS',len(tests))
print('MISSING_IMPORTS',missing)
print('PY_FAILS',[x for x in compile_results if x[1]!='PASS'])
print('DB_TABLES',[(x[0],x[1]) for x in db_info])
print('GIT_LINES',len(git.splitlines()))
