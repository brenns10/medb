# Simple "scripts" for development / administration

.PHONY: deploy push
deploy: push
push:
	./push.sh

.PHONY: upgrade upgrade-requirements
upgrade: upgrade-requirements
upgrade-requirements:
	pipenv update

.PHONY: venv
venv: .venv
.venv:
	pipenv sync -d
