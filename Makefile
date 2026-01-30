.PHONY: help install install-dev format lint type-check test test-cov clean pre-commit setup

help:
	@echo "Available commands:"
	@echo "  make install       - Install production dependencies"
	@echo "  make install-dev   - Install development dependencies"
	@echo "  make setup         - Complete setup (install-dev + pre-commit)"
	@echo "  make format        - Format code with black and ruff"
	@echo "  make lint          - Run ruff linter"
	@echo "  make type-check    - Run mypy type checker"
	@echo "  make test          - Run tests with pytest"
	@echo "  make test-cov      - Run tests with coverage report"
	@echo "  make pre-commit    - Run pre-commit hooks on all files"
	@echo "  make clean         - Remove build artifacts and cache files"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

setup: install-dev
	pre-commit install
	@echo "✅ Development environment setup complete!"
	@echo "   Pre-commit hooks installed"
	@echo "   Run 'make test' to verify everything works"

format:
	black .
	ruff check --fix .

lint:
	ruff check .

type-check:
	mypy *.py

test:
	pytest

test-cov:
	pytest --cov=. --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/index.html"

pre-commit:
	pre-commit run --all-files

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	@echo "✅ Cleaned build artifacts and cache files"
