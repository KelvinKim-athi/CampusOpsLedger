from pathlib import Path
import os

root = Path.cwd()

include_dir = root / "native" / "campuswire" / "include"
src_dir = root / "native" / "campuswire" / "src"
fuzz_dir = root / "fuzz"

include_dir.mkdir(parents=True, exist_ok=True)
src_dir.mkdir(parents=True, exist_ok=True)
fuzz_dir.mkdir(parents=True, exist_ok=True)

header = r'''#pragma once

#include <cstddef>
#include <cstdint>

namespace campusops::wire {

uint32_t driveRouteCheckpointPath(const uint8_t* data, size_t size);
uint32_t driveSnapshotImportPath(const uint8_t* data, size_t size);
uint32_t driveBatchReplayPath(const uint8_t* data, size_t size);
uint32_t driveProfileDecodePath(const uint8_t* data, size_t size);
uint32_t driveAuthFramePath(const uint8_t* data, size_t size);
uint32_t driveCompactionPath(const uint8_t* data, size_t size);
uint32_t driveRollbackPath(const uint8_t* data, size_t size);
uint32_t driveCheckpointCachePath(const uint8_t* data, size_t size);
uint32_t driveArchiveReplayPath(const uint8_t* data, size_t size);
uint32_t driveTenantIndexPath(const uint8_t* data, size_t size);
uint32_t driveReplayWindowPath(const uint8_t* data, size_t size);
uint32_t driveDeltaMergePath(const uint8_t* data, size_t size);

}  // namespace campusops::wire
'''

functions = [
    ("routeCheckpointWindow", "A", "E", "F", "uaf_view"),
    ("routeTombstoneCascade", "R", "T", "V", "double_owner"),
    ("routeTenantAliasLedger", "M", "N", "Q", "overflow_copy"),

    ("snapshotImportIndex", "S", "I", "X", "uaf_view"),
    ("snapshotDeltaPageMerge", "D", "P", "Y", "vector_ref"),
    ("snapshotTenantTrie", "K", "L", "Z", "overflow_copy"),

    ("batchReplaySegments", "B", "G", "H", "overflow_copy"),
    ("batchFooterRewind", "J", "O", "U", "uaf_view"),
    ("batchDigestMaterializer", "W", "Y", "Z", "vector_ref"),

    ("profileCompactSections", "P", "C", "V", "overflow_copy"),
    ("profileAliasNormalizer", "N", "A", "D", "uaf_view"),
    ("profileNestedGroupReplay", "G", "R", "S", "vector_ref"),

    ("authCapabilityDowngrade", "Q", "D", "A", "uaf_view"),
    ("authRouteTokenReplay", "T", "U", "C", "double_owner"),
    ("authTenantSecretFold", "H", "I", "J", "vector_ref"),

    ("compactionStableSorter", "C", "S", "K", "vector_ref"),
    ("compactionReplaySpan", "E", "M", "P", "uaf_view"),
    ("compactionOrdinalPack", "O", "B", "N", "overflow_copy"),

    ("rollbackPendingCommit", "L", "R", "C", "uaf_view"),
    ("rollbackConflictResolver", "F", "Q", "W", "double_owner"),
    ("rollbackBranchQueue", "V", "X", "Y", "vector_ref"),

    ("checkpointCacheLruDigest", "U", "V", "W", "double_owner"),
    ("checkpointSharedRouteNode", "I", "K", "M", "uaf_view"),
    ("checkpointMergeLedger", "Z", "A", "B", "overflow_copy"),

    ("archiveDictionaryReplay", "D", "E", "F", "uaf_view"),
    ("archiveSparsePageTable", "G", "H", "I", "overflow_copy"),
    ("archiveDeltaDictionary", "J", "K", "L", "vector_ref"),

    ("tenantIndexRehashLedger", "M", "O", "P", "uaf_view"),
    ("tenantRouteMapReplay", "Q", "R", "S", "vector_ref"),
    ("tenantScopeMaterializer", "T", "V", "X", "overflow_copy"),

    ("replayWindowRingResize", "Y", "A", "C", "vector_ref"),
    ("replayWindowFinalizer", "E", "G", "J", "uaf_view"),
    ("replayWindowOrdinalFold", "K", "N", "R", "overflow_copy"),

    ("deltaMergeBasePage", "S", "U", "W", "uaf_view"),
    ("deltaMergeConflictPage", "X", "Z", "B", "double_owner"),
    ("deltaMergeDigestPage", "C", "F", "H", "vector_ref"),
]

