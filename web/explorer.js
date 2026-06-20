function lvlColor(l) {
  return ['','#f0d2d1','#f6efa6','#d4e0c4','#8eb19d','#66b3ba','#42cafd','#1aa8d4'][+l] || '#eee';
}
function rangeBadge(mn, mx) {
  if (mn == null) return '';
  const pip = (v) => `<span class="lvl-pip" style="background:${lvlColor(v)}">${v}</span>`;
  if (mn === mx) return `<span class="range-badge">${pip(mn)}</span>`;
  return `<span class="range-badge">${pip(mn)}<span class="range-sep">–</span>${pip(mx)}</span>`;
}

function nodeR(type) {
  return {root: 14, role_family: 12, role: 10, role_level: 9, government_capability: 8, sfia_skill: 8}[type] || 8;
}
function nodeColors(type) {
  return {
    root:                  {fill: 'var(--navy)',            stroke: 'var(--navy)'},
    role_family:           {fill: 'var(--sky-aqua)',        stroke: '#1aa8d4'},
    role:                  {fill: 'var(--tropical-teal)',   stroke: '#4a9aa1'},
    role_level:            {fill: 'var(--muted-teal)',      stroke: '#6d9480'},
    government_capability: {fill: 'var(--vanilla-custard)', stroke: '#c9c050'},
    sfia_skill:            {fill: 'var(--soft-blush)',      stroke: '#c4a4a3'},
  }[type] || {fill: '#ccc', stroke: '#999'};
}
// Pointy-top hexagon
function hexPoints(r) {
  return Array.from({length: 6}, (_, i) => {
    const a = Math.PI / 3 * i - Math.PI / 2;
    return `${(r * Math.cos(a)).toFixed(2)},${(r * Math.sin(a)).toFixed(2)}`;
  }).join(' ');
}
// Upward triangle inscribed in radius r
function triPoints(r) {
  const s = (r * 0.866).toFixed(2), h = (r * 0.5).toFixed(2);
  return `0,${-r} ${s},${h} ${-s},${h}`;
}
// Diamond (rotated square)
function diamPoints(r) {
  return `0,${-r} ${r},0 0,${r} ${-r},0`;
}

function pillColor(type) {
  return {
    root:                  'rgba(26,35,50,0.10)',
    role_family:           'rgba(66,202,253,0.22)',
    role:                  'rgba(102,179,186,0.22)',
    role_level:            'rgba(142,177,157,0.22)',
    government_capability: 'rgba(246,239,166,0.60)',
    sfia_skill:            'rgba(240,210,209,0.60)',
  }[type] || 'rgba(244,248,248,0.9)';
}
function pillStroke(type) {
  return {
    root:                  'rgba(26,35,50,0.20)',
    role_family:           'rgba(26,168,212,0.35)',
    role:                  'rgba(74,154,161,0.35)',
    role_level:            'rgba(109,148,128,0.35)',
    government_capability: 'rgba(201,192,80,0.50)',
    sfia_skill:            'rgba(196,164,163,0.50)',
  }[type] || 'rgba(0,0,0,0.10)';
}
function linkColor(d) {
  return {
    root:                  'rgba(26,168,212,0.45)',
    role_family:           'rgba(74,154,161,0.45)',
    role:                  'rgba(109,148,128,0.40)',
    role_level:            'rgba(180,175,60,0.45)',
    government_capability: 'rgba(196,164,163,0.50)',
  }[d.source.data.type] || '#b8cfd1';
}

function measurePills() {
  gNode.selectAll('g.node').each(function() {
    const textEl = d3.select(this).select('text').node();
    const rectEl = d3.select(this).select('rect.node-pill').node();
    if (!textEl || !rectEl) return;
    try {
      const b = textEl.getBBox();
      if (!b.width) return;
      d3.select(rectEl)
        .attr('x', b.x - 8).attr('y', b.y - 5)
        .attr('width', b.width + 16).attr('height', b.height + 10);
    } catch(e) {}
  });
}

const MARGIN = {t: 40, r: 300, b: 40, l: 320};
const svgEl = document.getElementById('tree-svg');
const svg = d3.select(svgEl);
const gLink = svg.append('g').attr('class', 'links');
const gNode = svg.append('g').attr('class', 'nodes');

