#!/usr/bin/env python3
"""
Patch raw CSV to add missing core capabilities where the capability name
closely matches the role name but is absent from the role's skill list.
Descriptions are copied from existing rows that already use the capability.
Run once; re-running is safe (deduplication check prevents double-patching).
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / 'data' / 'raw' / 'Role and skill content - Capability Framework - Government Digital and Data profession2026-06-05_11-47-23.csv'

# (Role, Role Level, Skill Name, Skill Level)
PATCHES = [
    # Data architect ← Data architecture
    ('Data architect', 'Data architect',        'Data architecture', 'Working'),
    ('Data architect', 'Senior data architect', 'Data architecture', 'Practitioner'),
    ('Data architect', 'Chief data architect',  'Data architecture', 'Expert'),

    # Security architect ← Security architecture
    ('Security architect', 'Security architect',          'Security architecture', 'Working'),
    ('Security architect', 'Lead security architect',     'Security architecture', 'Practitioner'),
    ('Security architect', 'Principal security architect','Security architecture', 'Expert'),

    # Data engineer ← Data engineering
    ('Data engineer', 'Data engineer',          'Data engineering', 'Working'),
    ('Data engineer', 'Senior data engineer',   'Data engineering', 'Practitioner'),
    ('Data engineer', 'Lead data engineer',     'Data engineering', 'Expert'),
    ('Data engineer', 'Head of data engineering','Data engineering','Expert'),

    # QA test analyst ← Testing
    ('Quality assurance test analyst', 'Associate quality assurance test analyst', 'Testing', 'Awareness'),
    ('Quality assurance test analyst', 'Quality assurance test analyst',           'Testing', 'Working'),
    ('Quality assurance test analyst', 'Senior quality assurance test analyst',    'Testing', 'Practitioner'),
    ('Quality assurance test analyst', 'Lead quality assurance test analyst',      'Testing', 'Expert'),

    # Test engineer ← Testing
    ('Test engineer', 'Associate test engineer', 'Testing', 'Awareness'),
    ('Test engineer', 'Test engineer',           'Testing', 'Working'),
    ('Test engineer', 'Senior test engineer',    'Testing', 'Practitioner'),
    ('Test engineer', 'Lead test engineer',      'Testing', 'Expert'),

    # Test manager ← Testing
    ('Test manager', 'Test manager',  'Testing', 'Expert'),
    ('Test manager', 'Head of test',  'Testing', 'Expert'),

    # Accessibility specialist ← Accessibility
    ('Accessibility specialist', 'Junior accessibility specialist', 'Accessibility', 'Awareness'),
    ('Accessibility specialist', 'Accessibility specialist',        'Accessibility', 'Working'),
    ('Accessibility specialist', 'Senior accessibility specialist', 'Accessibility', 'Practitioner'),
    ('Accessibility specialist', 'Head of accessibility',          'Accessibility', 'Expert'),

    # Content designer ← User-centred content design
    ('Content designer', 'Associate content designer', 'User-centred content design', 'Awareness'),
    ('Content designer', 'Junior content designer',    'User-centred content design', 'Awareness'),
    ('Content designer', 'Content designer',           'User-centred content design', 'Working'),
    ('Content designer', 'Senior content designer',    'User-centred content design', 'Practitioner'),
    ('Content designer', 'Lead content designer',      'User-centred content design', 'Expert'),
    ('Content designer', 'Head of content design',     'User-centred content design', 'Expert'),
]

def main():
    df = pd.read_csv(CSV)

    # Build lookup tables from existing rows: skill_desc[skill_name] and
    # level_desc[(skill_name, level)] so we can copy descriptions faithfully.
    skill_desc = {}
    level_desc = {}
    for _, r in df.iterrows():
        sn = r['Skill Name']
        sl = r['Skill Level']
        sd = r.get('Skill Description', '')
        sld = r.get('Skill Level Description', '')
        if sn not in skill_desc and pd.notna(sd) and str(sd).strip() not in ('', 'MISSING'):
            skill_desc[sn] = sd
        key = (sn, sl)
        if key not in level_desc and pd.notna(sld) and str(sld).strip():
            level_desc[key] = sld

    # Build lookup for role-level metadata (Role Description, Role Level Description)
    role_desc = {}
    role_level_desc = {}
    role_family_map = {}
    for _, r in df.iterrows():
        role = r['Role']
        rl = r['Role Level']
        if role not in role_desc and pd.notna(r.get('Role Description', '')):
            role_desc[role] = r['Role Description']
        if (role, rl) not in role_level_desc and pd.notna(r.get('Role Level Description', '')):
            role_level_desc[(role, rl)] = r['Role Level Description']
        if role not in role_family_map:
            role_family_map[role] = r['Role Family']

    # Dedup key: existing (Role, Role Level, Skill Name) combinations
    existing = set(zip(df['Role'], df['Role Level'], df['Skill Name']))

    new_rows = []
    skipped = []
    for role, role_level, skill_name, skill_level in PATCHES:
        key = (role, role_level, skill_name)
        if key in existing:
            skipped.append(key)
            continue
        row = {
            'Role Family': role_family_map.get(role, ''),
            'Role': role,
            'Role Description': role_desc.get(role, ''),
            'Role Level': role_level,
            'Role Level Description': role_level_desc.get((role, role_level), ''),
            'Skill Name': skill_name,
            'Skill Description': skill_desc.get(skill_name, 'MISSING'),
            'Skill Level': skill_level,
            'Skill Level Description': level_desc.get((skill_name, skill_level), ''),
            'Role Type': None,
        }
        new_rows.append(row)

    if skipped:
        print(f'Skipped (already present): {len(skipped)}')
        for k in skipped:
            print(f'  {k}')

    if not new_rows:
        print('Nothing to add.')
        return

    patched = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    patched.to_csv(CSV, index=False)
    print(f'Added {len(new_rows)} rows to {CSV.name}:')
    for r in new_rows:
        print(f'  {r["Role"]} / {r["Role Level"]} <- {r["Skill Name"]} ({r["Skill Level"]})')

if __name__ == '__main__':
    main()
