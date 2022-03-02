# Simple "scripts" for development / administration

.PHONY: deploy push
deploy: push
push:
	./push.sh

.PHONY: upgrade upgrade-requirements
upgrade: upgrade-requirements
upgrade-requirements:
	upgrade-requirements

venv:
	rm -rf venv
	python -m venv venv
	venv/bin/pip install -r requirements.txt -r requirements-dev.txt

.PHONY: notebook
notebook:
	PYTHONPATH="$(shell pwd)" venv/bin/jupyter lab --notebook-dir=notebooks
