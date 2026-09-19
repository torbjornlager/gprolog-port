#ifndef ISO_MEMORY_TREE_H
#define ISO_MEMORY_TREE_H
#include "memory.h"
#include <errno.h>
#include <string.h>
#if defined(__APPLE__)
#include <sys/proc.h>
#endif

/* 1 = live and still owned, 0 = exited/reparented, -1 = accounting failure.
 * Checking ownership around sampling avoids charging a recycled worker PID. */
static int iso_owned_process(pid_t pid,pid_t parent) {
#if defined(__APPLE__)
  struct proc_bsdinfo info;errno=0;
  int n=proc_pidinfo(pid,PROC_PIDTBSDINFO,0,&info,sizeof info);
  if(n!=(int)sizeof info)return errno==ESRCH||errno==ENOENT?0:-1;
  return info.pbi_ppid==(uint32_t)parent && info.pbi_status!=SZOMB;
#elif defined(__linux__)
  char path[64],line[4096];snprintf(path,sizeof path,"/proc/%ld/stat",(long)pid);
  FILE *f=fopen(path,"r");if(!f)return errno==ENOENT?0:-1;
  int ok=fgets(line,sizeof line,f)!=NULL;fclose(f);
  char *end=ok?strrchr(line,')'):NULL,state;long owner;
  if(!end||sscanf(end+1," %c %ld",&state,&owner)!=2)return -1;
  return owner==(long)parent && state!='Z' && state!='X';
#else
  (void)pid;(void)parent;return -1;
#endif
}
static int iso_owned_memory(pid_t pid,pid_t parent,uint64_t *bytes) {
  *bytes=0;
  int live=iso_owned_process(pid,parent);if(live<=0)return live==0;
  uint64_t measured=0;int ok=iso_memory_bytes(pid,&measured);
  live=iso_owned_process(pid,parent);
  if(live==0)return 1;
  if(live<0||!ok)return 0;
  *bytes=measured;return 1;
}
/* The trusted supervisor forks one worker. Spare entries tolerate process
 * exit races; an unexpected fan-out fails closed instead of undercounting. */
static int iso_query_memory(pid_t supervisor,uint64_t *bytes) {
  if(!iso_owned_memory(supervisor,getpid(),bytes))return 0;
  int live=iso_owned_process(supervisor,getpid());if(live<=0)return live==0;
  pid_t children[16];int count=0;
#if defined(__APPLE__)
  errno=0;int n=proc_listchildpids(supervisor,children,sizeof children);
  /* Unlike proc_listpids, this convenience API returns a PID count. */
  if(n<0||n>=16||(n==0&&errno&&errno!=ESRCH))return 0;
  count=n;
#elif defined(__linux__)
  char path[96];snprintf(path,sizeof path,"/proc/%ld/task/%ld/children",(long)supervisor,(long)supervisor);
  FILE *f=fopen(path,"r");
  if(!f)return iso_owned_process(supervisor,getpid())==0;
  long pid;int rc;
  while((rc=fscanf(f,"%ld",&pid))==1 && count<16)children[count++]=(pid_t)pid;
  int ok=rc==EOF&&!ferror(f)&&count<16;fclose(f);if(!ok)return 0;
#else
  return 0;
#endif
  for(int i=0;i<count;i++) {
    uint64_t memory;
    if(!iso_owned_memory(children[i],supervisor,&memory)||memory>UINT64_MAX-*bytes)return 0;
    *bytes+=memory;
  }
  return 1;
}
#endif
