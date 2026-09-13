/* Only the owning Prolog thread touches GNU's runtime. Network threads own
 * byte buffers; bounded slots remain allocated until joined by that thread. */
#include <curl/curl.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <time.h>
#define __GPROLOG_FOREIGN_STRICT__
#include "gprolog.h"
#define SLOTS 16
#define BODY_MAX (1024*1024)
#define URL_MAX (256*1024)
typedef struct {
  long id, timeout;
  pthread_t thread;
  pthread_mutex_t mutex;
  pthread_cond_t ready;
  atomic_int cancel;
  int done, oversized;
  char *url, *body;
  size_t size;
  const char *error;
} Request;
static Request requests[SLOTS];
static long next_id=1000000000L;
static int initialized;
static int initialize(void) {
  if(!initialized){if(curl_global_init(CURL_GLOBAL_DEFAULT))return 0;initialized=1;}
  return 1;
}
static size_t receive_body(char *p,size_t n,size_t m,void *ctx) {
  Request *r=ctx;size_t size=n*m;
  if(size>BODY_MAX-r->size || memchr(p,0,size)){r->oversized=1;return 0;}
  char *b=realloc(r->body,r->size+size+1);if(!b)return 0;
  r->body=b;memcpy(b+r->size,p,size);r->size+=size;b[r->size]=0;return size;
}
static int progress(void *ctx,curl_off_t a,curl_off_t b,curl_off_t c,curl_off_t d) {
  (void)a;(void)b;(void)c;(void)d;return atomic_load(&((Request *)ctx)->cancel);
}
static void *run_request(void *ctx) {
  Request *r=ctx;CURL *curl=curl_easy_init();
  const char *error=NULL;
  if(!curl)error="transport_initialization_failed";
  else {
    curl_easy_setopt(curl,CURLOPT_URL,r->url);
    /* Trust configuration belongs to the process owner, never query options. */
    const char *ca_file=getenv("ISO_CA_FILE");
    if(ca_file && *ca_file)curl_easy_setopt(curl,CURLOPT_CAINFO,ca_file);
    curl_easy_setopt(curl,CURLOPT_SSL_VERIFYPEER,1L);
    curl_easy_setopt(curl,CURLOPT_SSL_VERIFYHOST,2L);
    curl_easy_setopt(curl,CURLOPT_PROTOCOLS,(long)(CURLPROTO_HTTP|CURLPROTO_HTTPS));
    curl_easy_setopt(curl,CURLOPT_REDIR_PROTOCOLS,(long)(CURLPROTO_HTTP|CURLPROTO_HTTPS));
    curl_easy_setopt(curl,CURLOPT_FOLLOWLOCATION,1L);
    curl_easy_setopt(curl,CURLOPT_MAXREDIRS,5L);
    curl_easy_setopt(curl,CURLOPT_NOSIGNAL,1L);
    curl_easy_setopt(curl,CURLOPT_TIMEOUT_MS,r->timeout);
    curl_easy_setopt(curl,CURLOPT_WRITEFUNCTION,receive_body);
    curl_easy_setopt(curl,CURLOPT_WRITEDATA,r);
    curl_easy_setopt(curl,CURLOPT_XFERINFOFUNCTION,progress);
    curl_easy_setopt(curl,CURLOPT_XFERINFODATA,r);
    curl_easy_setopt(curl,CURLOPT_NOPROGRESS,0L);
    CURLcode code=curl_easy_perform(curl);long status=0;
    curl_easy_getinfo(curl,CURLINFO_RESPONSE_CODE,&status);
    if(r->oversized)error="response_too_large_or_invalid";
    else if(code==CURLE_PEER_FAILED_VERIFICATION)error="https_certificate_error";
    else if(code==CURLE_SSL_CACERT_BADFILE)error="https_ca_file_error";
    else if(code==CURLE_SSL_CONNECT_ERROR)error="https_handshake_error";
    else if(code==CURLE_TOO_MANY_REDIRECTS)error="http_redirect_error";
    else if(code==CURLE_OPERATION_TIMEDOUT)error="http_timeout";
    else if(code!=CURLE_OK)error="http_transport_error";
    else if(status!=200)error="http_status_error";
    curl_easy_cleanup(curl);
  }
  pthread_mutex_lock(&r->mutex);r->error=error;r->done=1;
  pthread_cond_broadcast(&r->ready);pthread_mutex_unlock(&r->mutex);return NULL;
}
static Request *lookup(long id) {
  for(int i=0;i<SLOTS;i++)if(requests[i].id==id)return &requests[i];return NULL;
}
static void release(Request *r) {
  atomic_store(&r->cancel,1);pthread_join(r->thread,NULL);
  pthread_cond_destroy(&r->ready);pthread_mutex_destroy(&r->mutex);
  free(r->url);free(r->body);memset(r,0,sizeof *r);
}
PlBool iso_net_start(char *url,PlLong timeout,PlTerm reference,PlTerm status) {
  if(!initialize())return PL_FALSE;
  if(strlen(url)>URL_MAX)return Pl_Un_String("request_too_large",status);
  Request *r=NULL;for(int i=0;i<SLOTS;i++)if(!requests[i].id){r=&requests[i];break;}
  if(!r)return Pl_Un_String("promise_limit_exceeded",status);
  r->url=strdup(url);if(!r->url)return Pl_Un_String("out_of_memory",status);
  /* References are opaque ten-digit integers scoped to this worker. */
  long candidate;
  do { if(next_id>9999999999L)next_id=1000000000L;candidate=next_id++; }
  while(lookup(candidate));
  r->id=candidate;
  r->timeout=timeout;atomic_init(&r->cancel,0);
  pthread_mutex_init(&r->mutex,NULL);pthread_cond_init(&r->ready,NULL);
  if(pthread_create(&r->thread,NULL,run_request,r)) {
    pthread_cond_destroy(&r->ready);pthread_mutex_destroy(&r->mutex);
    free(r->url);memset(r,0,sizeof *r);return Pl_Un_String("transport_initialization_failed",status);
  }
  return Pl_Un_Integer(r->id,reference)&&Pl_Un_String("ok",status);
}
/* Waiting timeout retains the slot. A delivered response consumes it even if
 * subsequent Prolog unification fails. -1 means wait until transport ends. */
