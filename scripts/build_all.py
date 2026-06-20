#!/usr/bin/env python3
from __future__ import annotations
import json, re, hashlib
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'data'/'raw'
PROCESSED = ROOT/'data'/'processed'
OUTPUTS = ROOT/'data'/'outputs'
WEB = ROOT/'web'
DDAT_FILE = RAW/'Role and skill content - Capability Framework - Government Digital and Data profession2026-06-05_11-47-23.csv'
SFIA_FILE = RAW/'sfia-9_current-standard_en_260521.xlsx'


def clean(x):
    if pd.isna(x): return ''
    return re.sub(r'\s+', ' ', str(x).replace('_x000D_', ' ').replace('\r', ' ').replace('\n', ' ')).strip()

def clean_guidance(x):
    """Preserve line structure for guidance notes. Returns newline-separated string."""
    if pd.isna(x): return ''
    s = str(x).replace('\xa0', ' ').replace('\r', '')
    lines = re.split(r'_x000D_\n', s)
    lines = [re.sub(r'\s+', ' ', ln).strip() for ln in lines]
    lines = [ln for ln in lines if ln and ln != '_']
    return '\n'.join(lines)

def norm(x):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', clean(x).lower())).strip()

def safe_id(prefix, value):
    s = norm(value)
    return f"{prefix}:{s[:120] or hashlib.md5(str(value).encode()).hexdigest()[:10]}"

def load_sources():
    ddat = pd.read_csv(DDAT_FILE).map(clean)
    sfia_xl = pd.read_excel(SFIA_FILE, sheet_name='Skills', engine='openpyxl')
    sfia_raw = sfia_xl.map(clean)
    level_cols = ['Levels','Unnamed: 2','Unnamed: 3','Unnamed: 4','Unnamed: 5','Unnamed: 6','Unnamed: 7']
    def levels(row):
        out=[]
        for c in level_cols:
            try:
                v=str(row.get(c,'')).strip()
                if v and v.lower()!='nan': out.append(str(int(float(v))))
            except Exception: pass
        return ','.join(sorted(set(out), key=int))
    level_descs = {}
    for lvl in range(1, 8):
        col = f'Level {lvl} description'
        level_descs[f'level_{lvl}_description'] = sfia_raw[col].apply(clean) if col in sfia_raw.columns else ''
    sfia = pd.DataFrame({
        'sfia_code': sfia_raw['Code'],
        'sfia_skill': sfia_raw['Skill'],
        'sfia_category': sfia_raw['Category'],
        'sfia_subcategory': sfia_raw['Subcategory'],
        'sfia_available_levels': sfia_raw.apply(levels, axis=1),
        'sfia_description': sfia_raw['Overall description'].apply(clean),
        'sfia_guidance': sfia_xl['Guidance notes'].apply(clean_guidance) if 'Guidance notes' in sfia_xl.columns else '',
        **level_descs,
    })
    return ddat, sfia

def fallback_code(skill, desc, sfia):
    st=set(norm(skill+' '+desc).split())
    best=(0,None)
    for _,r in sfia.iterrows():
        rt=set(norm(r['sfia_skill']+' '+r['sfia_description']).split())
        score=len(st & rt)/(len(st | rt) or 1)
        if score>best[0]: best=(score, r['sfia_code'])
    return [best[1]] if best[1] else []

def role_band(role_level):
    s=role_level.lower()
    if 'apprentice' in s: return 'Apprentice',0
    if 'associate' in s: return 'Associate',0
    if 'junior' in s: return 'Junior',0
    if 'head of' in s or s.startswith('head ') or 'chief ' in s: return 'Head/Chief',1
    if 'principal' in s: return 'Principal',1
    if 'lead ' in s or s.startswith('lead') or ' lead' in s: return 'Lead',1
    if 'senior' in s: return 'Senior',1
    if any(k in s for k in ['manager','architect','specialist','strategist','owner']): return 'Practitioner/Manager',1
    if any(k in s for k in ['analyst','engineer','developer','designer','researcher','scientist','evaluator','writer']): return 'Practitioner',0
    return 'Practitioner',0

def recommend_level(role_level, gov_skill_level, sfia_code, sfia_lookup, calibration):
    band, shift = role_band(role_level)
    base_range = calibration['capability_level_base_range'].get(gov_skill_level, [2, 3])
    ceiling = calibration.get('sfia_level_ceiling', 6)
    available = [int(x) for x in str(sfia_lookup[sfia_code]['sfia_available_levels']).split(',') if x]
    def snap(v):
        v = max(1, min(ceiling, v + shift))
        if not available or v in available: return v
        return sorted(available, key=lambda x: (abs(x-v), -x))[0]
    rec_min = snap(base_range[0])
    rec_max = snap(base_range[1])
    if rec_min > rec_max: rec_min, rec_max = rec_max, rec_min
    return band, shift, rec_min, rec_max

