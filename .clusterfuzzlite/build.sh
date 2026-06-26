#!/bin/bash -eu

: "${SRC:=$(pwd)}"
: "${OUT:=$SRC/out}"
: "${CXX:=g++}"

mkdir -p "$OUT" /tmp/campuswire-build

COMMON_FLAGS="${CXXFLAGS:-} -std=c++17 -I$SRC/native/campuswire/include -Wall -Wextra -O1 -g"
ENGINE="${LIB_FUZZING_ENGINE:-}"
STANDALONE=""
if [ -z "$ENGINE" ]; then
  STANDALONE="-DFUZZ_STANDALONE"
fi

$CXX $COMMON_FLAGS -c "$SRC/native/campuswire/src/byte_reader.cc" -o /tmp/campuswire-build/byte_reader.o
$CXX $COMMON_FLAGS -c "$SRC/native/campuswire/src/router.cc" -o /tmp/campuswire-build/router.o
$CXX $COMMON_FLAGS -c "$SRC/native/campuswire/src/ledger.cc" -o /tmp/campuswire-build/ledger.o

$CXX $COMMON_FLAGS $STANDALONE \
  "$SRC/fuzz/campus_packet_fuzzer.cc" \
  /tmp/campuswire-build/byte_reader.o \
  /tmp/campuswire-build/router.o \
  /tmp/campuswire-build/ledger.o \
  $ENGINE \
  -o "$OUT/campus_packet_fuzzer"

$CXX $COMMON_FLAGS $STANDALONE \
  "$SRC/fuzz/campus_journal_fuzzer.cc" \
  /tmp/campuswire-build/byte_reader.o \
  /tmp/campuswire-build/router.o \
  /tmp/campuswire-build/ledger.o \
  $ENGINE \
  -o "$OUT/campus_journal_fuzzer"
