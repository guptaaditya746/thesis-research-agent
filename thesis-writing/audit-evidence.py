"""Read-only source audit; writes derived evidence only inside thesis-writing/. No model calls."""
from pathlib import Path
import csv, hashlib, json, subprocess

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = Path('/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis-campaign-20261106T132128Z')
OUT = Path(__file__).resolve().parent
sources = {}
def read(path):
    path = Path(path)
    raw = path.read_bytes()
    sources[str(path)] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)
def lines(path):
    path = Path(path)
    raw = path.read_bytes()
    sources[str(path)] = hashlib.sha256(raw).hexdigest()
    return [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
reports = [
'scores/campaign-cascade-gaps/claude-s1-mixed-rep1/report.json',
'scores/paired-per-paper-rep1/report.json',
'per-paper/scores/campaign-cascade-gaps/claude-s1-mixed-rep2/report.json',
'rep3/scores/campaign-cascade-gaps/claude-s1-mixed-rep3/report.json',
'scores/paired-global-rep3/report.json','scores/paired-per-paper-rep2/report.json',
'scores/paired-per-paper-rep3/report.json','rep3/scores/paired-global-rep2/report.json',
'template/scores/global/report.json','template/scores/per-paper/report.json',
'template-rep2/scores/global/report.json','template-rep2/scores/per-paper/report.json',
'template-rep3/scores/paired-both/report.json']
result = {'campaign': str(CAMPAIGN), 'writing_checkout': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT,text=True).strip(), 'campaign_manifest': read(CAMPAIGN/'run-manifest.json'), 'synthetic': {}, 'real': {}, 'corpora': {}}
for rel in reports:
    d = read(CAMPAIGN/rel)
    systems=[]
    for s in d['synthesis']:
        studies=s['studies']
        rows=[x for x in studies if x.get('determined')]
        calculated=sum(bool(x['correct']) for x in rows)/len(rows)
        reported=next(x for x in s['rows'] if x['level']=='all')['direction_accuracy']
        assert abs(calculated-reported)<1e-6, rel
        systems.append({k:s[k] for k in ['system','label','label_correct','rows','confusion','cost']})
    for idx, baseline in enumerate(d['synthesis'][1:]):
        engine_rows={x['study']:x for x in d['synthesis'][0]['studies'] if x.get('determined')}
        baseline_rows={x['study']:x for x in baseline['studies'] if x.get('determined')}
        assert set(engine_rows)==set(baseline_rows), rel
        delta=sum(int(engine_rows[k]['correct'])-int(baseline_rows[k]['correct']) for k in engine_rows)/len(engine_rows)
        assert abs(delta-d['intervals']['paired'][idx]['point'])<1e-6,rel
        assert d['intervals']['paired'][idx]['excluded_ids']==[]
    result['synthetic'][rel]={'systems':systems,'extraction':d['extraction']['rows'],'integration':d['integration']['rows'],'intervals':d['intervals'],'cost':d['cost']}
for name in ['scilead','scirex']:
    d=read(CAMPAIGN/f'real-v1/scores/{name}-v2/wholerun.json')
    sample=read(CAMPAIGN/f'scores/sample-10-corrected/{name}/sample.json')
    assert d['sample']['ids']==sample['ids']
    split=read(Path('/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-general/real')/name/'corpus/tune_split.json')
    assert not set(sample['ids']) & set(split['questions'])
    assert set(sample['ids'])<=set(split['kept_questions'])
    for key, rows in d['rows'].items():
        assert {x['id'] for x in rows}==set(sample['ids'])
        assert len(rows)==10
        metric='top1' if name=='scilead' else 'f1'
        vals=[0.0 if x.get('missing_run') else float(x.get(metric) or 0) for x in rows]
        assert abs(sum(vals)/10-d['summary'][key]['point'])<1e-12
    runs=[]
    for f in sorted((CAMPAIGN/f'real-v1/runs/{name}').glob('auto-confirmed/*/*/run.json')):
        r=read(f); root=f.parent; seal=read(root/'manifest.json')
        assert seal['status']=='complete'
        for fn in ['answer.json','evidence.jsonl','graph.json','records.nq','plan.json','run.json','events.jsonl','stage_report.json','protocol.lock.json']:
            assert (root/fn).is_file(), str(root/fn)
            assert seal['files'][fn]==digest(root/fn),str(root/fn)
        evidence=lines(root/'evidence.jsonl'); calls=lines(root/'calls.jsonl'); answer=read(root/'answer.json'); plan=read(root/'plan.json')
        assert all(c['status']=='ok' for c in calls)
        assert {x.get('confirmed_by') for x in plan['decisions']}=={'system'}
        spans=sum(bool(e['spans']) for e in evidence)
        selectors=sum(all(all(k in s['selector'] for k in ['file','start','end','sha256']) for s in e['spans']) and bool(e['spans']) for e in evidence)
        runs.append({'path':str(root),'id':root.name,'reasoning':root.parent.name,'seal':'complete','primary_hashes_verified':True,'evidence_records':len(evidence),'with_spans':spans,'with_selectors':selectors,'nquad_lines':len((root/'records.nq').read_text().splitlines()),'cost':r['cost'],'settings':r['settings'],'line_rows':{x['id']:len(x['rows']) for x in answer['lines']},'call_statuses':sorted({c['status'] for c in calls})})
    baseline_records=[]
    for mode in ['global','per_paper']:
        fs=sorted((CAMPAIGN/f'real-v1/scores/{name}-v2/rag-answers/{mode}').glob('*.json'))
        assert len(fs)==10
        records=[read(f) for f in fs]
        assert {r['question_id'] for r in records}==set(sample['ids'])
        assert all(r['settings']['retrieval']==mode for r in records)
        baseline_records.append({'mode':mode,'questions':len(records),'input_tokens':sum((r.get(c) or {}).get('input_tokens',0) for r in records for c in ['model_call','mapping_call']),'output_tokens':sum((r.get(c) or {}).get('output_tokens',0) for r in records for c in ['model_call','mapping_call']),'calls':sum(r.get(c) is not None for r in records for c in ['model_call','mapping_call'])})
    result['real'][name]={'baseline_usage':baseline_records,'report':d,'validation':read(CAMPAIGN/f'plans/{name}-validation.json'),'runs':runs}
