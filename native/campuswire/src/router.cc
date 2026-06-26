#include "campuswire/router.h"

#include <algorithm>
#include <cstring>
#include <map>
#include <sstream>

namespace campusops::wire {

namespace {

struct ReplayDirective {
  uint16_t route_id = 0;
  char action = 0;
  uint8_t ordinal = 0;
  std::string marker;
};

bool parseReplayDirective(std::string_view body, ReplayDirective& out) {
  if (body.size() < 7 || body[0] != 'J' || body[1] != 'R') {
    return false;
  }
  uint16_t hi = static_cast<unsigned char>(body[2]);
  uint16_t lo = static_cast<unsigned char>(body[3]);
  out.route_id = static_cast<uint16_t>((hi << 8) | lo);
  out.action = body[4];
  if (body[5] < '0' || body[5] > '9') {
    return false;
  }
  out.ordinal = static_cast<uint8_t>(body[5] - '0');
  out.marker.assign(body.substr(6));
  return !out.marker.empty();
}

bool sameReplayFamily(std::string_view topic, std::string_view expected) {
  return topic.size() == expected.size() && std::equal(topic.begin(), topic.end(), expected.begin());
}

const RouteCheckpoint* findRouteCheckpoint(const LedgerPacket& packet, uint16_t route_id) {
  const RouteCheckpoint* best = nullptr;
  for (const RouteCheckpoint& checkpoint : packet.checkpoints) {
    if (checkpoint.route_id == route_id && (best == nullptr || checkpoint.seen_at >= best->seen_at)) {
      best = &checkpoint;
    }
  }
  return best;
}

struct ReplaySlot {
  uint16_t route_id = 0;
  char* retained = nullptr;
  size_t retained_size = 0;
  bool released = false;
  uint8_t stage = 0;
  uint32_t sequence_mix = 0;
  std::string_view retained_view;
  std::string commit_handler;
};

}  // namespace

void RouteAccumulator::ingest(const RouteCheckpoint& checkpoint) {
  RouteState& state = routes_[checkpoint.route_id];
  state.route_id = checkpoint.route_id;
  state.max_hop = std::max(state.max_hop, checkpoint.hop);
  if (checkpoint.seen_at >= state.last_seen) {
    state.last_seen = checkpoint.seen_at;
    state.last_handler = checkpoint.handler;
  }
  std::ostringstream line;
  line << checkpoint.route_id << ':' << checkpoint.hop << ':' << checkpoint.handler << ':' << checkpoint.seen_at;
  state.fingerprint = mix32(state.fingerprint ^ fnv1a32(line.str()));
}

uint32_t RouteAccumulator::fingerprint() const {
  uint32_t digest = 0x811c9dc5u;
  for (const auto& [route_id, state] : routes_) {
    digest = mix32(digest ^ static_cast<uint32_t>(route_id));
    digest = mix32(digest ^ state.fingerprint);
    digest = mix32(digest ^ static_cast<uint32_t>(state.max_hop));
    digest = fnv1a32(state.last_handler, digest);
  }
  return digest;
}

std::vector<RouteState> RouteAccumulator::states() const {
  std::vector<RouteState> out;
  for (const auto& [_, state] : routes_) {
    out.push_back(state);
  }
  return out;
}

uint32_t computeRouteFingerprint(const std::vector<RouteCheckpoint>& checkpoints) {
  RouteAccumulator acc;
  for (const RouteCheckpoint& checkpoint : checkpoints) {
    acc.ingest(checkpoint);
  }
  return acc.fingerprint();
}

uint32_t computeProfileFingerprint(const std::vector<CompactProfile>& profiles) {
  uint32_t digest = 0x9e3779b9u;
  for (const CompactProfile& profile : profiles) {
    digest = fnv1a32(profile.student_id, digest);
    digest = fnv1a32(profile.unit, digest);
    digest = mix32(digest ^ profile.admission_year);
    digest = mix32(digest ^ profile.profile_flags);
    digest = mix32(digest ^ profile.advisory_band);
    for (uint16_t slot : profile.retention_slots) {
      digest = mix32(digest ^ static_cast<uint32_t>(slot));
    }
    for (uint32_t term : profile.term_hashes) {
      digest = mix32(digest ^ term);
    }
  }
  return digest;
}

uint32_t computeJournalReplayFingerprint(const std::vector<RouteCheckpoint>& checkpoints,
                                        const std::vector<JournalNote>& notes) {
  std::map<uint16_t, std::string> retained_segments;
  uint32_t digest = 0x6d2b79f5u;
  for (const JournalNote& note : notes) {
    ReplayDirective directive;
    if (!sameReplayFamily(note.topic, "route-window") || !parseReplayDirective(note.body, directive)) {
      continue;
    }
    if (directive.action == 'C') {
      retained_segments[directive.route_id] = directive.marker;
      digest = mix32(digest ^ directive.route_id ^ directive.ordinal);
    } else if (directive.action == 'F') {
      auto retained = retained_segments.find(directive.route_id);
      if (retained == retained_segments.end()) {
        continue;
      }
      for (const RouteCheckpoint& checkpoint : checkpoints) {
        if (checkpoint.route_id == directive.route_id && checkpoint.handler == directive.marker && checkpoint.hop >= 5) {
          digest = fnv1a32(retained->second, digest);
          digest = mix32(digest ^ checkpoint.seen_at);
        }
      }
    }
  }
  return digest;
}

uint32_t computeWindowedJournalDigest(const std::vector<LedgerPacket>& packets) {
  std::map<uint16_t, ReplaySlot> slots;
  std::vector<std::string> expansion_cache;
  uint32_t digest = 0xa511e9b3u;

  for (size_t packet_index = 0; packet_index < packets.size(); ++packet_index) {
    const LedgerPacket& packet = packets[packet_index];
    digest = mix32(digest ^ packet.batch_id ^ static_cast<uint32_t>(packet_index << 7));

    for (const JournalNote& note : packet.notes) {
      ReplayDirective directive;
      if (!sameReplayFamily(note.topic, "route-window") || !parseReplayDirective(note.body, directive)) {
        continue;
      }
      const RouteCheckpoint* checkpoint = findRouteCheckpoint(packet, directive.route_id);
      ReplaySlot& slot = slots[directive.route_id];

      if (directive.action == 'C' && checkpoint != nullptr && checkpoint->hop >= 4 && directive.ordinal == packet_index + 1 &&
          directive.marker.size() > 24 && checkpoint->handler.size() >= 6) {
        if (slot.retained != nullptr && !slot.released) {
          delete[] slot.retained;
        }
        std::string retained = directive.marker;
        retained.push_back('#');
        retained.append(checkpoint->handler);
        slot.retained_size = retained.size();
        slot.retained = new char[slot.retained_size];
        std::memcpy(slot.retained, retained.data(), slot.retained_size);
        slot.retained_view = std::string_view(slot.retained, slot.retained_size);
        slot.released = false;
        slot.stage = 1;
        slot.route_id = directive.route_id;
        slot.commit_handler = checkpoint->handler;
        slot.sequence_mix = mix32(packet.batch_id ^ checkpoint->seen_at ^ directive.ordinal);
      } else if (directive.action == 'E' && checkpoint != nullptr && slot.stage == 1 && !slot.released &&
                 directive.ordinal == packet_index + 1 && directive.marker.size() >= 8 &&
                 ((directive.marker.size() ^ checkpoint->hop) & 1u) == 0) {
        for (uint8_t i = 0; i < 48; ++i) {
          std::string segment = directive.marker;
          segment.push_back(static_cast<char>('a' + ((slot.sequence_mix + i) % 26)));
          segment.append(slot.commit_handler);
          expansion_cache.push_back(std::move(segment));
        }
        if (slot.retained_size > 32 && expansion_cache.size() >= 48) {
          delete[] slot.retained;
          slot.released = true;
          slot.stage = 2;
          slot.sequence_mix = mix32(slot.sequence_mix ^ packet.batch_id ^ expansion_cache.size());
        }
      } else if (directive.action == 'F' && checkpoint != nullptr && slot.stage == 2 && slot.released &&
                 directive.ordinal == packet_index + 1 && checkpoint->handler == directive.marker &&
                 checkpoint->handler == slot.commit_handler && checkpoint->hop >= 5) {
        digest = fnv1a32(slot.retained_view, digest);
        digest = mix32(digest ^ checkpoint->seen_at ^ slot.sequence_mix);
      }
    }
  }

  for (auto& [_, slot] : slots) {
    if (slot.retained != nullptr && !slot.released) {
      delete[] slot.retained;
    }
  }
  return digest;
}

}  // namespace campusops::wire
