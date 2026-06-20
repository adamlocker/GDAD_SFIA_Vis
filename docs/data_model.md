# Data model

The canonical graph model is:

```text
role_family → role → role_level → government_capability → sfia_skill
```

## Node types

- `role_family`
- `role`
- `role_level`
- `government_capability`
- `sfia_skill`

## Edge types

- `contains_role`: role family → role
- `has_role_level`: role → role level
- `requires_capability`: role level → Government capability
- `maps_to_sfia`: Government capability → SFIA skill
- `derived_role_level_to_sfia`: optional projection used for chord/summary views

The collapsible tree uses a hierarchy rather than raw graph edges, but the hierarchy is derived from the same model.
