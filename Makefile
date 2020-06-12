test:
	python3 setup.py test
	$(MAKE) test-sdist
	codespell -d $$(git ls-files \
	                | grep -v "\.bin" \
	                | grep -v "\.png" \
	                | grep -v "\.s19\.txt" \
	                | grep -v "\.hex\.txt")

test-sdist:
	rm -rf dist
	python3 setup.py sdist
	cd dist && \
	mkdir test && \
	cd test && \
	tar xf ../*.tar.gz && \
	cd bincopy-* && \
	python3 setup.py test

release-to-pypi:
	python3 setup.py sdist
	python3 setup.py bdist_wheel --universal
	twine upload dist/*
