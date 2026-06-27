#pragma once

#include <cstddef>
#include <cstdint>

namespace campusops::wire {

uint32_t driveRouteCheckpointPath(const uint8_t* data, size_t size);
uint32_t driveSnapshotImportPath(const uint8_t* data, size_t size);
uint32_t driveBatchReplayPath(const uint8_t* data, size_t size);
uint32_t driveProfileDecodePath(const uint8_t* data, size_t size);
uint32_t driveAuthFramePath(const uint8_t* data, size_t size);
uint32_t driveCompactionPath(const uint8_t* data, size_t size);
uint32_t driveRollbackPath(const uint8_t* data, size_t size);
uint32_t driveCheckpointCachePath(const uint8_t* data, size_t size);
uint32_t driveArchiveReplayPath(const uint8_t* data, size_t size);
uint32_t driveTenantIndexPath(const uint8_t* data, size_t size);
uint32_t driveReplayWindowPath(const uint8_t* data, size_t size);
uint32_t driveDeltaMergePath(const uint8_t* data, size_t size);

}  // namespace campusops::wire
