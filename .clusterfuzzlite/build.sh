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

# BEGIN campus deep replay buglab harnesses
mkdir -p "$OUT"
$CXX $CXXFLAGS -std=c++17 -I"$SRC/native/campuswire/include" "$SRC/fuzz/campus_deep_route_fuzzer.cc" "$SRC/native/campuswire/src/deep_replay_lab.cc" $LIB_FUZZING_ENGINE -o "$OUT/campus_deep_route_fuzzer"
$CXX $CXXFLAGS -std=c++17 -I"$SRC/native/campuswire/include" "$SRC/fuzz/campus_deep_snapshot_fuzzer.cc" "$SRC/native/campuswire/src/deep_replay_lab.cc" $LIB_FUZZING_ENGINE -o "$OUT/campus_deep_snapshot_fuzzer"
$CXX $CXXFLAGS -std=c++17 -I"$SRC/native/campuswire/include" "$SRC/fuzz/campus_deep_batch_fuzzer.cc" "$SRC/native/campuswire/src/deep_replay_lab.cc" $LIB_FUZZING_ENGINE -o "$OUT/campus_deep_batch_fuzzer"
$CXX $CXXFLAGS -std=c++17 -I"$SRC/native/campuswire/include" "$SRC/fuzz/campus_deep_profile_fuzzer.cc" "$SRC/native/campuswire/src/deep_replay_lab.cc" $LIB_FUZZING_ENGINE -o "$OUT/campus_deep_profile_fuzzer"
$CXX $CXXFLAGS -std=c++17 -I"$SRC/native/campuswire/include" "$SRC/fuzz/campus_deep_auth_fuzzer.cc" "$SRC/native/campuswire/src/deep_replay_lab.cc" $LIB_FUZZING_ENGINE -o "$OUT/campus_deep_auth_fuzzer"
$CXX $CXXFLAGS -std=c++17 -I"$SRC/native/campuswire/include" "$SRC/fuzz/campus_deep_compaction_fuzzer.cc" "$SRC/native/campuswire/src/deep_replay_lab.cc" $LIB_FUZZING_ENGINE -o "$OUT/campus_deep_compaction_fuzzer"
$CXX $CXXFLAGS -std=c++17 -I"$SRC/native/campuswire/include" "$SRC/fuzz/campus_deep_rollback_fuzzer.cc" "$SRC/native/campuswire/src/deep_replay_lab.cc" $LIB_FUZZING_ENGINE -o "$OUT/campus_deep_rollback_fuzzer"
$CXX $CXXFLAGS -std=c++17 -I"$SRC/native/campuswire/include" "$SRC/fuzz/campus_deep_checkpoint_fuzzer.cc" "$SRC/native/campuswire/src/deep_replay_lab.cc" $LIB_FUZZING_ENGINE -o "$OUT/campus_deep_checkpoint_fuzzer"
$CXX $CXXFLAGS -std=c++17 -I"$SRC/native/campuswire/include" "$SRC/fuzz/campus_deep_archive_fuzzer.cc" "$SRC/native/campuswire/src/deep_replay_lab.cc" $LIB_FUZZING_ENGINE -o "$OUT/campus_deep_archive_fuzzer"
$CXX $CXXFLAGS -std=c++17 -I"$SRC/native/campuswire/include" "$SRC/fuzz/campus_deep_tenant_fuzzer.cc" "$SRC/native/campuswire/src/deep_replay_lab.cc" $LIB_FUZZING_ENGINE -o "$OUT/campus_deep_tenant_fuzzer"
$CXX $CXXFLAGS -std=c++17 -I"$SRC/native/campuswire/include" "$SRC/fuzz/campus_deep_replay_window_fuzzer.cc" "$SRC/native/campuswire/src/deep_replay_lab.cc" $LIB_FUZZING_ENGINE -o "$OUT/campus_deep_replay_window_fuzzer"
$CXX $CXXFLAGS -std=c++17 -I"$SRC/native/campuswire/include" "$SRC/fuzz/campus_deep_delta_merge_fuzzer.cc" "$SRC/native/campuswire/src/deep_replay_lab.cc" $LIB_FUZZING_ENGINE -o "$OUT/campus_deep_delta_merge_fuzzer"
# END campus deep replay buglab harnesses
