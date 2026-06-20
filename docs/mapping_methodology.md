# Mapping methodology

## Capability mapping

Capability mappings are read from `mapping/mapping_decisions.json`.

Decision categories:

- `sfia_mapping`: maps to one or more SFIA skills.
- `generic_attribute`: not modelled as a SFIA professional skill.
- `role_context_dependent`: not forced globally.
- `ignored_heading`: not a capability.

## SFIA level recommendation

The level model is a heuristic:

```text
role-level seniority band + Government capability-level adjustment = raw target SFIA level
raw target constrained to levels available for the mapped SFIA skill = recommended SFIA level
```

Government capability adjustments:

- Awareness: -2
- Working: -1
- Practitioner: 0
- Expert: +1

Confidence:

- High: exact level available
- Medium: adjusted by 1 level
- Low: adjusted by more than 1 level

Low-confidence rows should be prioritised for SME review.
