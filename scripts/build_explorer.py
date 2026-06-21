#!/usr/bin/env python3
"""Builds the collapsible D3 explorer HTML with embedded data."""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_all import safe_id

import pandas as pd

def build_tree():
    g = json.loads((ROOT / 'data' / 'processed' / 'role_capability_sfia_graph.json').read_text(encoding='utf-8'))
    summary = pd.read_csv(ROOT / 'data' / 'processed' / 'role_level_sfia_level_summary.csv')

    # Build gov capability description lookups from raw CSV
    raw_csv = next((ROOT / 'data' / 'raw').glob('*.csv'))
    raw_df = pd.read_csv(raw_csv, encoding='utf-8-sig')
    cap_descriptions: dict[str, str] = {}
    cap_level_descriptions: dict[tuple, str] = {}
    for _, row in raw_df.iterrows():
        name = str(row.get('Skill Name', '')).strip()
        desc = str(row.get('Skill Description', '')).strip()
        if name and desc and desc != 'nan' and name.lower() not in cap_descriptions:
            cap_descriptions[name.lower()] = desc
        lvl  = str(row.get('Skill Level', '')).strip()
        ldesc = str(row.get('Skill Level Description', '')).strip()
        key = (name.lower(), lvl.lower())
        if name and lvl and ldesc and ldesc != 'nan' and key not in cap_level_descriptions:
            cap_level_descriptions[key] = ldesc

    nodes = {n['id']: n for n in g['nodes']}
    edges = g['edges']

    # Build adjacency
    children_of: dict[str, list[str]] = {}
    for e in edges:
        children_of.setdefault(e['source'], []).append(e['target'])

    # requires_capability edges carry government_capability_level
    cap_level_for: dict[tuple, str] = {}
    for e in edges:
        if e['type'] == 'requires_capability':
            cap_level_for[(e['source'], e['target'])] = e.get('government_capability_level', '')

    # Build summary lookup: (role_level_id, sfia_code) -> info
    level_lookup: dict[tuple, dict] = {}
    for _, r in summary.iterrows():
        rl_id = safe_id('role_level', str(r['role']) + '|' + str(r['role_level']))
        key = (rl_id, str(r['sfia_code']))
        level_lookup[key] = {
            'min': int(r['min_sfia_level']),
            'max': int(r['max_sfia_level']),
            'evidence': str(r['evidence_capabilities']),
            'count': int(r['evidence_count']),
            'band': str(r['role_level_band']),
        }

    def sfia_node_for_role_level(rl_id: str, sfia_id: str) -> dict:
        n = nodes[sfia_id]
        code = n.get('sfia_code', sfia_id.replace('sfia:', ''))
        info = level_lookup.get((rl_id, code), {})
        return {
            'id': f"{rl_id}|{sfia_id}",
            'name': n['label'],
            'type': 'sfia_skill',
            'sfia_code': code,
            'sfia_category': n.get('sfia_category', ''),
            'sfia_subcategory': n.get('sfia_subcategory', ''),
            'sfia_description': n.get('sfia_description', ''),
            'sfia_guidance': n.get('sfia_guidance', ''),
            'level_descriptions': n.get('level_descriptions', {}),
            'min': info.get('min'),
            'max': info.get('max'),
            'evidence': info.get('evidence', ''),
            'count': info.get('count', 0),
        }

    def capability_node(rl_id: str, cap_id: str) -> dict:
        n = nodes[cap_id]
        gov_level = cap_level_for.get((rl_id, cap_id), '')
        sfia_children = [
            sfia_node_for_role_level(rl_id, s)
            for s in children_of.get(cap_id, [])
            if nodes.get(s, {}).get('type') == 'sfia_skill'
        ]
        return {
            'id': f"{rl_id}|{cap_id}",
            'name': n['label'],
            'type': 'government_capability',
            'gov_level': gov_level,
            'gov_level_description': cap_level_descriptions.get((n['label'].lower(), gov_level.lower()), ''),
            'broadly_accepted': len(sfia_children) == 0,
            'description': cap_descriptions.get(n['label'].lower(), ''),
            'children': sfia_children,
        }

    def role_level_node(rl_id: str) -> dict:
        n = nodes[rl_id]
        cap_ids = [t for t in children_of.get(rl_id, []) if nodes.get(t, {}).get('type') == 'government_capability']
        caps = sorted(
            [capability_node(rl_id, c) for c in cap_ids],
            key=lambda x: (not x['broadly_accepted'], x['name'].lower())
        )
        # Also determine band from summary
        band = ''
        for (rid2, _), info in level_lookup.items():
            if rid2 == rl_id:
                band = info.get('band', '')
                break
        return {
            'id': rl_id,
            'name': n['label'],
            'type': 'role_level',
            'band': band,
            'children': caps,
        }

    BAND_ORDER = {
        'Apprentice': 0, 'Junior': 1, 'Associate': 2,
        'Practitioner': 3, 'Practitioner/Manager': 4,
        'Senior': 5, 'Principal': 6, 'Lead': 7, 'Head/Chief': 8,
    }

    def role_node(role_id: str) -> dict:
        n = nodes[role_id]
        rl_ids = list(dict.fromkeys(t for t in children_of.get(role_id, []) if nodes.get(t, {}).get('type') == 'role_level'))
        role_levels = [role_level_node(rl) for rl in rl_ids]
        role_levels.sort(key=lambda x: (BAND_ORDER.get(x.get('band', ''), 99), x.get('name', '').lower()))
        return {
            'id': role_id,
            'name': n['label'],
            'type': 'role',
            'role_family': n.get('role_family', ''),
            'role_levels': role_levels,
            'children': role_levels[0]['children'] if role_levels else [],
        }

    families = [n for n in g['nodes'] if n['type'] == 'role_family']
    tree_children = []
    for f in sorted(families, key=lambda x: x['label']):
        fid = f['id']
        role_ids = list(dict.fromkeys(t for t in children_of.get(fid, []) if nodes.get(t, {}).get('type') == 'role'))
        tree_children.append({
            'id': fid,
            'name': f['label'],
            'type': 'role_family',
            'children': [role_node(r) for r in role_ids],
        })

    return {'id': 'root', 'name': 'Government Digital and Data', 'type': 'root', 'children': tree_children}


