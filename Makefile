.PHONY: check sums

check:
	./scripts/check.sh
	./scripts/check_conform.sh

sums:
	cd schemas && sha256sum *.schema.json > SHA256SUMS
