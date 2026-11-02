# Resource Selection

Choose the smallest layout that removes ambiguity. Every bundled file must be
referenced directly from `SKILL.md` and must earn its place.

## Decision table

| Need | Put it in | Loaded how |
|---|---|---|
| Core workflow and rules | `SKILL.md` | Read when the skill activates |
| A deterministic operation the agent repeats | `scripts/` | Executed; only output enters context |
| Detailed documentation, schemas, or examples | `references/` | Read only when the agent follows the link |
| A template, icon, font, or file used in the output | `assets/` | Copied or used; not read into context |

## Use scripts when

- The operation is fragile or error-prone.
- The same code would otherwise be regenerated on every use.
- Validation must be objective and repeatable.
- The agent should not spend context tokens reading the implementation.

Examples: form filling, file conversion, schema validation, data migration.

Keep scripts small, documented, and free of unexplained constants. Make the
run-versus-read intent explicit in `SKILL.md`.

## Use references when

- The detail is useful only for a subset of tasks.
- The material is too long for the 500-line body budget.
- There are domain variants such as finance, sales, and marketing schemas.
- Examples and API signatures would clutter the core workflow.

Examples: API references, style guides, domain schemas, long worked examples.

Link each reference directly from `SKILL.md`. Do not require the agent to follow
a reference to another reference.

## Use assets when

- The file is part of the output rather than instructions.
- The agent should copy and customize a template.
- Binary resources such as icons or fonts are needed.

Examples: report templates, presentation layouts, HTML boilerplates, brand
assets.

## Layout patterns

### Minimal

```text
my-skill/
└── SKILL.md
```

### Guide plus references

```text
my-skill/
├── SKILL.md
└── references/
    ├── finance.md
    ├── sales.md
    └── product.md
```

### Workflow plus scripts

```text
my-skill/
├── SKILL.md
└── scripts/
    ├── analyze.py
    ├── validate.py
    └── apply.py
```

### Full layout

```text
my-skill/
├── SKILL.md
├── scripts/
│   └── validate.py
├── references/
│   └── authoring-guide.md
└── assets/
    └── output-template.md
```

Add directories only when the skill uses them. Empty folders add noise and
suggest resources that do not exist.
