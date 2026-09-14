.PHONY: test run smoke
run:
	python run.py
test:
	pytest
smoke:
	bash scripts/smoke.sh
