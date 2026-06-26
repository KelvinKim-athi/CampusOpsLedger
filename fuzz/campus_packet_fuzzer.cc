#include "campuswire/ledger.h"

#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iterator>
#include <vector>

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  campusops::wire::ParseOptions options;
  options.strict_lengths = (size % 3) != 0;
  options.allow_journal_notes = (size % 5) != 0;
  try {
    auto packet = campusops::wire::parseLedgerPacket(data, size, options);
    auto summary = campusops::wire::summarizeLedgerPacket(packet);
    volatile uint32_t sink = summary.route_fingerprint ^ summary.profile_fingerprint;
    (void)sink;
  } catch (const std::exception&) {
  }
  return 0;
}

#ifdef FUZZ_STANDALONE
int main(int argc, char** argv) {
  for (int i = 1; i < argc; ++i) {
    std::ifstream input(argv[i], std::ios::binary);
    std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    LLVMFuzzerTestOneInput(bytes.data(), bytes.size());
  }
  return 0;
}
#endif
