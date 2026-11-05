#define _GNU_SOURCE
/* Only the owning Prolog thread touches GNU's runtime. Network threads own
 * byte buffers; bounded slots remain allocated until joined by that thread. */
#include <curl/curl.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#ifdef __linux__
#include <sys/random.h>
#endif
#define __GPROLOG_FOREIGN_STRICT__
#include "gprolog.h"
#include "outbound_policy.h"
#include "outbound_credentials.h"
#define SLOTS 16
#define BODY_MAX (1024*1024)
#define URL_MAX (256*1024)
typedef struct {
  long id, timeout;
  OutboundPeer peer;
  pthread_t thread;
  pthread_mutex_t mutex;
  pthread_cond_t ready;
  atomic_int cancel;
  int done, oversized;
  char *url, *body, *header_text;
  char query_owner[65],purpose[8];
  int broker;
  size_t size;
  const char *error;
} Request;
#include "outbound_broker.h"
static Request requests[SLOTS];
static long next_id=1000000000L;
static int initialized;
static int initialize(void) {
  if(!initialized){if(curl_global_init(CURL_GLOBAL_DEFAULT))return 0;initialized=1;}
  return 1;
}
/* Parse only: no resolver, socket, request slot or worker thread is started.
 * Keep the caller's path bytes; this handle validates without normalizing them.
 * Exact source-resource URLs intentionally use a separate Prolog interface. */
