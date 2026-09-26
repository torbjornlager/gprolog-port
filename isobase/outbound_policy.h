/* Owner policy: scheme host port pinned-IP [rpc endpoint token-file].
 * Read before allocating a request; each transfer holds its own immutable pin. */
#include <arpa/inet.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <strings.h>
typedef struct {
  char host[256], ip[INET6_ADDRSTRLEN], credential_file[512];
  unsigned port;
  int family, blocked;
  unsigned char address[16];
} OutboundPeer;
static int outbound_ip(const char *ip,OutboundPeer *peer) {
  if(inet_pton(AF_INET,ip,peer->address)==1)peer->family=AF_INET;
  else if(inet_pton(AF_INET6,ip,peer->address)==1) {
    peer->family=AF_INET6;
    /* Scoped and mapped forms need a separate reviewed policy; reject here. */
    if(IN6_IS_ADDR_V4MAPPED((const struct in6_addr *)peer->address))return 0;
  } else return 0;
  snprintf(peer->ip,sizeof peer->ip,"%s",ip);return 1;
}
static const char *outbound_select(const char *url,const char *purpose,OutboundPeer *peer) {
  const char *path=getenv("ISO_OUTBOUND_POLICY");
  if(!path || !*path)return "outbound_denied";
  CURLU *u=curl_url();char *scheme=NULL,*host=NULL,*port=NULL,*zone=NULL,*request_path=NULL;
  const char *error="outbound_denied";
  FILE *file=NULL;int matched=0;
  if(!u)return "out_of_memory";
  if(curl_url_set(u,CURLUPART_URL,url,CURLU_DISALLOW_USER)!=CURLUE_OK ||
     curl_url_get(u,CURLUPART_SCHEME,&scheme,0)!=CURLUE_OK ||
     curl_url_get(u,CURLUPART_HOST,&host,0)!=CURLUE_OK ||
     curl_url_get(u,CURLUPART_PORT,&port,CURLU_DEFAULT_PORT)!=CURLUE_OK ||
     curl_url_get(u,CURLUPART_PATH,&request_path,0)!=CURLUE_OK ||
     curl_url_get(u,CURLUPART_ZONEID,&zone,0)==CURLUE_OK ||
     (strcmp(scheme,"http") && strcmp(scheme,"https")))goto done;
  int fd=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);
  struct stat st;
  if(fd<0){error="outbound_policy_invalid";goto done;}
  if(fstat(fd,&st) || !S_ISREG(st.st_mode) || st.st_uid!=geteuid() ||
     (st.st_mode&077) || st.st_size>65536) {
    close(fd);error="outbound_policy_invalid";goto done;
  }
  file=fdopen(fd,"r");
  if(!file){close(fd);error="outbound_policy_invalid";goto done;}
  char line[1024];size_t total=0;
  while(fgets(line,sizeof line,file)) {
    total+=strlen(line);
    if(total>65536 || (!strchr(line,'\n') && !feof(file))) {error="outbound_policy_invalid";goto done;}
    char s[8],h[256],p[8],ip[64],use[8],endpoint[256],secret[512],extra;OutboundPeer candidate={0};
    char *start=line;while(*start==' ' || *start=='\t')start++;
    if(*start=='#' || *start=='\n' || !*start)continue;
    int fields=sscanf(start,"%7s %255s %7s %63s %7s %255s %511s %c",s,h,p,ip,use,endpoint,secret,&extra);
    if((fields!=4 && fields!=7) ||
       (strcmp(s,"http") && strcmp(s,"https")) || !outbound_ip(ip,&candidate)) {
      error="outbound_policy_invalid";goto done;
    }
    if(fields==7) {
      if(strcmp(s,"https") || strcmp(use,"rpc") || endpoint[0]!='/' || secret[0]!='/') {
        error="outbound_policy_invalid";goto done;
      }
      /* Endpoint grants use unambiguous literal paths, not URL encodings. */
      for(char *c=endpoint;*c;c++)if(!((*c>='a'&&*c<='z') || (*c>='A'&&*c<='Z') ||
          (*c>='0'&&*c<='9') || strchr("/_-",*c))) {error="outbound_policy_invalid";goto done;}
    }
    unsigned n=0;
    for(char *c=p;*c;c++) {
      if(*c<'0' || *c>'9'){error="outbound_policy_invalid";goto done;}
      n=n*10+(unsigned)(*c-'0');
      if(n>65535){error="outbound_policy_invalid";goto done;}
    }
    if(!n){error="outbound_policy_invalid";goto done;}
    /* A rule host must be literal: no wildcard, userinfo, path or zone. */
    for(char *c=h;*c;c++)if(!((*c>='a'&&*c<='z') || (*c>='A'&&*c<='Z') ||
        (*c>='0'&&*c<='9') || strchr(".-:[]",*c))) {error="outbound_policy_invalid";goto done;}
    char rule_url[288],*canonical=NULL;
    snprintf(rule_url,sizeof rule_url,"%s://%s:%u/",s,h,n);
    CURLU *rule=curl_url();
    int valid=rule && curl_url_set(rule,CURLUPART_URL,rule_url,CURLU_DISALLOW_USER)==CURLUE_OK &&
      curl_url_get(rule,CURLUPART_HOST,&canonical,0)==CURLUE_OK && !strcasecmp(h,canonical);
    curl_free(canonical);curl_url_cleanup(rule);
    if(!valid){error="outbound_policy_invalid";goto done;}
    if(!strcmp(s,scheme) && !strcasecmp(h,host) && n==(unsigned)strtoul(port,NULL,10)) {
      if(matched++){error="outbound_policy_invalid";goto done;}
      if(fields==7 && !strcmp(purpose,"rpc")) {
        if(strcmp(endpoint,request_path)){error="outbound_credential_scope";goto done;}
        snprintf(candidate.credential_file,sizeof candidate.credential_file,"%s",secret);
      }
      *peer=candidate;peer->port=n;snprintf(peer->host,sizeof peer->host,"%s",host);
    }
  }
  if(ferror(file)){error="outbound_policy_invalid";goto done;}
  error=matched?NULL:"outbound_denied";
done:
  if(file)fclose(file);
  curl_free(scheme);curl_free(host);curl_free(port);curl_free(zone);curl_free(request_path);curl_url_cleanup(u);
  return error;
}
static curl_socket_t outbound_socket(void *context,curlsocktype purpose,struct curl_sockaddr *a) {
  OutboundPeer *peer=context;const void *ip=NULL;unsigned port=0;
  if(a->family==AF_INET && a->addrlen>=sizeof(struct sockaddr_in)) {
    const struct sockaddr_in *in=(const struct sockaddr_in *)&a->addr;
    ip=&in->sin_addr;port=ntohs(in->sin_port);
  } else if(a->family==AF_INET6 && a->addrlen>=sizeof(struct sockaddr_in6)) {
    const struct sockaddr_in6 *in=(const struct sockaddr_in6 *)&a->addr;
    if(in->sin6_scope_id){peer->blocked=1;return CURL_SOCKET_BAD;}
    ip=&in->sin6_addr;port=ntohs(in->sin6_port);
  }
  if(purpose!=CURLSOCKTYPE_IPCXN || a->socktype!=SOCK_STREAM || !ip ||
     a->family!=peer->family || port!=peer->port ||
     memcmp(ip,peer->address,peer->family==AF_INET?4:16)) {
    peer->blocked=1;return CURL_SOCKET_BAD;
  }
  return socket(a->family,a->socktype,a->protocol);
}
