#ifndef ISO_PROCESS_SECURITY_H
#define ISO_PROCESS_SECURITY_H
#include <sys/resource.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif
/* Set both limits before loading secrets or starting Prolog. */
static inline int iso_disable_dumps(void) {
  struct rlimit core={0,0};
  if(setrlimit(RLIMIT_CORE,&core))return 0;
#ifdef __linux__
  if(prctl(PR_SET_DUMPABLE,0,0,0,0))return 0;
#endif
  return 1;
}
#endif