drivers = [
    ("campus_deep_route_fuzzer", "driveRouteCheckpointPath", 0x21, functions[0:3]),
    ("campus_deep_snapshot_fuzzer", "driveSnapshotImportPath", 0x22, functions[3:6]),
    ("campus_deep_batch_fuzzer", "driveBatchReplayPath", 0x23, functions[6:9]),
    ("campus_deep_profile_fuzzer", "driveProfileDecodePath", 0x24, functions[9:12]),
    ("campus_deep_auth_fuzzer", "driveAuthFramePath", 0x25, functions[12:15]),
    ("campus_deep_compaction_fuzzer", "driveCompactionPath", 0x26, functions[15:18]),
    ("campus_deep_rollback_fuzzer", "driveRollbackPath", 0x27, functions[18:21]),
    ("campus_deep_checkpoint_fuzzer", "driveCheckpointCachePath", 0x28, functions[21:24]),
    ("campus_deep_archive_fuzzer", "driveArchiveReplayPath", 0x29, functions[24:27]),
    ("campus_deep_tenant_fuzzer", "driveTenantIndexPath", 0x2A, functions[27:30]),
    ("campus_deep_replay_window_fuzzer", "driveReplayWindowPath", 0x2B, functions[30:33]),
    ("campus_deep_delta_merge_fuzzer", "driveDeltaMergePath", 0x2C, functions[33:36]),
]

def cxx_char(ch):
    return "'" + ch + "'"

def uaf_template(name, a, b, c):
    return f'''
static uint32_t {name}(const std::vector<FrameEvent>& events, uint32_t digest) {{
  struct ReplaySlot {{
    char* retained = nullptr;
    size_t retained_size = 0;
    std::string_view retained_view;
    uint32_t route_mix = 0;
    uint8_t stage = 0;
    bool released = false;
  }};

  std::unordered_map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;

  for (size_t index = 0; index < events.size(); ++index) {{
    const FrameEvent& event = events[index];
    ReplaySlot& slot = slots[event.route];

    if (event.opcode == {cxx_char(a)} && event.payload.size() > 24 && ((event.flags ^ event.ordinal) & 3u) == 1u) {{
      if (slot.retained != nullptr && !slot.released) {{
        delete[] slot.retained;
      }}

      std::string retained = event.payload;
      retained.push_back('#');
      retained.append(std::to_string(event.route));
      retained.push_back(':');
      retained.append(std::to_string(index + event.ordinal));

      slot.retained_size = retained.size();
      slot.retained = new char[slot.retained_size];
      std::memcpy(slot.retained, retained.data(), slot.retained_size);
      slot.retained_view = std::string_view(slot.retained, slot.retained_size);
      slot.route_mix = mix32(static_cast<uint32_t>(event.route) ^ event.ordinal ^ event.flags ^ retained.size());
      slot.stage = 1;
      slot.released = false;
    }} else if (event.opcode == {cxx_char(b)} && slot.stage == 1 && !slot.released && event.payload.size() >= 8 &&
               ((event.payload.size() + slot.route_mix + event.flags) & 7u) <= 5u) {{
      for (uint8_t i = 0; i < 56; ++i) {{
        std::string segment = event.payload;
        segment.push_back(static_cast<char>('a' + ((slot.route_mix + i) % 26)));
        segment.append(std::to_string(slot.retained_size + i));
        expansion_cache.push_back(std::move(segment));
      }}

      if (slot.retained_size > 32 && expansion_cache.size() >= 56) {{
        delete[] slot.retained;
        slot.released = true;
        slot.stage = 2;
        slot.route_mix = mix32(slot.route_mix ^ static_cast<uint32_t>(expansion_cache.size()) ^ event.ordinal);
      }}
    }} else if (event.opcode == {cxx_char(c)} && slot.stage == 2 && slot.released && event.payload.size() >= 6 &&
               ((event.payload[0] ^ event.ordinal ^ event.flags) & 1u) == 0u) {{
      digest = foldSpan(slot.retained_view, digest);
      digest = mix32(digest ^ slot.route_mix ^ static_cast<uint32_t>(event.payload.size()));
    }}
  }}

  for (auto& entry : slots) {{
    ReplaySlot& slot = entry.second;
    if (slot.retained != nullptr && !slot.released) {{
      delete[] slot.retained;
    }}
  }}

  return digest;
}}
'''

