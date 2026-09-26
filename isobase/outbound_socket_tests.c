/* Deterministic rebinding/port/family cases at the actual socket boundary. */
#include <curl/curl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "outbound_policy.h"
#include "outbound_credentials.h"
int main(void) {
  OutboundPeer peer={0};peer.port=8080;
  assert(outbound_ip("127.0.0.1",&peer));
  struct { struct curl_sockaddr curl; unsigned char room[sizeof(struct sockaddr_in6)]; } storage={0};
  struct curl_sockaddr *a=&storage.curl;
  a->family=AF_INET;a->socktype=SOCK_STREAM;a->protocol=IPPROTO_TCP;a->addrlen=sizeof(struct sockaddr_in);
  struct sockaddr_in *in=(struct sockaddr_in *)&a->addr;
  in->sin_family=AF_INET;in->sin_port=htons(8080);assert(inet_pton(AF_INET,"127.0.0.1",&in->sin_addr)==1);
  curl_socket_t fd=outbound_socket(&peer,CURLSOCKTYPE_IPCXN,a);assert(fd!=CURL_SOCKET_BAD);close(fd);
  /* A resolver returning a different address cannot cause even a socket open. */
  for(const char **p=(const char *[]) {"127.0.0.2","10.0.0.1","169.254.169.254",NULL};*p;p++) {
    inet_pton(AF_INET,*p,&in->sin_addr);
    assert(outbound_socket(&peer,CURLSOCKTYPE_IPCXN,a)==CURL_SOCKET_BAD);
  }
  inet_pton(AF_INET,"127.0.0.1",&in->sin_addr);in->sin_port=htons(8081);
  assert(outbound_socket(&peer,CURLSOCKTYPE_IPCXN,a)==CURL_SOCKET_BAD);
  in->sin_port=htons(8080);a->socktype=SOCK_DGRAM;
  assert(outbound_socket(&peer,CURLSOCKTYPE_IPCXN,a)==CURL_SOCKET_BAD);
  a->socktype=SOCK_STREAM;a->family=AF_INET6;a->addrlen=sizeof(struct sockaddr_in6);
  struct sockaddr_in6 *six=(struct sockaddr_in6 *)&a->addr;
  memset(six,0,sizeof *six);six->sin6_family=AF_INET6;six->sin6_port=htons(8080);
  inet_pton(AF_INET6,"::1",&six->sin6_addr);
  assert(outbound_socket(&peer,CURLSOCKTYPE_IPCXN,a)==CURL_SOCKET_BAD);
  assert(outbound_ip("::1",&peer));
  fd=outbound_socket(&peer,CURLSOCKTYPE_IPCXN,a);assert(fd!=CURL_SOCKET_BAD);close(fd);
  six->sin6_scope_id=1;assert(outbound_socket(&peer,CURLSOCKTYPE_IPCXN,a)==CURL_SOCKET_BAD);
  six->sin6_scope_id=0;inet_pton(AF_INET6,"fd00::1",&six->sin6_addr);
  assert(outbound_socket(&peer,CURLSOCKTYPE_IPCXN,a)==CURL_SOCKET_BAD);
  assert(!outbound_ip("::ffff:127.0.0.1",&peer));
  unsetenv("ISO_OUTBOUND_POLICY");assert(!strcmp(outbound_select("http://localhost","rpc",&peer),"outbound_denied"));
  char name[]="/tmp/isobase-credential-unit-XXXXXX",header[280]={0};
  int token=mkstemp(name);assert(token>=0);
  char bytes[258];memset(bytes,'A',sizeof bytes);
  assert(write(token,bytes,256)==256);close(token);
  assert(outbound_authorization(name,header));assert(strlen(header)==278);
  outbound_wipe(header,sizeof header);for(size_t i=0;i<sizeof header;i++)assert(header[i]==0);
  token=open(name,O_WRONLY|O_APPEND);assert(token>=0);assert(write(token,"A",1)==1);close(token);
  assert(!outbound_authorization(name,header));
  token=open(name,O_WRONLY|O_TRUNC);assert(token>=0);bytes[16]='\r';
  assert(write(token,bytes,32)==32);close(token);assert(!outbound_authorization(name,header));
  unlink(name);
  puts("PASS socket-bound IP/port/family guards, including changed DNS addresses");
  return 0;
}