/* Trusted controller metadata only; never inferred from a caller URL/header. */
PlBool iso_net_local_node_uri(PlTerm uri) {
  const char *value=getenv("ISO_LOCAL_NODE_URI");
  return Pl_Un_String(value&&*value?value:"http://localhost",uri);
}
PlBool iso_net_node_uri(char *url) {
  size_t length=strlen(url);
  if(length>URL_MAX)return PL_FALSE;
  const char *authority;
  if(!strncmp(url,"http://",7))authority=url+7;
  else if(!strncmp(url,"https://",8))authority=url+8;
  else return PL_FALSE;
  for(const unsigned char *p=(const unsigned char *)url;*p;p++)
    if(*p<=32 || *p==127 || *p=='?' || *p=='#')return PL_FALSE;
  const char *end=authority+strcspn(authority,"/");
  if(end==authority || memchr(authority,'@',(size_t)(end-authority)))return PL_FALSE;
  const char *port=NULL;
  if(*authority=='[') {
    const char *close=memchr(authority,']',(size_t)(end-authority));
    if(!close)return PL_FALSE;
    if(close+1<end) {
      if(close[1]!=':')return PL_FALSE;
      port=close+2;
    }
  } else {
    const char *colon=memchr(authority,':',(size_t)(end-authority));
    if(colon)port=colon+1;
  }
  /* libcurl tolerates an empty explicit port; the node contract does not. */
  if(port) {
    if(port==end)return PL_FALSE;
    unsigned value=0;
    for(const char *p=port;p<end;p++) {
      if(*p<'0' || *p>'9')return PL_FALSE;
      value=value*10+(unsigned)(*p-'0');
      if(value>65535)return PL_FALSE;
    }
  }
  if(!initialize())return PL_FALSE;
  CURLU *parsed=curl_url();
  if(!parsed)return PL_FALSE;
  CURLUcode status=curl_url_set(parsed,CURLUPART_URL,url,CURLU_DISALLOW_USER);
  curl_url_cleanup(parsed);
  return status==CURLUE_OK ? PL_TRUE : PL_FALSE;
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
/* Validate the private framing as well as the language-level schema. */
static int header_name_char(unsigned char c) {
  return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||strchr("!#$%&'*+-.^_`|~",c)!=NULL;
}
static int has_header(const char *text,const char *name) {
  size_t n=strlen(name);
  for(const char *p=text;*p;) {
    const char *end=strchr(p,'\n');if(!end)return 0;
    if((size_t)(end-p)>n && p[n]==':' && !strncasecmp(p,name,n))return 1;
    p=end+1;
  }
  return 0;
}
static const char *check_headers(const char *text,char explicit_owner[65]) {
  if(strlen(text)>16384)return "request_too_large";
  for(const char *p=text;*p;) {
    const char *end=strchr(p,'\n'),*colon=strchr(p,':');
    if(!end||!colon||colon==p||colon>end||colon+1>=end||colon[1]!=' ')return "invalid_request_headers";
    for(const char *q=p;q<colon;q++)if(!header_name_char((unsigned char)*q))return "invalid_request_headers";
    for(const char *q=colon+2;q<end;q++)if(((unsigned char)*q<32&&*q!='\t')||*q==127)return "invalid_request_headers";
    if((size_t)(colon-p)==24&&!strncasecmp(p,"x-web-prolog-query-owner",24)) {
      const char *value=colon+2;if(end-value!=64)return "invalid_query_owner";
      for(int i=0;i<64;i++)if(!((value[i]>='0'&&value[i]<='9')||(value[i]>='a'&&value[i]<='f')))return "invalid_query_owner";
      memcpy(explicit_owner,value,64);explicit_owner[64]=0;
    }
    p=end+1;
  }
  return NULL;
}
static int append_request_headers(struct curl_slist **headers,const char *text) {
  for(const char *p=text;*p;) {
    const char *end=strchr(p,'\n');size_t n=(size_t)(end-p);
    char *line=strndup(p,n);if(!line)return 0;
    char *colon=strchr(line,':');
    if(colon && !colon[2]){*colon=';';colon[1]=0;} /* curl's explicit empty field syntax */
    struct curl_slist *next=curl_slist_append(*headers,line);free(line);
    if(!next)return 0;
    *headers=next;p=end+1;
  }
  return 1;
}
static void *run_request(void *ctx) {
  Request *r=ctx;
  if(r->timeout==0) {
    pthread_mutex_lock(&r->mutex);r->error="http_timeout";r->done=1;
    pthread_cond_signal(&r->ready);pthread_mutex_unlock(&r->mutex);return NULL;
  }
  if(r->broker)return run_broker_request(r);
  CURL *curl=curl_easy_init();
  const char *error=NULL;
  char authorization[280]={0};struct curl_slist *headers=NULL;
  if(r->peer.credential_file[0]) {
    if(!outbound_authorization(r->peer.credential_file,authorization))error="outbound_credential_invalid";
    else if(!(headers=curl_slist_append(NULL,authorization)))error="out_of_memory";
    outbound_wipe(authorization,sizeof authorization);
  }
  if(!error&&!append_request_headers(&headers,r->header_text))error="out_of_memory";
  if(!error&&r->query_owner[0]&&!has_header(r->header_text,"x-web-prolog-query-owner")) {
    char owner_header[96];snprintf(owner_header,sizeof owner_header,"X-Web-Prolog-Query-Owner: %s",r->query_owner);
    struct curl_slist *next=curl_slist_append(headers,owner_header);
    if(next)headers=next;else error="out_of_memory";
  }
  if(error){if(curl)curl_easy_cleanup(curl);}
  else if(!curl)error="transport_initialization_failed";
  else {
    curl_easy_setopt(curl,CURLOPT_URL,r->url);
    /* Trust configuration belongs to the process owner, never query options. */
    const char *ca_file=getenv("ISO_CA_FILE");
    if(ca_file && *ca_file)curl_easy_setopt(curl,CURLOPT_CAINFO,ca_file);
    curl_easy_setopt(curl,CURLOPT_SSL_VERIFYPEER,1L);
    curl_easy_setopt(curl,CURLOPT_SSL_VERIFYHOST,2L);
    curl_easy_setopt(curl,CURLOPT_PROTOCOLS,(long)(CURLPROTO_HTTP|CURLPROTO_HTTPS));
    curl_easy_setopt(curl,CURLOPT_REDIR_PROTOCOLS,(long)(CURLPROTO_HTTP|CURLPROTO_HTTPS));
    curl_easy_setopt(curl,CURLOPT_FOLLOWLOCATION,0L);
    curl_easy_setopt(curl,CURLOPT_MAXREDIRS,5L);
    curl_easy_setopt(curl,CURLOPT_NOSIGNAL,1L);
    curl_easy_setopt(curl,CURLOPT_TIMEOUT_MS,r->timeout);
    curl_easy_setopt(curl,CURLOPT_WRITEFUNCTION,receive_body);
    curl_easy_setopt(curl,CURLOPT_WRITEDATA,r);
    curl_easy_setopt(curl,CURLOPT_XFERINFOFUNCTION,progress);
    curl_easy_setopt(curl,CURLOPT_XFERINFODATA,r);
    curl_easy_setopt(curl,CURLOPT_NOPROGRESS,0L);
    char pin[512];
    snprintf(pin,sizeof pin,"%s:%u:%s%s%s:%u",r->peer.host,r->peer.port,
             r->peer.family==AF_INET6?"[":"",r->peer.ip,
             r->peer.family==AF_INET6?"]":"",r->peer.port);
    struct curl_slist *connect=curl_slist_append(NULL,pin);
    CURLcode code=CURLE_FAILED_INIT;
    /* Every security option must succeed before a connection is attempted. */
    if(connect &&
       curl_easy_setopt(curl,CURLOPT_SSL_VERIFYPEER,1L)==CURLE_OK &&
       curl_easy_setopt(curl,CURLOPT_SSL_VERIFYHOST,2L)==CURLE_OK &&
       curl_easy_setopt(curl,CURLOPT_HTTPHEADER,headers)==CURLE_OK &&
       curl_easy_setopt(curl,CURLOPT_HEADEROPT,(long)CURLHEADER_SEPARATE)==CURLE_OK &&
       curl_easy_setopt(curl,CURLOPT_PROXY,"")==CURLE_OK &&
       curl_easy_setopt(curl,CURLOPT_PRE_PROXY,"")==CURLE_OK &&
       curl_easy_setopt(curl,CURLOPT_FOLLOWLOCATION,0L)==CURLE_OK &&
       curl_easy_setopt(curl,CURLOPT_CONNECT_TO,connect)==CURLE_OK &&
       curl_easy_setopt(curl,CURLOPT_OPENSOCKETFUNCTION,outbound_socket)==CURLE_OK &&
       curl_easy_setopt(curl,CURLOPT_OPENSOCKETDATA,&r->peer)==CURLE_OK)
      code=curl_easy_perform(curl);
    long status=0;
    curl_easy_getinfo(curl,CURLINFO_RESPONSE_CODE,&status);
    if(r->peer.blocked)error="outbound_denied";
    else if(status>=300 && status<400)error="http_redirect_denied";
    else if(r->oversized)error="response_too_large_or_invalid";
    else if(code==CURLE_PEER_FAILED_VERIFICATION)error="https_certificate_error";
    else if(code==CURLE_SSL_CACERT_BADFILE)error="https_ca_file_error";
    else if(code==CURLE_SSL_CONNECT_ERROR)error="https_handshake_error";
    else if(code==CURLE_TOO_MANY_REDIRECTS)error="http_redirect_error";
    else if(code==CURLE_OPERATION_TIMEDOUT)error="http_timeout";
    else if(code!=CURLE_OK)error="http_transport_error";
    else if(status!=200)error="http_status_error";
    curl_easy_cleanup(curl);curl_slist_free_all(connect);
  }
  for(struct curl_slist *h=headers;h;h=h->next)outbound_wipe(h->data,strlen(h->data));
  curl_slist_free_all(headers);
  pthread_mutex_lock(&r->mutex);r->error=error;r->done=1;
  pthread_cond_broadcast(&r->ready);pthread_mutex_unlock(&r->mutex);return NULL;
}
static Request *lookup(long id) {
  for(int i=0;i<SLOTS;i++)if(requests[i].id==id)return &requests[i];return NULL;
}
static void release(Request *r) {
  atomic_store(&r->cancel,1);pthread_join(r->thread,NULL);
  pthread_cond_destroy(&r->ready);pthread_mutex_destroy(&r->mutex);
  free(r->url);free(r->body);if(r->header_text){outbound_wipe(r->header_text,strlen(r->header_text));free(r->header_text);}memset(r,0,sizeof *r);
}
PlBool iso_net_start(char *url,PlLong timeout,char *purpose,char *owner,char *header_text,PlTerm reference,PlTerm status) {
  if(!initialize())return PL_FALSE;
  char explicit_owner[65]={0};const char *header_error=check_headers(header_text,explicit_owner);
  if(header_error)return Pl_Un_String(header_error,status);
  /* The policy pins the destination authority, including its HTTP Host. */
  if(has_header(header_text,"host"))return Pl_Un_String("outbound_denied",status);
  if(*explicit_owner)owner=explicit_owner;
  if(strcmp(purpose,"rpc")&&*header_text)return Pl_Un_String("outbound_denied",status);
  if(strlen(url)>URL_MAX)return Pl_Un_String("request_too_large",status);
  if(strcmp(purpose,"rpc") && strcmp(purpose,"source"))return Pl_Un_String("outbound_denied",status);
  const char *broker=getenv("ISO_OUTBOUND_BROKER");
  if(broker&&strcmp(broker,"/broker.sock"))return Pl_Un_String("outbound_denied",status);
  OutboundPeer peer={0};const char *denied=broker?NULL:outbound_select(url,purpose,&peer);
  if(denied)return Pl_Un_String(denied,status);
  if(peer.credential_file[0]&&has_header(header_text,"authorization"))return Pl_Un_String("outbound_credential_conflict",status);
  Request *r=NULL;for(int i=0;i<SLOTS;i++)if(!requests[i].id){r=&requests[i];break;}
  if(!r)return Pl_Un_String("promise_limit_exceeded",status);
  if(*owner) {
    if(strlen(owner)!=64)return Pl_Un_String("invalid_query_owner",status);
    for(const char *p=owner;*p;p++)if(!((*p>='0'&&*p<='9')||(*p>='a'&&*p<='f')))return Pl_Un_String("invalid_query_owner",status);
  }
  snprintf(r->query_owner,sizeof r->query_owner,"%s",owner);
  r->url=strdup(url);r->header_text=strdup(header_text);
  if(!r->url||!r->header_text){free(r->url);free(r->header_text);memset(r,0,sizeof *r);return Pl_Un_String("out_of_memory",status);}
  /* References are opaque ten-digit integers scoped to this worker. */
  long candidate;
  do { if(next_id>9999999999L)next_id=1000000000L;candidate=next_id++; }
  while(lookup(candidate));
  r->id=candidate;
  r->peer=peer;r->broker=broker!=NULL;snprintf(r->purpose,sizeof r->purpose,"%s",purpose);
  r->timeout=timeout;atomic_init(&r->cancel,0);
  pthread_mutex_init(&r->mutex,NULL);pthread_cond_init(&r->ready,NULL);
  if(pthread_create(&r->thread,NULL,run_request,r)) {
    pthread_cond_destroy(&r->ready);pthread_mutex_destroy(&r->mutex);
    free(r->url);free(r->header_text);memset(r,0,sizeof *r);return Pl_Un_String("transport_initialization_failed",status);
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

/* Capabilities come from OS entropy, never Prolog's predictable RNG. */
PlBool iso_net_nonce(PlTerm value) {
  unsigned char bytes[32];size_t used=0;
#ifdef __linux__
  while(used<sizeof bytes){ssize_t n=getrandom(bytes+used,sizeof bytes-used,0);if(n<0&&errno==EINTR)continue;if(n<=0)return PL_FALSE;used+=(size_t)n;}
#else
  int fd=open("/dev/urandom",O_RDONLY|O_CLOEXEC);if(fd<0)return PL_FALSE;
  while(used<sizeof bytes) {
    ssize_t n=read(fd,bytes+used,sizeof bytes-used);
    if(n<0&&errno==EINTR)continue;
    if(n<=0){close(fd);return PL_FALSE;}used+=(size_t)n;
  }
  close(fd);
#endif
  char hex[65];const char *digits="0123456789abcdef";
  for(size_t i=0;i<sizeof bytes;i++){hex[2*i]=digits[bytes[i]>>4];hex[2*i+1]=digits[bytes[i]&15];}
  hex[64]=0;return Pl_Un_String(hex,value);
}
