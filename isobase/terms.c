/* List-spine inspection must use cell identity: GNU's structural == can
 * recurse forever on rational trees. Element contents are deliberately ignored. */
#define __GPROLOG_FOREIGN_STRICT__
#include "gprolog.h"
static const char *terminal(PlTerm t) {
  int type=Pl_Type_Of_Term(t);
  if(type==PL_REF)return "open";
  if(type==PL_LST)return 0;
  return type==PL_ATM && Pl_Rd_Atom(t)==Pl_Atom_Nil() ? "proper" : "improper";
}
PlBool iso_native_spine_kind(PlTerm list,PlTerm kind) {
  PlTerm fast=list,slow=list;
  for(;;) {
    for(int i=0;i<2;i++) {
      const char *end=terminal(fast);
      if(end)return Pl_Un_String((char *)end,kind);
      fast=Pl_Rd_List(fast)[1];
    }
    slow=Pl_Rd_List(slow)[1];
    if(Pl_Type_Of_Term(fast)==PL_LST && Pl_Type_Of_Term(slow)==PL_LST &&
       Pl_Rd_List(fast)==Pl_Rd_List(slow))return Pl_Un_String("cyclic",kind);
  }
}

/* Native text conversion can return infinities without an arithmetic error. */
#include <math.h>
PlBool iso_finite_number(PlTerm value) {
  return Pl_Type_Of_Term(value)!=PL_FLT || isfinite(Pl_Rd_Float(value));
}

/* Shortest significant-digit spelling that round-trips through the native
 * decimal reader. The worker uses the C locale. Keep a decimal point so
 * integer-valued floats remain floats when read back. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
PlBool iso_float_codes(PlTerm number, PlTerm codes) {
  double value=Pl_Rd_Float(number);
  if(!isfinite(value))return PL_FALSE;
  char raw[64],out[68];
  for(int precision=1;precision<=17;precision++) {
    snprintf(raw,sizeof(raw),"%.*g",precision,value);
    double parsed=strtod(raw,NULL);
    if(parsed==value && signbit(parsed)==signbit(value))break;
  }
  char *exponent=strchr(raw,'e');
  if(strchr(raw,'.'))return Pl_Un_Codes(raw,codes);
  if(exponent) {
    size_t prefix=(size_t)(exponent-raw);
    memcpy(out,raw,prefix);
    snprintf(out+prefix,sizeof(out)-prefix,".0%s",exponent);
  } else snprintf(out,sizeof(out),"%s.0",raw);
  return Pl_Un_Codes(out,codes);
}

/* Preserve IEEE signed-zero quadrants, rejected by GNU's native atan2. */
PlBool iso_atan2_zero(PlTerm y, PlTerm x, PlTerm result) {
  return Pl_Un_Float(atan2(Pl_Rd_Number(y),Pl_Rd_Number(x)),result);
}
