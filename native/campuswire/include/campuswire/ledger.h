#pragma once

#include "campuswire/byte_reader.h"

#include <array>
#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace campusops::wire {

enum class RecordType : uint8_t {
  kStudentEvent = 0x11,
  kFeeEvent = 0x24,
  kRouteCheckpoint = 0x33,
  kCompactProfile = 0x42,
  kJournalNote = 0x55,
};

struct StudentEvent {
  std::string student_id;
  std::string unit;
  std::string status;
  uint32_t logical_time = 0;
};

struct FeeEvent {
  std::string account;
  uint32_t amount_cents = 0;
  uint8_t stage = 0;
};

struct RouteCheckpoint {
  uint16_t route_id = 0;
  std::string handler;
  uint8_t hop = 0;
  uint32_t seen_at = 0;
};

struct CompactProfile {
  std::string student_id;
  std::string unit;
  uint16_t admission_year = 0;
  uint8_t profile_flags = 0;
  uint8_t advisory_band = 0;
  std::vector<uint16_t> retention_slots;
  std::array<uint32_t, 4> term_hashes{};
};

struct JournalNote {
  std::string topic;
  std::string body;
};

struct LedgerPacket {
  uint8_t version = 0;
  uint16_t declared_records = 0;
  uint32_t batch_id = 0;
  std::vector<StudentEvent> student_events;
  std::vector<FeeEvent> fee_events;
  std::vector<RouteCheckpoint> checkpoints;
  std::vector<CompactProfile> compact_profiles;
  std::vector<JournalNote> notes;
};

struct LedgerSummary {
  uint32_t accepted_records = 0;
  uint32_t rejected_records = 0;
  std::map<std::string, uint32_t> unit_counts;
  std::map<std::string, uint32_t> status_counts;
  uint32_t route_fingerprint = 0;
  uint32_t profile_fingerprint = 0;
  uint32_t journal_fingerprint = 0;
  std::string digest;
};

struct ParseOptions {
  bool strict_lengths = true;
  bool allow_journal_notes = true;
  bool derive_summary = true;
};

LedgerPacket parseLedgerPacket(const uint8_t* data, size_t size, const ParseOptions& options = {});
LedgerSummary summarizeLedgerPacket(const LedgerPacket& packet);
std::string packetToJsonLine(const LedgerPacket& packet, const LedgerSummary& summary);

}  // namespace campusops::wire
