# Kalpavriksha UI Primitives

| Component | Purpose | Design Constitution rule enforced |
|---|---|---|
| `Panel` | Fundamental content surface with optional tone and padding | Depth §: content plane only; no shadows; edge luminosity via hairline border; transparency at .028/.05 |
| `Kicker` | Small uppercase mono label above a heading | Typography §: IBM Plex Mono for labels; state via colour AND word |
| `H1` / `H2` / `H3` | Hierarchical headings in Inter | Typography §: flush left; weight 500 emphasis; line-heights are 8px multiples |
| `Speech` | 38/48 AI voice paragraph style | §5 narration: text is the source of truth; distinct from headings |
| `Body` / `Lede` / `Dim` | Prose text at body, lede, and muted scales | Typography §: Inter for judgment; flush left; never centred |
| `Mono` | Inline mono span for facts | Typography §: IBM Plex Mono for IDs, timestamps, amounts; never mixed with prose in one thought |
| `Button` | Interactive control, 48px at md | Grid §: 48px = 6 × 8px baseline; hard-edged (radius 0); four variants only |
| `Tag` | Mono uppercase hairline label chip | Typography §: mono for labels; state via colour AND word; greyscale-survivable |
| `Stat` | Large tabular numeral with left-rule signal | Typography §: tabular numerals; Colour §: left rule carries signal identity |
| `Bar` | 2px progress bar | Motion §: linear transition only for progress; no easing |
| `Rule` | 1px hairline divider | Palette §: hairline tokens; no decorative elements |
| `DataTable` | Typed columnar data with sticky header | Typography §: mono facts vs prose; Grid §: 48px row height; hover = panel-active |
| `Timeline` | Vertical event list with 7px nodes | Depth §: content plane; State via colour AND word on each item |
| `EmptyState` | Calm placeholder for empty collections | Constitution: "the empty state is the destination, not a failure"; flush left; no error language |
| `ErrorState` | Designed failure state for `KernelError` | Eng. Law IV: failure states must be designed; shows retry only when `retryable`; message must read as a sentence |
| `Skeleton` | Static loading placeholder | Motion §: nothing pulses or shimmers; static hairline block only |
| `UndoToast` | Undo affordance after consequential actions | Depth §: transient plane; 14px backdrop-blur; transparency .94; ONLY transient surface; notifications forbidden |
| `ConfidenceMark` | Renders `Confidence` union as filled marks + phrasing | §10: three-level union only; percentage rendering is impossible by construction |
| `ConsequenceGrid` | Renders `Consequence` quartet in 2×2 grid | Principle VI: all four fields required; money formatted via `@/lib/format` |
| `Sparkline` | Inline SVG trend line | Motion §: no animation; Typography §: mono facts, no axes |
| `TextField` | Hairline text input with mono label | Typography §: mono labels; Grid §: 40px height = 5 × 8px |
| `SelectField` | Hairline select with mono label | Typography §: mono labels; hard-edged |
| `SearchField` | Hairline search input with icon | Typography §: mono labels; icon only decorative |
| `Tabs` | Hairline-underline navigation with mono labels | Typography §: mono for labels; Colour §: active underline uses `--signal-live` |
| `SplitView` | Master/detail two-column layout | Grid §: 12-column alignment via configurable ratio |
| `KeyValue` | Mono key / prose value pairing | Typography §: IBM Plex Mono for facts, Inter for judgment; never mixed in one thought |
