#include "campuswire/router.h"

#include <algorithm>
#include <sstream>

namespace campusops::wire {

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

}  // namespace campusops::wire
