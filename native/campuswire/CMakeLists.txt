cmake_minimum_required(VERSION 3.16)
project(campuswire LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_library(campuswire
  src/byte_reader.cc
  src/ledger.cc
  src/router.cc
)
target_include_directories(campuswire PUBLIC include)
add_executable(dump_campus_packet tools/dump_campus_packet.cc)
target_link_libraries(dump_campus_packet PRIVATE campuswire)
