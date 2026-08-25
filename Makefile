.PHONY: build clean install-local uninstall-local fetch-cursor build-ci deps audit

build:
	./build.sh

fetch-cursor:
	chmod +x scripts/ci-fetch-cursor.sh && ./scripts/ci-fetch-cursor.sh

build-ci: fetch-cursor
	DCURSOR_STRICT_BUILD=1 ./build.sh

deps:
	sudo apt-get update
	sudo apt-get install -y \
		python3 python3-pil \
		dpkg-dev librsvg2-bin jq curl \
		ffmpeg imagemagick ripgrep

audit:
	chmod +x scripts/audit-isolation.sh
	./scripts/audit-isolation.sh $${DCURSOR_APP_ROOT:-/tmp/dcursor-build/staging/usr/share/dcursor}

clean:
	rm -rf build dist /tmp/dcursor-build.*

install-local: build
	chmod +x scripts/install.sh && ./scripts/install.sh

uninstall-local:
	sudo dpkg -r dcursor || true
