% Example owner-supplied ISOBASE shared database.
human(socrates).
human(plato).
human(aristotle).

list_price(widget,100).
list_price(gadget,250).
price(Item,Price) :- list_price(Item,Price).
