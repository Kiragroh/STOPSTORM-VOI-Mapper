from pathlib import Path
import argparse, csv, hashlib, html, json, math, sys, time
from .core import MASTERS, OPTIONS, PROMPT, enforce_unique, exact_proposals, predict_names

def load_rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not {'Case','ROI_ID','StructureName'}<=set(reader.fieldnames or []):raise ValueError('Required CSV headers: Case,ROI_ID,StructureName')
        rows=[];keys=set()
        for number,r in enumerate(reader,2):
            case=r['Case'].strip();roi=r['ROI_ID'].strip();name=r['StructureName'].strip()
            if not case or not roi or not name:raise ValueError(f'Empty required value in CSV row {number}')
            key=json.dumps([case,roi],ensure_ascii=False)
            if key in keys:raise ValueError(f'Duplicate Case/ROI_ID in row {number}')
            keys.add(key)
            volume=float(r['Volume_cc']) if r.get('Volume_cc','').strip() else None
            if volume is not None and (not math.isfinite(volume) or volume<0):raise ValueError(f'Invalid volume in row {number}')
            rows.append({'key':key,'case':case,'roi_id':roi,'name':name,'volume_cc':volume,'source_group':r.get('SourceGroup','')})
    if not rows:raise ValueError('No input structures')
    return rows

def safe_cell(value):
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):return "'"+value
    return value

def write_csv(path,header,rows):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(header)
        for row in rows:w.writerow([safe_cell(v) for v in row])

def export_review(output,result):
    header=['Case','ROI_ID','StructureName','Volume_cc','SourceGroup','Model proposal','Certainty (0-2)','Automatic master','Extra structure','Reason','Reviewed master','Comment']
    write_csv(output/'mappings.csv',header,[[r['case'],r.get('roi_id',r['key']),r['name'],r.get('volume_cc'),r.get('source_group',''),r['llm_master'],r['certainty'],r['automatic_master'],r.get('extra_structure',''),r['reason'],'',''] for r in result])
    write_csv(output/'extras.csv',['Case','ROI_ID','StructureName','Extra structure'],[[r['case'],r.get('roi_id',r['key']),r['name'],r['extra_structure']] for r in result if r.get('extra_structure')])
    missing=[]
    for case in sorted({r['case'] for r in result}):
        found={r['automatic_master'] for r in result if r['case']==case}
        missing.extend([[case,m] for m in MASTERS if m not in found])
    write_csv(output/'missing_masters.csv',['Case','Master without automatic assignment'],missing)
    rows=[]
    for r in result:
        status='extra' if r.get('extra_structure') else 'proposed' if r['automatic_master']!='x' else 'open'
        vals=[r['case'],r.get('source_group',''),r['name'],r.get('volume_cc',''),r.get('extra_structure') or r['automatic_master'],r['reason']]
        rows.append('<tr class="'+status+'">'+''.join('<td>'+html.escape(str(v) if v is not None else '')+'</td>' for v in vals)+'</tr>')
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VOI mapping review</title><style>body{font:15px Arial;color:#243357;margin:24px;background:#fff}h1{font-size:24px}table{border-collapse:collapse;width:100%}th{text-align:left;background:#eaf3f7}td,th{padding:9px;border-bottom:1px solid #ddd}tr.open td:nth-last-child(-n+2){background:#fff3d4}input,select{font:inherit;padding:8px;margin:8px 12px 16px 0}td{overflow-wrap:anywhere}header{position:sticky;top:0;background:white;padding:10px 0}p{max-width:80ch}</style><header><h1>VOI mapping review</h1><p>Proposals require human review. Unassigned masters are listed in missing_masters.csv. Edit Reviewed master and Comment in mappings.csv; source DICOM files are not modified.</p><input id="query" aria-label="Search" placeholder="Search case or structure"><select id="status" aria-label="Assignment status"><option value="">All structures</option value="open">Open assignments</option><option value="proposed">Automatic proposals</option></select></header><table><thead><tr><th>Case</th><th>Source group</th><th>Structure</th><th>Volume [cc]</th><th>Proposal</th><th>Reason</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table><script>function filter(){const q=document.getElementById('query').value.toLowerCase(),s=document.getElementById('status').value;document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q)||(s&&!r.classList.contains(s)))}document.getElementById('query').oninput=filter;document.getElementById('status').onchange=filter;</script></html>'''
    document=document.replace('</style>','tr.extra td:nth-last-child(-n+2){background:#e5e7eb;color:#263442}</style>').replace('<option value="proposed">Automatic proposals</option>','<option value="proposed">Automatic proposals</option><option value="extra">Extra structures</option>')
    (output/'review.html').write_text(document,encoding='utf-8')

def main():
    p=argparse.ArgumentParser(description='Local VOI name proposals. Never changes DICOM.')
    p.add_argument('--input',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--mode',choices=['exact','llm'],default='exact');p.add_argument('--model')
    p.add_argument('--endpoint',default='http://127.0.0.1:11434')
    args=p.parse_args()
    if args.output.exists():p.error('Use a new output directory. Keep previous reviews intact.')
    rows=load_rows(args.input);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.mkdir(exist_ok=False)
    metadata=None
    if args.mode=='llm':
        if not args.model:p.error('--model is required for llm mode')
        proposals,metadata=predict_names([r['name'] for r in rows],args.model,args.output/'cache',args.endpoint)
    else:proposals=exact_proposals(rows)
    result=enforce_unique(rows,proposals);export_review(args.output,result)
    from . import __version__
    receipt={'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'version':__version__,'mode':args.mode,'model':metadata,'options':OPTIONS,
        'input_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest(),'prompt_sha256':hashlib.sha256(PROMPT.encode()).hexdigest(),
        'rows':len(rows),'cases':len({r['case'] for r in rows}),'automatic_proposals':sum(r['automatic_master']!='x' for r in result),
        'code_sha256':hashlib.sha256(Path(__file__).with_name('core.py').read_bytes()).hexdigest(),
        'vocabulary_sha256':hashlib.sha256(Path(__file__).with_name('vocabulary.json').read_bytes()).hexdigest(),
        'extra_structures':sum(bool(r.get('extra_structure')) for r in result),
        'duplicate_master_assignments':0,'clinical_validation':False}
    (args.output/'run.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as exc:sys.exit(str(exc))
