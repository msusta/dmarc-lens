# Makefile for DMARC Lens development

.PHONY: help install test lint format format-check type-check ci clean deploy destroy

# Default target
help:
	@echo "DMARC Lens Development Commands"
	@echo "==============================="
	@echo ""
	@echo "Setup Commands:"
	@echo "  install        Install all dependencies"
	@echo ""
	@echo "Development Commands:"
	@echo "  test           Run all tests"
	@echo "  lint           Run code linting"
	@echo "  format         Format code with black"
	@echo "  format-check   Check code formatting"
	@echo "  type-check     Run type checking with mypy"
	@echo "  ci             Run all CI checks locally"
	@echo ""
	@echo "Infrastructure Commands:"
	@echo "  deploy         Deploy infrastructure to AWS"
	@echo "  destroy        Destroy infrastructure"
	@echo ""
	@echo "Utility Commands:"
	@echo "  clean          Clean build artifacts"

# Install dependencies
install:
	@echo "Installing dependencies..."
	uv sync --group dev --group cdk

# Run tests
test:
	@echo "Running tests..."
	uv run pytest

# Run linting
lint:
	@echo "Running linting..."
	uv run flake8 src/ tests/

# Format code
format:
	@echo "Formatting code..."
	uv run black src/ tests/

# Check code formatting
format-check:
	@echo "Checking code formatting..."
	uv run black --check src/ tests/

# Type checking
type-check:
	@echo "Running type checking..."
	uv run mypy src/dmarc_lens --ignore-missing-imports

# Run all CI checks locally
ci: lint format-check type-check test
	@echo "All CI checks passed!"

# Deploy infrastructure
deploy:
	@echo "Deploying infrastructure..."
	cd infrastructure && npx cdk deploy --all

# Destroy infrastructure
destroy:
	@echo "Destroying infrastructure..."
	cd infrastructure && npx cdk destroy --all

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/
	@rm -rf infrastructure/cdk.out/
