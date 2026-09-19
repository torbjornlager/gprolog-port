#include "protocol.h"
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include "memory.h"

/* One supervised query lifetime. The HTTP controller owns admission and the
 * public protocol; this process owns worker budgets, pipes and cleanup. */
static volatile sig_atomic_t interrupted;
static pid_t child=-1;
static uint64_t memory_limit;
static void on_signal(int sig) { interrupted=sig; }
static long long now_ms(void) {
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC,&t)) { perror("clock_gettime"); exit(2); }
  return (long long)t.tv_sec*1000+t.tv_nsec/1000000;
}
static void reap(void) {
  if (child<=0) return;
  kill(child,SIGKILL);
  while (waitpid(child,NULL,0)<0 && errno==EINTR) {}
  child=-1;
}
static const char *memory_status(void) {
  uint64_t own,worker;
  if(!iso_memory_bytes(getpid(),&own))return "memory_monitor_failed";
  if(!iso_memory_bytes(child,&worker)) {
    /* A child which has already exited is not an accounting failure. Keeping
     * ownership until waitpid also prevents sampling a reused process ID. */
    int status;pid_t ended=waitpid(child,&status,WNOHANG);
    if(ended==child){child=-1;return NULL;}
    return "memory_monitor_failed";
  }
  return own>memory_limit || worker>memory_limit-own ? "memory_limit_exceeded" : NULL;
}
static void nonblock(int fd) {
  int flags=fcntl(fd,F_GETFL);
  if (flags<0 || fcntl(fd,F_SETFL,flags|O_NONBLOCK)<0) { perror("fcntl"); exit(2); }
}
/* Bound backpressure as well as computation. Never wait indefinitely for a
 * controller that stopped reading. No event can be guaranteed to a lost peer. */
