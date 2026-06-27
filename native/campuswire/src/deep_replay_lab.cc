#include "deep_replay_lab.h"

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


static uint32_t routeCheckpointWindow(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplaySlot {
    char* retained = nullptr;
    size_t retained_size = 0;
    std::string_view retained_view;
    uint32_t route_mix = 0;
    uint8_t stage = 0;
    bool released = false;
  };

  std::unordered_map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;

  for (size_t index = 0; index < events.size(); ++index) {
    const FrameEvent& event = events[index];
    ReplaySlot& slot = slots[event.route];

    if (event.opcode == 'A' && event.payload.size() > 24 && ((event.flags ^ event.ordinal) & 3u) == 1u) {
      if (slot.retained != nullptr && !slot.released) {
        delete[] slot.retained;
      }

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
    } else if (event.opcode == 'E' && slot.stage == 1 && !slot.released && event.payload.size() >= 8 &&
               ((event.payload.size() + slot.route_mix + event.flags) & 7u) <= 5u) {
      for (uint8_t i = 0; i < 56; ++i) {
        std::string segment = event.payload;
        segment.push_back(static_cast<char>('a' + ((slot.route_mix + i) % 26)));
        segment.append(std::to_string(slot.retained_size + i));
        expansion_cache.push_back(std::move(segment));
      }

      if (slot.retained_size > 32 && expansion_cache.size() >= 56) {
        delete[] slot.retained;
        slot.released = true;
        slot.stage = 2;
        slot.route_mix = mix32(slot.route_mix ^ static_cast<uint32_t>(expansion_cache.size()) ^ event.ordinal);
      }
    } else if (event.opcode == 'F' && slot.stage == 2 && slot.released && event.payload.size() >= 6 &&
               ((event.payload[0] ^ event.ordinal ^ event.flags) & 1u) == 0u) {
      digest = foldSpan(slot.retained_view, digest);
      digest = mix32(digest ^ slot.route_mix ^ static_cast<uint32_t>(event.payload.size()));
    }
  }

  for (auto& entry : slots) {
    ReplaySlot& slot = entry.second;
    if (slot.retained != nullptr && !slot.released) {
      delete[] slot.retained;
    }
  }

  return digest;
}

static uint32_t routeTombstoneCascade(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct RouteNode {
    char* body = nullptr;
    size_t body_size = 0;
    uint32_t generation = 0;
  };

  std::unordered_map<uint16_t, RouteNode*> primary;
  std::unordered_map<uint16_t, RouteNode*> delayed;
  std::unordered_map<uint16_t, uint8_t> stages;

  for (const FrameEvent& event : events) {
    if (event.opcode == 'R' && event.payload.size() > 30 && ((event.flags + event.ordinal) & 3u) != 0u) {
      RouteNode* node = new RouteNode();
      node->body_size = event.payload.size() + 17;
      node->body = new char[node->body_size];
      for (size_t i = 0; i < node->body_size; ++i) {
        node->body[i] = event.payload[i % event.payload.size()] ^ static_cast<char>(i + event.flags);
      }
      node->generation = mix32(static_cast<uint32_t>(node->body_size) ^ event.route ^ event.ordinal);
      primary[event.route] = node;
      delayed[event.route] = node;
      stages[event.route] = 1;
    } else if (event.opcode == 'T' && stages[event.route] == 1 && primary[event.route] != nullptr &&
               event.payload.size() >= 9 && ((event.payload.back() + event.flags) & 1u) == 1u) {
      RouteNode* node = primary[event.route];
      delete[] node->body;
      delete node;
      primary[event.route] = nullptr;
      stages[event.route] = 2;
    } else if (event.opcode == 'V' && stages[event.route] == 2 && delayed[event.route] != nullptr &&
               event.payload.size() >= 5 && ((event.payload[0] ^ event.payload.back()) & 1u) == 0u) {
      RouteNode* node = delayed[event.route];
      digest = mix32(digest ^ node->generation ^ static_cast<uint32_t>(event.payload.size()));
      delete[] node->body;
      delete node;
      delayed[event.route] = nullptr;
      stages[event.route] = 3;
    }
  }

  for (auto& entry : primary) {
    if (entry.second != nullptr) {
      delete[] entry.second->body;
      delete entry.second;
      entry.second = nullptr;
    }
  }

  return digest;
}

static uint32_t routeTenantAliasLedger(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct MaterializedBatch {
    uint16_t count = 0;
    uint16_t width = 0;
    uint8_t stage = 0;
    std::string seed;
  };

  std::unordered_map<uint16_t, MaterializedBatch> batches;

  for (const FrameEvent& event : events) {
    MaterializedBatch& batch = batches[event.route];

    if (event.opcode == 'M' && event.payload.size() >= 12) {
      batch.count = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[0]) + 17u) * 19u);
      batch.width = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[1]) + 9u) * 13u);
      batch.seed = event.payload;
      batch.stage = 1;
    } else if (event.opcode == 'N' && batch.stage == 1 && event.payload.size() >= 16 &&
               ((event.flags ^ event.ordinal ^ event.payload[2]) & 3u) != 2u) {
      batch.count = static_cast<uint16_t>(batch.count + static_cast<unsigned char>(event.payload[3]) + 31u);
      batch.width = static_cast<uint16_t>(batch.width + static_cast<unsigned char>(event.payload[4]) + 23u);
      batch.seed.append(event.payload);
      if (batch.seed.size() > 96) {
        batch.seed.resize(96);
      }
      batch.stage = 2;
    } else if (event.opcode == 'Q' && batch.stage == 2 && batch.seed.size() >= 24) {
      size_t full_size = static_cast<size_t>(batch.count) * static_cast<size_t>(batch.width);
      uint16_t narrow_size = static_cast<uint16_t>(full_size + event.ordinal + event.flags + 11u);

      if (full_size > static_cast<size_t>(narrow_size) + 128u && full_size < 8192u) {
        char* materialized = new char[narrow_size + 16u];
        for (size_t i = 0; i < full_size; ++i) {
          materialized[i] = batch.seed[i % batch.seed.size()] ^ static_cast<char>(i + event.route);
        }
        digest = foldBytes(reinterpret_cast<const uint8_t*>(materialized), narrow_size + 16u, digest);
        delete[] materialized;
      }

      batch.stage = 3;
    }
  }

  return digest;
}

static uint32_t snapshotImportIndex(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplaySlot {
    char* retained = nullptr;
    size_t retained_size = 0;
    std::string_view retained_view;
    uint32_t route_mix = 0;
    uint8_t stage = 0;
    bool released = false;
  };

  std::unordered_map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;

  for (size_t index = 0; index < events.size(); ++index) {
    const FrameEvent& event = events[index];
    ReplaySlot& slot = slots[event.route];

    if (event.opcode == 'S' && event.payload.size() > 24 && ((event.flags ^ event.ordinal) & 3u) == 1u) {
      if (slot.retained != nullptr && !slot.released) {
        delete[] slot.retained;
      }

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
    } else if (event.opcode == 'I' && slot.stage == 1 && !slot.released && event.payload.size() >= 8 &&
               ((event.payload.size() + slot.route_mix + event.flags) & 7u) <= 5u) {
      for (uint8_t i = 0; i < 56; ++i) {
        std::string segment = event.payload;
        segment.push_back(static_cast<char>('a' + ((slot.route_mix + i) % 26)));
        segment.append(std::to_string(slot.retained_size + i));
        expansion_cache.push_back(std::move(segment));
      }

      if (slot.retained_size > 32 && expansion_cache.size() >= 56) {
        delete[] slot.retained;
        slot.released = true;
        slot.stage = 2;
        slot.route_mix = mix32(slot.route_mix ^ static_cast<uint32_t>(expansion_cache.size()) ^ event.ordinal);
      }
    } else if (event.opcode == 'X' && slot.stage == 2 && slot.released && event.payload.size() >= 6 &&
               ((event.payload[0] ^ event.ordinal ^ event.flags) & 1u) == 0u) {
      digest = foldSpan(slot.retained_view, digest);
      digest = mix32(digest ^ slot.route_mix ^ static_cast<uint32_t>(event.payload.size()));
    }
  }

  for (auto& entry : slots) {
    ReplaySlot& slot = entry.second;
    if (slot.retained != nullptr && !slot.released) {
      delete[] slot.retained;
    }
  }

  return digest;
}

static uint32_t snapshotDeltaPageMerge(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplayRows {
    std::vector<std::string> rows;
    std::string* retained = nullptr;
    uint8_t stage = 0;
  };

  std::unordered_map<uint16_t, ReplayRows> tables;

  for (const FrameEvent& event : events) {
    ReplayRows& table = tables[event.route];

    if (event.opcode == 'D' && event.payload.size() > 28 && ((event.flags + event.ordinal) & 1u) == 0u) {
      table.rows.clear();
      table.rows.reserve(1);
      std::string row = event.payload;
      row.append(":");
      row.append(std::to_string(event.route));
      row.append(":checkpoint-row");
      table.rows.push_back(row);
      table.retained = &table.rows.back();
      table.stage = 1;
    } else if (event.opcode == 'P' && table.stage == 1 && table.retained != nullptr && event.payload.size() >= 8) {
      for (uint8_t i = 0; i < 96; ++i) {
        std::string row = event.payload;
        row.push_back(static_cast<char>('A' + ((event.flags + i) % 26)));
        row.append(std::to_string(i + event.ordinal));
        row.append(":expanded");
        table.rows.push_back(row);
      }
      table.stage = 2;
    } else if (event.opcode == 'Y' && table.stage == 2 && table.retained != nullptr &&
               event.payload.size() >= 6 && ((event.payload[0] + event.flags) & 3u) != 3u) {
      digest = foldSpan(std::string_view(table.retained->data(), table.retained->size()), digest);
      digest = mix32(digest ^ static_cast<uint32_t>(table.rows.size()) ^ event.ordinal);
      table.stage = 3;
    }
  }

  return digest;
}

