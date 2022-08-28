test:
	python3 -m pytest
	$(MAKE) test-sdist

test-sdist:
	rm -rf dist
	python3 setup.py sdist
	cd dist && \
	mkdir test && \
	cd test && \
	tar xf ../*.tar.gz && \
	cd bincopy-* && \
	python3 -m pytest
