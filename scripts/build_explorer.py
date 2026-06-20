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
            'children': sfia_children,
        }

    def role_level_node(rl_id: str) -> dict:
        n = nodes[rl_id]
        cap_ids = [t for t in children_of.get(rl_id, []) if nodes.get(t, {}).get('type') == 'government_capability']
        caps = [capability_node(rl_id, c) for c in cap_ids]
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

    def role_node(role_id: str) -> dict:
        n = nodes[role_id]
        rl_ids = list(dict.fromkeys(t for t in children_of.get(role_id, []) if nodes.get(t, {}).get('type') == 'role_level'))
        return {
            'id': role_id,
            'name': n['label'],
            'type': 'role',
            'role_family': n.get('role_family', ''),
            'children': [role_level_node(rl) for rl in rl_ids],
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
        '<title>DDaT → SFIA 9 Explorer</title>\n'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>\n'
        '<style>\n'
        ':root {\n'
        '  --sky-aqua:        #42cafd;\n'
        '  --tropical-teal:   #66b3ba;\n'
        '  --muted-teal:      #8eb19d;\n'
        '  --vanilla-custard: #f6efa6;\n'
        '  --soft-blush:      #f0d2d1;\n'
        '  --navy:            #1a2332;\n'
        '  --accent:          #0e8fb5;\n'
        '  --text:            #1c2b2e;\n'
        '  --text-mid:        #4a5e62;\n'
        '  --text-light:      #7a8e91;\n'
        '  --border:          #dce8e9;\n'
        '  --bg:              #f4f8f8;\n'
        '  --panel-bg:        #ffffff;\n'
        '}\n'
        '* { box-sizing: border-box; margin: 0; padding: 0; }\n'
        'html, body { height: 100%; }\n'
        'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); display: flex; flex-direction: column; }\n'
        '#header { background: var(--navy); color: #fff; padding: 12px 20px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; flex-shrink: 0; border-bottom: 3px solid var(--tropical-teal); }\n'
        '#header h1 { font-size: 17px; font-weight: 600; white-space: nowrap; letter-spacing: -.01em; }\n'
        '#controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; flex: 1; }\n'
        '#search { padding: 6px 11px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15); font-size: 13px; width: 200px; background: rgba(255,255,255,0.08); color: #fff; }\n'
        '#search::placeholder { color: rgba(255,255,255,0.4); }\n'
        '#search:focus { outline: none; background: rgba(255,255,255,0.14); border-color: var(--sky-aqua); }\n'
        'select { padding: 6px 9px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15); font-size: 12px; background: rgba(255,255,255,0.08); color: #fff; cursor: pointer; }\n'
        'select option { background: var(--navy); color: #fff; }\n'
        'button { padding: 6px 13px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.2); font-size: 12px; cursor: pointer; background: rgba(255,255,255,0.1); color: #fff; transition: background .15s; }\n'
        'button:hover { background: rgba(255,255,255,0.22); border-color: var(--sky-aqua); }\n'
        '#main { display: flex; flex: 1; min-height: 0; }\n'
        '#tree-panel { flex: 1; overflow: hidden; position: relative; background: var(--bg); }\n'
        '#tree-svg { display: block; width: 100%; height: 100%; }\n'
        '#detail-panel { width: 340px; flex-shrink: 0; background: var(--panel-bg); border-left: 1px solid var(--border); overflow-y: auto; padding: 18px; display: flex; flex-direction: column; gap: 12px; }\n'
        '#detail-panel.hidden { display: none; }\n'
        '.detail-type { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: var(--tropical-teal); }\n'
        '.detail-title { font-size: 15px; font-weight: 700; line-height: 1.35; color: var(--text); }\n'
        '.detail-section { border-top: 1px solid var(--border); padding-top: 10px; }\n'
        '.detail-section h3 { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--text-light); margin-bottom: 7px; }\n'
        '.sfia-chip { display: flex; align-items: center; gap: 7px; background: #edf7f8; border: 1px solid #c2dfe2; border-radius: 7px; padding: 5px 10px; margin: 3px 0; font-size: 12px; color: var(--text); }\n'
        '.sfia-chip .code { font-weight: 700; color: var(--accent); font-size: 11px; white-space: nowrap; }\n'
        '.nav-code { background: none; border: none; padding: 0; font: inherit; cursor: pointer; }\n'
        '.nav-code:hover { text-decoration: underline; opacity: 0.75; }\n'
        '.range-badge { display: inline-flex; align-items: center; gap: 3px; flex-shrink: 0; }\n'
        '.lvl-pip { display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 50%; color: #1c2b2e; font-size: 10px; font-weight: 700; }\n'
        '.range-sep { font-size: 11px; color: var(--text-light); font-weight: 400; }\n'
        '.cap-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; border-bottom: 1px solid #eef3f3; color: var(--text); }\n'
        '.gov-level-tag { font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background: #e4f0f1; color: var(--text-mid); white-space: nowrap; flex-shrink: 0; }\n'
        '.cap-chip { display: flex; align-items: center; gap: 7px; background: #faf8e6; border: 1px solid #ddd89a; border-radius: 7px; padding: 5px 10px; margin: 3px 0; font-size: 12px; color: var(--text); }\n'
        '.gov-level-pip { display: inline-flex; align-items: center; justify-content: center; min-width: 22px; height: 20px; border-radius: 4px; font-size: 9px; font-weight: 700; letter-spacing: .02em; flex-shrink: 0; padding: 0 4px; }\n'
        '.gov-lvl-awareness    { background: #f0edcc; color: #7a6c10; }\n'
        '.gov-lvl-working      { background: #e8d96a; color: #5a4500; }\n'
        '.gov-lvl-practitioner { background: #c9b820; color: #4a3600; }\n'
        '.gov-lvl-expert       { background: #a89500; color: #faf8e6; }\n'
        '.gov-lvl-master       { background: #7a6c00; color: #faf8e6; }\n'
        '#close-detail { align-self: flex-end; background: none; border: none; font-size: 18px; cursor: pointer; color: var(--text-light); padding: 0; line-height: 1; }\n'
        '#close-detail:hover { color: var(--text); }\n'
        '.node .node-shape { cursor: pointer; stroke-width: 2px; transition: filter .15s; }\n'
        '.node:hover > .node-shape { filter: brightness(1.12) drop-shadow(0 2px 6px rgba(0,0,0,0.18)); }\n'
        '.node text { font-size: 14px; dominant-baseline: middle; cursor: pointer; pointer-events: none; fill: var(--text); }\n'
        '.node.root > text { font-weight: 700; font-size: 17px; fill: var(--navy); }\n'
        '.node.role_family > text { font-weight: 700; font-size: 15px; fill: var(--text); }\n'
        '.node.role > text { font-weight: 600; fill: var(--text); }\n'
        '.node.role_level > text { fill: var(--text); }\n'
        '.node.government_capability > text { font-size: 13px; fill: var(--text-mid); }\n'
        '.node.sfia_skill > text { font-size: 13px; fill: var(--text-mid); }\n'
        '.link { fill: none; stroke-width: 2px; }\n'
        '.node.highlight > .node-shape { stroke: var(--sky-aqua) !important; stroke-width: 3px !important; filter: drop-shadow(0 0 5px #42cafda0); }\n'
        '.node.dimmed { opacity: .18; }\n'
        '.node { transition: opacity .18s ease; }\n'
        '.node.branch-dim { opacity: 0.1; }\n'
        '.link { transition: opacity .18s ease; }\n'
        '.link.link-dim { opacity: 0.08; }\n'
        '#legend { position: absolute; bottom: 14px; left: 14px; background: rgba(255,255,255,.95); border: 1px solid var(--border); border-radius: 9px; padding: 11px 14px; font-size: 11px; line-height: 1.7; pointer-events: none; color: var(--text-mid); box-shadow: 0 2px 8px rgba(0,0,0,.06); }\n'
        '.legend-row { display: flex; align-items: center; gap: 8px; }\n'
        '.lc { width: 11px; height: 11px; border-radius: 50%; flex-shrink: 0; }\n'
        '.lc-root { background: var(--navy); }\n'
        '.lc-family { background: var(--sky-aqua); border: 1px solid #1aa8d4; }\n'
        '.lc-role { background: var(--tropical-teal); border: 1px solid #4a9aa1; }\n'
        '.lc-level { background: var(--muted-teal); border: 1px solid #6d9480; }\n'
        '.lc-cap { background: var(--vanilla-custard); border: 1px solid #c9c050; }\n'
        '.lc-sfia { background: var(--soft-blush); border: 1px solid #c4a4a3; }\n'
        '</style>\n'
        '</head>\n'
        '<body>\n'
        '<div id="header">\n'
        '  <h1>DDaT → SFIA 9 Explorer</h1>\n'
        '  <div id="controls">\n'
        '    <input id="search" type="text" placeholder="Search roles, skills, codes…">\n'
        '    <select id="family-filter"><option value="">All families</option></select>\n'
        '    <select id="level-filter">\n'
        '      <option value="">All SFIA levels</option>\n'
        '      <option value="1">Level 1</option><option value="2">Level 2</option><option value="3">Level 3</option>\n'
        '      <option value="4">Level 4</option><option value="5">Level 5</option><option value="6">Level 6</option><option value="7">Level 7</option>\n'
        '    </select>\n'
        '    <button onclick="expandAll()">Expand all</button>\n'
        '    <button onclick="collapseAll()">Collapse to families</button>\n'
        '  </div>\n'
        '</div>\n'
        '<div id="main">\n'
        '  <div id="tree-panel">\n'
        '    <svg id="tree-svg"></svg>\n'
        '    <div id="legend">\n'
        '      <div class="legend-row"><div class="lc lc-root"></div>Root</div>\n'
        '      <div class="legend-row"><div class="lc lc-family"></div>Role family</div>\n'
        '      <div class="legend-row"><div class="lc lc-role"></div>Role</div>\n'
        '      <div class="legend-row"><div class="lc lc-level"></div>Role level</div>\n'
        '      <div class="legend-row"><div class="lc lc-cap"></div>Gov. capability</div>\n'
        '      <div class="legend-row"><div class="lc lc-sfia"></div>SFIA skill</div>\n'
        '    </div>\n'
        '  </div>\n'
        '  <div id="detail-panel" class="hidden">\n'
        '    <button id="close-detail" onclick="closeDetail()">✕</button>\n'
        '    <div id="detail-content"></div>\n'
        '  </div>\n'
        '</div>\n'
        '<script src="explorer.js"></script>\n'
        '</body>\n'
        '</html>\n'
    )

    out = ROOT / 'web' / 'collapsible_role_capability_skill_level_tree.html'
    out.write_text(html, encoding='utf-8')
    print(f'Written: {out}')

if __name__ == '__main__':
    main()
