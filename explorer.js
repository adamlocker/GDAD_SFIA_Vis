function lvlColor(l) {
  return ['','#94d2bd','#e9d8a6','#ee9b00','#ca6702','#bb3e03','#ae2012','#9b2226'][+l] || '#eee';
}
function lvlTextColor(l) {
  return +l <= 3 ? '#3d2700' : '#fff';
}
function rangeBadge(mn, mx) {
  if (mn == null) return '';
  const pip = (v) => `<span class="lvl-pip" style="background:${lvlColor(v)};color:${lvlTextColor(v)}">${v}</span>`;
  if (mn === mx) return `<span class="range-badge">${pip(mn)}</span>`;
  return `<span class="range-badge">${pip(mn)}<span class="range-sep">–</span>${pip(mx)}</span>`;
}

function nodeR(type) {
  return {root: 14, role_family: 12, role: 15, role_level: 12, government_capability: 13, sfia_skill: 12}[type] || 12;
}
function nodeColors(type) {
  return {
    root:                  {fill: '#001219', stroke: '#000a0e'},
    role_family:           {fill: '#e9d8a6', stroke: '#c9b055'},
    role:                  {fill: '#94d2bd', stroke: '#6ab5a0'},
    role_level:            {fill: '#94d2bd', stroke: '#6ab5a0'},
    government_capability: {fill: '#0a9396', stroke: '#077f82'},
    sfia_skill:            {fill: '#005f73', stroke: '#003f4d'},
  }[type] || {fill: '#ccc', stroke: '#999'};
}
// Pointy-top hexagon
function hexPoints(r) {
  return Array.from({length: 6}, (_, i) => {
    const a = Math.PI / 3 * i - Math.PI / 2;
    return `${(r * Math.cos(a)).toFixed(2)},${(r * Math.sin(a)).toFixed(2)}`;
  }).join(' ');
}
// Regular pentagon, flat-top, vertex pointing up
function pentPoints(r) {
  return Array.from({length: 5}, (_, i) => {
    const a = (2 * Math.PI / 5) * i - Math.PI / 2;
    return `${(r * Math.cos(a)).toFixed(2)},${(r * Math.sin(a)).toFixed(2)}`;
  }).join(' ');
}

function pillColor(type) {
  return {
    root:                  'rgba(0,18,25,0.22)',
    role_family:           'rgba(233,216,166,0.76)',
    role:                  'rgba(148,210,189,0.68)',
    role_level:            'rgba(148,210,189,0.68)',
    government_capability: 'rgba(10,147,150,0.32)',
    sfia_skill:            'rgba(0,95,115,0.28)',
  }[type] || 'rgba(148,210,189,0.55)';
}
function pillStroke(type) {
  return {
    root:                  'rgba(0,18,25,0.55)',
    role_family:           'rgba(201,176,85,0.72)',
    role:                  'rgba(106,181,160,0.68)',
    role_level:            'rgba(106,181,160,0.68)',
    government_capability: 'rgba(7,127,130,0.58)',
    sfia_skill:            'rgba(0,63,77,0.55)',
  }[type] || 'rgba(0,0,0,0.15)';
}
function linkColor(d) {
  return {
    root:                  'rgba(233,216,166,0.55)',
    role_family:           'rgba(148,210,189,0.55)',
    role:                  'rgba(148,210,189,0.50)',
    role_level:            'rgba(10,147,150,0.40)',
    government_capability: 'rgba(0,95,115,0.35)',
  }[d.source.data.type] || '#94d2bd';
}

function sizePill(textEl, rectEl) {
  if (!textEl || !rectEl) return;
  try {
    const w = textEl.getComputedTextLength();
    if (!w) return;
    const fs = parseFloat(window.getComputedStyle(textEl).fontSize) || 14;
    const ph = fs + 10, pw = w + 16;
    const tx = +textEl.getAttribute('x') || 0;
    const anchor = textEl.getAttribute('text-anchor');
    const px = anchor === 'end' ? tx - w - 8 : tx - 8;
    d3.select(rectEl).attr('x', px).attr('y', -(ph / 2)).attr('width', pw).attr('height', ph);
  } catch(e) {}
}
function measurePills() {
  gNode.selectAll('g.node').each(function() {
    sizePill(
      d3.select(this).select('text').node(),
      d3.select(this).select('rect.node-pill').node()
    );
  });
}