const zoom = d3.zoom().scaleExtent([0.04, 4])
  .on('zoom', e => {
    gLink.attr('transform', e.transform);
    gNode.attr('transform', e.transform);
  });
svg.call(zoom).on('dblclick.zoom', null);

const treeFn = d3.tree().nodeSize([38, 300]);

let uid = 0;
let root;

function initTree(data) {
  // Populate family filter
  const familySelect = document.getElementById('family-filter');
  data.children.forEach(f => {
    const o = document.createElement('option');
    o.value = f.name; o.textContent = f.name;
    familySelect.appendChild(o);
  });

  root = d3.hierarchy(data);
  root.descendants().forEach(d => {
    d._uid = ++uid;
    if (d.depth >= 1) { d._children = d.children; d.children = null; }
  });
  root.x0 = 0; root.y0 = 0;

  requestAnimationFrame(() => {
    const r = svgEl.getBoundingClientRect();
    update(root);
    svg.call(zoom.transform, d3.zoomIdentity.translate(MARGIN.l, r.height / 2));
  });
}

function update(src) {
  treeFn(root);
  const nodes = root.descendants();
  const links = root.links();

  const node = gNode.selectAll('g.node').data(nodes, d => d._uid);

  const enter = node.enter().append('g')
    .attr('class', d => `node ${d.data.type}`)
    .attr('transform', () => `translate(${src.y0 ?? 0},${src.x0 ?? 0})`)
    .on('click', (evt, d) => { toggle(d); update(d); showDetail(d); })
    .on('mouseenter', (evt, d) => dimOthers(d))
    .on('mouseleave', () => undim());

  enter.append('title').text(d => d.data.name);

  // Shape — varies by node type
  enter.each(function(d) {
    const r = nodeR(d.data.type), c = nodeColors(d.data.type);
    const g = d3.select(this);
    let el;
    switch (d.data.type) {
      case 'role':
        el = g.append('rect').attr('class', 'node-shape')
          .attr('x', -r).attr('y', -r * 0.65)
          .attr('width', r * 2).attr('height', r * 1.3)
          .attr('rx', 5).attr('ry', 5);
        break;
      case 'role_level':
        el = g.append('polygon').attr('class', 'node-shape').attr('points', hexPoints(r));
        break;
      case 'government_capability':
        el = g.append('polygon').attr('class', 'node-shape').attr('points', triPoints(r));
        break;
      case 'sfia_skill':
        el = g.append('polygon').attr('class', 'node-shape').attr('points', diamPoints(r));
        break;
      default:  // root, role_family
        el = g.append('circle').attr('class', 'node-shape').attr('r', r);
    }
    el.style('fill', c.fill).style('stroke', c.stroke);
  });

  // Pill rect sits between shape and text in z-order
  enter.append('rect').attr('class', 'node-pill')
    .attr('rx', 5).attr('ry', 5)
    .attr('x', 0).attr('y', 0).attr('width', 0).attr('height', 0)
    .style('pointer-events', 'none')
    .style('fill', d => pillColor(d.data.type))
    .style('stroke', d => pillStroke(d.data.type))
    .style('stroke-width', '0.8px');

  enter.append('text')
    .attr('dy', '0.32em')
    .attr('x', d => (d.children || d._children) ? -(nodeR(d.data.type) + 6) : (nodeR(d.data.type) + 6))
    .attr('text-anchor', d => (d.children || d._children) ? 'end' : 'start')
    .text(d => trunc(d.data.name, 38));

  // Size pills immediately after text content is set
  enter.each(function() {
    const textEl = d3.select(this).select('text').node();
    const rectEl = d3.select(this).select('rect.node-pill').node();
    if (!textEl || !rectEl) return;
    try {
      const b = textEl.getBBox();
      if (b.width) d3.select(rectEl)
        .attr('x', b.x - 8).attr('y', b.y - 5)
        .attr('width', b.width + 16).attr('height', b.height + 10);
    } catch(e) {}
  });

  // Level range dots on SFIA skill nodes
  const sfiaEnter = enter.filter(d => d.data.type === 'sfia_skill' && d.data.min != null);
  sfiaEnter.append('circle').attr('class', 'lvl-dot')
    .attr('r', 7)
    .attr('cx', d => d.data.min === d.data.max ? -20 : -27)
    .attr('cy', 0)
    .style('fill', d => lvlColor(d.data.min))
    .attr('stroke', '#fff').attr('stroke-width', 2);
  sfiaEnter.filter(d => d.data.min !== d.data.max)
    .append('circle').attr('class', 'lvl-dot')
    .attr('r', 7).attr('cx', -14).attr('cy', 0)
    .style('fill', d => lvlColor(d.data.max))
    .attr('stroke', '#fff').attr('stroke-width', 2);

  const merged = enter.merge(node);
  merged.transition().duration(250)
    .attr('transform', d => `translate(${d.y},${d.x})`);
  // Node shapes are fixed on enter; no geometry update needed on merge
  merged.select('text')
    .attr('x', d => (d.children || d._children) ? -(nodeR(d.data.type) + 6) : (nodeR(d.data.type) + 6))
    .attr('text-anchor', d => (d.children || d._children) ? 'end' : 'start');

  node.exit().transition().duration(250)
    .attr('transform', () => `translate(${src.y ?? 0},${src.x ?? 0})`).remove();

  const link = gLink.selectAll('path.link').data(links, d => d.target._uid);
  const lEnter = link.enter().insert('path', 'g').attr('class', 'link')
    .attr('d', () => curve({x: src.x0 ?? 0, y: src.y0 ?? 0}, {x: src.x0 ?? 0, y: src.y0 ?? 0}))
    .style('stroke', linkColor);
  lEnter.merge(link).transition().duration(250)
    .attr('d', d => curve(d.source, d.target))
    .style('stroke', linkColor);
  link.exit().transition().duration(250)
    .attr('d', () => curve({x: src.x ?? 0, y: src.y ?? 0}, {x: src.x ?? 0, y: src.y ?? 0})).remove();

  nodes.forEach(d => { d.x0 = d.x; d.y0 = d.y; });
  setTimeout(measurePills, 260);
  applyFilters();
}

