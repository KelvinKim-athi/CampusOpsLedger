#pragma once

#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace campusops::wire {

class ParseError : public std::runtime_error {
 public:
  explicit ParseError(const std::string& message) : std::runtime_error(message) {}
};

class ByteReader {
 public:
  ByteReader(const uint8_t* data, size_t size);

  size_t position() const;
  size_t remaining() const;
  bool empty() const;

  uint8_t readU8();
  uint16_t readU16LE();
  uint32_t readU32LE();
  uint64_t readU64LE();
  std::vector<uint8_t> readBytes(size_t count);
  std::string readAscii(size_t count);
  std::string readLengthPrefixedString(uint8_t max_len);
  ByteReader subReader(size_t count);
  void skip(size_t count);

 private:
  const uint8_t* data_;
  size_t size_;
  size_t cursor_;

  void require(size_t count) const;
};

uint32_t fnv1a32(std::string_view text, uint32_t seed = 2166136261u);
uint32_t mix32(uint32_t value);
std::string hexDigest(uint32_t value);

}  // namespace campusops::wire