const MARGIN = {t: 40, r: 420, b: 40, l: 400};
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

const treeFn = d3.tree().nodeSize([56, 420]);

let uid = 0;
let root;
let snapMode = false;
function toggleSnap() {
  snapMode = !snapMode;
  document.getElementById('snap-btn').classList.toggle('snap-active', snapMode);
}
function snapTo(d) {
  const r = svgEl.getBoundingClientRect();
  svg.transition().duration(380).call(
    zoom.transform,
    d3.zoomIdentity.translate(r.width / 3 - d.y, r.height / 2 - d.x)
  );
}

function initTree(data) {
  // Build family chips
  const chipsEl = document.getElementById('family-chips');
  data.children.forEach(f => {
    const btn = document.createElement('button');
    btn.className = 'family-chip';
    btn.dataset.family = f.name;
    btn.textContent = toTitleCase(f.name);
    btn.addEventListener('click', () => {
      if (aFamily.has(f.name)) {
        aFamily.delete(f.name);
        toggleFamilyNode(f.name, false);
      } else {
        aFamily.add(f.name);
        toggleFamilyNode(f.name, true);
      }
      btn.classList.toggle('family-chip--active', aFamily.has(f.name));
      updateRoleChips();
      applyFilters();
    });
    chipsEl.appendChild(btn);
  });

  root = d3.hierarchy(data);
  root.descendants().forEach(d => {
    d._uid = ++uid;
    if (d.depth >= 1) { d._children = d.children; d.children = null; }
  });
  root.x0 = 0; root.y0 = 0;
  buildSearchIndex(root);

  requestAnimationFrame(() => {
    const r = svgEl.getBoundingClientRect();
    update(root);
    svg.call(zoom.transform, d3.zoomIdentity.translate(MARGIN.l, r.height / 2));
    showDetail(root);
  });
}