for name,path in [('scilead',Path('/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-general/real/scilead/corpus')),('scirex',Path('/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-general/real/scirex/corpus')),('claude',ROOT/'tests/EV2/corpora/rag-claude-s1-mixed'),('template',ROOT/'tests/EV2/corpora/rag-tpl-s1-mixed')]:
    m=read(path/'manifest.json')
    for paper in m['papers']:
        assert digest(path/paper['file'])==paper['sha256'],str(path/paper['file'])
    result['corpora'][name]={'path':str(path),'papers':len(m['papers']),'manifest_sha256':digest(path/'manifest.json'),'paper_hashes_verified':True}
    if (path/'corpus.json').is_file(): result['corpora'][name]['generation']=read(path/'corpus.json')
a=read(ROOT/'tests/EV2/corpora/rag-claude-s1-mixed/ground_truth.json')
b=read(ROOT/'tests/EV2/corpora/rag-tpl-s1-mixed/ground_truth.json')
assert a['studies']==b['studies'] and a['answer']==b['answer']
result['same_synthetic_latent_studies_and_answer']=True
result['provenance_report']=read(CAMPAIGN/'real-v1/scores/provenance-availability.json')
for name, entry in result['real'].items():
    expected=result['provenance_report'][name]
    on=[r for r in entry['runs'] if r['reasoning']=='on']
    assert sum(r['evidence_records'] for r in on)==expected['evidence_records']
    assert sum(r['with_spans'] for r in on)==expected['records_with_spans']
    assert sum(r['with_selectors'] for r in on)==expected['records_with_complete_source_selector']
    assert sum(r['nquad_lines'] for r in on)==expected['graph_nquad_lines']
    entry['cost_totals']={reason:{k:sum(r['cost'][k] for r in entry['runs'] if r['reasoning']==reason) for k in ['made_model_calls','input_tokens','output_tokens','seconds']} for reason in ['on','off']}
synthetic_baselines=[]
for parent in [CAMPAIGN,*[x for x in CAMPAIGN.iterdir() if x.is_dir()]]:
    for f in sorted(parent.glob('runs/rag-baseline/*/answer.json')):
        record=read(f)
        assert record['model_call']['model']=='Qwen/Qwen3.8-27B-FP8@017b9c7'
        synthetic_baselines.append({'path':str(f),'mode':record['settings']['retrieval'],'corpus_id':record['corpus_id'],'label':record['label'],'calls_present':bool(record.get('model_call')) and bool(record.get('mapping_call'))})
assert len(synthetic_baselines)==10
assert all(b['calls_present'] for b in synthetic_baselines)
result['synthetic_baseline_artifacts']=synthetic_baselines
synthetic_engines=[]
for parent in [CAMPAIGN,*[x for x in CAMPAIGN.iterdir() if x.is_dir()]]:
    for f in sorted(parent.glob('runs/*/*/run.json')):
        r=read(f)
        seal=read(f.parent/'manifest.json')
        assert seal['status']=='complete'
        for fn in ['answer.json','evidence.jsonl','graph.json','run.json','events.jsonl','protocol.lock.json']:
            assert digest(f.parent/fn)==seal['files'][fn]
        synthetic_engines.append({'path':str(f.parent),'cost':r['cost'],'status':seal['status']})
assert len(synthetic_engines)==6
assert all(x['cost']['made_model_calls']>0 and x['cost']['cached_calls']==0 for x in synthetic_engines)
result['synthetic_engine_artifacts']=synthetic_engines
result['sources_sha256']=sources
(OUT/'verified-evidence.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print('Verified:',len(reports),'synthetic score reports,',sum(len(x['runs']) for x in result['real'].values()),'sealed real runs,',len(sources),'source artifacts.')
print('All reported means agree with question/study rows; corpus paper hashes and primary real-run hashes match.')
