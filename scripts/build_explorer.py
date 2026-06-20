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
    tree_json = json.dumps(tree, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DDaT → SFIA 9 Explorer</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<style>
  :root {{
    --sky-aqua:         #42cafd;
    --tropical-teal:    #66b3ba;
    --muted-teal:       #8eb19d;
    --vanilla-custard:  #f6efa6;
    --soft-blush:       #f0d2d1;
    --navy:             #1a2332;
    --accent:           #0e8fb5;
    --text:             #1c2b2e;
    --text-mid:         #4a5e62;
    --text-light:       #7a8e91;
    --border:           #dce8e9;
    --bg:               #f4f8f8;
    --panel-bg:         #ffffff;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ height: 100%; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); display: flex; flex-direction: column; }}

  #header {{ background: var(--navy); color: #fff; padding: 12px 20px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; flex-shrink: 0; border-bottom: 3px solid var(--tropical-teal); }}
  #header h1 {{ font-size: 17px; font-weight: 600; white-space: nowrap; letter-spacing: -.01em; }}
  #controls {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; flex: 1; }}
  #search {{ padding: 6px 11px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15); font-size: 13px; width: 200px; background: rgba(255,255,255,0.08); color: #fff; }}
  #search::placeholder {{ color: rgba(255,255,255,0.4); }}
  #search:focus {{ outline: none; background: rgba(255,255,255,0.14); border-color: var(--sky-aqua); }}
  select {{ padding: 6px 9px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15); font-size: 12px; background: rgba(255,255,255,0.08); color: #fff; cursor: pointer; }}
  select option {{ background: var(--navy); color: #fff; }}
  button {{ padding: 6px 13px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.2); font-size: 12px; cursor: pointer; background: rgba(255,255,255,0.1); color: #fff; transition: background .15s; }}
  button:hover {{ background: rgba(255,255,255,0.22); border-color: var(--sky-aqua); }}

  #main {{ display: flex; flex: 1; min-height: 0; }}

  #tree-panel {{ flex: 1; overflow: hidden; position: relative; background: var(--bg); }}
  #tree-svg {{ display: block; width: 100%; height: 100%; }}

  #detail-panel {{ width: 340px; flex-shrink: 0; background: var(--panel-bg); border-left: 1px solid var(--border); overflow-y: auto; padding: 18px; display: flex; flex-direction: column; gap: 12px; }}
  #detail-panel.hidden {{ display: none; }}
  .detail-type {{ font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: var(--tropical-teal); }}
  .detail-title {{ font-size: 15px; font-weight: 700; line-height: 1.35; color: var(--text); }}
  .detail-section {{ border-top: 1px solid var(--border); padding-top: 10px; }}
  .detail-section h3 {{ font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--text-light); margin-bottom: 7px; }}
  .sfia-chip {{ display: flex; align-items: center; gap: 7px; background: #edf7f8; border: 1px solid #c2dfe2; border-radius: 7px; padding: 5px 10px; margin: 3px 0; font-size: 12px; color: var(--text); }}
  .sfia-chip .code {{ font-weight: 700; color: var(--accent); font-size: 11px; white-space: nowrap; }}
  .range-badge {{ display: inline-flex; align-items: center; gap: 3px; flex-shrink: 0; }}
  .lvl-pip {{ display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 50%; color: #1c2b2e; font-size: 10px; font-weight: 700; }}
  .range-sep {{ font-size: 11px; color: var(--text-light); font-weight: 400; }}
  .cap-row {{ display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; border-bottom: 1px solid #eef3f3; color: var(--text); }}
  .gov-level-tag {{ font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background: #e4f0f1; color: var(--text-mid); white-space: nowrap; flex-shrink: 0; }}
  #close-detail {{ align-self: flex-end; background: none; border: none; font-size: 18px; cursor: pointer; color: var(--text-light); padding: 0; line-height: 1; }}
  #close-detail:hover {{ color: var(--text); }}

  /* Tree nodes */
  .node circle {{ cursor: pointer; stroke-width: 1.5px; }}
  .node text {{ font-size: 12px; dominant-baseline: middle; cursor: pointer; pointer-events: none; fill: var(--text); }}
  .node.root > circle {{ fill: var(--navy); stroke: var(--navy); }}
  .node.root > text {{ font-weight: 700; font-size: 14px; fill: var(--navy); }}
  .node.role_family > circle {{ fill: var(--sky-aqua); stroke: #1aa8d4; }}
  .node.role_family > text {{ font-weight: 700; font-size: 13px; fill: var(--text); }}
  .node.role > circle {{ fill: var(--tropical-teal); stroke: #4a9aa1; }}
  .node.role > text {{ fill: var(--text); }}
  .node.role_level > circle {{ fill: var(--muted-teal); stroke: #6d9480; }}
  .node.role_level > text {{ fill: var(--text); }}
  .node.government_capability > circle {{ fill: var(--vanilla-custard); stroke: #c9c050; }}
  .node.government_capability > text {{ fill: var(--text-mid); }}
  .node.sfia_skill > circle {{ fill: var(--soft-blush); stroke: #c4a4a3; }}
  .node.sfia_skill > text {{ fill: var(--text-mid); }}
  .link {{ fill: none; stroke: var(--border); stroke-width: 1.3px; }}
  .node.highlight > circle {{ stroke: var(--sky-aqua) !important; stroke-width: 3px !important; filter: drop-shadow(0 0 5px #42cafda0); }}
  .node.dimmed {{ opacity: .18; }}

  #legend {{ position: absolute; bottom: 14px; left: 14px; background: rgba(255,255,255,.95); border: 1px solid var(--border); border-radius: 9px; padding: 11px 14px; font-size: 11px; line-height: 1.7; pointer-events: none; color: var(--text-mid); box-shadow: 0 2px 8px rgba(0,0,0,.06); }}
  .legend-row {{ display: flex; align-items: center; gap: 8px; }}
  .lc {{ width: 11px; height: 11px; border-radius: 50%; flex-shrink: 0; }}
  .lc-root {{ background: var(--navy); }}
  .lc-family {{ background: var(--sky-aqua); border: 1px solid #1aa8d4; }}
  .lc-role {{ background: var(--tropical-teal); border: 1px solid #4a9aa1; }}
  .lc-level {{ background: var(--muted-teal); border: 1px solid #6d9480; }}
  .lc-cap {{ background: var(--vanilla-custard); border: 1px solid #c9c050; }}
  .lc-sfia {{ background: var(--soft-blush); border: 1px solid #c4a4a3; }}
</style>
</head>
<body>
<div id="header">
  <h1>DDaT → SFIA 9 Explorer</h1>
  <div id="controls">
    <input id="search" type="text" placeholder="Search roles, skills, codes…">
    <select id="family-filter"><option value="">All families</option></select>
    <select id="level-filter">
      <option value="">All SFIA levels</option>
      <option value="1">Level 1</option><option value="2">Level 2</option><option value="3">Level 3</option>
      <option value="4">Level 4</option><option value="5">Level 5</option><option value="6">Level 6</option><option value="7">Level 7</option>
    </select>
    <button onclick="expandAll()">Expand all</button>
    <button onclick="collapseAll()">Collapse to families</button>
  </div>
</div>
<div id="main">
  <div id="tree-panel">
    <svg id="tree-svg"></svg>
    <div id="legend">
      <div class="legend-row"><div class="lc lc-root"></div>Root</div>
      <div class="legend-row"><div class="lc lc-family"></div>Role family</div>
      <div class="legend-row"><div class="lc lc-role"></div>Role</div>
      <div class="legend-row"><div class="lc lc-level"></div>Role level</div>
      <div class="legend-row"><div class="lc lc-cap"></div>Gov. capability</div>
      <div class="legend-row"><div class="lc lc-sfia"></div>SFIA skill</div>
    </div>
  </div>
  <div id="detail-panel" class="hidden">
    <button id="close-detail" onclick="closeDetail()">✕</button>
    <div id="detail-content"></div>
  </div>
</div>
<script>
const RAW_TREE = {tree_json};

function lvlColor(l) {{
  return ['','#f0d2d1','#f6efa6','#d4e0c4','#8eb19d','#66b3ba','#42cafd','#1aa8d4'][+l] || '#eee';
}}
function rangeBadge(mn, mx) {{
  if (mn == null) return '';
  if (mn === mx) return `<span class="range-badge"><span class="lvl-pip" style="background:${{lvlColor(mn)}}">${{mn}}</span></span>`;
  return `<span class="range-badge"><span class="lvl-pip" style="background:${{lvlColor(mn)}}">${{mn}}</span><span class="range-sep">–</span><span class="lvl-pip" style="background:${{lvlColor(mx)}}">${{mx}}</span></span>`;
}}

// Populate family filter
const familySelect = document.getElementById('family-filter');
RAW_TREE.children.forEach(f => {{
  const o = document.createElement('option');
  o.value = f.name; o.textContent = f.name;
  familySelect.appendChild(o);
}});

// ── Tree setup ────────────────────────────────────────────────────────────────
const MARGIN = {{t: 40, r: 240, b: 40, l: 80}};
const svgEl = document.getElementById('tree-svg');
const svg = d3.select(svgEl);
const gLink = svg.append('g').attr('class', 'links');
const gNode = svg.append('g').attr('class', 'nodes');

const zoom = d3.zoom().scaleExtent([0.04, 4])
  .on('zoom', e => {{
    gLink.attr('transform', e.transform);
    gNode.attr('transform', e.transform);
  }});
svg.call(zoom).on('dblclick.zoom', null);

const treeFn = d3.tree().nodeSize([24, 240]);

let uid = 0;
let root = d3.hierarchy(RAW_TREE);

// Collapse everything below depth 1 (roles stay collapsed inside families)
root.descendants().forEach(d => {{
  d._uid = ++uid;
  if (d.depth >= 1) {{ d._children = d.children; d.children = null; }}
}});

// Set initial positions
root.x0 = 0; root.y0 = 0;

function getViewCenter() {{
  const r = svgEl.getBoundingClientRect();
  return [MARGIN.l, r.height / 2];
}}

function update(src) {{
  treeFn(root);
  const nodes = root.descendants();
  const links = root.links();

  // ── nodes ──
  const node = gNode.selectAll('g.node')
    .data(nodes, d => d._uid);

  const enter = node.enter().append('g')
    .attr('class', d => `node ${{d.data.type}}`)
    .attr('transform', () => `translate(${{src.y0 ?? 0}},${{src.x0 ?? 0}})`)
    .on('click', (evt, d) => {{ toggle(d); update(d); }})
    .on('click.detail', (evt, d) => showDetail(d));

  enter.append('circle').attr('r', d => d.data.type === 'root' ? 10 : d.data.type === 'role_family' ? 8 : 6);

  enter.append('text')
    .attr('dy', '0.32em')
    .attr('x', d => (d.children || d._children) ? -13 : 13)
    .attr('text-anchor', d => (d.children || d._children) ? 'end' : 'start')
    .text(d => trunc(d.data.name, 38));

  // Level range dots on SFIA skill nodes (min dot + max dot if different)
  const sfiaEnter = enter.filter(d => d.data.type === 'sfia_skill' && d.data.min != null);
  sfiaEnter.append('circle').attr('class', 'lvl-dot')
    .attr('r', 5).attr('cx', d => d.data.min === d.data.max ? -14 : -20).attr('cy', 0)
    .style('fill', d => lvlColor(d.data.min))
    .attr('stroke', '#fff').attr('stroke-width', 1.5);
  sfiaEnter.filter(d => d.data.min !== d.data.max)
    .append('circle').attr('class', 'lvl-dot')
    .attr('r', 5).attr('cx', -9).attr('cy', 0)
    .style('fill', d => lvlColor(d.data.max))
    .attr('stroke', '#fff').attr('stroke-width', 1.5);

  const merged = enter.merge(node);
  merged.transition().duration(250)
    .attr('transform', d => `translate(${{d.y}},${{d.x}})`);
  merged.select('circle:not(.lvl-dot)')
    .attr('r', d => d.data.type === 'root' ? 10 : d.data.type === 'role_family' ? 8 : 6);
  merged.select('text')
    .attr('x', d => (d.children || d._children) ? -13 : 13)
    .attr('text-anchor', d => (d.children || d._children) ? 'end' : 'start');

  node.exit().transition().duration(250)
    .attr('transform', () => `translate(${{src.y ?? 0}},${{src.x ?? 0}})`).remove();

  // ── links ──
  const link = gLink.selectAll('path.link')
    .data(links, d => d.target._uid);

  const lEnter = link.enter().insert('path', 'g').attr('class', 'link')
    .attr('d', () => curve({{x: src.x0 ?? 0, y: src.y0 ?? 0}}, {{x: src.x0 ?? 0, y: src.y0 ?? 0}}));

  lEnter.merge(link).transition().duration(250)
    .attr('d', d => curve(d.source, d.target));

  link.exit().transition().duration(250)
    .attr('d', () => curve({{x: src.x ?? 0, y: src.y ?? 0}}, {{x: src.x ?? 0, y: src.y ?? 0}})).remove();

  // Store positions
  nodes.forEach(d => {{ d.x0 = d.x; d.y0 = d.y; }});

  applyFilters();
}}

function curve(s, d) {{
  return `M${{s.y}},${{s.x}}C${{(s.y+d.y)/2}},${{s.x}} ${{(s.y+d.y)/2}},${{d.x}} ${{d.y}},${{d.x}}`;
}}

function toggle(d) {{
  if (d.children) {{ d._children = d.children; d.children = null; }}
  else {{ d.children = d._children; d._children = null; }}
}}

function trunc(s, n) {{ return s && s.length > n ? s.slice(0, n - 1) + '…' : s; }}

function expandAll() {{
  root.descendants().forEach(d => {{ if (d._children) {{ d.children = d._children; d._children = null; }} }});
  update(root);
}}
function collapseAll() {{
  root.descendants().forEach(d => {{
    if (d.depth >= 1 && d.children) {{ d._children = d.children; d.children = null; }}
  }});
  update(root);
}}

// ── Initial render ────────────────────────────────────────────────────────────
// Run after layout so getBoundingClientRect is available
requestAnimationFrame(() => {{
  const r = svgEl.getBoundingClientRect();
  const cx = MARGIN.l, cy = r.height / 2;
  update(root);
  // Translate so root appears at (cx, cy)
  svg.call(zoom.transform, d3.zoomIdentity.translate(cx, cy));
}});

// ── Detail panel ──────────────────────────────────────────────────────────────
function showDetail(d) {{
  const nd = d.data;
  const dp = document.getElementById('detail-panel');
  const dc = document.getElementById('detail-content');
  dp.classList.remove('hidden');

  const labels = {{root:'',role_family:'Role Family',role:'Role',role_level:'Role Level',government_capability:'Government Capability',sfia_skill:'SFIA 9 Skill'}};
  let h = `<div class="detail-type">${{labels[nd.type]||nd.type}}</div><div class="detail-title">${{nd.name}}</div>`;

  if (nd.type === 'role_family') {{
    const n = (d.children||d._children||[]).length;
    h += `<div class="detail-section"><h3>Roles</h3><p style="font-size:13px">${{n}} role${{n!==1?'s':''}}</p></div>`;
  }}
  if (nd.type === 'role') {{
    h += `<div class="detail-section"><h3>Family</h3><p style="font-size:13px">${{nd.role_family}}</p></div>`;
    const lvls = d.children||d._children||[];
    h += `<div class="detail-section"><h3>Role levels (${{lvls.length}})</h3>`;
    lvls.forEach(l => {{ h += `<div class="cap-row"><span style="flex:1">${{l.data.name}}</span><span class="gov-level-tag">${{l.data.band}}</span></div>`; }});
    h += `</div>`;
  }}
  if (nd.type === 'role_level') {{
    h += `<div class="detail-section"><h3>Band</h3><p style="font-size:13px">${{nd.band||'—'}}</p></div>`;
    const caps = d.children||d._children||[];
    const sm = {{}};
    caps.forEach(c => {{ (c.children||c._children||[]).forEach(s => {{ if(!sm[s.data.sfia_code]) sm[s.data.sfia_code]=s.data; }}); }});
    const sfias = Object.values(sm).sort((a,b)=>(b.max||0)-(a.max||0));
    h += `<div class="detail-section"><h3>SFIA skills (${{sfias.length}})</h3>`;
    sfias.forEach(s => {{
      h += `<div class="sfia-chip">${{rangeBadge(s.min,s.max)}}<span class="code">${{s.sfia_code}}</span><span style="flex:1">${{s.name.replace(/^[A-Z]+ — /,'')}}</span></div>`;
    }});
    h += `</div><div class="detail-section"><h3>Gov. capabilities (${{caps.length}})</h3>`;
    caps.forEach(c => {{ h += `<div class="cap-row"><span style="flex:1">${{c.data.name}}</span><span class="gov-level-tag">${{c.data.gov_level}}</span></div>`; }});
    h += `</div>`;
  }}
  if (nd.type === 'government_capability') {{
    const sfias = d.children||d._children||[];
    h += `<div class="detail-section"><h3>Gov. skill level</h3><p style="font-size:13px">${{nd.gov_level||'—'}}</p></div>`;
    h += `<div class="detail-section"><h3>SFIA skills (${{sfias.length}})</h3>`;
    sfias.forEach(s => {{
      h += `<div class="sfia-chip">${{rangeBadge(s.data.min,s.data.max)}}<span class="code">${{s.data.sfia_code}}</span><span style="flex:1">${{s.data.name.replace(/^[A-Z]+ — /,'')}}</span></div>`;
    }});
    h += `</div>`;
  }}
  if (nd.type === 'sfia_skill') {{
    const width = (nd.max != null && nd.min != null) ? nd.max - nd.min : 0;
    h += `<div class="detail-section">
      <div style="display:flex;align-items:baseline;gap:10px">
        <p style="font-size:14px;font-weight:700;color:#3b5bdb">${{nd.sfia_code}}</p>
        <p style="font-size:11px;color:#888">${{nd.sfia_category}}${{nd.sfia_subcategory ? ' · '+nd.sfia_subcategory : ''}}</p>
      </div>
      ${{nd.sfia_description ? `<p style="font-size:13px;line-height:1.5;margin-top:6px;color:#333">${{nd.sfia_description}}</p>` : ''}}
    </div>`;
    if (nd.sfia_guidance) {{
      const lines = nd.sfia_guidance.split('\n').filter(l => l.trim());
      const intro = lines[0] && lines[0].endsWith(':') ? lines[0] : null;
      const items = intro ? lines.slice(1) : lines;
      const SHOW = 4;
      const uid = 'g' + Math.random().toString(36).slice(2);
      let gh = `<div class="detail-section"><h3>Guidance notes</h3>`;
      if (intro) gh += `<p style="font-size:12px;color:var(--text-mid);margin-bottom:6px">${{intro}}</p>`;
      gh += `<ul id="${{uid}}-list" style="padding-left:16px;font-size:12px;line-height:1.6;color:var(--text);list-style:disc">`;
      items.slice(0, SHOW).forEach(it => {{ gh += `<li style="margin-bottom:3px">${{it}}</li>`; }});
      if (items.length > SHOW) {{
        gh += `</ul><ul id="${{uid}}-more" style="padding-left:16px;font-size:12px;line-height:1.6;color:var(--text);list-style:disc;display:none">`;
        items.slice(SHOW).forEach(it => {{ gh += `<li style="margin-bottom:3px">${{it}}</li>`; }});
        gh += `</ul><button onclick="(function(){{var m=document.getElementById('${{uid}}-more'),b=event.target;var open=m.style.display!=='none';m.style.display=open?'none':'block';b.textContent=open?'Show all ${{items.length}} activities':'Show fewer'}})()" style="margin-top:6px;font-size:11px;color:var(--accent);background:none;border:none;cursor:pointer;padding:0;font-weight:600">Show all ${{items.length}} activities</button>`;
      }} else {{
        gh += `</ul>`;
      }}
      gh += `</div>`;
      h += gh;
    }}
    h += `<div class="detail-section"><h3>Expected SFIA level range</h3>
      <div style="display:flex;align-items:center;gap:10px;margin-top:4px">
        ${{rangeBadge(nd.min, nd.max)}}
        <span style="font-size:12px;color:#555">${{nd.min===nd.max ? `Level ${{nd.min}}` : `Levels ${{nd.min}} to ${{nd.max}}`}}${{width>2?' — wider range due to multiple capabilities':''}} </span>
      </div>
    </div>`;
    if (nd.level_descriptions && nd.min != null) {{
      h += `<div class="detail-section"><h3>What this looks like at each level</h3>`;
      for (let lvl = nd.min; lvl <= nd.max; lvl++) {{
        const desc = nd.level_descriptions[String(lvl)];
        if (desc) {{
          h += `<div style="display:flex;gap:10px;margin-bottom:10px;align-items:flex-start">
            <span class="lvl-pip" style="background:${{lvlColor(lvl)}};flex-shrink:0;margin-top:2px">${{lvl}}</span>
            <p style="font-size:12px;line-height:1.55;color:#333">${{desc}}</p>
          </div>`;
        }}
      }}
      h += `</div>`;
    }}
    h += `<div class="detail-section"><h3>Evidence (${{nd.count}} gov. capability${{nd.count!==1?'s':''}})</h3>
      <p style="font-size:12px;color:#555;line-height:1.5">${{nd.evidence}}</p>
    </div>`;
  }}
  dc.innerHTML = h;
}}

function closeDetail() {{ document.getElementById('detail-panel').classList.add('hidden'); }}

// ── Filters ───────────────────────────────────────────────────────────────────
let aSearch='', aFamily='', aLevel='', aConf='';

function applyFilters() {{
  const q = aSearch.toLowerCase().trim();
  const lvl = aLevel ? +aLevel : null;
  const hasFilter = q || lvl || aConf || aFamily;

  gNode.selectAll('g.node').each(function(d) {{
    const nd = d.data;
    let match = false;
    if (hasFilter) {{
      const txt = (nd.name+' '+(nd.sfia_code||'')).toLowerCase();
      const qm = !q || txt.includes(q);
      const lm = !lvl || (nd.min != null && nd.max != null && lvl >= nd.min && lvl <= nd.max);
      const cm = true;
      const fm = !aFamily || (nd.type==='role_family' ? nd.name===aFamily : true);
      match = qm && lm && cm && fm && (nd.type==='sfia_skill'||nd.type==='government_capability'||nd.type==='role_level'||nd.type==='role'||nd.type==='role_family');
    }}
    d3.select(this).classed('highlight', hasFilter && match).classed('dimmed', false);
  }});
}}

document.getElementById('search').addEventListener('input', e => {{ aSearch=e.target.value; applyFilters(); }});
document.getElementById('family-filter').addEventListener('change', e => {{ aFamily=e.target.value; applyFilters(); }});
document.getElementById('level-filter').addEventListener('change', e => {{ aLevel=e.target.value; applyFilters(); }});
</script>
</body>
</html>"""

    out = ROOT / 'web' / 'collapsible_role_capability_skill_level_tree.html'
    out.write_text(html, encoding='utf-8')
    print(f'Written: {out}')

if __name__ == '__main__':
    main()