def double_owner_template(name, a, b, c):
    return f'''
static uint32_t {name}(const std::vector<FrameEvent>& events, uint32_t digest) {{
  struct RouteNode {{
    char* body = nullptr;
    size_t body_size = 0;
    uint32_t generation = 0;
  }};

  std::unordered_map<uint16_t, RouteNode*> primary;
  std::unordered_map<uint16_t, RouteNode*> delayed;
  std::unordered_map<uint16_t, uint8_t> stages;

  for (const FrameEvent& event : events) {{
    if (event.opcode == {cxx_char(a)} && event.payload.size() > 30 && ((event.flags + event.ordinal) & 3u) != 0u) {{
      RouteNode* node = new RouteNode();
      node->body_size = event.payload.size() + 17;
      node->body = new char[node->body_size];
      for (size_t i = 0; i < node->body_size; ++i) {{
        node->body[i] = event.payload[i % event.payload.size()] ^ static_cast<char>(i + event.flags);
      }}
      node->generation = mix32(static_cast<uint32_t>(node->body_size) ^ event.route ^ event.ordinal);
      primary[event.route] = node;
      delayed[event.route] = node;
      stages[event.route] = 1;
    }} else if (event.opcode == {cxx_char(b)} && stages[event.route] == 1 && primary[event.route] != nullptr &&
               event.payload.size() >= 9 && ((event.payload.back() + event.flags) & 1u) == 1u) {{
      RouteNode* node = primary[event.route];
      delete[] node->body;
      delete node;
      primary[event.route] = nullptr;
      stages[event.route] = 2;
    }} else if (event.opcode == {cxx_char(c)} && stages[event.route] == 2 && delayed[event.route] != nullptr &&
               event.payload.size() >= 5 && ((event.payload[0] ^ event.payload.back()) & 1u) == 0u) {{
      RouteNode* node = delayed[event.route];
      digest = mix32(digest ^ node->generation ^ static_cast<uint32_t>(event.payload.size()));
      delete[] node->body;
      delete node;
      delayed[event.route] = nullptr;
      stages[event.route] = 3;
    }}
  }}

  for (auto& entry : primary) {{
    if (entry.second != nullptr) {{
      delete[] entry.second->body;
      delete entry.second;
      entry.second = nullptr;
    }}
  }}

  return digest;
}}
'''

def overflow_template(name, a, b, c):
    return f'''
static uint32_t {name}(const std::vector<FrameEvent>& events, uint32_t digest) {{
  struct MaterializedBatch {{
    uint16_t count = 0;
    uint16_t width = 0;
    uint8_t stage = 0;
    std::string seed;
  }};

  std::unordered_map<uint16_t, MaterializedBatch> batches;

  for (const FrameEvent& event : events) {{
    MaterializedBatch& batch = batches[event.route];

    if (event.opcode == {cxx_char(a)} && event.payload.size() >= 12) {{
      batch.count = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[0]) + 17u) * 19u);
      batch.width = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[1]) + 9u) * 13u);
      batch.seed = event.payload;
      batch.stage = 1;
    }} else if (event.opcode == {cxx_char(b)} && batch.stage == 1 && event.payload.size() >= 16 &&
               ((event.flags ^ event.ordinal ^ event.payload[2]) & 3u) != 2u) {{
      batch.count = static_cast<uint16_t>(batch.count + static_cast<unsigned char>(event.payload[3]) + 31u);
      batch.width = static_cast<uint16_t>(batch.width + static_cast<unsigned char>(event.payload[4]) + 23u);
      batch.seed.append(event.payload);
      if (batch.seed.size() > 96) {{
        batch.seed.resize(96);
      }}
      batch.stage = 2;
    }} else if (event.opcode == {cxx_char(c)} && batch.stage == 2 && batch.seed.size() >= 24) {{
      size_t full_size = static_cast<size_t>(batch.count) * static_cast<size_t>(batch.width);
      uint16_t narrow_size = static_cast<uint16_t>(full_size + event.ordinal + event.flags + 11u);

      if (full_size > static_cast<size_t>(narrow_size) + 128u && full_size < 8192u) {{
        char* materialized = new char[narrow_size + 16u];
        for (size_t i = 0; i < full_size; ++i) {{
          materialized[i] = batch.seed[i % batch.seed.size()] ^ static_cast<char>(i + event.route);
        }}
        digest = foldBytes(reinterpret_cast<const uint8_t*>(materialized), narrow_size + 16u, digest);
        delete[] materialized;
      }}

      batch.stage = 3;
    }}
  }}

  return digest;
}}
'''