static uint32_t snapshotTenantTrie(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct MaterializedBatch {
    uint16_t count = 0;
    uint16_t width = 0;
    uint8_t stage = 0;
    std::string seed;
  };

  std::unordered_map<uint16_t, MaterializedBatch> batches;

  for (const FrameEvent& event : events) {
    MaterializedBatch& batch = batches[event.route];

    if (event.opcode == 'K' && event.payload.size() >= 12) {
      batch.count = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[0]) + 17u) * 19u);
      batch.width = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[1]) + 9u) * 13u);
      batch.seed = event.payload;
      batch.stage = 1;
    } else if (event.opcode == 'L' && batch.stage == 1 && event.payload.size() >= 16 &&
               ((event.flags ^ event.ordinal ^ event.payload[2]) & 3u) != 2u) {
      batch.count = static_cast<uint16_t>(batch.count + static_cast<unsigned char>(event.payload[3]) + 31u);
      batch.width = static_cast<uint16_t>(batch.width + static_cast<unsigned char>(event.payload[4]) + 23u);
      batch.seed.append(event.payload);
      if (batch.seed.size() > 96) {
        batch.seed.resize(96);
      }
      batch.stage = 2;
    } else if (event.opcode == 'Z' && batch.stage == 2 && batch.seed.size() >= 24) {
      size_t full_size = static_cast<size_t>(batch.count) * static_cast<size_t>(batch.width);
      uint16_t narrow_size = static_cast<uint16_t>(full_size + event.ordinal + event.flags + 11u);

      if (full_size > static_cast<size_t>(narrow_size) + 128u && full_size < 8192u) {
        char* materialized = new char[narrow_size + 16u];
        for (size_t i = 0; i < full_size; ++i) {
          materialized[i] = batch.seed[i % batch.seed.size()] ^ static_cast<char>(i + event.route);
        }
        digest = foldBytes(reinterpret_cast<const uint8_t*>(materialized), narrow_size + 16u, digest);
        delete[] materialized;
      }

      batch.stage = 3;
    }
  }

  return digest;
}

static uint32_t batchReplaySegments(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct MaterializedBatch {
    uint16_t count = 0;
    uint16_t width = 0;
    uint8_t stage = 0;
    std::string seed;
  };

  std::unordered_map<uint16_t, MaterializedBatch> batches;

  for (const FrameEvent& event : events) {
    MaterializedBatch& batch = batches[event.route];

    if (event.opcode == 'B' && event.payload.size() >= 12) {
      batch.count = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[0]) + 17u) * 19u);
      batch.width = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[1]) + 9u) * 13u);
      batch.seed = event.payload;
      batch.stage = 1;
    } else if (event.opcode == 'G' && batch.stage == 1 && event.payload.size() >= 16 &&
               ((event.flags ^ event.ordinal ^ event.payload[2]) & 3u) != 2u) {
      batch.count = static_cast<uint16_t>(batch.count + static_cast<unsigned char>(event.payload[3]) + 31u);
      batch.width = static_cast<uint16_t>(batch.width + static_cast<unsigned char>(event.payload[4]) + 23u);
      batch.seed.append(event.payload);
      if (batch.seed.size() > 96) {
        batch.seed.resize(96);
      }
      batch.stage = 2;
    } else if (event.opcode == 'H' && batch.stage == 2 && batch.seed.size() >= 24) {
      size_t full_size = static_cast<size_t>(batch.count) * static_cast<size_t>(batch.width);
      uint16_t narrow_size = static_cast<uint16_t>(full_size + event.ordinal + event.flags + 11u);

      if (full_size > static_cast<size_t>(narrow_size) + 128u && full_size < 8192u) {
        char* materialized = new char[narrow_size + 16u];
        for (size_t i = 0; i < full_size; ++i) {
          materialized[i] = batch.seed[i % batch.seed.size()] ^ static_cast<char>(i + event.route);
        }
        digest = foldBytes(reinterpret_cast<const uint8_t*>(materialized), narrow_size + 16u, digest);
        delete[] materialized;
      }

      batch.stage = 3;
    }
  }

  return digest;
}

static uint32_t batchFooterRewind(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplaySlot {
    char* retained = nullptr;
    size_t retained_size = 0;
    std::string_view retained_view;
    uint32_t route_mix = 0;
    uint8_t stage = 0;
    bool released = false;
  };

  std::unordered_map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;

  for (size_t index = 0; index < events.size(); ++index) {
    const FrameEvent& event = events[index];
    ReplaySlot& slot = slots[event.route];

    if (event.opcode == 'J' && event.payload.size() > 24 && ((event.flags ^ event.ordinal) & 3u) == 1u) {
      if (slot.retained != nullptr && !slot.released) {
        delete[] slot.retained;
      }

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
    } else if (event.opcode == 'O' && slot.stage == 1 && !slot.released && event.payload.size() >= 8 &&
               ((event.payload.size() + slot.route_mix + event.flags) & 7u) <= 5u) {
      for (uint8_t i = 0; i < 56; ++i) {
        std::string segment = event.payload;
        segment.push_back(static_cast<char>('a' + ((slot.route_mix + i) % 26)));
        segment.append(std::to_string(slot.retained_size + i));
        expansion_cache.push_back(std::move(segment));
      }

      if (slot.retained_size > 32 && expansion_cache.size() >= 56) {
        delete[] slot.retained;
        slot.released = true;
        slot.stage = 2;
        slot.route_mix = mix32(slot.route_mix ^ static_cast<uint32_t>(expansion_cache.size()) ^ event.ordinal);
      }
    } else if (event.opcode == 'U' && slot.stage == 2 && slot.released && event.payload.size() >= 6 &&
               ((event.payload[0] ^ event.ordinal ^ event.flags) & 1u) == 0u) {
      digest = foldSpan(slot.retained_view, digest);
      digest = mix32(digest ^ slot.route_mix ^ static_cast<uint32_t>(event.payload.size()));
    }
  }

  for (auto& entry : slots) {
    ReplaySlot& slot = entry.second;
    if (slot.retained != nullptr && !slot.released) {
      delete[] slot.retained;
    }
  }

  return digest;
}

static uint32_t batchDigestMaterializer(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplayRows {
    std::vector<std::string> rows;
    std::string* retained = nullptr;
    uint8_t stage = 0;
  };

  std::unordered_map<uint16_t, ReplayRows> tables;

  for (const FrameEvent& event : events) {
    ReplayRows& table = tables[event.route];

    if (event.opcode == 'W' && event.payload.size() > 28 && ((event.flags + event.ordinal) & 1u) == 0u) {
      table.rows.clear();
      table.rows.reserve(1);
      std::string row = event.payload;
      row.append(":");
      row.append(std::to_string(event.route));
      row.append(":checkpoint-row");
      table.rows.push_back(row);
      table.retained = &table.rows.back();
      table.stage = 1;
    } else if (event.opcode == 'Y' && table.stage == 1 && table.retained != nullptr && event.payload.size() >= 8) {
      for (uint8_t i = 0; i < 96; ++i) {
        std::string row = event.payload;
        row.push_back(static_cast<char>('A' + ((event.flags + i) % 26)));
        row.append(std::to_string(i + event.ordinal));
        row.append(":expanded");
        table.rows.push_back(row);
      }
      table.stage = 2;
    } else if (event.opcode == 'Z' && table.stage == 2 && table.retained != nullptr &&
               event.payload.size() >= 6 && ((event.payload[0] + event.flags) & 3u) != 3u) {
      digest = foldSpan(std::string_view(table.retained->data(), table.retained->size()), digest);
      digest = mix32(digest ^ static_cast<uint32_t>(table.rows.size()) ^ event.ordinal);
      table.stage = 3;
    }
  }

  return digest;
}

static uint32_t profileCompactSections(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct MaterializedBatch {
    uint16_t count = 0;
    uint16_t width = 0;
    uint8_t stage = 0;
    std::string seed;
  };

  std::unordered_map<uint16_t, MaterializedBatch> batches;

  for (const FrameEvent& event : events) {
    MaterializedBatch& batch = batches[event.route];

    if (event.opcode == 'P' && event.payload.size() >= 12) {
      batch.count = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[0]) + 17u) * 19u);
      batch.width = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[1]) + 9u) * 13u);
      batch.seed = event.payload;
      batch.stage = 1;
    } else if (event.opcode == 'C' && batch.stage == 1 && event.payload.size() >= 16 &&
               ((event.flags ^ event.ordinal ^ event.payload[2]) & 3u) != 2u) {
      batch.count = static_cast<uint16_t>(batch.count + static_cast<unsigned char>(event.payload[3]) + 31u);
      batch.width = static_cast<uint16_t>(batch.width + static_cast<unsigned char>(event.payload[4]) + 23u);
      batch.seed.append(event.payload);
      if (batch.seed.size() > 96) {
        batch.seed.resize(96);
      }
      batch.stage = 2;
    } else if (event.opcode == 'V' && batch.stage == 2 && batch.seed.size() >= 24) {
      size_t full_size = static_cast<size_t>(batch.count) * static_cast<size_t>(batch.width);
      uint16_t narrow_size = static_cast<uint16_t>(full_size + event.ordinal + event.flags + 11u);

      if (full_size > static_cast<size_t>(narrow_size) + 128u && full_size < 8192u) {
        char* materialized = new char[narrow_size + 16u];
        for (size_t i = 0; i < full_size; ++i) {
          materialized[i] = batch.seed[i % batch.seed.size()] ^ static_cast<char>(i + event.route);
        }
        digest = foldBytes(reinterpret_cast<const uint8_t*>(materialized), narrow_size + 16u, digest);
        delete[] materialized;
      }

      batch.stage = 3;
    }
  }

  return digest;
}

