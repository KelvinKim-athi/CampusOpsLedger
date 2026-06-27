#include <cstddef>
#include <cstdint>

#include "deep_replay_lab.h"

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  volatile uint32_t digest = campusops::wire::driveDeltaMergePath(data, size);
  (void)digest;
  return 0;
}
