#ifndef ISO_MEMORY_H
#define ISO_MEMORY_H
#include <stdint.h>
#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>
#include "protocol.h"
#if defined(__APPLE__)
#include <libproc.h>
#include <sys/resource.h>
#endif

#define ISO_MEMORY_POLL_MS 50

/* Current usage, not peak usage or virtual address space. Fail closed when
 * accounting is unavailable. The Linux fallback is RSS, not macOS footprint. */
static int iso_memory_bytes(pid_t pid,uint64_t *bytes) {
#if defined(__APPLE__)
  struct rusage_info_v2 usage;
  if(proc_pid_rusage(pid,RUSAGE_INFO_V2,(rusage_info_t *)&usage))return 0;
  *bytes=usage.ri_phys_footprint;return 1;
#elif defined(__linux__)
  char path[64];snprintf(path,sizeof path,"/proc/%ld/statm",(long)pid);
  FILE *f=fopen(path,"r");if(!f)return 0;
  unsigned long long total,resident;
  int ok=fscanf(f,"%llu %llu",&total,&resident)==2;fclose(f);
  long page=sysconf(_SC_PAGESIZE);
  if(!ok||page<=0||resident>UINT64_MAX/(uint64_t)page)return 0;
  *bytes=(uint64_t)resident*(uint64_t)page;return 1;
#else
  (void)pid;(void)bytes;return 0;
#endif
}
#endif
