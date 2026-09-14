.PHONY: run test verify verify-backend verify-frontend verify-deploy smoke
run:
	python run.py
test:
	pytest -q
verify:
	bash scripts/verify-package.sh
verify-backend:
	bash scripts/verify-backend.sh
verify-frontend:
	bash scripts/verify-frontend.sh
verify-deploy:
	bash scripts/verify-deploy.sh
smoke:
	bash scripts/smoke.sh
