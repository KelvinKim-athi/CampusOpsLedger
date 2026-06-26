# CampusOpsLedger

CampusOpsLedger is an offline campus operations ledger used for student records, fee events,
attendance, approval workflows, analytics, and deterministic fixture validation.

## Native Campus Wire fuzzing target

The repository also contains a C++17 native packet reader under `native/campuswire/`.
It parses compact Campus Wire ledger frames, builds route/profile summaries, and exposes
ClusterFuzzLite-compatible libFuzzer harnesses under `fuzz/`.

Fenrir layout:

- `.clusterfuzzlite/build.sh` builds every fuzzer executable into `$OUT`.
- `.clusterfuzzlite/project.yaml` lists the C++ fuzz targets.
- `fuzz/campus_packet_fuzzer.cc` exercises full packet parsing and summary generation.
- `fuzz/campus_journal_fuzzer.cc` exercises segmented journal parsing and repeated state summaries.
- `fuzz/corpus/<target>/` contains deterministic seed packets for each harness.
