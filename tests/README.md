# Test ownership

Choose a directory by the behavior asserted. Real compilers may prepare query fixtures without making a test an integration test.

| Directory | Contract |
| --- | --- |
| `core` | Abstraction, container bindings, native mappings, ownership, reconstruction, metrics |
| `compilers` | Direct configuration, allocation, projection, reconstructed semantics, subprocess failures |
| `compilation` | Public normalization, lemmas, projection, registration/reuse, statistics, lifecycle |
| `queries` | Direct engine semantics/validation; session inputs, normalization/delegation, resource lifecycle |
| `persistence` | Serialization, metadata, environment restoration, native payloads, failures, write safety |
| `integration` | Regressions crossing compilation, target lifetime/reuse, persistence, and queries |

Keep backend pairings, strategies, formula cases, and equivalence helpers in existing shared support. Keep engine cleanup and artifact fixtures local to their directories. Formula-bank IDs include the generator, variable count, and projection strategy.

The complete bank runs independently for compiler reconstruction, native persistence, engine solver equivalence, and engine assumptions. Exact model-set equality establishes completeness; separate assertions check uniqueness, counts, satisfiability, implicants, and clauses. Dedicated constant-circuit tests assert ddnnife's unsupported cases explicitly; broad semantic matrices skip only those known circuits.
