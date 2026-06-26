#include "campuswire/ledger.h"

#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

int main(int argc, char** argv) {
  if (argc != 2) {
    std::cerr << "usage: dump_campus_packet <packet-file>\n";
    return 2;
  }
  std::ifstream input(argv[1], std::ios::binary);
  if (!input) {
    std::cerr << "could not open input file\n";
    return 2;
  }
  std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
  try {
    campusops::wire::ParseOptions options;
    options.strict_lengths = true;
    auto packet = campusops::wire::parseLedgerPacket(bytes.data(), bytes.size(), options);
    auto summary = campusops::wire::summarizeLedgerPacket(packet);
    std::cout << campusops::wire::packetToJsonLine(packet, summary) << "\n";
  } catch (const std::exception& e) {
    std::cerr << "parse error: " << e.what() << "\n";
    return 1;
  }
  return 0;
}