static uint32_t profileAliasNormalizer(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplaySlot {
    char* retained = nullptr;
    size_t retained_size = 0;
    std::string_view retained_view;
    uint32_t route_mix = 0;
    uint8_t stage = 0;
    bool released = false;
  };

  std::unordered_map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;

  for (size_t index = 0; index < events.size(); ++index) {
    const FrameEvent& event = events[index];
    ReplaySlot& slot = slots[event.route];

    if (event.opcode == 'N' && event.payload.size() > 24 && ((event.flags ^ event.ordinal) & 3u) == 1u) {
      if (slot.retained != nullptr && !slot.released) {
        delete[] slot.retained;
      }

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
    } else if (event.opcode == 'A' && slot.stage == 1 && !slot.released && event.payload.size() >= 8 &&
               ((event.payload.size() + slot.route_mix + event.flags) & 7u) <= 5u) {
      for (uint8_t i = 0; i < 56; ++i) {
        std::string segment = event.payload;
        segment.push_back(static_cast<char>('a' + ((slot.route_mix + i) % 26)));
        segment.append(std::to_string(slot.retained_size + i));
        expansion_cache.push_back(std::move(segment));
      }

      if (slot.retained_size > 32 && expansion_cache.size() >= 56) {
        delete[] slot.retained;
        slot.released = true;
        slot.stage = 2;
        slot.route_mix = mix32(slot.route_mix ^ static_cast<uint32_t>(expansion_cache.size()) ^ event.ordinal);
      }
    } else if (event.opcode == 'D' && slot.stage == 2 && slot.released && event.payload.size() >= 6 &&
               ((event.payload[0] ^ event.ordinal ^ event.flags) & 1u) == 0u) {
      digest = foldSpan(slot.retained_view, digest);
      digest = mix32(digest ^ slot.route_mix ^ static_cast<uint32_t>(event.payload.size()));
    }
  }

  for (auto& entry : slots) {
    ReplaySlot& slot = entry.second;
    if (slot.retained != nullptr && !slot.released) {
      delete[] slot.retained;
    }
  }

  return digest;
}

static uint32_t profileNestedGroupReplay(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplayRows {
    std::vector<std::string> rows;
    std::string* retained = nullptr;
    uint8_t stage = 0;
  };

  std::unordered_map<uint16_t, ReplayRows> tables;

  for (const FrameEvent& event : events) {
    ReplayRows& table = tables[event.route];

    if (event.opcode == 'G' && event.payload.size() > 28 && ((event.flags + event.ordinal) & 1u) == 0u) {
      table.rows.clear();
      table.rows.reserve(1);
      std::string row = event.payload;
      row.append(":");
      row.append(std::to_string(event.route));
      row.append(":checkpoint-row");
      table.rows.push_back(row);
      table.retained = &table.rows.back();
      table.stage = 1;
    } else if (event.opcode == 'R' && table.stage == 1 && table.retained != nullptr && event.payload.size() >= 8) {
      for (uint8_t i = 0; i < 96; ++i) {
        std::string row = event.payload;
        row.push_back(static_cast<char>('A' + ((event.flags + i) % 26)));
        row.append(std::to_string(i + event.ordinal));
        row.append(":expanded");
        table.rows.push_back(row);
      }
      table.stage = 2;
    } else if (event.opcode == 'S' && table.stage == 2 && table.retained != nullptr &&
               event.payload.size() >= 6 && ((event.payload[0] + event.flags) & 3u) != 3u) {
      digest = foldSpan(std::string_view(table.retained->data(), table.retained->size()), digest);
      digest = mix32(digest ^ static_cast<uint32_t>(table.rows.size()) ^ event.ordinal);
      table.stage = 3;
    }
  }

  return digest;
}

static uint32_t authCapabilityDowngrade(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplaySlot {
    char* retained = nullptr;
    size_t retained_size = 0;
    std::string_view retained_view;
    uint32_t route_mix = 0;
    uint8_t stage = 0;
    bool released = false;
  };

  std::unordered_map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;

  for (size_t index = 0; index < events.size(); ++index) {
    const FrameEvent& event = events[index];
    ReplaySlot& slot = slots[event.route];

    if (event.opcode == 'Q' && event.payload.size() > 24 && ((event.flags ^ event.ordinal) & 3u) == 1u) {
      if (slot.retained != nullptr && !slot.released) {
        delete[] slot.retained;
      }

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
    } else if (event.opcode == 'D' && slot.stage == 1 && !slot.released && event.payload.size() >= 8 &&
               ((event.payload.size() + slot.route_mix + event.flags) & 7u) <= 5u) {
      for (uint8_t i = 0; i < 56; ++i) {
        std::string segment = event.payload;
        segment.push_back(static_cast<char>('a' + ((slot.route_mix + i) % 26)));
        segment.append(std::to_string(slot.retained_size + i));
        expansion_cache.push_back(std::move(segment));
      }

      if (slot.retained_size > 32 && expansion_cache.size() >= 56) {
        delete[] slot.retained;
        slot.released = true;
        slot.stage = 2;
        slot.route_mix = mix32(slot.route_mix ^ static_cast<uint32_t>(expansion_cache.size()) ^ event.ordinal);
      }
    } else if (event.opcode == 'A' && slot.stage == 2 && slot.released && event.payload.size() >= 6 &&
               ((event.payload[0] ^ event.ordinal ^ event.flags) & 1u) == 0u) {
      digest = foldSpan(slot.retained_view, digest);
      digest = mix32(digest ^ slot.route_mix ^ static_cast<uint32_t>(event.payload.size()));
    }
  }

  for (auto& entry : slots) {
    ReplaySlot& slot = entry.second;
    if (slot.retained != nullptr && !slot.released) {
      delete[] slot.retained;
    }
  }

  return digest;
}

static uint32_t authRouteTokenReplay(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct RouteNode {
    char* body = nullptr;
    size_t body_size = 0;
    uint32_t generation = 0;
  };

  std::unordered_map<uint16_t, RouteNode*> primary;
  std::unordered_map<uint16_t, RouteNode*> delayed;
  std::unordered_map<uint16_t, uint8_t> stages;

  for (const FrameEvent& event : events) {
    if (event.opcode == 'T' && event.payload.size() > 30 && ((event.flags + event.ordinal) & 3u) != 0u) {
      RouteNode* node = new RouteNode();
      node->body_size = event.payload.size() + 17;
      node->body = new char[node->body_size];
      for (size_t i = 0; i < node->body_size; ++i) {
        node->body[i] = event.payload[i % event.payload.size()] ^ static_cast<char>(i + event.flags);
      }
      node->generation = mix32(static_cast<uint32_t>(node->body_size) ^ event.route ^ event.ordinal);
      primary[event.route] = node;
      delayed[event.route] = node;
      stages[event.route] = 1;
    } else if (event.opcode == 'U' && stages[event.route] == 1 && primary[event.route] != nullptr &&
               event.payload.size() >= 9 && ((event.payload.back() + event.flags) & 1u) == 1u) {
      RouteNode* node = primary[event.route];
      delete[] node->body;
      delete node;
      primary[event.route] = nullptr;
      stages[event.route] = 2;
    } else if (event.opcode == 'C' && stages[event.route] == 2 && delayed[event.route] != nullptr &&
               event.payload.size() >= 5 && ((event.payload[0] ^ event.payload.back()) & 1u) == 0u) {
      RouteNode* node = delayed[event.route];
      digest = mix32(digest ^ node->generation ^ static_cast<uint32_t>(event.payload.size()));
      delete[] node->body;
      delete node;
      delayed[event.route] = nullptr;
      stages[event.route] = 3;
    }
  }

  for (auto& entry : primary) {
    if (entry.second != nullptr) {
      delete[] entry.second->body;
      delete entry.second;
      entry.second = nullptr;
    }
  }

  return digest;
}