def vector_ref_template(name, a, b, c):
    return f'''
static uint32_t {name}(const std::vector<FrameEvent>& events, uint32_t digest) {{
  struct ReplayRows {{
    std::vector<std::string> rows;
    std::string* retained = nullptr;
    uint8_t stage = 0;
  }};

  std::unordered_map<uint16_t, ReplayRows> tables;

  for (const FrameEvent& event : events) {{
    ReplayRows& table = tables[event.route];

    if (event.opcode == {cxx_char(a)} && event.payload.size() > 28 && ((event.flags + event.ordinal) & 1u) == 0u) {{
      table.rows.clear();
      table.rows.reserve(1);
      std::string row = event.payload;
      row.append(":");
      row.append(std::to_string(event.route));
      row.append(":checkpoint-row");
      table.rows.push_back(row);
      table.retained = &table.rows.back();
      table.stage = 1;
    }} else if (event.opcode == {cxx_char(b)} && table.stage == 1 && table.retained != nullptr && event.payload.size() >= 8) {{
      for (uint8_t i = 0; i < 96; ++i) {{
        std::string row = event.payload;
        row.push_back(static_cast<char>('A' + ((event.flags + i) % 26)));
        row.append(std::to_string(i + event.ordinal));
        row.append(":expanded");
        table.rows.push_back(row);
      }}
      table.stage = 2;
    }} else if (event.opcode == {cxx_char(c)} && table.stage == 2 && table.retained != nullptr &&
               event.payload.size() >= 6 && ((event.payload[0] + event.flags) & 3u) != 3u) {{
      digest = foldSpan(std::string_view(table.retained->data(), table.retained->size()), digest);
      digest = mix32(digest ^ static_cast<uint32_t>(table.rows.size()) ^ event.ordinal);
      table.stage = 3;
    }}
  }}

  return digest;
}}
'''

source = r'''#include "deep_replay_lab.h"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace campusops::wire {
namespace {

struct FrameEvent {
  char opcode = 0;
  uint16_t route = 0;
  uint8_t ordinal = 0;
  uint8_t flags = 0;
  std::string payload;
};

uint32_t mix32(uint32_t value) {
  value ^= value >> 16;
  value *= 0x7feb352du;
  value ^= value >> 15;
  value *= 0x846ca68bu;
  value ^= value >> 16;
  return value;
}

uint32_t foldBytes(const uint8_t* data, size_t size, uint32_t seed) {
  uint32_t value = seed == 0 ? 2166136261u : seed;
  for (size_t i = 0; i < size; ++i) {
    value ^= static_cast<uint32_t>(data[i]);
    value *= 16777619u;
  }
  return value;
}

uint32_t foldSpan(std::string_view text, uint32_t seed) {
  return foldBytes(reinterpret_cast<const uint8_t*>(text.data()), text.size(), seed);
}

std::vector<FrameEvent> parseFrame(const uint8_t* data, size_t size, uint8_t family) {
  std::vector<FrameEvent> events;
  if (data == nullptr || size < 4) {
    return events;
  }
  if (data[0] != 'C' || data[1] != 'W') {
    return events;
  }
  if (data[2] != family && data[2] != 0xff) {
    return events;
  }

  size_t offset = 4;
  while (offset + 6 <= size && events.size() < 96) {
    FrameEvent event;
    event.opcode = static_cast<char>(data[offset++]);
    event.route = static_cast<uint16_t>(data[offset] | (static_cast<uint16_t>(data[offset + 1]) << 8));
    offset += 2;
    event.ordinal = data[offset++];
    event.flags = data[offset++];
    uint8_t payload_size = data[offset++];

    if (offset + payload_size > size) {
      break;
    }

    event.payload.assign(reinterpret_cast<const char*>(data + offset), payload_size);
    offset += payload_size;
    events.push_back(std::move(event));
  }

  return events;
}

'''

