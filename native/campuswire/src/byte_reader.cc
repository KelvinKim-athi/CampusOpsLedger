#include "campuswire/byte_reader.h"

#include <algorithm>
#include <iomanip>
#include <sstream>

namespace campusops::wire {

ByteReader::ByteReader(const uint8_t* data, size_t size) : data_(data), size_(size), cursor_(0) {}

size_t ByteReader::position() const { return cursor_; }
size_t ByteReader::remaining() const { return size_ - cursor_; }
bool ByteReader::empty() const { return remaining() == 0; }

void ByteReader::require(size_t count) const {
  if (count > remaining()) {
    throw ParseError("campus wire packet ended before requested field was available");
  }
}

uint8_t ByteReader::readU8() {
  require(1);
  return data_[cursor_++];
}

uint16_t ByteReader::readU16LE() {
  require(2);
  uint16_t value = static_cast<uint16_t>(data_[cursor_]) |
                   static_cast<uint16_t>(data_[cursor_ + 1]) << 8;
  cursor_ += 2;
  return value;
}

uint32_t ByteReader::readU32LE() {
  require(4);
  uint32_t value = static_cast<uint32_t>(data_[cursor_]) |
                   static_cast<uint32_t>(data_[cursor_ + 1]) << 8 |
                   static_cast<uint32_t>(data_[cursor_ + 2]) << 16 |
                   static_cast<uint32_t>(data_[cursor_ + 3]) << 24;
  cursor_ += 4;
  return value;
}

uint64_t ByteReader::readU64LE() {
  uint64_t lo = readU32LE();
  uint64_t hi = readU32LE();
  return lo | (hi << 32);
}

std::vector<uint8_t> ByteReader::readBytes(size_t count) {
  require(count);
  std::vector<uint8_t> out(data_ + cursor_, data_ + cursor_ + count);
  cursor_ += count;
  return out;
}

std::string ByteReader::readAscii(size_t count) {
  require(count);
  std::string out(reinterpret_cast<const char*>(data_ + cursor_), count);
  cursor_ += count;
  for (char& c : out) {
    unsigned char uc = static_cast<unsigned char>(c);
    if (uc < 0x20 || uc > 0x7e) {
      c = '_';
    }
  }
  return out;
}

std::string ByteReader::readLengthPrefixedString(uint8_t max_len) {
  uint8_t length = readU8();
  if (length > max_len) {
    throw ParseError("length-prefixed string exceeds campus wire limit");
  }
  return readAscii(length);
}

ByteReader ByteReader::subReader(size_t count) {
  require(count);
  ByteReader sub(data_ + cursor_, count);
  cursor_ += count;
  return sub;
}

void ByteReader::skip(size_t count) {
  require(count);
  cursor_ += count;
}

uint32_t fnv1a32(std::string_view text, uint32_t seed) {
  uint32_t hash = seed;
  for (unsigned char c : text) {
    hash ^= c;
    hash *= 16777619u;
  }
  return hash;
}

uint32_t mix32(uint32_t value) {
  value ^= value >> 16;
  value *= 0x7feb352du;
  value ^= value >> 15;
  value *= 0x846ca68bu;
  value ^= value >> 16;
  return value;
}

std::string hexDigest(uint32_t value) {
  std::ostringstream out;
  out << std::hex << std::setw(8) << std::setfill('0') << value;
  return out.str();
}

}  // namespace campusops::wire
