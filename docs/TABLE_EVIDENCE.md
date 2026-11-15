# Opt-in CSV and Markdown evidence

Enable `settings.table_evidence: true` in a new reviewed workspace/configuration. Defaults retain legacy CSV extraction and existing historical fingerprints. For source-calculation mode also keep `chunk_strategy: sentences` and `answering_mode: source_calculation` with explicitly authorized per-task calculation contracts. This does not enable automatic semantic approval.

## Supported structures

Long CSV uses an unambiguous subject column (`subject`, `entity`, `company`, `product` or `plan`), an optional explicit predicate column (`predicate`, `attribute` or `metric`), a period/year column, a numeric value and an explicit unit. Example grammar:

```csv
company,attribute,period,value,unit
ExampleCo,revenue,FY2024,1200,USD
ExampleCo,revenue,FY2025,1350,USD
```

Wide history uses explicit period headers, an attribute and a unit:

```csv
company,attribute,unit,FY2024,FY2025
ExampleCo,revenue,USD,1200,1350
```

Markdown tables require a valid alignment row. A specific value header can declare both predicate and units:

```markdown
| Plan | Period | Price USD |
|---|---|---|
| Pro | Q2 | 24 |
```

A contract may name subject `Plan Pro`, predicate `price`, unit `USD`, period `Q2`. Header-plus-cell association is exact and deterministic, not fuzzy entity matching. Units come from a column or explicit value header, never merely from the requested unit. Periods come from a row or explicit historical header. The intended operation still requires the existing question/scope/formula authorization.

Quoted CSV commas/multiline fields, escaped Markdown pipes, raw byte hashes and exact cell/header spans are preserved. Offsets count UTF-8-sig decoded document characters with original newlines; byte provenance is a separate SHA-256. They are not byte offsets. Entire literal table blocks use stable content/offset-bound `#chunk-t...` IDs; the table's source version and original cells are retained for every operand. Values are not rewritten into invented natural-language source sentences.

## Refusal boundaries

Duplicate/ambiguous headers, conflicting rows, malformed row widths, missing cells, unknown units, implicit conversion, nonnumeric expressions, unrecognized nonempty qualification columns and nearby qualification language require review/refusal. Scope/date checks continue to use explicit source metadata. Row-level jurisdiction/date columns and narrative captions are not silently interpreted as authoritative applicability or units. General financial-table semantics, nested/multilevel headers, arbitrary markup, and OCR tables are unverified.

A table larger than `chunk_chars` is not partially selected or forwarded wholesale to a model; selection records `excluded_oversized_table_ids`. Split such a source into separately meaningful, reviewed tables rather than relying on truncation. Conflicting values remain visible and prevent calculation. Nearby qualification detection is conservative and can reject legitimate tables; independent semantic review remains necessary.

## Existing release/integration workflow

Create/review the new configuration before freezing a baseline. Both sides of a data-only Data CI comparison must use matching settings. Raw CSV provenance differs from the legacy normalized representation, so enabling this setting is an explicit configuration/source-version change. Source changes, evidence proposals, exact reference coverage, citation membership, numeric consistency, diagnosis and repair all reuse the existing index and assurance pipeline.

A correctly calculated value with matching cells passes deterministic numerical consistency; it does not establish independent claim support or authorize strict ACCEPT. Required independent review stays REVIEW/PENDING. Header/cell subject association resolves only necessary lexical subject checks; it does not create an alias or semantic judgment.

External apps must use the same actual table passages/IDs or a verified exact mapping. Keep original source/cell evidence in review packets and reject stale source versions. See [the external workflow](CONNECT_EXISTING_RAG.md). Existing exposed examples are development material; independent final labels and actual customer validation remain pending.

## Register original CSV/Markdown without changing internals

The source-owner text-bundle helper is limited to text basenames. For original
CSV/Markdown, use the existing generic importer instead of renaming/flattening
files. Put owner-supplied files under a `records/` subdirectory so that source
IDs are predictable, and provide a real owner-checked JSONL benchmark:

```bash
python -m sourceroi init --documents PATH_TO_BEFORE_DOCUMENTS \
  --benchmark PATH_TO_OWNER_CHECKED_BENCHMARK_JSONL \
  --output workspace/tabular-source
```

In the public `project.json`, explicitly set `table_evidence: true` and the desired
answering/indexing settings before freezing; add actual authority/scope/date
metadata. Configure calculation contracts and genuine operator authorization if
using source calculation. This is normal workspace configuration, not a change
to SourceROI internals. The importer's default model configuration must not be
used to infer approval for any paid call. No live-model execution is authorized
through the still-pending owned-native gate.

```bash
python -m sourceroi --project workspace/tabular-source freeze \
  --output workspace/tabular-accepted
```

Copy the configured source workspace into a new candidate directory (refuse an
existing destination), replace only the proposed source files there, and retain
the frozen benchmark. Follow the existing `change-plan`, explicit `change-review`
and strict release workflow in [CONNECT_EXISTING_RAG.md](CONNECT_EXISTING_RAG.md).
Replacement expected answers/evidence belong in reviewed decisions, not silent
benchmark edits. The external app must read the matching indexed snapshot. A
synthetic importer/freeze/calculation smoke verifies this path mechanically; it
is not a real source owner, customer application or independent label study.
