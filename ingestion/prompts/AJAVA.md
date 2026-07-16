Subject: Advanced Programming in Java (AJAVA). Same two-tier rules as JAVA, advanced topics.

`answer` (full exam-scoring solution) by qtype:
- **`program`:** the COMPLETE compilable program is the exam answer (imports, class, methods)
  — shown on the watch as a scrollable code block, full on the phone. Cover the advanced
  mechanism correctly: collections, generics, threads/synchronization, JDBC, servlets/JSP,
  streams, lambdas.
- **`predict_output`:** exact output + the reason (thread interleaving, stream laziness,
  generic erasure, exception flow).
- **`concept`:** full examiner-ready explanation with a short illustrative example.

`summary` (glance line):
- `program` → the ONE key line/mechanism (e.g. "synchronized(this) on shared counter — else
  race"); never the whole program.
- `predict_output` → exact output, one line (" ⏎ " joins lines).
- `concept` → one-line definition/distinction naming the exact API/mechanism.

Code in `answer` must compile as-is.