function curve(s, d) {
  return `M${s.y},${s.x}C${(s.y+d.y)/2},${s.x} ${(s.y+d.y)/2},${d.x} ${d.y},${d.x}`;
}
function toggle(d) {
  if (d.children) { d._children = d.children; d.children = null; }
  else { d.children = d._children; d._children = null; }
}
function trunc(s, n) { return s && s.length > n ? s.slice(0, n-1) + '…' : s; }
function dimOthers(hovered) {
  const focus = new Set();
  // All ancestors (path to root)
  let n = hovered;
  while (n) { focus.add(n); n = n.parent; }
  // Full subtree of hovered node (including collapsed _children)
  allNodes(hovered).forEach(n => focus.add(n));

  gNode.selectAll('g.node').classed('branch-dim', d => !focus.has(d));
  gLink.selectAll('path.link').classed('link-dim', d => !focus.has(d.target));
}
function undim() {
  gNode.selectAll('g.node').classed('branch-dim', false);
  gLink.selectAll('path.link').classed('link-dim', false);
}

function allNodes(node) {
  const out = [];
  (function walk(n) {
    out.push(n);
    const ch = n.children || n._children;
    if (ch) ch.forEach(walk);
  })(node);
  return out;
}

function navigateToNode(nodeId) {
  const target = allNodes(root).find(d => d.data.id === nodeId);
  if (!target) return;
  // Expand the full path from root down to the target
  let n = target;
  while (n) {
    if (n._children) { n.children = n._children; n._children = null; }
    n = n.parent;
  }
  update(target); // treeFn(root) inside sets target.x / target.y synchronously
  showDetail(target);
  const r = svgEl.getBoundingClientRect();
  svg.transition().duration(500).call(
    zoom.transform,
    d3.zoomIdentity.translate(r.width / 2 - target.y, r.height / 2 - target.x)
  );
}

function expandAll() {
  root.descendants().forEach(d => { if (d._children) { d.children = d._children; d._children = null; } });
  update(root);
}
function collapseAll() {
  root.descendants().forEach(d => {
    if (d.depth >= 1 && d.children) { d._children = d.children; d.children = null; }
  });
  update(root);
}

