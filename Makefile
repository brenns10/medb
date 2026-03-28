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

SPEEDTEST_VER="1.2.0"
FAST_VER="0.2.10"
.PHONY: utils
utils:
	wget -nc -P ./utils \
		"https://install.speedtest.net/app/cli/ookla-speedtest-${SPEEDTEST_VER}-linux-x86_64.tgz" \
		"https://github.com/gesquive/fast-cli/releases/download/v${FAST_VER}/fast-cli-v${FAST_VER}-linux-amd64.tar.gz"
	tar -C ./utils -xf "./utils/ookla-speedtest-${SPEEDTEST_VER}-linux-x86_64.tgz" speedtest
	tar -C ./utils -xf "./utils/fast-cli-v${FAST_VER}-linux-amd64.tar.gz" fast-cli
	sha256sum -c utils.checksum.txt
