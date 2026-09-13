#include <stdio.h>
#include "gprolog.h"
int main(int argc,char **argv) {
  if(argc!=3){fprintf(stderr,"usage: shared-compiler INPUT OUTPUT\n");return 2;}
  Pl_Start_Prolog(1,argv);Pl_Query_Begin(PL_TRUE);
  PlTerm a[2]={Pl_Mk_Atom(Pl_Create_Atom(argv[1])),Pl_Mk_Atom(Pl_Create_Atom(argv[2]))};
  int status=Pl_Query_Call(Pl_Find_Atom("iso_compile_shared"),2,a);
  if(status==PL_EXCEPTION)fprintf(stderr,"%s\n",Pl_Write_Canonical_To_String(Pl_Get_Exception()));
  else if(status!=PL_SUCCESS)fprintf(stderr,"Shared database compilation failed\n");
  Pl_Query_End(PL_RECOVER);Pl_Stop_Prolog();return status==PL_SUCCESS?0:1;
}
