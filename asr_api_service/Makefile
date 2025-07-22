.PHONY: help install install-dev test test-cov lint format clean build run docker-build docker-run

# Default target
help:
	@echo "Available commands:"
	@echo "  install      - Install the package"
	@echo "  install-dev  - Install the package with development dependencies"
	@echo "  test         - Run tests"
	@echo "  test-cov     - Run tests with coverage"
	@echo "  lint         - Run linting checks"
	@echo "  format       - Format code with black and isort"
	@echo "  clean        - Clean build artifacts"
	@echo "  build        - Build the package"
	@echo "  run          - Run the development server"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

# Testing
test:
	pytest

test-cov:
	pytest --cov=src --cov-report=html --cov-report=term

# Code quality
lint:
	flake8 src/ tests/
	mypy src/

format:
	black src/ tests/
	isort src/ tests/

# Maintenance
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:
	python -m build

# Development
run:
	asr-api serve --reload --log-level debug

run-prod:
	asr-api serve --workers 4

# Docker
docker-build:
	docker build -t asr-api-service .

docker-run:
	docker run -p 8000:8000 --env-file .env asr-api-service

docker-compose-up:
	docker-compose up -d

docker-compose-down:
	docker-compose down

# Database/migrations (if needed in future)
migrate:
	# Placeholder for database migrations
	@echo "No migrations needed currently"

# Documentation
docs:
	mkdocs serve

docs-build:
	mkdocs build

# Security
security-check:
	pip-audit
	safety check

# Full development setup
setup-dev: install-dev
	pre-commit install
	@echo "Development environment ready!"

# CI/CD helpers
ci-test: install-dev lint test-cov
	@echo "CI tests passed!"

# Release helpers
version-patch:
	bump2version patch

version-minor:
	bump2version minor

version-major:
	bump2version major