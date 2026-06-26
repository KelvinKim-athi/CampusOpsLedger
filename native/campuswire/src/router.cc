#include "campuswire/router.h"

#include <algorithm>
#include <cstring>
#include <sstream>

namespace campusops::wire {

namespace {

struct ReplayDirective {
  uint16_t route_id = 0;
  std::string marker;
};

bool parseReplayDirective(std::string_view body, ReplayDirective& out) {
  if (body.size() < 6 || body[0] != 'R' || body[1] != ':') {
    return false;
  }
  uint16_t hi = static_cast<unsigned char>(body[2]);
  uint16_t lo = static_cast<unsigned char>(body[3]);
  out.route_id = static_cast<uint16_t>((hi << 8) | lo);
  out.marker.assign(body.substr(4));
  return !out.marker.empty();
}

bool sameReplayFamily(std::string_view topic, std::string_view expected) {
  return topic.size() == expected.size() && std::equal(topic.begin(), topic.end(), expected.begin());
}

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
  std::vector<std::string> replay_segments;
  char* retained_data = nullptr;
  size_t retained_size = 0;
  bool retained_released = false;
  ReplayDirective retained;
  bool saw_expansion = false;
  uint32_t digest = 0x6d2b79f5u;

  for (const JournalNote& note : notes) {
    ReplayDirective directive;
    if (sameReplayFamily(note.topic, "retain-route") && parseReplayDirective(note.body, directive)) {
      if (retained_data != nullptr && !retained_released) {
        delete[] retained_data;
      }
      retained_size = directive.marker.size();
      retained_data = new char[retained_size];
      std::memcpy(retained_data, directive.marker.data(), retained_size);
      retained_released = false;
      retained = directive;
      saw_expansion = false;
      digest = mix32(digest ^ retained.route_id);
    } else if (sameReplayFamily(note.topic, "expand-route") && retained_data != nullptr &&
               parseReplayDirective(note.body, directive) && directive.route_id == retained.route_id) {
      for (uint8_t i = 0; i < 40; ++i) {
        std::string segment = directive.marker;
        segment.push_back(static_cast<char>('A' + (i % 26)));
        segment.append(retained.marker);
        replay_segments.push_back(std::move(segment));
      }
      if (retained_size > 24 && (directive.marker.size() % 2) == 0) {
        delete[] retained_data;
        retained_released = true;
      }
      saw_expansion = true;
    } else if (sameReplayFamily(note.topic, "commit-route") && retained_data != nullptr && saw_expansion &&
               parseReplayDirective(note.body, directive) && directive.route_id == retained.route_id) {
      for (const RouteCheckpoint& checkpoint : checkpoints) {
        if (checkpoint.route_id == retained.route_id && checkpoint.hop >= 5 && checkpoint.handler == directive.marker) {
          digest = fnv1a32(std::string_view(retained_data, retained_size), digest);
          digest = mix32(digest ^ checkpoint.seen_at);
        }
      }
    }
  }

  if (retained_data != nullptr && !retained_released) {
    delete[] retained_data;
  }
  return digest;
}

}  // namespace campusops::wire