static uint32_t authTenantSecretFold(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplayRows {
    std::vector<std::string> rows;
    std::string* retained = nullptr;
    uint8_t stage = 0;
  };

  std::unordered_map<uint16_t, ReplayRows> tables;

  for (const FrameEvent& event : events) {
    ReplayRows& table = tables[event.route];

    if (event.opcode == 'H' && event.payload.size() > 28 && ((event.flags + event.ordinal) & 1u) == 0u) {
      table.rows.clear();
      table.rows.reserve(1);
      std::string row = event.payload;
      row.append(":");
      row.append(std::to_string(event.route));
      row.append(":checkpoint-row");
      table.rows.push_back(row);
      table.retained = &table.rows.back();
      table.stage = 1;
    } else if (event.opcode == 'I' && table.stage == 1 && table.retained != nullptr && event.payload.size() >= 8) {
      for (uint8_t i = 0; i < 96; ++i) {
        std::string row = event.payload;
        row.push_back(static_cast<char>('A' + ((event.flags + i) % 26)));
        row.append(std::to_string(i + event.ordinal));
        row.append(":expanded");
        table.rows.push_back(row);
      }
      table.stage = 2;
    } else if (event.opcode == 'J' && table.stage == 2 && table.retained != nullptr &&
               event.payload.size() >= 6 && ((event.payload[0] + event.flags) & 3u) != 3u) {
      digest = foldSpan(std::string_view(table.retained->data(), table.retained->size()), digest);
      digest = mix32(digest ^ static_cast<uint32_t>(table.rows.size()) ^ event.ordinal);
      table.stage = 3;
    }
  }

  return digest;
}

static uint32_t compactionStableSorter(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplayRows {
    std::vector<std::string> rows;
    std::string* retained = nullptr;
    uint8_t stage = 0;
  };

  std::unordered_map<uint16_t, ReplayRows> tables;

  for (const FrameEvent& event : events) {
    ReplayRows& table = tables[event.route];

    if (event.opcode == 'C' && event.payload.size() > 28 && ((event.flags + event.ordinal) & 1u) == 0u) {
      table.rows.clear();
      table.rows.reserve(1);
      std::string row = event.payload;
      row.append(":");
      row.append(std::to_string(event.route));
      row.append(":checkpoint-row");
      table.rows.push_back(row);
      table.retained = &table.rows.back();
      table.stage = 1;
    } else if (event.opcode == 'S' && table.stage == 1 && table.retained != nullptr && event.payload.size() >= 8) {
      for (uint8_t i = 0; i < 96; ++i) {
        std::string row = event.payload;
        row.push_back(static_cast<char>('A' + ((event.flags + i) % 26)));
        row.append(std::to_string(i + event.ordinal));
        row.append(":expanded");
        table.rows.push_back(row);
      }
      table.stage = 2;
    } else if (event.opcode == 'K' && table.stage == 2 && table.retained != nullptr &&
               event.payload.size() >= 6 && ((event.payload[0] + event.flags) & 3u) != 3u) {
      digest = foldSpan(std::string_view(table.retained->data(), table.retained->size()), digest);
      digest = mix32(digest ^ static_cast<uint32_t>(table.rows.size()) ^ event.ordinal);
      table.stage = 3;
    }
  }

  return digest;
}

static uint32_t compactionReplaySpan(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplaySlot {
    char* retained = nullptr;
    size_t retained_size = 0;
    std::string_view retained_view;
    uint32_t route_mix = 0;
    uint8_t stage = 0;
    bool released = false;
  };

  std::unordered_map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;

  for (size_t index = 0; index < events.size(); ++index) {
    const FrameEvent& event = events[index];
    ReplaySlot& slot = slots[event.route];

    if (event.opcode == 'E' && event.payload.size() > 24 && ((event.flags ^ event.ordinal) & 3u) == 1u) {
      if (slot.retained != nullptr && !slot.released) {
        delete[] slot.retained;
      }

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
    } else if (event.opcode == 'M' && slot.stage == 1 && !slot.released && event.payload.size() >= 8 &&
               ((event.payload.size() + slot.route_mix + event.flags) & 7u) <= 5u) {
      for (uint8_t i = 0; i < 56; ++i) {
        std::string segment = event.payload;
        segment.push_back(static_cast<char>('a' + ((slot.route_mix + i) % 26)));
        segment.append(std::to_string(slot.retained_size + i));
        expansion_cache.push_back(std::move(segment));
      }

      if (slot.retained_size > 32 && expansion_cache.size() >= 56) {
        delete[] slot.retained;
        slot.released = true;
        slot.stage = 2;
        slot.route_mix = mix32(slot.route_mix ^ static_cast<uint32_t>(expansion_cache.size()) ^ event.ordinal);
      }
    } else if (event.opcode == 'P' && slot.stage == 2 && slot.released && event.payload.size() >= 6 &&
               ((event.payload[0] ^ event.ordinal ^ event.flags) & 1u) == 0u) {
      digest = foldSpan(slot.retained_view, digest);
      digest = mix32(digest ^ slot.route_mix ^ static_cast<uint32_t>(event.payload.size()));
    }
  }

  for (auto& entry : slots) {
    ReplaySlot& slot = entry.second;
    if (slot.retained != nullptr && !slot.released) {
      delete[] slot.retained;
    }
  }

  return digest;
}

static uint32_t compactionOrdinalPack(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct MaterializedBatch {
    uint16_t count = 0;
    uint16_t width = 0;
    uint8_t stage = 0;
    std::string seed;
  };

  std::unordered_map<uint16_t, MaterializedBatch> batches;

  for (const FrameEvent& event : events) {
    MaterializedBatch& batch = batches[event.route];

    if (event.opcode == 'O' && event.payload.size() >= 12) {
      batch.count = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[0]) + 17u) * 19u);
      batch.width = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[1]) + 9u) * 13u);
      batch.seed = event.payload;
      batch.stage = 1;
    } else if (event.opcode == 'B' && batch.stage == 1 && event.payload.size() >= 16 &&
               ((event.flags ^ event.ordinal ^ event.payload[2]) & 3u) != 2u) {
      batch.count = static_cast<uint16_t>(batch.count + static_cast<unsigned char>(event.payload[3]) + 31u);
      batch.width = static_cast<uint16_t>(batch.width + static_cast<unsigned char>(event.payload[4]) + 23u);
      batch.seed.append(event.payload);
      if (batch.seed.size() > 96) {
        batch.seed.resize(96);
      }
      batch.stage = 2;
    } else if (event.opcode == 'N' && batch.stage == 2 && batch.seed.size() >= 24) {
      size_t full_size = static_cast<size_t>(batch.count) * static_cast<size_t>(batch.width);
      uint16_t narrow_size = static_cast<uint16_t>(full_size + event.ordinal + event.flags + 11u);

      if (full_size > static_cast<size_t>(narrow_size) + 128u && full_size < 8192u) {
        char* materialized = new char[narrow_size + 16u];
        for (size_t i = 0; i < full_size; ++i) {
          materialized[i] = batch.seed[i % batch.seed.size()] ^ static_cast<char>(i + event.route);
        }
        digest = foldBytes(reinterpret_cast<const uint8_t*>(materialized), narrow_size + 16u, digest);
        delete[] materialized;
      }

      batch.stage = 3;
    }
  }

  return digest;
}

static uint32_t rollbackPendingCommit(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplaySlot {
    char* retained = nullptr;
    size_t retained_size = 0;
    std::string_view retained_view;
    uint32_t route_mix = 0;
    uint8_t stage = 0;
    bool released = false;
  };

  std::unordered_map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;

  for (size_t index = 0; index < events.size(); ++index) {
    const FrameEvent& event = events[index];
    ReplaySlot& slot = slots[event.route];

    if (event.opcode == 'L' && event.payload.size() > 24 && ((event.flags ^ event.ordinal) & 3u) == 1u) {
      if (slot.retained != nullptr && !slot.released) {
        delete[] slot.retained;
      }

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
    } else if (event.opcode == 'R' && slot.stage == 1 && !slot.released && event.payload.size() >= 8 &&
               ((event.payload.size() + slot.route_mix + event.flags) & 7u) <= 5u) {
      for (uint8_t i = 0; i < 56; ++i) {
        std::string segment = event.payload;
        segment.push_back(static_cast<char>('a' + ((slot.route_mix + i) % 26)));
        segment.append(std::to_string(slot.retained_size + i));
        expansion_cache.push_back(std::move(segment));
      }

      if (slot.retained_size > 32 && expansion_cache.size() >= 56) {
        delete[] slot.retained;
        slot.released = true;
        slot.stage = 2;
        slot.route_mix = mix32(slot.route_mix ^ static_cast<uint32_t>(expansion_cache.size()) ^ event.ordinal);
      }
    } else if (event.opcode == 'C' && slot.stage == 2 && slot.released && event.payload.size() >= 6 &&
               ((event.payload[0] ^ event.ordinal ^ event.flags) & 1u) == 0u) {
      digest = foldSpan(slot.retained_view, digest);
      digest = mix32(digest ^ slot.route_mix ^ static_cast<uint32_t>(event.payload.size()));
    }
  }

  for (auto& entry : slots) {
    ReplaySlot& slot = entry.second;
    if (slot.retained != nullptr && !slot.released) {
      delete[] slot.retained;
    }
  }

  return digest;
}