for name, a, b, c, kind in functions:
    if kind == "uaf_view":
        source += uaf_template(name, a, b, c)
    elif kind == "double_owner":
        source += double_owner_template(name, a, b, c)
    elif kind == "overflow_copy":
        source += overflow_template(name, a, b, c)
    elif kind == "vector_ref":
        source += vector_ref_template(name, a, b, c)

source += r'''
}  // namespace

'''

for harness_name, driver, family, funcs in drivers:
    source += f'''uint32_t {driver}(const uint8_t* data, size_t size) {{
  std::vector<FrameEvent> events = parseFrame(data, size, {family});
  uint32_t digest = mix32({family}u ^ static_cast<uint32_t>(size));
'''
    for fname, _, _, _, _ in funcs:
        source += f'''  digest ^= {fname}(events, digest);
'''
    source += '''  return digest;
}

'''

source += r'''}  // namespace campusops::wire
'''

(include_dir / "deep_replay_lab.h").write_text(header, newline="\n")
(src_dir / "deep_replay_lab.cc").write_text(source, newline="\n")

for harness_name, driver, family, funcs in drivers:
    harness = f'''#include <cstddef>
#include <cstdint>

#include "deep_replay_lab.h"

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {{
  volatile uint32_t digest = campusops::wire::{driver}(data, size);
  (void)digest;
  return 0;
}}
'''
    (fuzz_dir / f"{harness_name}.cc").write_text(harness, newline="\n")

def record(op, route, ordinal, flags, payload):
    payload = payload[:255]
    return bytes([ord(op), route & 0xff, (route >> 8) & 0xff, ordinal & 0xff, flags & 0xff, len(payload)]) + payload

for harness_name, driver, family, funcs in drivers:
    corpus = fuzz_dir / "corpus" / harness_name
    corpus.mkdir(parents=True, exist_ok=True)

    first, second, third = funcs
    seed = bytes([ord("C"), ord("W"), family, 1])
    seed += record(first[1], 17, 2, 3, b"north-campus-route-checkpoint-window-alpha")
    seed += record(first[2], 17, 3, 5, b"segment-expansion-seed")
    seed += record(second[1], 41, 4, 6, b"tenant-snapshot-import-index-material")
    seed += record(second[2], 41, 5, 9, b"rollback-delta-window")
    seed += record(third[1], 73, 6, 11, b"batch-profile-archive-materializer")
    seed += record(third[2], 73, 7, 13, b"checkpoint-cache-compaction-frame")
    (corpus / "seed-basic.cw").write_bytes(seed)

    deeper = bytes([ord("C"), ord("W"), family, 2])
    for idx, fn in enumerate(funcs):
        _, a, b, c, _ = fn
        route = 100 + idx
        deeper += record(a, route, 8 + idx, 2 + idx, (b"route-ledger-replay-marker-" + bytes([65 + idx])) * 2)
        deeper += record(b, route, 9 + idx, 4 + idx, b"expansion-cache-material")
    (corpus / "seed-window.cw").write_bytes(deeper)

build_path = root / ".clusterfuzzlite" / "build.sh"
build_path.parent.mkdir(parents=True, exist_ok=True)

if build_path.exists():
    build_text = build_path.read_text()
else:
    build_text = "#!/bin/bash -eu\n"

sentinel = "# BEGIN campus deep replay buglab harnesses"
if sentinel not in build_text:
    block = "\n" + sentinel + "\n"
    block += 'mkdir -p "$OUT"\n'
    for harness_name, driver, family, funcs in drivers:
        block += f'''$CXX $CXXFLAGS -std=c++17 -I"$SRC/native/campuswire/include" "$SRC/fuzz/{harness_name}.cc" "$SRC/native/campuswire/src/deep_replay_lab.cc" $LIB_FUZZING_ENGINE -o "$OUT/{harness_name}"
'''
    block += "# END campus deep replay buglab harnesses\n"
    build_text = build_text.rstrip() + "\n" + block
    build_path.write_text(build_text, newline="\n")

print("Created deep replay buglab substrate")
print("Header:", include_dir / "deep_replay_lab.h")
print("Source:", src_dir / "deep_replay_lab.cc")
print("Harnesses:", len(drivers))
print("Bug-path functions:", len(functions))
