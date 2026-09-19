#ifndef ISO_PROTOCOL_H
#define ISO_PROTOCOL_H
/* Match the demonstrator's RPC default. No buffer is allocated by answer count;
 * supervisor byte/stack/time bounds still limit the actual computation. */
#define ISO_MAX_PAGE 10000000000L
#define ISO_DEFAULT_MEMORY_MB 256
#define ISO_MAX_MEMORY_MB 1048576
#define ISO_DEFAULT_TOTAL_MEMORY_MB 1024
#define ISO_ADMISSION_MEMORY_MB 16
#endif
