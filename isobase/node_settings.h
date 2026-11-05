#ifndef ISO_NODE_SETTINGS_H
#define ISO_NODE_SETTINGS_H
#include "protocol.h"
#include <stdlib.h>
#include <string.h>

/* Private controller/supervisor/worker argument. Never parse Prolog or accept
 * arbitrary key names here; only public serving-node fields cross this path. */
typedef struct { int port,capacity; const char *auth; } IsoPublicNode;
static int iso_parse_public_node(const char *text,IsoPublicNode *node) {
  char *end;
  if(!text||*text<'0'||*text>'9')return 0;
  unsigned long port=strtoul(text,&end,10);
  if(port<1||port>65535||*end!=':')return 0;
  text=end+1;if(*text<'0'||*text>'9')return 0;
  unsigned long capacity=strtoul(text,&end,10);
  if(capacity<1||capacity>ISO_MAX_NODE_QUERIES||*end!=':')return 0;
  const char *auth=end+1;
  if(strcmp(auth,"open")&&strcmp(auth,"private"))return 0;
  node->port=(int)port;node->capacity=(int)capacity;node->auth=auth;
  return 1;
}
#endif
