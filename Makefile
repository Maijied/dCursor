.PHONY: build clean install-local uninstall-local fetch-cursor

build:
	./build.sh

fetch-cursor:
	chmod +x scripts/ci-fetch-cursor.sh && ./scripts/ci-fetch-cursor.sh

build-ci: fetch-cursor
	./build.sh

clean:
	rm -rf build dist /tmp/dcursor-build.*

install-local: build
	chmod +x scripts/install.sh && ./scripts/install.sh

uninstall-local:
	sudo dpkg -r dcursor || true