static uint32_t rollbackConflictResolver(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct RouteNode {
    char* body = nullptr;
    size_t body_size = 0;
    uint32_t generation = 0;
  };

  std::unordered_map<uint16_t, RouteNode*> primary;
  std::unordered_map<uint16_t, RouteNode*> delayed;
  std::unordered_map<uint16_t, uint8_t> stages;

  for (const FrameEvent& event : events) {
    if (event.opcode == 'F' && event.payload.size() > 30 && ((event.flags + event.ordinal) & 3u) != 0u) {
      RouteNode* node = new RouteNode();
      node->body_size = event.payload.size() + 17;
      node->body = new char[node->body_size];
      for (size_t i = 0; i < node->body_size; ++i) {
        node->body[i] = event.payload[i % event.payload.size()] ^ static_cast<char>(i + event.flags);
      }
      node->generation = mix32(static_cast<uint32_t>(node->body_size) ^ event.route ^ event.ordinal);
      primary[event.route] = node;
      delayed[event.route] = node;
      stages[event.route] = 1;
    } else if (event.opcode == 'Q' && stages[event.route] == 1 && primary[event.route] != nullptr &&
               event.payload.size() >= 9 && ((event.payload.back() + event.flags) & 1u) == 1u) {
      RouteNode* node = primary[event.route];
      delete[] node->body;
      delete node;
      primary[event.route] = nullptr;
      stages[event.route] = 2;
    } else if (event.opcode == 'W' && stages[event.route] == 2 && delayed[event.route] != nullptr &&
               event.payload.size() >= 5 && ((event.payload[0] ^ event.payload.back()) & 1u) == 0u) {
      RouteNode* node = delayed[event.route];
      digest = mix32(digest ^ node->generation ^ static_cast<uint32_t>(event.payload.size()));
      delete[] node->body;
      delete node;
      delayed[event.route] = nullptr;
      stages[event.route] = 3;
    }
  }

  for (auto& entry : primary) {
    if (entry.second != nullptr) {
      delete[] entry.second->body;
      delete entry.second;
      entry.second = nullptr;
    }
  }

  return digest;
}

static uint32_t rollbackBranchQueue(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplayRows {
    std::vector<std::string> rows;
    std::string* retained = nullptr;
    uint8_t stage = 0;
  };

  std::unordered_map<uint16_t, ReplayRows> tables;

  for (const FrameEvent& event : events) {
    ReplayRows& table = tables[event.route];

    if (event.opcode == 'V' && event.payload.size() > 28 && ((event.flags + event.ordinal) & 1u) == 0u) {
      table.rows.clear();
      table.rows.reserve(1);
      std::string row = event.payload;
      row.append(":");
      row.append(std::to_string(event.route));
      row.append(":checkpoint-row");
      table.rows.push_back(row);
      table.retained = &table.rows.back();
      table.stage = 1;
    } else if (event.opcode == 'X' && table.stage == 1 && table.retained != nullptr && event.payload.size() >= 8) {
      for (uint8_t i = 0; i < 96; ++i) {
        std::string row = event.payload;
        row.push_back(static_cast<char>('A' + ((event.flags + i) % 26)));
        row.append(std::to_string(i + event.ordinal));
        row.append(":expanded");
        table.rows.push_back(row);
      }
      table.stage = 2;
    } else if (event.opcode == 'Y' && table.stage == 2 && table.retained != nullptr &&
               event.payload.size() >= 6 && ((event.payload[0] + event.flags) & 3u) != 3u) {
      digest = foldSpan(std::string_view(table.retained->data(), table.retained->size()), digest);
      digest = mix32(digest ^ static_cast<uint32_t>(table.rows.size()) ^ event.ordinal);
      table.stage = 3;
    }
  }

  return digest;
}

static uint32_t checkpointCacheLruDigest(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct RouteNode {
    char* body = nullptr;
    size_t body_size = 0;
    uint32_t generation = 0;
  };

  std::unordered_map<uint16_t, RouteNode*> primary;
  std::unordered_map<uint16_t, RouteNode*> delayed;
  std::unordered_map<uint16_t, uint8_t> stages;

  for (const FrameEvent& event : events) {
    if (event.opcode == 'U' && event.payload.size() > 30 && ((event.flags + event.ordinal) & 3u) != 0u) {
      RouteNode* node = new RouteNode();
      node->body_size = event.payload.size() + 17;
      node->body = new char[node->body_size];
      for (size_t i = 0; i < node->body_size; ++i) {
        node->body[i] = event.payload[i % event.payload.size()] ^ static_cast<char>(i + event.flags);
      }
      node->generation = mix32(static_cast<uint32_t>(node->body_size) ^ event.route ^ event.ordinal);
      primary[event.route] = node;
      delayed[event.route] = node;
      stages[event.route] = 1;
    } else if (event.opcode == 'V' && stages[event.route] == 1 && primary[event.route] != nullptr &&
               event.payload.size() >= 9 && ((event.payload.back() + event.flags) & 1u) == 1u) {
      RouteNode* node = primary[event.route];
      delete[] node->body;
      delete node;
      primary[event.route] = nullptr;
      stages[event.route] = 2;
    } else if (event.opcode == 'W' && stages[event.route] == 2 && delayed[event.route] != nullptr &&
               event.payload.size() >= 5 && ((event.payload[0] ^ event.payload.back()) & 1u) == 0u) {
      RouteNode* node = delayed[event.route];
      digest = mix32(digest ^ node->generation ^ static_cast<uint32_t>(event.payload.size()));
      delete[] node->body;
      delete node;
      delayed[event.route] = nullptr;
      stages[event.route] = 3;
    }
  }

  for (auto& entry : primary) {
    if (entry.second != nullptr) {
      delete[] entry.second->body;
      delete entry.second;
      entry.second = nullptr;
    }
  }

  return digest;
}

static uint32_t checkpointSharedRouteNode(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplaySlot {
    char* retained = nullptr;
    size_t retained_size = 0;
    std::string_view retained_view;
    uint32_t route_mix = 0;
    uint8_t stage = 0;
    bool released = false;
  };

  std::unordered_map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;

  for (size_t index = 0; index < events.size(); ++index) {
    const FrameEvent& event = events[index];
    ReplaySlot& slot = slots[event.route];

    if (event.opcode == 'I' && event.payload.size() > 24 && ((event.flags ^ event.ordinal) & 3u) == 1u) {
      if (slot.retained != nullptr && !slot.released) {
        delete[] slot.retained;
      }

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
    } else if (event.opcode == 'K' && slot.stage == 1 && !slot.released && event.payload.size() >= 8 &&
               ((event.payload.size() + slot.route_mix + event.flags) & 7u) <= 5u) {
      for (uint8_t i = 0; i < 56; ++i) {
        std::string segment = event.payload;
        segment.push_back(static_cast<char>('a' + ((slot.route_mix + i) % 26)));
        segment.append(std::to_string(slot.retained_size + i));
        expansion_cache.push_back(std::move(segment));
      }

      if (slot.retained_size > 32 && expansion_cache.size() >= 56) {
        delete[] slot.retained;
        slot.released = true;
        slot.stage = 2;
        slot.route_mix = mix32(slot.route_mix ^ static_cast<uint32_t>(expansion_cache.size()) ^ event.ordinal);
      }
    } else if (event.opcode == 'M' && slot.stage == 2 && slot.released && event.payload.size() >= 6 &&
               ((event.payload[0] ^ event.ordinal ^ event.flags) & 1u) == 0u) {
      digest = foldSpan(slot.retained_view, digest);
      digest = mix32(digest ^ slot.route_mix ^ static_cast<uint32_t>(event.payload.size()));
    }
  }

  for (auto& entry : slots) {
    ReplaySlot& slot = entry.second;
    if (slot.retained != nullptr && !slot.released) {
      delete[] slot.retained;
    }
  }

  return digest;
}

static uint32_t checkpointMergeLedger(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct MaterializedBatch {
    uint16_t count = 0;
    uint16_t width = 0;
    uint8_t stage = 0;
    std::string seed;
  };

  std::unordered_map<uint16_t, MaterializedBatch> batches;

  for (const FrameEvent& event : events) {
    MaterializedBatch& batch = batches[event.route];

    if (event.opcode == 'Z' && event.payload.size() >= 12) {
      batch.count = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[0]) + 17u) * 19u);
      batch.width = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[1]) + 9u) * 13u);
      batch.seed = event.payload;
      batch.stage = 1;
    } else if (event.opcode == 'A' && batch.stage == 1 && event.payload.size() >= 16 &&
               ((event.flags ^ event.ordinal ^ event.payload[2]) & 3u) != 2u) {
      batch.count = static_cast<uint16_t>(batch.count + static_cast<unsigned char>(event.payload[3]) + 31u);
      batch.width = static_cast<uint16_t>(batch.width + static_cast<unsigned char>(event.payload[4]) + 23u);
      batch.seed.append(event.payload);
      if (batch.seed.size() > 96) {
        batch.seed.resize(96);
      }
      batch.stage = 2;
    } else if (event.opcode == 'B' && batch.stage == 2 && batch.seed.size() >= 24) {
      size_t full_size = static_cast<size_t>(batch.count) * static_cast<size_t>(batch.width);
      uint16_t narrow_size = static_cast<uint16_t>(full_size + event.ordinal + event.flags + 11u);

      if (full_size > static_cast<size_t>(narrow_size) + 128u && full_size < 8192u) {
        char* materialized = new char[narrow_size + 16u];
        for (size_t i = 0; i < full_size; ++i) {
          materialized[i] = batch.seed[i % batch.seed.size()] ^ static_cast<char>(i + event.route);
        }
        digest = foldBytes(reinterpret_cast<const uint8_t*>(materialized), narrow_size + 16u, digest);
        delete[] materialized;
      }

      batch.stage = 3;
    }
  }

  return digest;
}

