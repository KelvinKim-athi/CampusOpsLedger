#include "campuswire/ledger.h"
#include "campuswire/router.h"

#include <algorithm>
#include <array>
#include <sstream>

namespace campusops::wire {
namespace {

constexpr uint8_t kCurrentVersion = 3;
constexpr uint16_t kMaxRecords = 512;
constexpr uint16_t kMaxRecordLength = 4096;

bool knownRecordType(uint8_t type) {
  return type == static_cast<uint8_t>(RecordType::kStudentEvent) ||
         type == static_cast<uint8_t>(RecordType::kFeeEvent) ||
         type == static_cast<uint8_t>(RecordType::kRouteCheckpoint) ||
         type == static_cast<uint8_t>(RecordType::kCompactProfile) ||
         type == static_cast<uint8_t>(RecordType::kJournalNote);
}

StudentEvent decodeStudentEvent(ByteReader& record) {
  StudentEvent out;
  out.student_id = record.readLengthPrefixedString(32);
  out.unit = record.readLengthPrefixedString(24);
  out.status = record.readLengthPrefixedString(20);
  out.logical_time = record.readU32LE();
  return out;
}

FeeEvent decodeFeeEvent(ByteReader& record) {
  FeeEvent out;
  out.account = record.readLengthPrefixedString(32);
  out.amount_cents = record.readU32LE();
  out.stage = record.readU8();
  return out;
}

RouteCheckpoint decodeRouteCheckpoint(ByteReader& record) {
  RouteCheckpoint out;
  out.route_id = record.readU16LE();
  out.handler = record.readLengthPrefixedString(28);
  out.hop = record.readU8();
  out.seen_at = record.readU32LE();
  return out;
}

uint32_t foldSlot(uint32_t seed, uint16_t slot, uint8_t index, std::string_view student_id) {
  uint32_t value = seed ^ (static_cast<uint32_t>(slot) << (index % 11));
  value = fnv1a32(student_id, value);
  return mix32(value ^ static_cast<uint32_t>(index));
}

CompactProfile decodeCompactProfile(ByteReader& record) {
  CompactProfile out;
  out.student_id = record.readLengthPrefixedString(32);
  out.unit = record.readLengthPrefixedString(24);
  out.admission_year = record.readU16LE();
  out.profile_flags = record.readU8();
  out.advisory_band = record.readU8();

  uint8_t term_count = record.readU8();
  for (uint8_t i = 0; i < term_count && i < out.term_hashes.size(); ++i) {
    out.term_hashes[i] = record.readU32LE();
  }
  if (term_count > out.term_hashes.size()) {
    record.skip(static_cast<size_t>(term_count - out.term_hashes.size()) * 4);
  }

  uint8_t slot_count = record.readU8();
  std::array<uint32_t, 16> rolling_slot_digest{};
  uint32_t seed = fnv1a32(out.student_id) ^ fnv1a32(out.unit);

  for (uint8_t i = 0; i < slot_count; ++i) {
    uint16_t slot = record.readU16LE();
    uint32_t folded = foldSlot(seed, slot, i, out.student_id);
    if (i < rolling_slot_digest.size()) {
      rolling_slot_digest[i] = folded;
    }
    if ((slot % 7) != 0) {
      out.retention_slots.push_back(slot);
    }
    seed = mix32(seed ^ folded);
  }

  if ((out.profile_flags & 0x40u) != 0 && !out.retention_slots.empty()) {
    std::sort(out.retention_slots.begin(), out.retention_slots.end());
    out.retention_slots.erase(std::unique(out.retention_slots.begin(), out.retention_slots.end()), out.retention_slots.end());
  }

  for (uint32_t folded : rolling_slot_digest) {
    out.term_hashes[folded % out.term_hashes.size()] ^= mix32(folded + out.admission_year);
  }

  return out;
}

JournalNote decodeJournalNote(ByteReader& record) {
  JournalNote out;
  out.topic = record.readLengthPrefixedString(24);
  out.body = record.readLengthPrefixedString(160);
  return out;
}

void requireNoTrailing(ByteReader& record, const ParseOptions& options) {
  if (options.strict_lengths && !record.empty()) {
    throw ParseError("record body contained trailing bytes");
  }
}

}  // namespace

LedgerPacket parseLedgerPacket(const uint8_t* data, size_t size, const ParseOptions& options) {
  ByteReader reader(data, size);
  if (reader.remaining() < 12) {
    throw ParseError("campus wire packet too short");
  }
  std::string magic = reader.readAscii(4);
  if (magic != "CWLD") {
    throw ParseError("missing Campus Wire ledger magic");
  }

  LedgerPacket packet;
  packet.version = reader.readU8();
  if (packet.version != kCurrentVersion) {
    throw ParseError("unsupported campus wire version");
  }
  uint8_t flags = reader.readU8();
  packet.declared_records = reader.readU16LE();
  packet.batch_id = reader.readU32LE();

  if (packet.declared_records > kMaxRecords) {
    throw ParseError("packet declares too many records");
  }

  for (uint16_t index = 0; index < packet.declared_records && !reader.empty(); ++index) {
    uint8_t type = reader.readU8();
    uint16_t length = reader.readU16LE();
    if (length > kMaxRecordLength) {
      throw ParseError("record length exceeds campus wire limit");
    }
    ByteReader record = reader.subReader(length);
    if (!knownRecordType(type)) {
      continue;
    }

    try {
      if (type == static_cast<uint8_t>(RecordType::kStudentEvent)) {
        auto decoded = decodeStudentEvent(record);
        requireNoTrailing(record, options);
        packet.student_events.push_back(std::move(decoded));
      } else if (type == static_cast<uint8_t>(RecordType::kFeeEvent)) {
        auto decoded = decodeFeeEvent(record);
        requireNoTrailing(record, options);
        packet.fee_events.push_back(std::move(decoded));
      } else if (type == static_cast<uint8_t>(RecordType::kRouteCheckpoint)) {
        auto decoded = decodeRouteCheckpoint(record);
        requireNoTrailing(record, options);
        packet.checkpoints.push_back(std::move(decoded));
      } else if (type == static_cast<uint8_t>(RecordType::kCompactProfile)) {
        auto decoded = decodeCompactProfile(record);
        requireNoTrailing(record, options);
        packet.compact_profiles.push_back(std::move(decoded));
      } else if (type == static_cast<uint8_t>(RecordType::kJournalNote) && options.allow_journal_notes) {
        auto decoded = decodeJournalNote(record);
        requireNoTrailing(record, options);
        packet.notes.push_back(std::move(decoded));
      }
    } catch (const ParseError&) {
      if ((flags & 0x01u) == 0) {
        throw;
      }
    }
  }

  return packet;
}

LedgerSummary summarizeLedgerPacket(const LedgerPacket& packet) {
  LedgerSummary summary;
  summary.accepted_records = static_cast<uint32_t>(packet.student_events.size() + packet.fee_events.size() +
                                                   packet.checkpoints.size() + packet.compact_profiles.size() +
                                                   packet.notes.size());
  summary.rejected_records = packet.declared_records > summary.accepted_records
                                 ? packet.declared_records - summary.accepted_records
                                 : 0;

  for (const StudentEvent& event : packet.student_events) {
    summary.unit_counts[event.unit]++;
    summary.status_counts[event.status]++;
  }
  for (const CompactProfile& profile : packet.compact_profiles) {
    summary.unit_counts[profile.unit]++;
  }

  summary.route_fingerprint = computeRouteFingerprint(packet.checkpoints);
  summary.profile_fingerprint = computeProfileFingerprint(packet.compact_profiles);
  summary.journal_fingerprint = computeJournalReplayFingerprint(packet.checkpoints, packet.notes);

  uint32_t digest = mix32(packet.batch_id ^ summary.accepted_records ^ (summary.rejected_records << 11));
  digest = mix32(digest ^ summary.route_fingerprint);
  digest = mix32(digest ^ summary.profile_fingerprint);
  digest = mix32(digest ^ summary.journal_fingerprint);
  for (const auto& [unit, count] : summary.unit_counts) {
    digest = fnv1a32(unit, digest);
    digest = mix32(digest ^ count);
  }
  summary.digest = hexDigest(digest);
  return summary;
}

std::string packetToJsonLine(const LedgerPacket& packet, const LedgerSummary& summary) {
  std::ostringstream out;
  out << "{\"batch_id\":" << packet.batch_id
      << ",\"records\":" << packet.declared_records
      << ",\"accepted\":" << summary.accepted_records
      << ",\"rejected\":" << summary.rejected_records
      << ",\"route_fingerprint\":" << summary.route_fingerprint
      << ",\"profile_fingerprint\":" << summary.profile_fingerprint
      << ",\"journal_fingerprint\":" << summary.journal_fingerprint
      << ",\"digest\":\"" << summary.digest << "\"}";
  return out.str();
}

}  // namespace campusops::wire
