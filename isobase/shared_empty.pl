% Default build: shared clauses are loaded from the startup snapshot.
iso_shared_mode(interpreted).
iso_native_shared(_,_,_) :- fail.

iso_native_clause(_,_) :- fail.