static void event(const char *reason);
static int emit(const char *text,size_t n) {
  size_t original=n;
  long long end=now_ms()+1000;
  while (n && !interrupted) {
    /* Background RPC threads can allocate even while a controller is slow.
     * Once output is partial we can only close it, but still reclaim memory. */
    const char *memory_error=child>0?memory_status():NULL;
    if(memory_error){reap();if(n==original)event(memory_error);return 0;}
    ssize_t sent=write(STDOUT_FILENO,text,n);
    if (sent>0) { text+=sent;n-=(size_t)sent;continue; }
    if (sent<0 && errno!=EAGAIN && errno!=EINTR) return 0;
    if (now_ms()>=end) return 0;
    struct pollfd p={STDOUT_FILENO,POLLOUT,0};
    poll(&p,1,20);
  }
  return n==0;
}
static void event(const char *reason) {
  char line[160];
  int n=snprintf(line,sizeof line,"{\"type\":\"error\",\"term\":\"%s\"}\n",reason);
  emit(line,(size_t)n);
}
static long number(const char *s,long min,long max) {
  char *end;errno=0;long n=strtol(s,&end,10);
  if (errno || !*s || *end || n<min || n>max) {
    fprintf(stderr,"invalid limit: %s\n",s);exit(2);
  }
  return n;
}
static int continuation(const char *s,size_t n) {
  const char suffix[]=",\"more\":true}";
  return n>=sizeof suffix-1 && !memcmp(s+n-(sizeof suffix-1),suffix,sizeof suffix-1);
}
static int valid_event(const char *s,size_t n) {
  const char success[]="{\"type\":\"success\",\"answers\":[";
  const char error[]="{\"type\":\"error\",\"term\":";
  return n && s[n-1]=='}' &&
    (!strncmp(s,success,sizeof success-1) ||
     !strncmp(s,error,sizeof error-1) ||
     !strcmp(s,"{\"type\":\"failure\"}"));
}
int main(int argc,char **argv) {
  if (argc<3 || (argc-3)%2) {
    fprintf(stderr,"usage: %s 'query(Goal,Template)' PAGE_SIZE [--source FILE] [--shared-db FILE] "
      "[--time-ms N] [--idle-ms N] [--heap-kb N] [--memory-mb N] [--max-output N]\n",argv[0]);
    return 2;
  }
  number(argv[2],0,ISO_MAX_PAGE);
  long time_limit=1000,idle_limit=30000,heap=16384,max_output=1048576;
  memory_limit=(uint64_t)ISO_DEFAULT_MEMORY_MB*1024*1024;
  const char *source=NULL,*shared=NULL,*offset="0",*format="private";
  for (int i=3;i<argc;i+=2) {
    if (!strcmp(argv[i],"--source")) source=argv[i+1];
    else if (!strcmp(argv[i],"--shared-db")) shared=argv[i+1];
    else if (!strcmp(argv[i],"--offset")) { number(argv[i+1],0,1000000000);offset=argv[i+1]; }
    else if (!strcmp(argv[i],"--format")) {
      format=argv[i+1];if (strcmp(format,"json") && strcmp(format,"prolog") && strcmp(format,"private")) return 2;
    }
    else if (!strcmp(argv[i],"--time-ms")) time_limit=number(argv[i+1],1,3600000);
    else if (!strcmp(argv[i],"--idle-ms")) idle_limit=number(argv[i+1],1,3600000);
    else if (!strcmp(argv[i],"--heap-kb")) heap=number(argv[i+1],64,1048576);
    else if (!strcmp(argv[i],"--memory-mb")) memory_limit=(uint64_t)number(argv[i+1],1,ISO_MAX_MEMORY_MB)*1024*1024;
    else if (!strcmp(argv[i],"--max-output")) max_output=number(argv[i+1],64,16777216);
    else { fprintf(stderr,"unknown option: %s\n",argv[i]);return 2; }
  }
  char worker[PATH_MAX];
  if (strlen(argv[0])+14>=sizeof worker) return 2;
  strcpy(worker,argv[0]);char *slash=strrchr(worker,'/');
  if (slash) strcpy(slash+1,"query-worker"); else strcpy(worker,"./query-worker");
  int commands[2],answers[2],diagnostics[2];
  if (pipe(commands)||pipe(answers)||pipe(diagnostics)) { perror("pipe");return 2; }
  signal(SIGPIPE,SIG_IGN);
  struct sigaction sa;memset(&sa,0,sizeof sa);sa.sa_handler=on_signal;
  sigaction(SIGTERM,&sa,NULL);sigaction(SIGINT,&sa,NULL);
  atexit(reap);
  child=fork();
  if (child<0) { perror("fork");return 2; }
  if (!child) {
    signal(SIGTERM,SIG_DFL);signal(SIGINT,SIG_DFL);
    if (dup2(commands[0],STDIN_FILENO)<0 || dup2(answers[1],STDOUT_FILENO)<0 ||
        dup2(diagnostics[1],STDERR_FILENO)<0) _exit(126);
    close(commands[0]);close(commands[1]);close(answers[0]);close(answers[1]);
    close(diagnostics[0]);close(diagnostics[1]);
    char size[32];snprintf(size,sizeof size,"%ld",heap);
    if (!strcmp(format,"json")) setenv("ISO_JSON_BINDINGS","1",1);
    else unsetenv("ISO_JSON_BINDINGS");
    if (!strcmp(format,"prolog")) setenv("ISO_PROLOG_DISPLAY","1",1);
    else unsetenv("ISO_PROLOG_DISPLAY");
    setenv("ISO_OFFSET",offset,1);
    if(shared)setenv("ISO_SHARED_DB",shared,1);
    else unsetenv("ISO_SHARED_DB");
    if (setenv("GLOBALSZ",size,1) || setenv("LOCALSZ","8192",1) ||
        setenv("TRAILSZ","4096",1) || setenv("CSTRSZ","4096",1)) _exit(126);
    struct rlimit core={0,0};if (setrlimit(RLIMIT_CORE,&core)) _exit(126);
    if (source) execl(worker,worker,argv[1],argv[2],"--source",source,(char *)NULL);
    else execl(worker,worker,argv[1],argv[2],(char *)NULL);
    _exit(127);
  }
  close(commands[0]);close(answers[1]);close(diagnostics[1]);
  nonblock(STDIN_FILENO);nonblock(STDOUT_FILENO);
  nonblock(answers[0]);nonblock(diagnostics[0]);
  char *frame=malloc((size_t)max_output+2);
  if (!frame) { perror("malloc");return 2; }
  size_t used=0,command_used=0;
  char command[32];int active=1,done=0,diagnostic_open=1;
  long long remaining=time_limit,started=now_ms(),idle_started=0;
  while (!done && !interrupted) {
    const char *memory_error=child>0?memory_status():NULL;
    if(memory_error){reap();event(memory_error);break;}
    long long left=active ? remaining-(now_ms()-started) : idle_limit-(now_ms()-idle_started);
    if (left<=0) { event(active?"time_limit_exceeded":"continuation_expired");break; }
    struct pollfd p[3]={{answers[0],POLLIN,0},{STDIN_FILENO,POLLIN,0},
                       {diagnostic_open?diagnostics[0]:-1,POLLIN,0}};
    int rc=poll(p,3,left>ISO_MEMORY_POLL_MS?ISO_MEMORY_POLL_MS:(int)left);
    if (rc<0) { if (errno==EINTR) continue;event("supervisor_io_error");break; }
    /* Consume a full response before commands that arrived at the same time. */
    if (p[0].revents) {
      char buf[4096];ssize_t n=read(answers[0],buf,sizeof buf);
      if (n==0) { event("worker_exit");break; }
      if (n<0 && errno!=EAGAIN && errno!=EINTR) { event("worker_io_error");break; }
      for (ssize_t i=0;i<n && !done;i++) {
        if (used>=(size_t)max_output) { event("output_limit_exceeded");done=1;break; }
        if (buf[i]=='\n') {
          frame[used]=0;
          if (!active || !valid_event(frame,used)) { event("worker_protocol_error");done=1;break; }
          int more=continuation(frame,used);
          memory_error=child>0?memory_status():NULL;
          if(memory_error){reap();event(memory_error);done=1;break;}
          remaining-=now_ms()-started;
          if (remaining<=0) { event("time_limit_exceeded");done=1;break; }
          frame[used++]='\n';
          if (!emit(frame,used)) { done=1;break; }
          used=0;active=0;idle_started=now_ms();
          if (!more) done=1;
        } else frame[used++]=buf[i];
      }
    }
    if (!done && p[1].revents) {
      /* Byte-at-a-time commands avoid consuming unbounded controller input. */
      char c;ssize_t n=read(STDIN_FILENO,&c,1);
      if (n==0) { event("controller_disconnected");break; }
      if (n<0 && errno!=EAGAIN && errno!=EINTR) { event("controller_io_error");break; }
      if (n>0) {
        if (command_used>=sizeof command-1) { event("protocol_error");break; }
        if (c=='\n') {
          command[command_used]=0;command_used=0;
          if (!strcmp(command,"stop")) { event("cancelled");break; }
          if (active || (strcmp(command,"next") && strncmp(command,"next ",5))) {
            event("protocol_error");break;
          }
          if (!strncmp(command,"next ",5)) {
            char *end;errno=0;long size=strtol(command+5,&end,10);
            if (errno || *end || size<0 || size>ISO_MAX_PAGE) { event("protocol_error");break; }
          }
          size_t length=strlen(command);command[length++]='\n';
          if (write(commands[1],command,length)!=(ssize_t)length) { event("worker_exit");break; }
          active=1;started=now_ms();
        } else command[command_used++]=c;
      }
    }
    if (p[2].revents) {
      char discard[4096];ssize_t n=read(diagnostics[0],discard,sizeof discard);
      if (!n) { close(diagnostics[0]);diagnostic_open=0; }
      /* Runtime diagnostics are drained but cannot become wire events. */
    }
  }
  close(commands[1]);close(answers[0]);if (diagnostic_open) close(diagnostics[0]);
  free(frame);reap();
  return interrupted?128+interrupted:0;
}