function update(src) {
  treeFn(root);
  const nodes = root.descendants();
  const links = root.links();

  const node = gNode.selectAll('g.node').data(nodes, d => d._uid);

  const enter = node.enter().append('g')
    .attr('class', d => `node ${d.data.type}${d.data.broadly_accepted ? ' broadly-accepted' : ''}`)
    .attr('transform', () => `translate(${src.y0 ?? 0},${src.x0 ?? 0})`)
    .on('click', (evt, d) => { toggle(d); update(d); showDetail(d); if (snapMode) snapTo(d); })
    .on('mouseenter', (evt, d) => dimOthers(d))
    .on('mouseleave', () => undim());

  enter.append('title').text(d => tcNode(d.data.type, d.data.name));

  // Shape — varies by node type
  enter.each(function(d) {
    const r = nodeR(d.data.type);
    const c = (d.data.type === 'government_capability' && d.data.broadly_accepted)
      ? {fill: '#94d2bd', stroke: '#6ab5a0'}
      : nodeColors(d.data.type);
    const g = d3.select(this);
    let el;
    switch (d.data.type) {
      case 'role':
        el = g.append('rect').attr('class', 'node-shape')
          .attr('x', -r).attr('y', -r)
          .attr('width', r * 2).attr('height', r * 2)
          .attr('rx', 5).attr('ry', 5);
        break;
      case 'role_level':
        el = g.append('polygon').attr('class', 'node-shape').attr('points', hexPoints(r));
        break;
      case 'government_capability':
        el = g.append('polygon').attr('class', 'node-shape').attr('points', pentPoints(r));
        break;
      case 'sfia_skill':
        el = g.append('polygon').attr('class', 'node-shape').attr('points', hexPoints(r));
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
    .style('fill', d => (d.data.type === 'government_capability' && d.data.broadly_accepted) ? 'rgba(148,210,189,0.78)' : pillColor(d.data.type))
    .style('stroke', d => (d.data.type === 'government_capability' && d.data.broadly_accepted) ? 'rgba(106,181,160,0.72)' : pillStroke(d.data.type))
    .style('stroke-width', '0.8px');

  enter.append('text')
    .attr('x', d => (d.children || d._children) ? -(nodeR(d.data.type) + 12) : (nodeR(d.data.type) + 12))
    .attr('text-anchor', d => (d.children || d._children) ? 'end' : 'start')
    .text(d => trunc(tcNode(d.data.type, d.data.name), 38));

  // Size pills — deferred to next frame so text is measurable
  requestAnimationFrame(() => {
    enter.each(function() {
      sizePill(
        d3.select(this).select('text').node(),
        d3.select(this).select('rect.node-pill').node()
      );
    });
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
    .attr('x', d => (d.children || d._children) ? -(nodeR(d.data.type) + 12) : (nodeR(d.data.type) + 12))
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
  setTimeout(measurePills, 600);
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
const TC_SMALL = new Set(['a','an','the','and','but','or','nor','for','in','of','on','at','to','by','with','via','as','per']);
function toTitleCase(s) {
  if (!s) return s;
  s = s.replace(/\s*\(QAT\)\s*/gi, '').trim();
  return s.split(' ').map((w, i) =>
    (!w || (i > 0 && TC_SMALL.has(w.toLowerCase()))) ? w.toLowerCase() : w.charAt(0).toUpperCase() + w.slice(1)
  ).join(' ');
}
const TC_TYPES = new Set(['role_family','role','role_level']);
function tcNode(type, s) {
  const v = TC_TYPES.has(type) ? toTitleCase(s) : s;
  return v ? v.replace(/ — /g, ' | ') : v;
}
function shortLevel(roleName, levelName, band) {
  const variant = (levelName.match(/ - (.+)$/) || [])[1] || null;
  const base = levelName.replace(/ - .+$/, '');
  const esc = roleName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const short = base.replace(new RegExp('\\b' + esc + '\\b', 'gi'), '').trim();
  const label = (short && short.length <= 18 && short.toLowerCase() !== base.toLowerCase())
    ? short : (band || base);
  return variant ? `${label} (${variant})` : label;
}

const bandSelection = {};

function selectBand(roleId, bandIndex) {
  bandSelection[roleId] = bandIndex;
  const roleNode = allNodes(root).find(n => n.data.id === roleId);
  if (!roleNode) return;

  const bandData = roleNode.data.role_levels[bandIndex];
  const newChildData = bandData ? (bandData.children || []) : [];
  const wasExpanded = !!roleNode.children;

  roleNode.children = null;
  roleNode._children = null;

  if (newChildData.length > 0) {
    const tempHier = d3.hierarchy({ children: newChildData });
    const newNodes = tempHier.children || [];

    function collapseSubtree(node) {
      if (node.children) { node._children = node.children; node.children = null; }
      (node._children || []).forEach(collapseSubtree);
    }
    newNodes.forEach(collapseSubtree);

    function fixRefs(node, parent, depth) {
      node.parent = parent;
      node.depth = depth;
      (node.children || node._children || []).forEach(c => fixRefs(c, node, depth + 1));
    }
    newNodes.forEach(c => fixRefs(c, roleNode, roleNode.depth + 1));

    if (wasExpanded) {
      roleNode.children = newNodes;
    } else {
      roleNode._children = newNodes;
    }
  }

  update(roleNode);
  showDetail(roleNode);
}

function navigateToSfiaFromRole(roleId, bandIdx, nodeId) {
  if ((bandSelection[roleId] ?? 0) !== bandIdx) {
    selectBand(roleId, bandIdx);
  }
  navigateToNode(nodeId);
}
function govLevelBadge(level) {
  const map = {
    'Awareness':    ['Aw', 'awareness'],
    'Working':      ['W',  'working'],
    'Practitioner': ['P',  'practitioner'],
    'Expert':       ['E',  'expert'],
    'Master':       ['M',  'master'],
  };
  const [abbr, cls] = map[level] || (level ? [level[0], 'working'] : ['?', 'working']);
  return `<span class="gov-level-pip gov-lvl-${cls}">${abbr}</span>`;
}
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

  const labels = {root:'Profession Framework',role_family:'Role Family',role:'Role',role_level:'Role Level',
    government_capability:'Government Capability',sfia_skill:'SFIA 9 Skill'};
  let h = `<div class="detail-type">${labels[nd.type]||nd.type}</div><div class="detail-title">${tcNode(nd.type, nd.name)}</div>`;

  if (nd.type === 'root') {
    const families = d.children || d._children || [];
    h += `<div class="detail-section"><p style="font-size:14px;line-height:1.6;color:var(--text-mid)">Use this panel to navigate the framework — select a role family to explore roles, capabilities and SFIA skills.</p></div>`;
    h += `<div class="detail-section"><h3>Role families (${families.length})</h3>`;
    families.forEach(f => {
      h += `<div class="nav-chip" onclick="navigateToNode('${f.data.id}')"><span style="flex:1">${toTitleCase(f.data.name)}</span><span style="color:var(--accent);font-size:15px">→</span></div>`;
    });
    h += `</div>`;
  }
  if (nd.type === 'role_family') {
    const roles = d.children || d._children || [];
    h += `<div class="detail-section"><h3>Roles (${roles.length})</h3>`;
    roles.forEach(r => {
      h += `<div class="nav-chip" onclick="navigateToNode('${r.data.id}')"><span style="flex:1">${toTitleCase(r.data.name)}</span><span style="color:var(--accent);font-size:15px">→</span></div>`;
    });
    h += `</div>`;
  }
  if (nd.type === 'role') {
    h += `<div class="detail-section"><h3>Family</h3><p class="detail-family">${toTitleCase(nd.role_family)}</p></div>`;
    const rls = nd.role_levels || [];
    const bandIdx = bandSelection[nd.id] ?? 0;
    const rl = rls[bandIdx] || {};

    h += `<div class="detail-section"><div class="band-selector">`;
    rls.forEach((level, i) => {
      h += `<button class="band-pill${i===bandIdx?' band-pill--active':''}" onclick="selectBand('${nd.id}',${i})">${toTitleCase(shortLevel(nd.name, level.name, level.band))}</button>`;
    });
    h += `</div></div>`;

    const caps = rl.children || [];
    const totalSkills = [...new Set(caps.flatMap(c => (c.children||[]).map(s => s.sfia_code)))].length;
    h += `<div class="detail-section"><h3>Capabilities &amp; skills (${caps.length} / ${totalSkills})</h3>`;
    caps.forEach(c => {
      const skills = c.children || [];
      if (skills.length > 0) {
        h += `<div class="cap-group"><div class="cap-chip" style="cursor:pointer" onclick="navigateToSfiaFromRole('${nd.id}',${bandIdx},'${c.id}')">${govLevelBadge(c.gov_level)}<span style="flex:1">${c.name}</span><span style="color:var(--accent);font-size:15px;flex-shrink:0">→</span></div><div class="skills-rail">`;
        skills.forEach(s => {
          h += `<div class="sfia-chip" style="cursor:pointer" onclick="navigateToSfiaFromRole('${nd.id}',${bandIdx},'${s.id}')">${rangeBadge(s.min,s.max)}<span style="flex:1">${s.name.replace(/^[A-Z]+ — /,'')}</span><span style="color:var(--accent);font-size:15px;flex-shrink:0">→</span></div>`;
        });
        h += `</div></div>`;
      } else {
        h += `<div class="cap-group"><div class="cap-chip cap-chip--broad" style="cursor:pointer" onclick="navigateToSfiaFromRole('${nd.id}',${bandIdx},'${c.id}')">${govLevelBadge(c.gov_level)}<span style="flex:1">${c.name}</span><span style="color:var(--burnt-caramel);font-size:15px;flex-shrink:0">→</span></div></div>`;
      }
    });
    h += `</div>`;
  }
  if (nd.type === 'government_capability') {
    const sfias = d.children||d._children||[];
    if (nd.description) {
      h += `<div class="detail-section"><p style="font-size:15px;line-height:1.6;color:var(--text)">${nd.description}</p></div>`;
    }
    const lvlMap = {Awareness:['Aw','awareness'],Working:['W','working'],Practitioner:['P','practitioner'],Expert:['E','expert'],Master:['M','master']};
    const [abbr, lvlCls] = lvlMap[nd.gov_level] || [nd.gov_level?.[0]||'?', 'working'];
    h += `<div class="detail-section"><h3>Gov. skill level</h3><div class="gov-lvl-${lvlCls}" style="display:flex;align-items:center;gap:8px;border-radius:7px;padding:7px 10px;margin-top:5px;border:1px solid rgba(0,0,0,0.15)"><span style="flex:1;font-size:15px;font-weight:600">${nd.gov_level||'—'}</span><span style="font-size:12px;font-weight:700;padding:2px 7px;border-radius:4px;background:rgba(0,0,0,0.15)">${abbr}</span></div></div>`;
    if (sfias.length) {
      h += `<div class="detail-section"><h3>SFIA skills (${sfias.length})</h3>`;
      sfias.forEach(s => {
        h += `<div class="sfia-chip" style="cursor:pointer" onclick="navigateToNode('${s.data.id}')">${rangeBadge(s.data.min,s.data.max)}<span style="flex:1">${s.data.name.replace(/^[A-Z]+ — /,'')}</span><span style="color:var(--accent);font-size:15px;flex-shrink:0">→</span></div>`;
      });
      h += `</div>`;
    } else {
      h += `<div class="detail-section"><p style="font-size:14px;color:var(--text-light);font-style:italic">No SFIA skills mapped — broadly accepted behaviour.</p></div>`;
    }
  }
  if (nd.type === 'sfia_skill') {
    const width = (nd.max != null && nd.min != null) ? nd.max - nd.min : 0;
    h += `<div class="detail-section">
      <div style="display:flex;align-items:baseline;gap:10px">
        <p style="font-size:16px;font-weight:700;color:var(--accent)">${nd.sfia_code}</p>
        <p style="font-size:13px;color:var(--text-light)">${nd.sfia_category}${nd.sfia_subcategory ? ' · '+nd.sfia_subcategory : ''}</p>
      </div>
      ${nd.sfia_description ? `<p style="font-size:15px;line-height:1.5;margin-top:6px;color:var(--text)">${nd.sfia_description}</p>` : ''}
    </div>`;

    if (nd.sfia_guidance) {
      const lines = nd.sfia_guidance.split('\n').filter(l => l.trim());
      const isIntro = l => l.trimEnd().endsWith(':') && l.length < 80;
      const items = lines;
      const SHOW = 4;
      const gid = 'g' + Math.random().toString(36).slice(2);
      h += `<div class="detail-section"><h3>Guidance notes</h3>`;
      const introLine = it => `<p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text-light);margin-bottom:5px;margin-top:6px">${it}</p>`;
      const arrowItem = it => `<div style="display:flex;gap:6px;align-items:flex-start;margin-bottom:3px;font-size:14px;line-height:1.6;color:var(--text)"><span style="color:var(--text-light);flex-shrink:0;font-weight:700;margin-top:1px">›</span><span>${it}</span></div>`;
      const renderItems = (list) => list.map(it => isIntro(it) ? introLine(it) : arrowItem(it)).join('');
      h += `<div>${renderItems(items.slice(0, SHOW))}</div>`;
      if (items.length > SHOW) {
        h += `<div id="${gid}" style="display:none">${renderItems(items.slice(SHOW))}</div>
        <button id="${gid}-btn" onclick="toggleGuidance('${gid}')"
          style="margin-top:6px;font-size:13px;color:var(--accent);background:none;border:none;cursor:pointer;padding:0;font-weight:600">
          Show all ${items.length} activities
        </button>`;
      }
      h += `</div>`;
    }

    h += `<div class="detail-section"><h3>Expected SFIA level range</h3>
      <div style="display:flex;align-items:center;gap:10px;margin-top:4px">
        ${rangeBadge(nd.min, nd.max)}
        <span style="font-size:14px;color:var(--text-mid)">${nd.min===nd.max ? `Level ${nd.min}` : `Levels ${nd.min} to ${nd.max}`}${width>2?' — wider range due to multiple capabilities':''}</span>
      </div>
    </div>`;

    if (nd.level_descriptions && nd.min != null) {
      h += `<div class="detail-section"><h3>What this looks like at each level</h3>`;
      for (let lvl = nd.min; lvl <= nd.max; lvl++) {
        const desc = nd.level_descriptions[String(lvl)];
        if (desc) {
          h += `<div style="display:flex;gap:10px;margin-bottom:10px;align-items:flex-start">
            <span class="lvl-pip" style="background:${lvlColor(lvl)};color:${lvlTextColor(lvl)};flex-shrink:0;margin-top:2px">${lvl}</span>
            <p style="font-size:14px;line-height:1.55;color:var(--text)">${desc}</p>
          </div>`;
        }
      }
      h += `</div>`;
    }

    h += `<div class="detail-section"><h3>Evidence (${nd.count} gov. capability${nd.count!==1?'s':''})</h3>
      <p style="font-size:14px;color:var(--text-mid);line-height:1.5">${nd.evidence}</p>
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
let aSearch='', aFamily=new Set(), aRole=new Set();

function nodeFamily(d) {
  let cur = d;
  while (cur) {
    if (cur.data.type === 'role_family') return cur.data.name;
    cur = cur.parent;
  }
  return null;
}

function nodeRoleId(d) {
  let cur = d;
  while (cur) {
    if (cur.data.type === 'role') return cur.data.id;
    cur = cur.parent;
  }
  return null;
}

function toggleFamilyNode(name, expand) {
  const n = allNodes(root).find(d => d.data.type === 'role_family' && d.data.name === name);
  if (!n) return;
  if (expand && n._children) { n.children = n._children; n._children = null; }
  if (!expand && n.children) { n._children = n.children; n.children = null; }
  update(n);
}

function updateRoleChips() {
  const container = document.getElementById('role-chips');
  container.innerHTML = '';
  aRole.clear();

  if (aFamily.size === 0) {
    container.style.display = 'none';
    return;
  }

  const roles = [];
  allNodes(root)
    .filter(d => d.data.type === 'role_family' && aFamily.has(d.data.name))
    .forEach(fn => {
      const ch = fn.children || fn._children || [];
      ch.filter(c => c.data.type === 'role').forEach(r => roles.push(r));
    });

  roles.sort((a, b) => a.data.name.localeCompare(b.data.name)).forEach(r => {
    const btn = document.createElement('button');
    btn.className = 'role-chip';
    btn.dataset.roleId = r.data.id;
    btn.textContent = tcNode('role', r.data.name);
    btn.addEventListener('click', () => {
      if (aRole.has(r.data.id)) aRole.delete(r.data.id); else aRole.add(r.data.id);
      btn.classList.toggle('role-chip--active', aRole.has(r.data.id));
      applyFilters();
    });
    container.appendChild(btn);
  });

  container.style.display = 'flex';
}

function applyFilters() {
  const q = aSearch.toLowerCase().trim();

  gNode.selectAll('g.node').each(function(d) {
    const nd = d.data;

    const fam = nodeFamily(d);
    const dimmedByFamily = aFamily.size > 0 && fam !== null && !aFamily.has(fam);

    const rid = nodeRoleId(d);
    const dimmedByRole = !dimmedByFamily && aRole.size > 0 && rid !== null && !aRole.has(rid);

    const dimmed = dimmedByFamily || dimmedByRole;

    let highlighted = false;
    if (!dimmed && q) {
      const txt = (nd.name + ' ' + (nd.sfia_code || '')).toLowerCase();
      const typeMatch = ['sfia_skill','government_capability','role_level','role','role_family'].includes(nd.type);
      highlighted = txt.includes(q) && typeMatch;
    }

    d3.select(this).classed('highlight', highlighted).classed('dimmed', dimmed);
  });
}

// ── Autocomplete ──────────────────────────────────────────────────────────────
let searchIndex = [];

function buildSearchIndex(node) {
  searchIndex = allNodes(node)
    .filter(d => d.data.type !== 'root')
    .map(d => ({
      id: d.data.id,
      type: d.data.type,
      display: tcNode(d.data.type, d.data.name),
      raw: d.data.name.toLowerCase(),
      code: (d.data.sfia_code || '').toLowerCase(),
    }));
}

const SD_BADGE = {
  role_family:           'background:#ee9b00;color:#3d2700',
  role:                  'background:#0a9396;color:#fff',
  role_level:            'background:#005f73;color:#fff',
  government_capability: 'background:#bb3e03;color:#fff',
  sfia_skill:            'background:#9b2226;color:#fff',
};
const SD_LABEL = {
  role_family: 'Family', role: 'Role', role_level: 'Level',
  government_capability: 'Capability', sfia_skill: 'SFIA Skill',
};

const sdEl = document.getElementById('search-dropdown');
let sdFocusIdx = -1;

function openDropdown(q) {
  const results = searchIndex
    .filter(e => e.raw.includes(q) || e.code.includes(q))
    .map(e => {
      const score = (e.raw === q || e.code === q) ? 0
        : (e.raw.startsWith(q) || e.code.startsWith(q)) ? 1 : 2;
      return { ...e, score };
    })
    .sort((a, b) => a.score - b.score || a.display.localeCompare(b.display))
    .slice(0, 8);

  sdFocusIdx = -1;
  if (!results.length) {
    sdEl.innerHTML = '<div class="sd-empty">No matches</div>';
  } else {
    sdEl.innerHTML = results.map((r, i) =>
      `<div class="sd-item" data-id="${r.id}" data-idx="${i}">`
      + `<span class="sd-badge" style="${SD_BADGE[r.type]||''}">${SD_LABEL[r.type]||r.type}</span>`
      + `<span class="sd-name">${r.display}</span>`
      + `</div>`
    ).join('');
    sdEl.querySelectorAll('.sd-item').forEach(el => {
      el.addEventListener('mousedown', e => { e.preventDefault(); selectResult(el.dataset.id); });
    });
  }
  sdEl.classList.add('open');
}

function closeDropdown() {
  sdEl.classList.remove('open');
  sdFocusIdx = -1;
}

function selectResult(id) {
  const inp = document.getElementById('search');
  inp.value = '';
  aSearch = '';
  applyFilters();
  closeDropdown();
  navigateToNode(id);
}

const searchInp = document.getElementById('search');

searchInp.addEventListener('input', e => {
  aSearch = e.target.value;
  applyFilters();
  const q = aSearch.toLowerCase().trim();
  if (q.length >= 2) openDropdown(q); else closeDropdown();
});

searchInp.addEventListener('keydown', e => {
  if (!sdEl.classList.contains('open')) return;
  const items = sdEl.querySelectorAll('.sd-item');
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    sdFocusIdx = Math.min(sdFocusIdx + 1, items.length - 1);
    items.forEach((el, i) => el.classList.toggle('sd-focus', i === sdFocusIdx));
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    sdFocusIdx = Math.max(sdFocusIdx - 1, 0);
    items.forEach((el, i) => el.classList.toggle('sd-focus', i === sdFocusIdx));
  } else if (e.key === 'Enter' && sdFocusIdx >= 0) {
    e.preventDefault();
    selectResult(items[sdFocusIdx].dataset.id);
  } else if (e.key === 'Escape') {
    closeDropdown();
    searchInp.blur();
  }
});

searchInp.addEventListener('blur', () => setTimeout(closeDropdown, 150));


// ── Bootstrap ─────────────────────────────────────────────────────────────────
fetch('explorer_data.json')
  .then(r => r.json())
  .then(data => initTree(data))
  .catch(err => {
    document.getElementById('tree-panel').innerHTML =
      `<p style="padding:40px;color:red">Failed to load data: ${err.message}</p>`;
  });
