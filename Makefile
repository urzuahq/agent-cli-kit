.PHONY: check sums

check:
	./scripts/check.sh

sums:
	cd schemas && sha256sum *.schema.json > SHA256SUMS