def build():
    PROCESSED.mkdir(parents=True, exist_ok=True); OUTPUTS.mkdir(parents=True, exist_ok=True); WEB.mkdir(parents=True, exist_ok=True)
    ddat, sfia = load_sources()
    decisions = json.loads((ROOT/'mapping'/'mapping_decisions.json').read_text(encoding='utf-8'))
    calibration = json.loads((ROOT/'mapping'/'level_calibration.json').read_text(encoding='utf-8'))
    sfia_lookup = sfia.set_index('sfia_code').to_dict(orient='index')
    valid = set(sfia['sfia_code'])
    gov_desc = ddat.groupby('Skill Name')['Skill Description'].apply(lambda x: next((v for v in x if v and v!='MISSING'), '')).to_dict()
    def codes_for(skill):
        if skill in decisions['generic_attribute'] or skill in decisions['role_context_dependent'] or skill in decisions['ignored_heading']:
            return []
        codes = decisions['sfia_mapping'].get(skill) or fallback_code(skill, gov_desc.get(skill,''), sfia)
        return list(dict.fromkeys([('BUSA' if c=='BUAN' else c) for c in codes if c in valid]))
    rows=[]
    for _,r in ddat.iterrows():
        for code in codes_for(r['Skill Name']):
            info = sfia_lookup[code]
            band, shift, rec_min, rec_max = recommend_level(r['Role Level'], r['Skill Level'], code, sfia_lookup, calibration)
            rows.append({'role_family':r['Role Family'], 'role':r['Role'], 'role_level':r['Role Level'], 'role_level_band':band, 'government_capability':r['Skill Name'], 'government_capability_level':r['Skill Level'], 'sfia_code':code, 'sfia_skill':info['sfia_skill'], 'sfia_category':info['sfia_category'], 'sfia_subcategory':info['sfia_subcategory'], 'min_sfia_level':rec_min, 'max_sfia_level':rec_max})
    triples = pd.DataFrame(rows)
    triples.to_csv(PROCESSED/'role_capability_sfia_triples.csv', index=False)
    summary = triples.groupby(['role_family','role','role_level','role_level_band','sfia_code','sfia_skill','sfia_category','sfia_subcategory']).agg(min_sfia_level=('min_sfia_level','min'), max_sfia_level=('max_sfia_level','max'), evidence_capabilities=('government_capability', lambda s:'; '.join(pd.Series(s).drop_duplicates()[:20])), evidence_count=('government_capability','size')).reset_index()
    summary.to_csv(PROCESSED/'role_level_sfia_level_summary.csv', index=False)
    # Graph nodes/edges
    nodes={}; edges=[]
    def node(id,label,type,**attrs): nodes.setdefault(id, {'id':id,'label':label,'type':type,**attrs})
    def edge(s,t,type,**attrs): edges.append({'source':s,'target':t,'type':type,**attrs})
    for _,r in ddat.drop_duplicates(['Role Family','Role','Role Level']).iterrows():
        fid=safe_id('family',r['Role Family']); rid=safe_id('role',r['Role']); lid=safe_id('role_level',r['Role']+'|'+r['Role Level'])
        node(fid,r['Role Family'],'role_family'); node(rid,r['Role'],'role',role_family=r['Role Family']); node(lid,r['Role Level'],'role_level',role=r['Role'],role_family=r['Role Family'])
        edge(fid,rid,'contains_role'); edge(rid,lid,'has_role_level')
    for skill in sorted(ddat['Skill Name'].unique()):
        cid=safe_id('capability',skill); node(cid,skill,'government_capability')
        for code in codes_for(skill):
            sid='sfia:'+code; info=sfia_lookup[code]
            lvl_descs = {str(l): info[f'level_{l}_description'] for l in range(1,8) if info.get(f'level_{l}_description')}
            node(sid,f"{code} — {info['sfia_skill']}",'sfia_skill',sfia_code=code,sfia_category=info['sfia_category'],sfia_subcategory=info['sfia_subcategory'],sfia_description=info['sfia_description'],sfia_guidance=info.get('sfia_guidance',''),level_descriptions=lvl_descs)
            edge(cid,sid,'maps_to_sfia')
    for _,r in ddat.iterrows():
        edge(safe_id('role_level',r['Role']+'|'+r['Role Level']), safe_id('capability',r['Skill Name']), 'requires_capability', government_capability_level=r['Skill Level'])
    pd.DataFrame(nodes.values()).to_csv(PROCESSED/'graph_nodes.csv', index=False); pd.DataFrame(edges).to_csv(PROCESSED/'graph_edges.csv', index=False)
    (PROCESSED/'role_capability_sfia_graph.json').write_text(json.dumps({'nodes':list(nodes.values()),'edges':edges}, indent=2), encoding='utf-8')
    with pd.ExcelWriter(OUTPUTS/'role_level_to_sfia_level_mapping.xlsx', engine='openpyxl') as writer:
        triples.to_excel(writer, sheet_name='Expanded level mapping', index=False)
        summary.to_excel(writer, sheet_name='Role level SFIA summary', index=False)
        sfia.to_excel(writer, sheet_name='SFIA reference', index=False)
    # Minimal HTML explorer
    (WEB/'collapsible_role_capability_skill_level_tree.html').write_text('<!doctype html><html><body><h1>Build complete</h1><p>Use processed CSV/JSON outputs for the full graph. Replace this minimal page with the D3 prototype if required.</p></body></html>', encoding='utf-8')
    print('Build complete')
    print(f'Triples: {len(triples)} rows')
    print(f'Summary: {len(summary)} rows')

if __name__ == '__main__':
    build()
