# Makefile for DMARC Lens development

.PHONY: help setup install test lint format type-check clean deploy destroy

# Default target
help:
	@echo "DMARC Lens Development Commands"
	@echo "==============================="
	@echo ""
	@echo "Setup Commands:"
	@echo "  setup          Set up development environment"
	@echo "  install        Install dependencies"
	@echo ""
	@echo "Development Commands:"
	@echo "  test           Run all tests"
	@echo "  lint           Run code linting"
	@echo "  format         Format code with black"
	@echo "  type-check     Run type checking with mypy"
	@echo ""
	@echo "Infrastructure Commands:"
	@echo "  deploy         Deploy infrastructure to AWS"
	@echo "  destroy        Destroy infrastructure"
	@echo ""
	@echo "Utility Commands:"
	@echo "  clean          Clean build artifacts"

# Setup development environment
setup:
	@echo "Setting up development environment..."
	@./scripts/setup-dev.sh

# Install dependencies
install:
	@echo "Installing dependencies..."
	@source venv/bin/activate && pip install -r requirements-dev.txt
	@source venv/bin/activate && pip install -r requirements-cdk.txt
	@source venv/bin/activate && pip install -e .

# Run tests
test:
	@echo "Running tests..."
	@source venv/bin/activate && pytest

# Run linting
lint:
	@echo "Running linting..."
	@source venv/bin/activate && flake8 src/ tests/

# Format code
format:
	@echo "Formatting code..."
	@source venv/bin/activate && black src/ tests/

# Type checking
type-check:
	@echo "Running type checking..."
	@source venv/bin/activate && mypy src/

# Deploy infrastructure
deploy:
	@echo "Deploying infrastructure..."
	@cd infrastructure && ../scripts/deploy.sh

# Destroy infrastructure
destroy:
	@echo "Destroying infrastructure..."
	@cd infrastructure && source ../venv/bin/activate && npx cdk destroy

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/
	@rm -rf infrastructure/cdk.out/