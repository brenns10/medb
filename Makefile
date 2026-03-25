# Simple "scripts" for development / administration

.PHONY: deploy push
deploy: push
push:
	./push.sh

.PHONY: upgrade upgrade-requirements
upgrade: upgrade-requirements
upgrade-requirements:
	uv lock

.PHONY: venv
venv: .venv
.venv:
	uv sync