def main():
    import time
    cache_bust = str(int(time.time()))

    tree = build_tree()

    data_path = ROOT / 'web' / 'explorer_data.json'
    data_path.write_text(json.dumps(tree, ensure_ascii=False), encoding='utf-8')
    print(f'Data: {data_path.stat().st_size / 1024:.0f} KB')

    # HTML is a plain string — NO f-string, so CSS/JS braces need no escaping.
    # All JS lives in explorer.js to keep this file brace-collision-free forever.
    html = (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<title>GDaD → SFIA 9 Explorer</title>\n'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>\n'
        '<style>\n'
        ':root {\n'
        '  --ink-black:       #001219;\n'
        '  --golden-orange:   #c97a00;\n'
        '  --brown-red:       #9b2226;\n'
        '  --sage-light:      #bad8c4;\n'
        '  --sage-mid:        #60a478;\n'
        '  --sage-dark:       #1e6038;\n'
        '  --stone-light:     #f3f1ee;\n'
        '  --stone-mid:       #d8d2c8;\n'
        '  --stone-dark:      #b0a898;\n'
        '  --accent:          #3a8455;\n'
        '  --text:            #1e2420;\n'
        '  --text-mid:        #3a5a48;\n'
        '  --text-light:      #6a8570;\n'
        '  --border:          #d8d2c8;\n'
        '  --bg:              #ffffff;\n'
        '  --panel-bg:        #ffffff;\n'
        '}\n'
        '* { box-sizing: border-box; margin: 0; padding: 0; }\n'
        'html, body { height: 100%; }\n'
        'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); display: flex; flex-direction: column; }\n'
        '#header { background: #1e6038; color: #fff; padding: 10px 22px; display: flex; align-items: center; gap: 24px; flex-wrap: wrap; flex-shrink: 0; border-bottom: 3px solid #60a478; }\n'
        '.hdr-brand { display: flex; flex-direction: column; justify-content: center; gap: 2px; }\n'
        '#header h1 { display: flex; align-items: center; gap: 10px; font-family: "Gill Sans", "Gill Sans MT", Calibri, sans-serif; font-size: 26px; font-weight: 700; white-space: nowrap; letter-spacing: .02em; line-height: 1; }\n'
        '.hdr-badge { background: #d8d2c8; color: #1e4030; font-size: 0.46em; font-weight: 800; letter-spacing: .1em; padding: 0.22em 0.6em; border-radius: 0.3em; text-transform: uppercase; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; vertical-align: middle; flex-shrink: 0; }\n'
        '.hdr-subtitle { font-size: 11px; color: rgba(255,255,255,0.6); letter-spacing: .08em; text-transform: uppercase; font-weight: 500; white-space: nowrap; }\n'
        '.search-wrap { position: relative; display: flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.35); border-radius: 6px; padding: 5px 12px; margin-left: auto; }\n'
        '.search-wrap:focus-within { background: rgba(255,255,255,0.28); border-color: rgba(255,255,255,0.7); }\n'
        '#search-dropdown { position: absolute; top: calc(100% + 4px); left: 0; right: 0; background: #fff; border: 1px solid var(--border); border-radius: 8px; box-shadow: 0 6px 20px rgba(0,18,25,0.14); z-index: 1000; overflow: hidden; display: none; min-width: 320px; }\n'
        '#search-dropdown.open { display: block; }\n'
        '.sd-item { display: flex; align-items: center; gap: 8px; padding: 8px 12px; cursor: pointer; font-size: 14px; color: var(--text); border-bottom: 1px solid #f5efd5; }\n'
        '.sd-item:last-child { border-bottom: none; }\n'
        '.sd-item:hover, .sd-item.sd-focus { background: #f3f1ee; }\n'
        '.sd-badge { font-size: 10px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; flex-shrink: 0; white-space: nowrap; }\n'
        '.sd-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }\n'
        '.sd-empty { padding: 10px 12px; font-size: 13px; color: var(--text-light); }\n'
        '#search { border: none; background: none; outline: none; font-size: 15px; width: 380px; color: #fff; }\n'
        '#search::placeholder { color: rgba(255,255,255,0.55); }\n'
        '#search:focus { outline: none; }\n'
        'button { padding: 6px 13px; border-radius: 6px; border: 1px solid rgba(0,18,25,0.25); font-size: 14px; cursor: pointer; background: rgba(255,255,255,0.35); color: #001219; transition: background .15s, border-color .15s; }\n'
        'button:hover { background: #eeecea; border-color: var(--stone-dark); }\n'
        '#button-column button { background: #3a8455; color: #fff; border: 1px solid #2d6642; font-size: 13px; font-weight: 600; }\n'
        '#button-column button:hover { background: #2d6642; border-color: #226038; }\n'
        '#button-column button.snap-active { background: #1e6038; border-color: #144828; color: #bad8c4; }\n'
        '#button-column button.snap-active:hover { background: #144828; }\n'
        '#control-row { display: flex; flex-shrink: 0; border-bottom: 2px solid var(--border); }\n'
        '#filter-column { flex: 1; display: flex; flex-direction: column; min-width: 0; }\n'
        '.filter-row { display: flex; align-items: center; background: #f5f8fa; border-bottom: 1px solid var(--border); min-height: 34px; padding: 4px 0; }\n'
        '.filter-row:last-child { border-bottom: none; }\n'
        '.filter-label { width: 110px; min-width: 110px; padding-left: 22px; font-size: 11px; font-weight: 700; letter-spacing: .07em; text-transform: uppercase; color: var(--text-light); white-space: nowrap; flex-shrink: 0; }\n'
        '.filter-chips { display: flex; gap: 5px; flex-wrap: wrap; align-items: center; flex: 1; padding: 2px 8px 2px 0; }\n'
        '#button-column { width: 500px; min-width: 500px; flex-shrink: 0; border-left: 1px solid var(--border); background: #f5f8fa; display: flex; flex-direction: column; align-items: flex-end; justify-content: center; gap: 6px; padding: 8px 18px; }\n'
        '#button-column button { min-width: 170px; text-align: center; }\n'
        '.filter-chip { padding: 3px 11px; border-radius: 20px; border: 1px solid var(--border); font-size: 12px; font-weight: 600; cursor: pointer; background: #fff; color: var(--text-mid); transition: background .12s, border-color .12s; white-space: nowrap; }\n'
        '.family-chip { padding: 3px 11px; border-radius: 20px; border: 1px solid var(--border); font-size: 12px; font-weight: 600; cursor: pointer; background: #fff; color: var(--text-mid); transition: background .12s, border-color .12s; white-space: nowrap; }\n'
        '.family-chip:hover { background: #e2efe8; border-color: #8ec0a0; }\n'
        '.family-chip--active { background: #8ec0a0; border-color: #8ec0a0; color: #1e4030; font-weight: 700; }\n'
        '.role-chip { padding: 3px 11px; border-radius: 20px; border: 1px solid var(--border); font-size: 12px; font-weight: 600; cursor: pointer; background: #fff; color: var(--text-mid); transition: background .12s, border-color .12s; white-space: nowrap; }\n'
        '.role-chip:hover { background: #c8e4d0; border-color: #3a8455; }\n'
        '.role-chip--active { background: #3a8455; border-color: #3a8455; color: #fff; font-weight: 700; }\n'
        '.band-chip { padding: 3px 11px; border-radius: 20px; border: 1px solid var(--border); font-size: 12px; font-weight: 600; cursor: pointer; background: #fff; color: var(--text-mid); transition: background .12s, border-color .12s; white-space: nowrap; }\n'
        '.band-chip:hover { background: #b0d4bc; border-color: #1e6038; }\n'
        '.band-chip--active { background: #1e6038; border-color: #1e6038; color: #fff; font-weight: 700; }\n'
        '.band-chip--unavailable { opacity: 0.25; pointer-events: none; }\n'
        '#main { display: flex; flex: 1; min-height: 0; }\n'
        '#tree-panel { flex: 1; overflow: hidden; position: relative; background: var(--bg); }\n'
        '#tree-svg { display: block; width: 100%; height: 100%; }\n'
        '#detail-panel { width: 500px; flex-shrink: 0; background: var(--panel-bg); border-left: 1px solid var(--border); overflow-y: auto; padding: 18px; display: flex; flex-direction: column; gap: 12px; }\n'
        '#detail-panel.hidden { display: none; }\n'
        '.detail-type { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: var(--golden-orange); }\n'
        '.detail-title { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 25px; font-weight: 600; line-height: 1.2; color: var(--text); padding: 4px 0 2px; }\n'
        '.detail-family { font-size: 17px; font-weight: 500; color: var(--text-mid); line-height: 1.4; }\n'
        '.detail-section { border-top: 1px solid var(--border); padding-top: 10px; padding-bottom: 6px; }\n'
        '.detail-section h3 { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--text-light); margin-bottom: 7px; }\n'
        '.sfia-chip { display: flex; align-items: center; gap: 7px; background: #f8f7f5; border: 1px solid #e4dfd8; border-radius: 7px; padding: 5px 10px; margin: 3px 0; font-size: 14px; color: var(--text); }\n'
        '.sfia-chip .code { font-weight: 700; color: var(--accent); font-size: 13px; white-space: nowrap; }\n'
        '.nav-code { background: none; border: none; padding: 0; font: inherit; cursor: pointer; }\n'
        '.nav-code:hover { text-decoration: underline; opacity: 0.75; }\n'
        '.range-badge { display: inline-flex; align-items: center; gap: 3px; flex-shrink: 0; }\n'
        '.lvl-pip { display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 50%; color: #fff; font-size: 12px; font-weight: 700; }\n'
        '.range-sep { font-size: 13px; color: var(--text-light); font-weight: 400; }\n'
        '.cap-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 14px; border-bottom: 1px solid #f5edd8; color: var(--text); }\n'
        '.gov-level-tag { font-size: 12px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background: #e2efe8; color: #1e4030; white-space: nowrap; flex-shrink: 0; }\n'
        '.cap-chip { display: flex; align-items: center; gap: 7px; background: #f3f1ee; border: 1px solid #d8d2c8; border-radius: 7px; padding: 5px 10px; margin: 3px 0; font-size: 14px; color: var(--text); }\n'
        '.cap-chip--broad { background: #eeecea; border-color: #cdc8c0; }\n'
        '.cap-group { margin-bottom: 5px; }\n'
        '.skills-rail { margin-left: 9px; padding-left: 10px; border-left: 2px solid #d8d2c8; border-radius: 0; margin-top: 3px; }\n'
        '.nav-chip { display: flex; align-items: center; gap: 6px; padding: 6px 10px; margin: 2px 0; border-radius: 6px; font-size: 15px; cursor: pointer; color: var(--text); background: #f3f1ee; border: 1px solid #d8d2c8; transition: background .12s, border-color .12s; }\n'
        '.nav-chip:hover { background: #eeecea; border-color: #c8c0b4; }\n'
        '.gov-level-pip { display: inline-flex; align-items: center; justify-content: center; min-width: 22px; height: 20px; border-radius: 4px; font-size: 11px; font-weight: 700; letter-spacing: .02em; flex-shrink: 0; padding: 0 4px; }\n'
        '.gov-lvl-awareness    { background: #e2efe8; color: #1e4030; }\n'
        '.gov-lvl-working      { background: #8ec0a0; color: #fff; }\n'
        '.gov-lvl-practitioner { background: #3a8455; color: #fff; }\n'
        '.gov-lvl-expert       { background: #0a4025; color: #fff; }\n'
        '.gov-lvl-master       { background: #062918; color: #fff; }\n'
        '#close-detail { align-self: flex-end; background: none; border: none; font-size: 20px; cursor: pointer; color: var(--text-light); padding: 0; line-height: 1; }\n'
        '#close-detail:hover { color: var(--text); }\n'
        '.node .node-shape { cursor: pointer; stroke-width: 2px; transition: filter .15s; }\n'
        '.node:hover > .node-shape { filter: brightness(1.12) drop-shadow(0 2px 6px rgba(0,0,0,0.18)); }\n'
        '.node text { font-size: 16px; dominant-baseline: central; cursor: pointer; pointer-events: none; fill: var(--text); }\n'
        '.node.root > text { font-weight: 700; font-size: 19px; fill: var(--ink-black); }\n'
        '.node.role_family > text { font-weight: 700; font-size: 17px; fill: var(--text); }\n'
        '.node.role > text { font-weight: 600; fill: var(--text); }\n'
        '.node.role_level > text { fill: var(--text); }\n'
        '.node.government_capability > text { font-size: 15px; fill: var(--text-mid); }\n'
        '.node.broadly-accepted > text { font-weight: 600; fill: #144828; }\n'
        '.node.sfia_skill > text { font-size: 15px; fill: var(--text-mid); }\n'
        '.link { fill: none; stroke-width: 2px; }\n'
        '.node.highlight > .node-shape { stroke: #3a8455 !important; stroke-width: 3px !important; filter: drop-shadow(0 0 5px rgba(58,132,85,0.7)); }\n'
        '.node.dimmed { opacity: .18; }\n'
        '.node { transition: opacity .18s ease; }\n'
        '.node.branch-dim { opacity: 0.1; }\n'
        '.link { transition: opacity .18s ease; }\n'
        '.link.link-dim { opacity: 0.08; }\n'
        '#legend { position: absolute; bottom: 14px; left: 14px; background: rgba(255,255,255,.95); border: 1px solid var(--border); border-radius: 9px; padding: 11px 14px; font-size: 13px; line-height: 1.7; pointer-events: none; color: var(--text-mid); box-shadow: 0 2px 8px rgba(0,0,0,.06); }\n'
        '.legend-row { display: flex; align-items: center; gap: 8px; }\n'
        '.lc { width: 11px; height: 11px; border-radius: 50%; flex-shrink: 0; }\n'
        '.lc-root { background: #3d3530; }\n'
        '.lc-family { background: #c8c0b4; border: 1px solid #b0a898; }\n'
        '.lc-role { background: #bad8c4; border: 1px solid #96c4a8; }\n'
        '.lc-cap { background: #60a478; }\n'
        '.lc-sfia { background: #1e6038; }\n'
        '.band-selector { display: flex; flex-wrap: wrap; gap: 5px; padding: 8px 0 4px; }\n'
        '.band-pill { background: var(--bg); border: 1px solid var(--border); border-radius: 20px; padding: 4px 11px; font-size: 13px; font-weight: 600; cursor: pointer; color: var(--text-mid); transition: background .12s, border-color .12s; }\n'
        '.band-pill:hover { background: #e2efe8; border-color: #3a8455; color: var(--text); }\n'
        '.band-pill--active { background: #3a8455; border-color: #3a8455; color: #fff; }\n'
        '</style>\n'
        '</head>\n'
        '<body>\n'
        '<div id="header">\n'
        '  <div class="hdr-brand">\n'
        '    <h1><span>GDaD</span><span class="hdr-badge">SFIA 9</span></h1>\n'
        '    <p class="hdr-subtitle">Government Digital and Data &middot; Profession Framework</p>\n'
        '  </div>\n'
        '  <div class="search-wrap">\n'
        '    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.6)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>\n'
        '    <input id="search" type="text" placeholder="Search roles, skills, codes…" autocomplete="off">\n'
        '    <div id="search-dropdown"></div>\n'
        '  </div>\n'
        '</div>\n'
        '<div id="control-row">\n'
        '  <div id="filter-column">\n'
        '    <div class="filter-row">\n'
        '      <span class="filter-label">Role family</span>\n'
        '      <div class="filter-chips" id="family-chips"></div>\n'
        '    </div>\n'
        '    <div class="filter-row">\n'
        '      <span class="filter-label">Role</span>\n'
        '      <div class="filter-chips" id="role-chips"></div>\n'
        '    </div>\n'
        '    <div class="filter-row">\n'
        '      <span class="filter-label">Role level</span>\n'
        '      <div class="filter-chips" id="band-chips"></div>\n'
        '    </div>\n'
        '  </div>\n'
        '  <div id="button-column">\n'
        '    <button onclick="expandAll()">Expand all</button>\n'
        '    <button onclick="collapseAll()">Collapse all</button>\n'
        '    <button id="snap-btn" onclick="toggleSnap()">Snap</button>\n'
        '  </div>\n'
        '</div>\n'
        '<div id="main">\n'
        '  <div id="tree-panel">\n'
        '    <svg id="tree-svg"></svg>\n'
        '    <div id="legend">\n'
        '      <div class="legend-row"><div class="lc lc-family"></div>Role family</div>\n'
        '      <div class="legend-row"><div class="lc lc-role"></div>Role</div>\n'
        '      <div class="legend-row"><div class="lc lc-cap"></div>Capability</div>\n'
        '      <div class="legend-row"><div class="lc lc-sfia"></div>SFIA skill</div>\n'
        '    </div>\n'
        '  </div>\n'
        '  <div id="detail-panel" class="hidden">\n'
        '    <button id="close-detail" onclick="closeDetail()">✕</button>\n'
        '    <div id="detail-content"></div>\n'
        '  </div>\n'
        '</div>\n'
        '<script src="explorer.js?v=' + cache_bust + '"></script>\n'
        '</body>\n'
        '</html>\n'
    )

    out = ROOT / 'web' / 'collapsible_role_capability_skill_level_tree.html'
    out.write_text(html, encoding='utf-8')
    print(f'Written: {out}')

if __name__ == '__main__':
    main()
