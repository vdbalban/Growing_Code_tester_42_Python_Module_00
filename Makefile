PYTHON	= python3
TESTER	= tester.py
EXOS	= ex0 ex1 ex2 ex3 ex4 ex5 ex6 ex7

all:
	@$(PYTHON) $(TESTER) all

$(EXOS):
	@$(PYTHON) $(TESTER) $@

.PHONY: all $(EXOS)