static uint32_t archiveDictionaryReplay(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplaySlot {
    char* retained = nullptr;
    size_t retained_size = 0;
    std::string_view retained_view;
    uint32_t route_mix = 0;
    uint8_t stage = 0;
    bool released = false;
  };

  std::unordered_map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;

  for (size_t index = 0; index < events.size(); ++index) {
    const FrameEvent& event = events[index];
    ReplaySlot& slot = slots[event.route];

    if (event.opcode == 'D' && event.payload.size() > 24 && ((event.flags ^ event.ordinal) & 3u) == 1u) {
      if (slot.retained != nullptr && !slot.released) {
        delete[] slot.retained;
      }

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
    } else if (event.opcode == 'E' && slot.stage == 1 && !slot.released && event.payload.size() >= 8 &&
               ((event.payload.size() + slot.route_mix + event.flags) & 7u) <= 5u) {
      for (uint8_t i = 0; i < 56; ++i) {
        std::string segment = event.payload;
        segment.push_back(static_cast<char>('a' + ((slot.route_mix + i) % 26)));
        segment.append(std::to_string(slot.retained_size + i));
        expansion_cache.push_back(std::move(segment));
      }

      if (slot.retained_size > 32 && expansion_cache.size() >= 56) {
        delete[] slot.retained;
        slot.released = true;
        slot.stage = 2;
        slot.route_mix = mix32(slot.route_mix ^ static_cast<uint32_t>(expansion_cache.size()) ^ event.ordinal);
      }
    } else if (event.opcode == 'F' && slot.stage == 2 && slot.released && event.payload.size() >= 6 &&
               ((event.payload[0] ^ event.ordinal ^ event.flags) & 1u) == 0u) {
      digest = foldSpan(slot.retained_view, digest);
      digest = mix32(digest ^ slot.route_mix ^ static_cast<uint32_t>(event.payload.size()));
    }
  }

  for (auto& entry : slots) {
    ReplaySlot& slot = entry.second;
    if (slot.retained != nullptr && !slot.released) {
      delete[] slot.retained;
    }
  }

  return digest;
}

static uint32_t archiveSparsePageTable(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct MaterializedBatch {
    uint16_t count = 0;
    uint16_t width = 0;
    uint8_t stage = 0;
    std::string seed;
  };

  std::unordered_map<uint16_t, MaterializedBatch> batches;

  for (const FrameEvent& event : events) {
    MaterializedBatch& batch = batches[event.route];

    if (event.opcode == 'G' && event.payload.size() >= 12) {
      batch.count = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[0]) + 17u) * 19u);
      batch.width = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[1]) + 9u) * 13u);
      batch.seed = event.payload;
      batch.stage = 1;
    } else if (event.opcode == 'H' && batch.stage == 1 && event.payload.size() >= 16 &&
               ((event.flags ^ event.ordinal ^ event.payload[2]) & 3u) != 2u) {
      batch.count = static_cast<uint16_t>(batch.count + static_cast<unsigned char>(event.payload[3]) + 31u);
      batch.width = static_cast<uint16_t>(batch.width + static_cast<unsigned char>(event.payload[4]) + 23u);
      batch.seed.append(event.payload);
      if (batch.seed.size() > 96) {
        batch.seed.resize(96);
      }
      batch.stage = 2;
    } else if (event.opcode == 'I' && batch.stage == 2 && batch.seed.size() >= 24) {
      size_t full_size = static_cast<size_t>(batch.count) * static_cast<size_t>(batch.width);
      uint16_t narrow_size = static_cast<uint16_t>(full_size + event.ordinal + event.flags + 11u);

      if (full_size > static_cast<size_t>(narrow_size) + 128u && full_size < 8192u) {
        char* materialized = new char[narrow_size + 16u];
        for (size_t i = 0; i < full_size; ++i) {
          materialized[i] = batch.seed[i % batch.seed.size()] ^ static_cast<char>(i + event.route);
        }
        digest = foldBytes(reinterpret_cast<const uint8_t*>(materialized), narrow_size + 16u, digest);
        delete[] materialized;
      }

      batch.stage = 3;
    }
  }

  return digest;
}

static uint32_t archiveDeltaDictionary(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplayRows {
    std::vector<std::string> rows;
    std::string* retained = nullptr;
    uint8_t stage = 0;
  };

  std::unordered_map<uint16_t, ReplayRows> tables;

  for (const FrameEvent& event : events) {
    ReplayRows& table = tables[event.route];

    if (event.opcode == 'J' && event.payload.size() > 28 && ((event.flags + event.ordinal) & 1u) == 0u) {
      table.rows.clear();
      table.rows.reserve(1);
      std::string row = event.payload;
      row.append(":");
      row.append(std::to_string(event.route));
      row.append(":checkpoint-row");
      table.rows.push_back(row);
      table.retained = &table.rows.back();
      table.stage = 1;
    } else if (event.opcode == 'K' && table.stage == 1 && table.retained != nullptr && event.payload.size() >= 8) {
      for (uint8_t i = 0; i < 96; ++i) {
        std::string row = event.payload;
        row.push_back(static_cast<char>('A' + ((event.flags + i) % 26)));
        row.append(std::to_string(i + event.ordinal));
        row.append(":expanded");
        table.rows.push_back(row);
      }
      table.stage = 2;
    } else if (event.opcode == 'L' && table.stage == 2 && table.retained != nullptr &&
               event.payload.size() >= 6 && ((event.payload[0] + event.flags) & 3u) != 3u) {
      digest = foldSpan(std::string_view(table.retained->data(), table.retained->size()), digest);
      digest = mix32(digest ^ static_cast<uint32_t>(table.rows.size()) ^ event.ordinal);
      table.stage = 3;
    }
  }

  return digest;
}

static uint32_t tenantIndexRehashLedger(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplaySlot {
    char* retained = nullptr;
    size_t retained_size = 0;
    std::string_view retained_view;
    uint32_t route_mix = 0;
    uint8_t stage = 0;
    bool released = false;
  };

  std::unordered_map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;

  for (size_t index = 0; index < events.size(); ++index) {
    const FrameEvent& event = events[index];
    ReplaySlot& slot = slots[event.route];

    if (event.opcode == 'M' && event.payload.size() > 24 && ((event.flags ^ event.ordinal) & 3u) == 1u) {
      if (slot.retained != nullptr && !slot.released) {
        delete[] slot.retained;
      }

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
    } else if (event.opcode == 'O' && slot.stage == 1 && !slot.released && event.payload.size() >= 8 &&
               ((event.payload.size() + slot.route_mix + event.flags) & 7u) <= 5u) {
      for (uint8_t i = 0; i < 56; ++i) {
        std::string segment = event.payload;
        segment.push_back(static_cast<char>('a' + ((slot.route_mix + i) % 26)));
        segment.append(std::to_string(slot.retained_size + i));
        expansion_cache.push_back(std::move(segment));
      }

      if (slot.retained_size > 32 && expansion_cache.size() >= 56) {
        delete[] slot.retained;
        slot.released = true;
        slot.stage = 2;
        slot.route_mix = mix32(slot.route_mix ^ static_cast<uint32_t>(expansion_cache.size()) ^ event.ordinal);
      }
    } else if (event.opcode == 'P' && slot.stage == 2 && slot.released && event.payload.size() >= 6 &&
               ((event.payload[0] ^ event.ordinal ^ event.flags) & 1u) == 0u) {
      digest = foldSpan(slot.retained_view, digest);
      digest = mix32(digest ^ slot.route_mix ^ static_cast<uint32_t>(event.payload.size()));
    }
  }

  for (auto& entry : slots) {
    ReplaySlot& slot = entry.second;
    if (slot.retained != nullptr && !slot.released) {
      delete[] slot.retained;
    }
  }

  return digest;
}

static uint32_t tenantRouteMapReplay(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplayRows {
    std::vector<std::string> rows;
    std::string* retained = nullptr;
    uint8_t stage = 0;
  };

  std::unordered_map<uint16_t, ReplayRows> tables;

  for (const FrameEvent& event : events) {
    ReplayRows& table = tables[event.route];

    if (event.opcode == 'Q' && event.payload.size() > 28 && ((event.flags + event.ordinal) & 1u) == 0u) {
      table.rows.clear();
      table.rows.reserve(1);
      std::string row = event.payload;
      row.append(":");
      row.append(std::to_string(event.route));
      row.append(":checkpoint-row");
      table.rows.push_back(row);
      table.retained = &table.rows.back();
      table.stage = 1;
    } else if (event.opcode == 'R' && table.stage == 1 && table.retained != nullptr && event.payload.size() >= 8) {
      for (uint8_t i = 0; i < 96; ++i) {
        std::string row = event.payload;
        row.push_back(static_cast<char>('A' + ((event.flags + i) % 26)));
        row.append(std::to_string(i + event.ordinal));
        row.append(":expanded");
        table.rows.push_back(row);
      }
      table.stage = 2;
    } else if (event.opcode == 'S' && table.stage == 2 && table.retained != nullptr &&
               event.payload.size() >= 6 && ((event.payload[0] + event.flags) & 3u) != 3u) {
      digest = foldSpan(std::string_view(table.retained->data(), table.retained->size()), digest);
      digest = mix32(digest ^ static_cast<uint32_t>(table.rows.size()) ^ event.ordinal);
      table.stage = 3;
    }
  }

  return digest;
}

