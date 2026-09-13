#include "protocol.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>
#define __GPROLOG_FOREIGN_STRICT__
#include "gprolog.h"
static int json_bindings,prolog_display,empty_page;

/* Private, trusted-input protocol, not an HTTP or sandbox boundary.
 * A process owns one query. One answer is buffered ahead of each page.
 * Serialize before advancing: backtracking invalidates previous bindings.
 */
static void json_string(const char *s) {
  putchar('"');
  for (const unsigned char *p=(const unsigned char *)s; *p; ++p) {
    if (*p=='"' || *p=='\\') { putchar('\\'); putchar(*p); }
    else if (*p<32) printf("\\u%04x", *p);
    else putchar(*p);
  }
  putchar('"');
}
static char *copy_term(PlTerm t) {
  Pl_Query_Begin(PL_TRUE);
  PlTerm args[2]={t,Pl_Mk_Variable()};
  int result=Pl_Query_Call(Pl_Find_Atom("iso_render_canonical"),2,args);
  char *s=result==PL_SUCCESS ? strdup(Pl_Atom_Name(Pl_Rd_Atom_Check(args[1])))
                            : strdup("error(representation_error(utf8),serialization)");
  Pl_Query_End(PL_RECOVER);
  if (!s) { perror("strdup"); exit(2); }
  return s;
}
static int begin(const char *text, PlTerm args[2]) {
  Pl_Query_Begin(PL_TRUE);
  args[0]=Pl_Mk_Atom(Pl_Create_Atom(text));
  args[1]=Pl_Mk_Variable();
  return Pl_Query_Call(Pl_Find_Atom(empty_page?"iso_query_empty":json_bindings?"iso_http_json":"iso_query"),2,args);
}
static void print_answer(PlTerm term) {
  if (!json_bindings) {
    static PlLong serial;
    char *s;
    if(prolog_display) {
      Pl_Query_Begin(PL_TRUE);
      PlTerm args[3]={term,Pl_Mk_Integer(serial++),Pl_Mk_Variable()};
      if(Pl_Query_Call(Pl_Find_Atom("iso_render_prolog"),3,args)!=PL_SUCCESS)exit(2);
      s=strdup(Pl_Atom_Name(Pl_Rd_Atom_Check(args[2])));
      Pl_Query_End(PL_RECOVER);
    } else s=copy_term(term);
    if(!s)exit(2);json_string(s);free(s);return;
  }
  putchar('{');int first=1;
  while (Pl_Type_Of_Term(term)==PL_LST) {
    PlTerm *list=Pl_Rd_List_Check(term);int f,n;
    PlTerm *pair=Pl_Rd_Compound_Check(list[0],&f,&n);
    if (!first) putchar(',');first=0;
    json_string(Pl_Atom_Name(Pl_Rd_Atom_Check(pair[0])));putchar(':');
    json_string(Pl_Atom_Name(Pl_Rd_Atom_Check(pair[1])));
    term=list[1];
  }
  putchar('}');
}
static void error_event(PlTerm term) {
  char *error=copy_term(term);
  printf("{\"type\":\"error\",\"term\":"); json_string(error); puts("}");
  free(error);
}
static int load_source(const char *file,const char *loader) {
  /* A future controller owns this path. Bound trusted local input now;
   * this stat check is not an untrusted-path security boundary. */
  struct stat info;
  if (stat(file,&info) || !S_ISREG(info.st_mode) || info.st_size>1024*1024) {
    puts("{\"type\":\"error\",\"term\":\"source_file_unavailable_or_too_large\"}");
    return 0;
  }
  Pl_Query_Begin(PL_TRUE);
  PlTerm arg=Pl_Mk_Atom(Pl_Create_Atom(file));
  int status=Pl_Query_Call(Pl_Find_Atom(loader),1,&arg);
  if (status==PL_EXCEPTION) error_event(Pl_Get_Exception());
  else if (status!=PL_SUCCESS)
    puts("{\"type\":\"error\",\"term\":\"source_loading_failed\"}");
  /* Asserted source survives recovery; parsing and expansion terms do not. */
  Pl_Query_End(PL_RECOVER);
  return status==PL_SUCCESS;
}
static long heap_used(void) {
  Pl_Query_Begin(PL_TRUE);
  PlTerm a[2]={Pl_Mk_Atom(Pl_Find_Atom("global_stack")),Pl_Mk_Variable()};
  if (Pl_Query_Call(Pl_Find_Atom("statistics"),2,a)!=PL_SUCCESS) exit(2);
  PlTerm *list=Pl_Rd_List_Check(a[1]);
  long n=Pl_Rd_Integer_Check(list[0]);
  Pl_Query_End(PL_RECOVER);
  return n;
}
static int recovery_test(void) {
  const char *text="query(iso_alloc(100),ok)";
  /* Warm up atom interning. This test measures heap, not atom-table memory. */
  Pl_Create_Atom(text);
  long before=heap_used();
  for (int i=0;i<1000;i++) {
    PlTerm a[2];
    Pl_Query_Begin(PL_TRUE);
    a[0]=Pl_Mk_Integer(100);
    if (Pl_Query_Call(Pl_Find_Atom("iso_alloc"),1,a)!=PL_SUCCESS) return 2;
    Pl_Query_End(PL_RECOVER);
  }
  long after=heap_used();
  printf("{\"queries\":1000,\"before\":%ld,\"after\":%ld}\n",before,after);
  return before==after ? 0 : 1;
}
int main(int argc,char **argv) {
  int recovery=argc==2 && !strcmp(argv[1],"--recovery-test");
  int source=argc==5 && !strcmp(argv[3],"--source");
  if (argc!=3 && !recovery && !source) {
    fprintf(stderr,"usage: %s 'query(Goal,Template)' PAGE_SIZE [--source FILE]\n",argv[0]);
    return 2;
  }
  long limit=1;
  if (!recovery) {
    char *end; errno=0; limit=strtol(argv[2],&end,10);
    if (errno || *end || limit<0 || limit>ISO_MAX_PAGE) return 2;
  }
  empty_page=limit==0;
  Pl_Start_Prolog(1,argv);
  json_bindings=getenv("ISO_JSON_BINDINGS")!=NULL;
  prolog_display=getenv("ISO_PROLOG_DISPLAY")!=NULL;
  if (recovery) { int rc=recovery_test(); Pl_Stop_Prolog(); return rc; }
  const char *shared=getenv("ISO_SHARED_DB");
  if (shared) {
    Pl_Query_Begin(PL_TRUE);
    PlTerm mode=Pl_Mk_Atom(Pl_Create_Atom("compiled"));
    int compiled=Pl_Query_Call(Pl_Find_Atom("iso_shared_mode"),1,&mode)==PL_SUCCESS;
    Pl_Query_End(PL_RECOVER);
    if(compiled) {
      puts("{\"type\":\"error\",\"term\":\"compiled_shared_database_cannot_be_overlaid\"}");
      Pl_Stop_Prolog();return 0;
    }
  }
  if (shared && !load_source(shared,"iso_load_shared")) { Pl_Stop_Prolog(); return 0; }
  if (source && !load_source(argv[4],"iso_load_source")) { Pl_Stop_Prolog(); return 0; }
  PlTerm a[2]; int status=begin(argv[1],a);
  const char *offset_text=getenv("ISO_OFFSET");
  long offset=offset_text?strtol(offset_text,NULL,10):0;
  while (offset-->0 && status==PL_SUCCESS) status=Pl_Query_Next_Solution();
  for (;;) {
    if (status==PL_EXCEPTION) {
      error_event(Pl_Get_Exception()); break;
    }
    if (status==PL_FAILURE) { puts("{\"type\":\"failure\"}"); break; }
    /* Hold at most a page of serialized answers; no Prolog answer list. */
    printf("{\"type\":\"success\",\"answers\":[");
    long count=0;
    do {
      if (count) putchar(',');
      print_answer(a[1]);count++;
      status=Pl_Query_Next_Solution();
    } while (count<limit && status==PL_SUCCESS);
    printf("],\"more\":%s}\n",status==PL_FAILURE ? "false" : "true");
    fflush(stdout);
    if (status==PL_FAILURE) break;
    /* A pending exception is a continuation event, not a lost answer. */
    char command[32];
    if (!fgets(command,sizeof command,stdin) || !strcmp(command,"stop\n")) break;
    if (!strncmp(command,"next ",5)) {
      char *end;errno=0;long next=strtol(command+5,&end,10);
      if (errno || *end!='\n' || end[1] || next<0 || next>ISO_MAX_PAGE) {
        puts("{\"type\":\"protocol_error\"}");break;
      }
      limit=next;
      if(limit==0){puts("{\"type\":\"failure\"}");break;}
    } else if (strcmp(command,"next\n")) {
      puts("{\"type\":\"protocol_error\"}"); break;
    }
  }
  Pl_Query_End(PL_RECOVER);
  Pl_Stop_Prolog();
  return 0;
}
