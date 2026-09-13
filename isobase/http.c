#include "protocol.h"
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <math.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
extern char **environ;
#define MAX_QUERIES 32
#define MAX_CLIENTS 32
#define REQUEST_CAP 262144
#define RESPONSE_CAP 1048576
#define CONNECTION_IDLE_MS 10000
#define HEADER_READ_MS 2000

typedef struct { pid_t pid; int in,out,busy; long offset; long long expires; unsigned long long cached_order; char *key; char source[PATH_MAX]; } Query;
typedef struct { char *goal,*template,*source,*format; long offset,limit; int once,timeout; } Request;
static Query queries[MAX_QUERIES];
/* Updated under mutex whenever a continuation is inserted/reinserted. */
static unsigned long long cache_order;
static pthread_mutex_t mutex=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t drained=PTHREAD_COND_INITIALIZER;
static int clients[MAX_CLIENTS],client_count,max_queries=8,time_ms=1000,idle_ms=30000;
static volatile sig_atomic_t stopping;
static char supervisor[PATH_MAX],directory[PATH_MAX],shared_snapshot[PATH_MAX];
static void stop(int sig) { (void)sig;stopping=1; }
static long long now(void) { struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (long long)t.tv_sec*1000+t.tv_nsec/1000000; }
static void cloexec(int fd) { fcntl(fd,F_SETFD,FD_CLOEXEC); }
static int write_all(int fd,const char *s,size_t n) {
  while(n) { ssize_t k=write(fd,s,n);if(k<0 && errno==EINTR)continue;if(k<=0)return 0;s+=k;n-=(size_t)k; }return 1;
}
static void cleanup_directory(void) {
  if(*shared_snapshot)unlink(shared_snapshot);
  if(*directory)rmdir(directory);
}
static int snapshot_shared(const char *path) {
  int input=open(path,O_RDONLY|O_NONBLOCK);
  if(input<0)return 0;
  struct stat info;
  if(fstat(input,&info)||!S_ISREG(info.st_mode)||info.st_size>RESPONSE_CAP) {
    close(input);return 0;
  }
  snprintf(shared_snapshot,sizeof shared_snapshot,"%s/shared-XXXXXX",directory);
  int output=mkstemp(shared_snapshot);
  if(output<0){close(input);shared_snapshot[0]=0;return 0;}
  size_t total=0;int good=1;char bytes[8192];
  for(;;) {
    ssize_t n=read(input,bytes,sizeof bytes);
    if(n<0&&errno==EINTR)continue;
    if(n==0)break;
    if(n<0){good=0;break;}
    total+=(size_t)n;
    if(total>RESPONSE_CAP||memchr(bytes,0,(size_t)n)||!write_all(output,bytes,(size_t)n)) {
      good=0;break;
    }
  }
  close(input);if(close(output))good=0;
  return good;
}
static void finish_rejected_request(int fd) {
  /* Closing with unread request bytes can reset the connection and discard
   * the error body. Send FIN first, then perform a strictly bounded drain. */
  shutdown(fd,SHUT_WR);
  long long end=now()+100;
  size_t drained=0;
  char discard[4096];
  while(drained<REQUEST_CAP&&!stopping) {
    long long left=end-now();if(left<=0)break;
    struct pollfd p={fd,POLLIN,0};
    int status=poll(&p,1,(int)left);
    if(status<0&&errno==EINTR)continue;
    if(status<=0)break;
    ssize_t n=recv(fd,discard,sizeof discard,MSG_DONTWAIT);
    if(n<0&&(errno==EAGAIN||errno==EINTR))continue;
    if(n<=0)break;
    drained+=(size_t)n;
  }
}
/* Called with the registry lock, never while another thread owns this slot. */
static void release(Query *q) {
  if(!q->pid)return;
  close(q->in);close(q->out);kill(q->pid,SIGTERM);
  while(waitpid(q->pid,NULL,0)<0 && errno==EINTR){}
  if(*q->source)unlink(q->source);
  free(q->key);memset(q,0,sizeof *q);
}
static void reply(int fd,int code,const char *format,const char *body) {
  char h[512];int n=snprintf(h,sizeof h,"HTTP/1.1 %d %s\r\nContent-Type: %s; charset=UTF-8\r\nContent-Length: %zu\r\nConnection: close\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n\r\n",code,code==200?"OK":code==503?"Service Unavailable":code==404?"Not Found":code==405?"Method Not Allowed":code==408?"Request Timeout":code==431?"Request Header Fields Too Large":"Bad Request",!strcmp(format,"prolog")?"text/plain":"application/json",strlen(body));
  if(write_all(fd,h,(size_t)n))write_all(fd,body,strlen(body));
}
static void error_reply(int fd,int code,const char *format,const char *reason) {
  char b[256];if(!strcmp(format,"prolog"))snprintf(b,sizeof b,"error(%s).\n",reason);
  else snprintf(b,sizeof b,"{\"type\":\"error\",\"data\":\"%s\"}\n",reason);
  reply(fd,code,format,b);
}
static int hex(char c) { if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1; }
static char *decode(const char *s) {
  char *v=malloc(strlen(s)+1),*p=v;if(!v)return NULL;
  for(;*s;s++) { unsigned char c=(unsigned char)*s;
    if(c=='%') { if(!s[1]||!s[2]||hex(s[1])<0||hex(s[2])<0){free(v);return NULL;}c=(unsigned char)(hex(s[1])*16+hex(s[2]));s+=2; }
    else if(c=='+')c=' ';
    if(!c){free(v);return NULL;}*p++=(char)c;
  }*p=0;return v;
}
static int integer(const char *s,long min,long max,long *v) {
  char *e;errno=0;long n=strtol(s,&e,10);if(errno||!*s||*e||n<min||n>max)return 0;*v=n;return 1;
}
static void free_request(Request *r) { free(r->goal);free(r->template);free(r->source);free(r->format); }
static int parameters(char *s,Request *r) {
  memset(r,0,sizeof *r);r->limit=ISO_MAX_PAGE;r->timeout=time_ms;
  unsigned seen=0;char *save=NULL;
  for(char *part=strtok_r(s,"&",&save);part;part=strtok_r(NULL,"&",&save)) {
    char *eq=strchr(part,'=');if(!eq)return 0;*eq++=0;
    char *name=decode(part),*v=decode(eq);if(!name||!v){free(name);free(v);return 0;}
    const char *names[]={"goal","template","src_text","format","offset","limit","once","timeout"};
    unsigned i;for(i=0;i<8;i++)if(!strcmp(name,names[i]))break;free(name);
    if(i==8 || (seen&(1u<<i))){free(v);return 0;}seen|=1u<<i;
    long n=0;int good=1;
    switch(i) {
      case 0:r->goal=v;v=NULL;break;
      case 1:r->template=v;v=NULL;break;
      case 2:r->source=v;v=NULL;break;
      case 3:r->format=v;v=NULL;break;
      case 4:good=integer(v,0,1000000000,&r->offset);break;
      case 5:good=integer(v,0,ISO_MAX_PAGE,&r->limit);break;
      case 6:good=!strcmp(v,"true")||!strcmp(v,"false");r->once=!strcmp(v,"true");break;
      case 7:{char *end;errno=0;double t=strtod(v,&end);good=!errno&&*v&&!*end&&isfinite(t)&&t>0;
        if(good && t*1000<time_ms){n=(long)ceil(t*1000);r->timeout=(int)n;}break;}
    }free(v);if(!good)return 0;
  }
  if(!r->format)r->format=strdup("json");
  if(!r->source)r->source=strdup("");
  if(!r->template && r->goal)r->template=strdup(r->goal);
  return r->goal&&*r->goal&&r->template&&r->source&&r->format&&
         (!strcmp(r->format,"json")||!strcmp(r->format,"prolog"));
}
static char *key_for(Request *r) {
  char *key=NULL;
  if(asprintf(&key,"%zu:%s%zu:%s%zu:%s%s:%d",strlen(r->goal),r->goal,strlen(r->template),r->template,strlen(r->source),r->source,r->format,r->once)<0)return NULL;
  return key;
}
static int start_query(Query *q,Request *r,char *key) {
  int in[2],out[2];if(pipe(in))return 0;
  if(pipe(out)){close(in[0]);close(in[1]);return 0;}
  cloexec(in[0]);cloexec(in[1]);cloexec(out[0]);cloexec(out[1]);
  q->source[0]=0;
  if(*r->source) {
    snprintf(q->source,sizeof q->source,"%s/source-XXXXXX",directory);
    int fd=mkstemp(q->source);
    if(fd<0 || !write_all(fd,r->source,strlen(r->source))) { if(fd>=0)close(fd);goto failed; }
    close(fd);
  }
  char *term=NULL;if(asprintf(&term,"query((%s),(%s))",r->goal,r->template)<0)goto failed;
  char limit[32],offset[32],budget[32],idle[32];
  snprintf(limit,sizeof limit,"%ld",r->limit);snprintf(offset,sizeof offset,"%ld",r->offset);
  snprintf(budget,sizeof budget,"%d",time_ms);snprintf(idle,sizeof idle,"%d",idle_ms+250);
  char *args[]={supervisor,term,limit,"--offset",offset,"--format",r->format,"--time-ms",budget,"--idle-ms",idle,NULL,NULL,NULL,NULL,NULL};
  int next=11;
  if(*r->source){args[next++]="--source";args[next++]=q->source;}
  if(*shared_snapshot){args[next++]="--shared-db";args[next++]=shared_snapshot;}
  args[next]=NULL;
  posix_spawn_file_actions_t a;posix_spawn_file_actions_init(&a);
  posix_spawn_file_actions_adddup2(&a,in[0],0);posix_spawn_file_actions_adddup2(&a,out[1],1);
  posix_spawn_file_actions_addopen(&a,2,"/dev/null",O_WRONLY,0);
  int status=posix_spawn(&q->pid,supervisor,&a,NULL,args,environ);
  posix_spawn_file_actions_destroy(&a);free(term);
  if(status){q->pid=0;goto failed;}
  close(in[0]);close(out[1]);q->in=in[1];q->out=out[0];q->key=key;q->busy=1;return 1;
failed:
  close(in[0]);close(in[1]);close(out[0]);close(out[1]);if(*q->source)unlink(q->source);q->source[0]=0;return 0;
}
static int validate_shared(void) {
  Request r={.goal="true",.template="ok",.source="",.format="prolog",.limit=1};
  Query check={0};char *key=strdup("startup-validation");
  if(!key)return 0;
  if(!start_query(&check,&r,key)){free(key);return 0;}
  char result[2048];size_t used=0;long long end=now()+time_ms+1000;
  while(used<sizeof result-1&&!stopping) {
    long long left=end-now();if(left<=0)break;
    struct pollfd p={check.out,POLLIN,0};int status=poll(&p,1,(int)left);
    if(status<0&&errno==EINTR)continue;
    if(status<=0)break;
    ssize_t n=read(check.out,result+used,sizeof result-1-used);
    if(n<=0)break;
    used+=(size_t)n;if(memchr(result,'\n',used))break;
  }
  result[used]=0;
  int good=!strcmp(result,"{\"type\":\"success\",\"answers\":[\"ok\"],\"more\":false}\n");
  if(!good)fprintf(stderr,"Shared database validation failed: %s\n",used?result:"no worker response");
  release(&check);return good;
}
/* JSON strings in the private protocol only use escapes emitted by worker.c. */
static char *json_text(const char **p) {
  if(*(*p)++!='"')return NULL;
  char *s=malloc(strlen(*p)+1),*o=s;if(!s)return NULL;
  while(**p && **p!='"') { unsigned char c=(unsigned char)*(*p)++;
    if(c=='\\') { c=(unsigned char)*(*p)++;
      if(c=='u'){if(strlen(*p)<4||(*p)[0]!='0'||(*p)[1]!='0'||hex((*p)[2])<0||hex((*p)[3])<0){free(s);return NULL;}c=(unsigned char)(hex((*p)[2])*16+hex((*p)[3]));*p+=4;}
      else if(c!='"'&&c!='\\'){free(s);return NULL;}
    }*o++=(char)c;
  }
  if(**p!='"'){free(s);return NULL;}(*p)++;*o=0;return s;
}
static char *public_body(char *line,const char *format,int once,int *more) {
  const char *success="{\"type\":\"success\",\"answers\":[",*error="{\"type\":\"error\",\"term\":";
  size_t n=strlen(line);const char suffix[]=",\"more\":true}";
  *more=n>=sizeof suffix-1 && !strcmp(line+n-(sizeof suffix-1),suffix);
  if(once && *more) { strcpy(line+n-(sizeof suffix-1),",\"more\":false}");*more=0; }
  if(!strcmp(format,"json")) {
    char *body=NULL;
    if(!strncmp(line,success,strlen(success)))asprintf(&body,"{\"type\":\"success\",\"data\":[%s\n",line+strlen(success));
    else if(!strncmp(line,error,strlen(error)))asprintf(&body,"{\"type\":\"error\",\"data\":%s\n",line+strlen(error));
    else asprintf(&body,"%s\n",line);
    return body;
  }
  if(!strcmp(line,"{\"type\":\"failure\"}"))return strdup("failure.\n");
  if(!strncmp(line,error,strlen(error))) {
    const char *p=line+strlen(error);char *term=json_text(&p),*body=NULL;
    if(term){asprintf(&body,"error(%s).\n",term);free(term);}return body;
  }
  if(strncmp(line,success,strlen(success)))return NULL;
  const char *p=line+strlen(success);char *body=malloc(strlen(line)+32);if(!body)return NULL;
  strcpy(body,"success([");size_t used=strlen(body);int first=1;
  while(*p!=']') { if(!first){if(*p++!=','){free(body);return NULL;}body[used++]=',';}first=0;
    char *term=json_text(&p);if(!term){free(body);return NULL;}size_t len=strlen(term);memcpy(body+used,term,len);used+=len;free(term);
  }snprintf(body+used,32,"],%s).\n",*more?"true":"false");return body;
}
static void call_request(int fd,Request *r) {
  char *key=key_for(r);if(!key){error_reply(fd,503,r->format,"allocation_failed");return;}
  pthread_mutex_lock(&mutex);Query *q=NULL;
  for(int i=0;i<max_queries;i++)if(queries[i].pid&&!queries[i].busy&&queries[i].expires<=now())release(&queries[i]);
  for(int i=0;i<max_queries;i++)if(queries[i].pid&&!queries[i].busy&&queries[i].offset==r->offset&&!strcmp(queries[i].key,key)){q=&queries[i];break;}
  if(q) { free(key);
    /* The demonstrator treats zero on a resumed page as its default limit. */
    if(r->limit==0)r->limit=ISO_MAX_PAGE;
    q->busy=1;char next[40];int len=snprintf(next,sizeof next,"next %ld\n",r->limit);
    if(!write_all(q->in,next,(size_t)len)){release(q);q=NULL;}
  } else {
    for(int i=0;i<max_queries;i++)if(!queries[i].pid){q=&queries[i];break;}
    if(!q) {
      /* Like SWI's insertion-order cache eviction, but never stop an active
       * request. Resuming and recaching a continuation makes it newest. */
      for(int i=0;i<max_queries;i++)
        if(!queries[i].busy && (!q || queries[i].cached_order<q->cached_order))q=&queries[i];
      if(q)release(q);
    }
    if(!q){pthread_mutex_unlock(&mutex);free(key);error_reply(fd,503,r->format,"query_limit_exceeded");return;}
    if(!start_query(q,r,key)){q=NULL;free(key);}
  }
  pthread_mutex_unlock(&mutex);
  if(!q){error_reply(fd,503,r->format,"worker_start_failed");return;}
  char *line=malloc(RESPONSE_CAP+4);size_t used=0;int complete=0,abandoned=0;long long end=now()+r->timeout;
  while(line && !complete && !stopping) {
    long long left=end-now();if(left<=0)break;
    struct pollfd p[2]={{q->out,POLLIN,0},{fd,POLLIN,0}};
    if(poll(p,2,left>100?100:(int)left)<0){if(errno==EINTR)continue;break;}
    if(p[1].revents) { char c;ssize_t k=recv(fd,&c,1,MSG_PEEK|MSG_DONTWAIT);
      if(k==0 || (k<0&&errno!=EAGAIN)){abandoned=1;break;}
    }
    if(p[0].revents) { ssize_t n=read(q->out,line+used,RESPONSE_CAP-used);
      if(n<=0)break;used+=(size_t)n;
      if(memchr(line,'\n',used)){char *nl=memchr(line,'\n',used);*nl=0;complete=1;}
      else if(used>=RESPONSE_CAP)break;
    }
  }
  int more=0;char *body=complete?public_body(line,r->format,r->once,&more):NULL;
  pthread_mutex_lock(&mutex);
  if(body&&more&&!abandoned&&!stopping){q->busy=0;q->offset=r->offset+r->limit;q->expires=now()+idle_ms;q->cached_order=++cache_order;}
  else release(q);
  pthread_mutex_unlock(&mutex);
  if(!abandoned){if(body)reply(fd,200,r->format,body);else error_reply(fd,200,r->format,"timeout_or_worker_failure");}
  free(body);free(line);
}
static void *client(void *arg) {
  int index=(int)(long)arg,fd=clients[index];
  char *b=malloc(REQUEST_CAP+1);
  size_t used=0;
  int ready=0,timed_out=0;
  long long deadline=now()+CONNECTION_IDLE_MS;
  while(b&&used<REQUEST_CAP&&!stopping) {
    long long left=deadline-now();
    if(left<=0){timed_out=1;break;}
    struct pollfd pending={fd,POLLIN,0};
    int status=poll(&pending,1,(int)left);
    if(status<0&&errno==EINTR)continue;
    if(status==0){timed_out=1;break;}
    if(status<0)break;
    ssize_t n=read(fd,b+used,REQUEST_CAP-used);
    if(n<0&&(errno==EINTR||errno==EAGAIN))continue;
    if(n<=0)break;
    /* A speculative connection is not an incomplete HTTP request. Start
     * the absolute header deadline only when the first bytes arrive. */
    if(!used)deadline=now()+HEADER_READ_MS;
    used+=(size_t)n;b[used]=0;
    if(strstr(b,"\r\n\r\n")){ready=1;break;}
  }
  if(!b)error_reply(fd,503,"json","allocation_failed");
  else if(!ready) {
    /* Never queue an unsolicited error on an idle preconnection: a browser
     * could later mistake it for the response to a request it just sent. */
    if(used&&!stopping) {
      if(used>=REQUEST_CAP) {
        error_reply(fd,431,"json","request_headers_too_large");
        finish_rejected_request(fd);
      }
      else error_reply(fd,timed_out?408:400,"json","incomplete_request");
    }
  } else {
    char *end=strstr(b,"\r\n");*end=0;char *space=strchr(b,' '),*last=space?strchr(space+1,' '):NULL;
    if(!space||!last)error_reply(fd,400,"json","invalid_request");
    else {*space++=0;*last++=0;
      if(strcmp(b,"GET"))error_reply(fd,405,"json","get_required");
      else if(strcmp(last,"HTTP/1.1")&&strcmp(last,"HTTP/1.0"))error_reply(fd,400,"json","invalid_http_version");
      else {char *params=strchr(space,'?');if(params)*params++=0;
        if(strcmp(space,"/call"))error_reply(fd,404,"json","not_found");
        else if(!params)error_reply(fd,400,"json","goal_required");
        else {Request r;if(parameters(params,&r))call_request(fd,&r);else error_reply(fd,400,"json","invalid_parameters");free_request(&r);}
      }
    }
  }
  free(b);pthread_mutex_lock(&mutex);close(fd);clients[index]=-1;client_count--;pthread_cond_signal(&drained);pthread_mutex_unlock(&mutex);return NULL;
}
int main(int argc,char **argv) {
  long port=8081;const char *shared_file=NULL;
  for(int i=1;i<argc;i+=2){long n;if(i+1>=argc)return 2;
    if(!strcmp(argv[i],"--shared-db")){shared_file=argv[i+1];continue;}
    if(!integer(argv[i+1],0,3600000,&n))return 2;
    if(!strcmp(argv[i],"--port")&&n<=65535)port=n;
    else if(!strcmp(argv[i],"--max-queries")&&n>=1&&n<=MAX_QUERIES)max_queries=(int)n;
    else if(!strcmp(argv[i],"--time-ms")&&n>=1)time_ms=(int)n;
    else if(!strcmp(argv[i],"--idle-ms")&&n>=1)idle_ms=(int)n;else return 2;}
  if(strlen(argv[0])+18>=sizeof supervisor)return 2;
  strcpy(supervisor,argv[0]);char *slash=strrchr(supervisor,'/');if(slash)strcpy(slash+1,"query-supervisor");else strcpy(supervisor,"./query-supervisor");
  strcpy(directory,"/tmp/gprolog-http-XXXXXX");if(!mkdtemp(directory)){perror("mkdtemp");return 2;}
  atexit(cleanup_directory);
  if(shared_file&&!snapshot_shared(shared_file)) {
    fprintf(stderr,"Cannot snapshot shared database (requires a regular text file up to 1 MiB): %s\n",shared_file);return 2;
  }
  for(int i=0;i<MAX_CLIENTS;i++)clients[i]=-1;
  signal(SIGPIPE,SIG_IGN);struct sigaction sa;memset(&sa,0,sizeof sa);sa.sa_handler=stop;sigaction(SIGTERM,&sa,NULL);sigaction(SIGINT,&sa,NULL);
  if(shared_file&&!validate_shared())return 2;
  int listener=socket(AF_INET,SOCK_STREAM,0);if(listener<0)return 2;cloexec(listener);
  int one=1;setsockopt(listener,SOL_SOCKET,SO_REUSEADDR,&one,sizeof one);
  struct sockaddr_in address;memset(&address,0,sizeof address);address.sin_family=AF_INET;address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);address.sin_port=htons((unsigned short)port);
  if(bind(listener,(struct sockaddr *)&address,sizeof address)||listen(listener,32)){perror("listen");close(listener);rmdir(directory);return 2;}
  socklen_t size=sizeof address;getsockname(listener,(struct sockaddr *)&address,&size);
  printf("{\"port\":%u,\"address\":\"127.0.0.1\"}\n",ntohs(address.sin_port));fflush(stdout);
  while(!stopping) {
    struct pollfd p={listener,POLLIN,0};int rc=poll(&p,1,50);
    pthread_mutex_lock(&mutex);for(int i=0;i<max_queries;i++)if(queries[i].pid&&!queries[i].busy&&queries[i].expires<=now())release(&queries[i]);pthread_mutex_unlock(&mutex);
    if(rc<=0)continue;pthread_mutex_lock(&mutex);int fd=accept(listener,NULL,NULL);if(fd<0){pthread_mutex_unlock(&mutex);continue;}cloexec(fd);
    struct timeval timeout={2,0};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof timeout);setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof timeout);
    int index;for(index=0;index<MAX_CLIENTS;index++)if(clients[index]<0)break;
    if(index==MAX_CLIENTS){pthread_mutex_unlock(&mutex);error_reply(fd,503,"json","connection_limit_exceeded");close(fd);continue;}
    clients[index]=fd;client_count++;pthread_t thread;
    if(pthread_create(&thread,NULL,client,(void *)(long)index)){clients[index]=-1;client_count--;close(fd);}else pthread_detach(thread);
    pthread_mutex_unlock(&mutex);
  }
  close(listener);pthread_mutex_lock(&mutex);
  for(int i=0;i<MAX_CLIENTS;i++)if(clients[i]>=0)shutdown(clients[i],SHUT_RDWR);
  while(client_count)pthread_cond_wait(&drained,&mutex);
  for(int i=0;i<max_queries;i++)release(&queries[i]);pthread_mutex_unlock(&mutex);
  rmdir(directory);return 0;
}