static uint32_t tenantScopeMaterializer(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct MaterializedBatch {
    uint16_t count = 0;
    uint16_t width = 0;
    uint8_t stage = 0;
    std::string seed;
  };

  std::unordered_map<uint16_t, MaterializedBatch> batches;

  for (const FrameEvent& event : events) {
    MaterializedBatch& batch = batches[event.route];

    if (event.opcode == 'T' && event.payload.size() >= 12) {
      batch.count = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[0]) + 17u) * 19u);
      batch.width = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[1]) + 9u) * 13u);
      batch.seed = event.payload;
      batch.stage = 1;
    } else if (event.opcode == 'V' && batch.stage == 1 && event.payload.size() >= 16 &&
               ((event.flags ^ event.ordinal ^ event.payload[2]) & 3u) != 2u) {
      batch.count = static_cast<uint16_t>(batch.count + static_cast<unsigned char>(event.payload[3]) + 31u);
      batch.width = static_cast<uint16_t>(batch.width + static_cast<unsigned char>(event.payload[4]) + 23u);
      batch.seed.append(event.payload);
      if (batch.seed.size() > 96) {
        batch.seed.resize(96);
      }
      batch.stage = 2;
    } else if (event.opcode == 'X' && batch.stage == 2 && batch.seed.size() >= 24) {
      size_t full_size = static_cast<size_t>(batch.count) * static_cast<size_t>(batch.width);
      uint16_t narrow_size = static_cast<uint16_t>(full_size + event.ordinal + event.flags + 11u);

      if (full_size > static_cast<size_t>(narrow_size) + 128u && full_size < 8192u) {
        char* materialized = new char[narrow_size + 16u];
        for (size_t i = 0; i < full_size; ++i) {
          materialized[i] = batch.seed[i % batch.seed.size()] ^ static_cast<char>(i + event.route);
        }
        digest = foldBytes(reinterpret_cast<const uint8_t*>(materialized), narrow_size + 16u, digest);
        delete[] materialized;
      }

      batch.stage = 3;
    }
  }

  return digest;
}

static uint32_t replayWindowRingResize(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplayRows {
    std::vector<std::string> rows;
    std::string* retained = nullptr;
    uint8_t stage = 0;
  };

  std::unordered_map<uint16_t, ReplayRows> tables;

  for (const FrameEvent& event : events) {
    ReplayRows& table = tables[event.route];

    if (event.opcode == 'Y' && event.payload.size() > 28 && ((event.flags + event.ordinal) & 1u) == 0u) {
      table.rows.clear();
      table.rows.reserve(1);
      std::string row = event.payload;
      row.append(":");
      row.append(std::to_string(event.route));
      row.append(":checkpoint-row");
      table.rows.push_back(row);
      table.retained = &table.rows.back();
      table.stage = 1;
    } else if (event.opcode == 'A' && table.stage == 1 && table.retained != nullptr && event.payload.size() >= 8) {
      for (uint8_t i = 0; i < 96; ++i) {
        std::string row = event.payload;
        row.push_back(static_cast<char>('A' + ((event.flags + i) % 26)));
        row.append(std::to_string(i + event.ordinal));
        row.append(":expanded");
        table.rows.push_back(row);
      }
      table.stage = 2;
    } else if (event.opcode == 'C' && table.stage == 2 && table.retained != nullptr &&
               event.payload.size() >= 6 && ((event.payload[0] + event.flags) & 3u) != 3u) {
      digest = foldSpan(std::string_view(table.retained->data(), table.retained->size()), digest);
      digest = mix32(digest ^ static_cast<uint32_t>(table.rows.size()) ^ event.ordinal);
      table.stage = 3;
    }
  }

  return digest;
}

static uint32_t replayWindowFinalizer(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplaySlot {
    char* retained = nullptr;
    size_t retained_size = 0;
    std::string_view retained_view;
    uint32_t route_mix = 0;
    uint8_t stage = 0;
    bool released = false;
  };

  std::unordered_map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;

  for (size_t index = 0; index < events.size(); ++index) {
    const FrameEvent& event = events[index];
    ReplaySlot& slot = slots[event.route];

    if (event.opcode == 'E' && event.payload.size() > 24 && ((event.flags ^ event.ordinal) & 3u) == 1u) {
      if (slot.retained != nullptr && !slot.released) {
        delete[] slot.retained;
      }

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
    } else if (event.opcode == 'G' && slot.stage == 1 && !slot.released && event.payload.size() >= 8 &&
               ((event.payload.size() + slot.route_mix + event.flags) & 7u) <= 5u) {
      for (uint8_t i = 0; i < 56; ++i) {
        std::string segment = event.payload;
        segment.push_back(static_cast<char>('a' + ((slot.route_mix + i) % 26)));
        segment.append(std::to_string(slot.retained_size + i));
        expansion_cache.push_back(std::move(segment));
      }

      if (slot.retained_size > 32 && expansion_cache.size() >= 56) {
        delete[] slot.retained;
        slot.released = true;
        slot.stage = 2;
        slot.route_mix = mix32(slot.route_mix ^ static_cast<uint32_t>(expansion_cache.size()) ^ event.ordinal);
      }
    } else if (event.opcode == 'J' && slot.stage == 2 && slot.released && event.payload.size() >= 6 &&
               ((event.payload[0] ^ event.ordinal ^ event.flags) & 1u) == 0u) {
      digest = foldSpan(slot.retained_view, digest);
      digest = mix32(digest ^ slot.route_mix ^ static_cast<uint32_t>(event.payload.size()));
    }
  }

  for (auto& entry : slots) {
    ReplaySlot& slot = entry.second;
    if (slot.retained != nullptr && !slot.released) {
      delete[] slot.retained;
    }
  }

  return digest;
}

static uint32_t replayWindowOrdinalFold(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct MaterializedBatch {
    uint16_t count = 0;
    uint16_t width = 0;
    uint8_t stage = 0;
    std::string seed;
  };

  std::unordered_map<uint16_t, MaterializedBatch> batches;

  for (const FrameEvent& event : events) {
    MaterializedBatch& batch = batches[event.route];

    if (event.opcode == 'K' && event.payload.size() >= 12) {
      batch.count = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[0]) + 17u) * 19u);
      batch.width = static_cast<uint16_t>((static_cast<unsigned char>(event.payload[1]) + 9u) * 13u);
      batch.seed = event.payload;
      batch.stage = 1;
    } else if (event.opcode == 'N' && batch.stage == 1 && event.payload.size() >= 16 &&
               ((event.flags ^ event.ordinal ^ event.payload[2]) & 3u) != 2u) {
      batch.count = static_cast<uint16_t>(batch.count + static_cast<unsigned char>(event.payload[3]) + 31u);
      batch.width = static_cast<uint16_t>(batch.width + static_cast<unsigned char>(event.payload[4]) + 23u);
      batch.seed.append(event.payload);
      if (batch.seed.size() > 96) {
        batch.seed.resize(96);
      }
      batch.stage = 2;
    } else if (event.opcode == 'R' && batch.stage == 2 && batch.seed.size() >= 24) {
      size_t full_size = static_cast<size_t>(batch.count) * static_cast<size_t>(batch.width);
      uint16_t narrow_size = static_cast<uint16_t>(full_size + event.ordinal + event.flags + 11u);

      if (full_size > static_cast<size_t>(narrow_size) + 128u && full_size < 8192u) {
        char* materialized = new char[narrow_size + 16u];
        for (size_t i = 0; i < full_size; ++i) {
          materialized[i] = batch.seed[i % batch.seed.size()] ^ static_cast<char>(i + event.route);
        }
        digest = foldBytes(reinterpret_cast<const uint8_t*>(materialized), narrow_size + 16u, digest);
        delete[] materialized;
      }

      batch.stage = 3;
    }
  }

  return digest;
}

static uint32_t deltaMergeBasePage(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplaySlot {
    char* retained = nullptr;
    size_t retained_size = 0;
    std::string_view retained_view;
    uint32_t route_mix = 0;
    uint8_t stage = 0;
    bool released = false;
  };

  std::unordered_map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;

  for (size_t index = 0; index < events.size(); ++index) {
    const FrameEvent& event = events[index];
    ReplaySlot& slot = slots[event.route];

    if (event.opcode == 'S' && event.payload.size() > 24 && ((event.flags ^ event.ordinal) & 3u) == 1u) {
      if (slot.retained != nullptr && !slot.released) {
        delete[] slot.retained;
      }

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
    } else if (event.opcode == 'U' && slot.stage == 1 && !slot.released && event.payload.size() >= 8 &&
               ((event.payload.size() + slot.route_mix + event.flags) & 7u) <= 5u) {
      for (uint8_t i = 0; i < 56; ++i) {
        std::string segment = event.payload;
        segment.push_back(static_cast<char>('a' + ((slot.route_mix + i) % 26)));
        segment.append(std::to_string(slot.retained_size + i));
        expansion_cache.push_back(std::move(segment));
      }

      if (slot.retained_size > 32 && expansion_cache.size() >= 56) {
        delete[] slot.retained;
        slot.released = true;
        slot.stage = 2;
        slot.route_mix = mix32(slot.route_mix ^ static_cast<uint32_t>(expansion_cache.size()) ^ event.ordinal);
      }
    } else if (event.opcode == 'W' && slot.stage == 2 && slot.released && event.payload.size() >= 6 &&
               ((event.payload[0] ^ event.ordinal ^ event.flags) & 1u) == 0u) {
      digest = foldSpan(slot.retained_view, digest);
      digest = mix32(digest ^ slot.route_mix ^ static_cast<uint32_t>(event.payload.size()));
    }
  }

  for (auto& entry : slots) {
    ReplaySlot& slot = entry.second;
    if (slot.retained != nullptr && !slot.released) {
      delete[] slot.retained;
    }
  }

  return digest;
}