static PlBool wait_request(PlLong id,PlLong timeout,PlTerm body,PlTerm status,int consume) {
  Request *r=lookup(id);if(!r)return Pl_Un_String("missing",status);
  struct timespec until;clock_gettime(CLOCK_REALTIME,&until);
  if(timeout>=0){until.tv_sec+=timeout/1000;until.tv_nsec+=(timeout%1000)*1000000;
    if(until.tv_nsec>=1000000000){until.tv_sec++;until.tv_nsec-=1000000000;}}
  pthread_mutex_lock(&r->mutex);
  while(!r->done) {
    int rc=timeout<0?pthread_cond_wait(&r->ready,&r->mutex):pthread_cond_timedwait(&r->ready,&r->mutex,&until);
    if(rc)break;
  }
  int done=r->done;pthread_mutex_unlock(&r->mutex);
  if(!done)return Pl_Un_String("timeout",status);
  /* Copy to runtime before freeing the network-owned bytes. */
  PlBool ok=Pl_Un_String(r->error?r->error:"ok",status);
  if(!r->error)ok=ok&&Pl_Un_String(r->body?r->body:"",body);
  if(consume)release(r);return ok;
}
PlBool iso_net_wait(PlLong id,PlLong timeout,PlTerm body,PlTerm status) {
  return wait_request(id,timeout,body,status,1);
}
PlBool iso_net_peek(PlLong id,PlTerm body,PlTerm status) {
  return wait_request(id,-1,body,status,0);
}
/* yield/2 waits for a matching message, as thread_get_message/2 does in SWI.
 * There is only one response per promise. If it cannot match, the owning
 * query remains blocked until the supervisor terminates it; do not spin. */
PlBool iso_net_unmatched(PlLong id) {
  Request *r=lookup(id);if(!r)return PL_FALSE;
  pthread_mutex_lock(&r->mutex);
  for(;;)pthread_cond_wait(&r->ready,&r->mutex);
}
PlBool iso_net_cancel(PlLong id) {Request *r=lookup(id);if(r)release(r);return PL_TRUE;}
PlBool iso_net_escape(char *text,PlTerm escaped) {
  if(!initialize() || strlen(text)>URL_MAX)return PL_FALSE;
  char *s=curl_easy_escape(NULL,text,0);if(!s)return PL_FALSE;
  PlBool ok=Pl_Un_String(s,escaped);curl_free(s);return ok;
}
