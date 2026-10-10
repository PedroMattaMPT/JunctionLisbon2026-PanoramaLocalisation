# EvidenceCard

One piece of evidence in three registers kept apart: observed (bracketed, mono, what a model saw) → inferred (italic serif after ∴) → estimate (≈ mono in `solver`), plus polarity per candidate and who produced it.

- **Provide:** `e` (`id`, `kind` = text | object | checklist | measure | sun | language | neighbour | region | name | contradiction, `stage`, `actor`, `model`, `obs`, `conf`, `inference`, `estimate`, `pol` {candidate: 1 | 0 | −1}, `notVisible`, `empty`, `t`), `names` (candidate short names), optional `selected`, `compact`, `isNew`, `crop`.
- `not_visible` reads "Can't tell" on a dashed box — never as a failure. A contradiction card is outlined in `contra` and names both sources.
- Selecting a card links it to its pixels and map area (`data-link`).