// ── Detail panel ──────────────────────────────────────────────────────────────
function showDetail(d) {
  const nd = d.data;
  const dp = document.getElementById('detail-panel');
  const dc = document.getElementById('detail-content');
  dp.classList.remove('hidden');

  const labels = {root:'',role_family:'Role Family',role:'Role',role_level:'Role Level',
    government_capability:'Government Capability',sfia_skill:'SFIA 9 Skill'};
  let h = `<div class="detail-type">${labels[nd.type]||nd.type}</div><div class="detail-title">${nd.name}</div>`;

  if (nd.type === 'role_family') {
    const n = (d.children||d._children||[]).length;
    h += `<div class="detail-section"><h3>Roles</h3><p style="font-size:13px">${n} role${n!==1?'s':''}</p></div>`;
  }
  if (nd.type === 'role') {
    h += `<div class="detail-section"><h3>Family</h3><p style="font-size:13px">${nd.role_family}</p></div>`;
    const lvls = d.children||d._children||[];
    h += `<div class="detail-section"><h3>Role levels (${lvls.length})</h3>`;
    lvls.forEach(l => { h += `<div class="cap-row"><span style="flex:1">${l.data.name}</span><span class="gov-level-tag">${l.data.band}</span></div>`; });
    h += `</div>`;
  }
  if (nd.type === 'role_level') {
    h += `<div class="detail-section"><h3>Band</h3><p style="font-size:13px">${nd.band||'—'}</p></div>`;
    const caps = d.children||d._children||[];
    const sm = {};
    caps.forEach(c => { (c.children||c._children||[]).forEach(s => { if(!sm[s.data.sfia_code]) sm[s.data.sfia_code]=s.data; }); });
    const sfias = Object.values(sm).sort((a,b)=>(b.max||0)-(a.max||0));
    h += `<div class="detail-section"><h3>SFIA skills (${sfias.length})</h3>`;
    sfias.forEach(s => {
      h += `<div class="sfia-chip">${rangeBadge(s.min,s.max)}<button class="code nav-code" onclick="navigateToNode('${s.id}')" title="Jump to this skill in the tree">${s.sfia_code}</button><span style="flex:1">${s.name.replace(/^[A-Z]+ — /,'')}</span></div>`;
    });
    h += `</div><div class="detail-section"><h3>Gov. capabilities (${caps.length})</h3>`;
    caps.forEach(c => { h += `<div class="cap-row"><span style="flex:1">${c.data.name}</span><span class="gov-level-tag">${c.data.gov_level}</span></div>`; });
    h += `</div>`;
  }
  if (nd.type === 'government_capability') {
    const sfias = d.children||d._children||[];
    h += `<div class="detail-section"><h3>Gov. skill level</h3><p style="font-size:13px">${nd.gov_level||'—'}</p></div>`;
    h += `<div class="detail-section"><h3>SFIA skills (${sfias.length})</h3>`;
    sfias.forEach(s => {
      h += `<div class="sfia-chip">${rangeBadge(s.data.min,s.data.max)}<span class="code">${s.data.sfia_code}</span><span style="flex:1">${s.data.name.replace(/^[A-Z]+ — /,'')}</span></div>`;
    });
    h += `</div>`;
  }
  if (nd.type === 'sfia_skill') {
    const width = (nd.max != null && nd.min != null) ? nd.max - nd.min : 0;
    h += `<div class="detail-section">
      <div style="display:flex;align-items:baseline;gap:10px">
        <p style="font-size:14px;font-weight:700;color:var(--accent)">${nd.sfia_code}</p>
        <p style="font-size:11px;color:var(--text-light)">${nd.sfia_category}${nd.sfia_subcategory ? ' · '+nd.sfia_subcategory : ''}</p>
      </div>
      ${nd.sfia_description ? `<p style="font-size:13px;line-height:1.5;margin-top:6px;color:var(--text)">${nd.sfia_description}</p>` : ''}
    </div>`;

    if (nd.sfia_guidance) {
      const lines = nd.sfia_guidance.split('\n').filter(l => l.trim());
      const intro = lines[0] && lines[0].endsWith(':') ? lines[0] : null;
      const items = intro ? lines.slice(1) : lines;
      const SHOW = 4;
      const gid = 'g' + Math.random().toString(36).slice(2);
      h += `<div class="detail-section"><h3>Guidance notes</h3>`;
      if (intro) h += `<p style="font-size:12px;color:var(--text-mid);margin-bottom:6px">${intro}</p>`;
      h += `<ul style="padding-left:16px;font-size:12px;line-height:1.6;color:var(--text);list-style:disc">`;
      items.slice(0, SHOW).forEach(it => { h += `<li style="margin-bottom:3px">${it}</li>`; });
      h += `</ul>`;
      if (items.length > SHOW) {
        h += `<ul id="${gid}" style="padding-left:16px;font-size:12px;line-height:1.6;color:var(--text);list-style:disc;display:none">`;
        items.slice(SHOW).forEach(it => { h += `<li style="margin-bottom:3px">${it}</li>`; });
        h += `</ul>
        <button id="${gid}-btn" onclick="toggleGuidance('${gid}')"
          style="margin-top:6px;font-size:11px;color:var(--accent);background:none;border:none;cursor:pointer;padding:0;font-weight:600">
          Show all ${items.length} activities
        </button>`;
      }
      h += `</div>`;
    }

    h += `<div class="detail-section"><h3>Expected SFIA level range</h3>
      <div style="display:flex;align-items:center;gap:10px;margin-top:4px">
        ${rangeBadge(nd.min, nd.max)}
        <span style="font-size:12px;color:var(--text-mid)">${nd.min===nd.max ? `Level ${nd.min}` : `Levels ${nd.min} to ${nd.max}`}${width>2?' — wider range due to multiple capabilities':''}</span>
      </div>
    </div>`;

    if (nd.level_descriptions && nd.min != null) {
      h += `<div class="detail-section"><h3>What this looks like at each level</h3>`;
      for (let lvl = nd.min; lvl <= nd.max; lvl++) {
        const desc = nd.level_descriptions[String(lvl)];
        if (desc) {
          h += `<div style="display:flex;gap:10px;margin-bottom:10px;align-items:flex-start">
            <span class="lvl-pip" style="background:${lvlColor(lvl)};flex-shrink:0;margin-top:2px">${lvl}</span>
            <p style="font-size:12px;line-height:1.55;color:var(--text)">${desc}</p>
          </div>`;
        }
      }
      h += `</div>`;
    }

    h += `<div class="detail-section"><h3>Evidence (${nd.count} gov. capability${nd.count!==1?'s':''})</h3>
      <p style="font-size:12px;color:var(--text-mid);line-height:1.5">${nd.evidence}</p>
    </div>`;
  }
  dc.innerHTML = h;
}