static uint32_t deltaMergeConflictPage(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct RouteNode {
    char* body = nullptr;
    size_t body_size = 0;
    uint32_t generation = 0;
  };

  std::unordered_map<uint16_t, RouteNode*> primary;
  std::unordered_map<uint16_t, RouteNode*> delayed;
  std::unordered_map<uint16_t, uint8_t> stages;

  for (const FrameEvent& event : events) {
    if (event.opcode == 'X' && event.payload.size() > 30 && ((event.flags + event.ordinal) & 3u) != 0u) {
      RouteNode* node = new RouteNode();
      node->body_size = event.payload.size() + 17;
      node->body = new char[node->body_size];
      for (size_t i = 0; i < node->body_size; ++i) {
        node->body[i] = event.payload[i % event.payload.size()] ^ static_cast<char>(i + event.flags);
      }
      node->generation = mix32(static_cast<uint32_t>(node->body_size) ^ event.route ^ event.ordinal);
      primary[event.route] = node;
      delayed[event.route] = node;
      stages[event.route] = 1;
    } else if (event.opcode == 'Z' && stages[event.route] == 1 && primary[event.route] != nullptr &&
               event.payload.size() >= 9 && ((event.payload.back() + event.flags) & 1u) == 1u) {
      RouteNode* node = primary[event.route];
      delete[] node->body;
      delete node;
      primary[event.route] = nullptr;
      stages[event.route] = 2;
    } else if (event.opcode == 'B' && stages[event.route] == 2 && delayed[event.route] != nullptr &&
               event.payload.size() >= 5 && ((event.payload[0] ^ event.payload.back()) & 1u) == 0u) {
      RouteNode* node = delayed[event.route];
      digest = mix32(digest ^ node->generation ^ static_cast<uint32_t>(event.payload.size()));
      delete[] node->body;
      delete node;
      delayed[event.route] = nullptr;
      stages[event.route] = 3;
    }
  }

  for (auto& entry : primary) {
    if (entry.second != nullptr) {
      delete[] entry.second->body;
      delete entry.second;
      entry.second = nullptr;
    }
  }

  return digest;
}

static uint32_t deltaMergeDigestPage(const std::vector<FrameEvent>& events, uint32_t digest) {
  struct ReplayRows {
    std::vector<std::string> rows;
    std::string* retained = nullptr;
    uint8_t stage = 0;
  };

  std::unordered_map<uint16_t, ReplayRows> tables;

  for (const FrameEvent& event : events) {
    ReplayRows& table = tables[event.route];

    if (event.opcode == 'C' && event.payload.size() > 28 && ((event.flags + event.ordinal) & 1u) == 0u) {
      table.rows.clear();
      table.rows.reserve(1);
      std::string row = event.payload;
      row.append(":");
      row.append(std::to_string(event.route));
      row.append(":checkpoint-row");
      table.rows.push_back(row);
      table.retained = &table.rows.back();
      table.stage = 1;
    } else if (event.opcode == 'F' && table.stage == 1 && table.retained != nullptr && event.payload.size() >= 8) {
      for (uint8_t i = 0; i < 96; ++i) {
        std::string row = event.payload;
        row.push_back(static_cast<char>('A' + ((event.flags + i) % 26)));
        row.append(std::to_string(i + event.ordinal));
        row.append(":expanded");
        table.rows.push_back(row);
      }
      table.stage = 2;
    } else if (event.opcode == 'H' && table.stage == 2 && table.retained != nullptr &&
               event.payload.size() >= 6 && ((event.payload[0] + event.flags) & 3u) != 3u) {
      digest = foldSpan(std::string_view(table.retained->data(), table.retained->size()), digest);
      digest = mix32(digest ^ static_cast<uint32_t>(table.rows.size()) ^ event.ordinal);
      table.stage = 3;
    }
  }

  return digest;
}

}  // namespace

uint32_t driveRouteCheckpointPath(const uint8_t* data, size_t size) {
  std::vector<FrameEvent> events = parseFrame(data, size, 33);
  uint32_t digest = mix32(33u ^ static_cast<uint32_t>(size));
  digest ^= routeCheckpointWindow(events, digest);
  digest ^= routeTombstoneCascade(events, digest);
  digest ^= routeTenantAliasLedger(events, digest);
  return digest;
}

uint32_t driveSnapshotImportPath(const uint8_t* data, size_t size) {
  std::vector<FrameEvent> events = parseFrame(data, size, 34);
  uint32_t digest = mix32(34u ^ static_cast<uint32_t>(size));
  digest ^= snapshotImportIndex(events, digest);
  digest ^= snapshotDeltaPageMerge(events, digest);
  digest ^= snapshotTenantTrie(events, digest);
  return digest;
}

uint32_t driveBatchReplayPath(const uint8_t* data, size_t size) {
  std::vector<FrameEvent> events = parseFrame(data, size, 35);
  uint32_t digest = mix32(35u ^ static_cast<uint32_t>(size));
  digest ^= batchReplaySegments(events, digest);
  digest ^= batchFooterRewind(events, digest);
  digest ^= batchDigestMaterializer(events, digest);
  return digest;
}

uint32_t driveProfileDecodePath(const uint8_t* data, size_t size) {
  std::vector<FrameEvent> events = parseFrame(data, size, 36);
  uint32_t digest = mix32(36u ^ static_cast<uint32_t>(size));
  digest ^= profileCompactSections(events, digest);
  digest ^= profileAliasNormalizer(events, digest);
  digest ^= profileNestedGroupReplay(events, digest);
  return digest;
}

uint32_t driveAuthFramePath(const uint8_t* data, size_t size) {
  std::vector<FrameEvent> events = parseFrame(data, size, 37);
  uint32_t digest = mix32(37u ^ static_cast<uint32_t>(size));
  digest ^= authCapabilityDowngrade(events, digest);
  digest ^= authRouteTokenReplay(events, digest);
  digest ^= authTenantSecretFold(events, digest);
  return digest;
}

uint32_t driveCompactionPath(const uint8_t* data, size_t size) {
  std::vector<FrameEvent> events = parseFrame(data, size, 38);
  uint32_t digest = mix32(38u ^ static_cast<uint32_t>(size));
  digest ^= compactionStableSorter(events, digest);
  digest ^= compactionReplaySpan(events, digest);
  digest ^= compactionOrdinalPack(events, digest);
  return digest;
}

uint32_t driveRollbackPath(const uint8_t* data, size_t size) {
  std::vector<FrameEvent> events = parseFrame(data, size, 39);
  uint32_t digest = mix32(39u ^ static_cast<uint32_t>(size));
  digest ^= rollbackPendingCommit(events, digest);
  digest ^= rollbackConflictResolver(events, digest);
  digest ^= rollbackBranchQueue(events, digest);
  return digest;
}

uint32_t driveCheckpointCachePath(const uint8_t* data, size_t size) {
  std::vector<FrameEvent> events = parseFrame(data, size, 40);
  uint32_t digest = mix32(40u ^ static_cast<uint32_t>(size));
  digest ^= checkpointCacheLruDigest(events, digest);
  digest ^= checkpointSharedRouteNode(events, digest);
  digest ^= checkpointMergeLedger(events, digest);
  return digest;
}

uint32_t driveArchiveReplayPath(const uint8_t* data, size_t size) {
  std::vector<FrameEvent> events = parseFrame(data, size, 41);
  uint32_t digest = mix32(41u ^ static_cast<uint32_t>(size));
  digest ^= archiveDictionaryReplay(events, digest);
  digest ^= archiveSparsePageTable(events, digest);
  digest ^= archiveDeltaDictionary(events, digest);
  return digest;
}

uint32_t driveTenantIndexPath(const uint8_t* data, size_t size) {
  std::vector<FrameEvent> events = parseFrame(data, size, 42);
  uint32_t digest = mix32(42u ^ static_cast<uint32_t>(size));
  digest ^= tenantIndexRehashLedger(events, digest);
  digest ^= tenantRouteMapReplay(events, digest);
  digest ^= tenantScopeMaterializer(events, digest);
  return digest;
}

uint32_t driveReplayWindowPath(const uint8_t* data, size_t size) {
  std::vector<FrameEvent> events = parseFrame(data, size, 43);
  uint32_t digest = mix32(43u ^ static_cast<uint32_t>(size));
  digest ^= replayWindowRingResize(events, digest);
  digest ^= replayWindowFinalizer(events, digest);
  digest ^= replayWindowOrdinalFold(events, digest);
  return digest;
}

uint32_t driveDeltaMergePath(const uint8_t* data, size_t size) {
  std::vector<FrameEvent> events = parseFrame(data, size, 44);
  uint32_t digest = mix32(44u ^ static_cast<uint32_t>(size));
  digest ^= deltaMergeBasePage(events, digest);
  digest ^= deltaMergeConflictPage(events, digest);
  digest ^= deltaMergeDigestPage(events, digest);
  return digest;
}

}  // namespace campusops::wire
