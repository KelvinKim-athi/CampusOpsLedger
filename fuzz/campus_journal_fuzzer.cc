#include "campuswire/byte_reader.h"
#include "campuswire/ledger.h"
#include "campuswire/router.h"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iterator>
#include <vector>

namespace {

bool driveWindowedReplay(const uint8_t* data, size_t size) {
  if (size < 7 || std::memcmp(data, "CWS3", 4) != 0) {
    return false;
  }
  campusops::wire::ByteReader stream(data + 4, size - 4);
  uint8_t frame_count = stream.readU8();
  if (frame_count < 3 || frame_count > 6) {
    return false;
  }

  std::vector<campusops::wire::LedgerPacket> packets;
  campusops::wire::ParseOptions options;
  options.strict_lengths = true;
  options.allow_journal_notes = true;
  for (uint8_t i = 0; i < frame_count && !stream.empty(); ++i) {
    uint16_t frame_size = stream.readU16LE();
    if (frame_size == 0 || frame_size > stream.remaining()) {
      return false;
    }
    auto frame = stream.readBytes(frame_size);
    try {
      packets.push_back(campusops::wire::parseLedgerPacket(frame.data(), frame.size(), options));
    } catch (const std::exception&) {
    }
  }
  if (packets.size() < 3) {
    return false;
  }
  volatile uint32_t sink = campusops::wire::computeWindowedJournalDigest(packets);
  (void)sink;
  return true;
}

}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  if (size == 0) {
    return 0;
  }

  try {
    if (driveWindowedReplay(data, size)) {
      return 0;
    }
  } catch (const std::exception&) {
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