function toggleGuidance(gid) {
  const el = document.getElementById(gid);
  const btn = document.getElementById(gid + '-btn');
  const open = el.style.display !== 'none';
  el.style.display = open ? 'none' : 'block';
  btn.textContent = open ? btn.textContent.replace('Show fewer','Show all') : 'Show fewer';
}

function closeDetail() { document.getElementById('detail-panel').classList.add('hidden'); }

// ── Filters ───────────────────────────────────────────────────────────────────
let aSearch='', aFamily='', aLevel='';

function applyFilters() {
  const q = aSearch.toLowerCase().trim();
  const lvl = aLevel ? +aLevel : null;
  const hasFilter = q || lvl || aFamily;
  gNode.selectAll('g.node').each(function(d) {
    const nd = d.data;
    let match = false;
    if (hasFilter) {
      const txt = (nd.name+' '+(nd.sfia_code||'')).toLowerCase();
      const qm = !q || txt.includes(q);
      const lm = !lvl || (nd.min != null && nd.max != null && lvl >= nd.min && lvl <= nd.max);
      const fm = !aFamily || (nd.type==='role_family' ? nd.name===aFamily : true);
      match = qm && lm && fm &&
        ['sfia_skill','government_capability','role_level','role','role_family'].includes(nd.type);
    }
    d3.select(this).classed('highlight', hasFilter && match).classed('dimmed', false);
  });
}

document.getElementById('search').addEventListener('input', e => { aSearch=e.target.value; applyFilters(); });
document.getElementById('family-filter').addEventListener('change', e => { aFamily=e.target.value; applyFilters(); });
document.getElementById('level-filter').addEventListener('change', e => { aLevel=e.target.value; applyFilters(); });

// ── Bootstrap ─────────────────────────────────────────────────────────────────
fetch('explorer_data.json')
  .then(r => r.json())
  .then(data => initTree(data))
  .catch(err => {
    document.getElementById('tree-panel').innerHTML =
      `<p style="padding:40px;color:red">Failed to load data: ${err.message}</p>`;
  });
