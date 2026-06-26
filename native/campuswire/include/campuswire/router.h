#pragma once

#include "campuswire/ledger.h"

#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace campusops::wire {

struct RouteState {
  uint16_t route_id = 0;
  std::string last_handler;
  uint8_t max_hop = 0;
  uint32_t last_seen = 0;
  uint32_t fingerprint = 0;
};

class RouteAccumulator {
 public:
  void ingest(const RouteCheckpoint& checkpoint);
  uint32_t fingerprint() const;
  std::vector<RouteState> states() const;

 private:
  std::map<uint16_t, RouteState> routes_;
};

uint32_t computeProfileFingerprint(const std::vector<CompactProfile>& profiles);
uint32_t computeRouteFingerprint(const std::vector<RouteCheckpoint>& checkpoints);
uint32_t computeJournalReplayFingerprint(const std::vector<RouteCheckpoint>& checkpoints,
                                        const std::vector<JournalNote>& notes);

}  // namespace campusops::wire
