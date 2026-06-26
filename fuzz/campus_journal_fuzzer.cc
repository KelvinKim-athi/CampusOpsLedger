#include "campuswire/ledger.h"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iterator>
#include <vector>

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  if (size == 0) {
    return 0;
  }
  size_t midpoint = size / 2;
  campusops::wire::ParseOptions first_options;
  first_options.strict_lengths = true;
  campusops::wire::ParseOptions second_options;
  second_options.strict_lengths = false;
  second_options.allow_journal_notes = true;

  try {
    auto first = campusops::wire::parseLedgerPacket(data, midpoint, first_options);
    auto first_summary = campusops::wire::summarizeLedgerPacket(first);
    volatile uint32_t sink = first_summary.route_fingerprint;
    (void)sink;
  } catch (const std::exception&) {
  }

  try {
    auto second = campusops::wire::parseLedgerPacket(data + midpoint, size - midpoint, second_options);
    auto second_summary = campusops::wire::summarizeLedgerPacket(second);
    volatile uint32_t sink = second_summary.profile_fingerprint;
    (void)sink;
  } catch (const std::exception&) {
  }

  try {
    auto whole = campusops::wire::parseLedgerPacket(data, size, second_options);
    auto summary = campusops::wire::summarizeLedgerPacket(whole);
    volatile uint32_t sink = summary.accepted_records;
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
