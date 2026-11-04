#ifndef ISO_OUTBOUND_BROKER_H
#define ISO_OUTBOUND_BROKER_H
#include <sys/socket.h>
#include <sys/un.h>
#include <stddef.h>
#include <poll.h>
/* Transport only: the trusted broker validates destinations, TLS, response
 * bounds, admission and peer credentials. Workers cannot open IP sockets. */
static long long broker_now(void) {
  struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (long long)t.tv_sec*1000+t.tv_nsec/1000000;
}
static int broker_ready(int fd,short events,long long until,Request *r) {
  while(!atomic_load(&r->cancel)) {
    long long left=until-broker_now();if(left<=0)return 0;
    struct pollfd p={fd,events,0};int code=poll(&p,1,left>100?100:(int)left);
    if(code<0&&errno==EINTR)continue;
    if(code<0)return 0;if(code>0)return 1;
  }
  return 0;
}
static void *run_broker_request(Request *r) {
  const char *error="http_transport_error";int fd=-1;char *body=NULL,*request=NULL,*reply=NULL;
  char *url=curl_easy_escape(NULL,r->url,0);size_t used=0;
  long long until=broker_now()+r->timeout;
  if(!url){error="out_of_memory";goto done;}
  if(asprintf(&body,"url=%s&purpose=%s&query_owner=%s&timeout_ms=%ld",url,r->purpose,r->query_owner,r->timeout)<0){body=NULL;goto done;}
  if(asprintf(&request,"POST /fetch HTTP/1.1\r\nHost: broker\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: %zu\r\nConnection: close\r\n\r\n%s",strlen(body),body)<0){request=NULL;goto done;}
#ifdef SOCK_CLOEXEC
  fd=socket(AF_UNIX,SOCK_STREAM|SOCK_CLOEXEC,0);
#else
  fd=socket(AF_UNIX,SOCK_STREAM,0);
  if(fd>=0&&fcntl(fd,F_SETFD,FD_CLOEXEC)){close(fd);fd=-1;}
#endif
  if(fd<0)goto done;
  if(fcntl(fd,F_SETFL,fcntl(fd,F_GETFL)|O_NONBLOCK))goto done;
  struct sockaddr_un address={.sun_family=AF_UNIX};strcpy(address.sun_path+1,"trinity-n6-egress");
  if(connect(fd,(struct sockaddr *)&address,offsetof(struct sockaddr_un,sun_path)+1+strlen(address.sun_path+1))<0&&errno!=EINPROGRESS)goto done;
  size_t remaining=strlen(request);char *at=request;
  while(remaining) {
    if(!broker_ready(fd,POLLOUT,until,r)){error="http_timeout";goto done;}
    ssize_t n=send(fd,at,remaining,MSG_NOSIGNAL);
    if(n<0&&(errno==EINTR||errno==EAGAIN))continue;
    if(n<=0)goto done;at+=n;remaining-=(size_t)n;
  }
  reply=malloc(BODY_MAX+16385);if(!reply){error="out_of_memory";goto done;}
  while(used<BODY_MAX+16384) {
    if(!broker_ready(fd,POLLIN,until,r)){error="http_timeout";goto done;}
    ssize_t n=recv(fd,reply+used,BODY_MAX+16384-used,0);
    if(n<0&&(errno==EINTR||errno==EAGAIN))continue;
    if(n<0)goto done;if(!n)break;
    if(memchr(reply+used,0,(size_t)n))goto done;
    used+=(size_t)n;
  }
  reply[used]=0;char *start=strstr(reply,"\r\n\r\n");int status=0;
  if(!start||start-reply>16384||sscanf(reply,"HTTP/%*d.%*d %d",&status)!=1)goto done;
  start+=4;size_t length=used-(size_t)(start-reply);
  if(length>BODY_MAX){error="response_too_large_or_invalid";goto done;}
  if(status!=200) {
    error=status==403?"outbound_denied":status==429?"outbound_busy":status==504?"http_timeout":"http_transport_error";
    goto done;
  }
  r->body=strdup(start);if(!r->body){error="out_of_memory";goto done;}r->size=length;error=NULL;
done:
  if(fd>=0)close(fd);if(url)curl_free(url);free(body);free(request);free(reply);
  pthread_mutex_lock(&r->mutex);r->error=error;r->done=1;
  pthread_cond_signal(&r->ready);pthread_mutex_unlock(&r->mutex);return NULL;
}
#endif
