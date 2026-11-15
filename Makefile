.PHONY: install test serve doctor demo
install:
	python -m pip install -e '.[dev]'
test:
	python -m pytest -q
serve:
	python -m sourceroi serve
doctor:
	python -m sourceroi doctor
demo:
	python -m sourceroi demo serve --port 8766
