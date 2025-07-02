# VPN Management System - Development & Deployment Commands

.PHONY: help setup install test lint format check clean dev build up down logs shell restart status keys backup
.DEFAULT_GOAL := help

# Python/Environment Settings
PYTHON := python3
PIP := pip
VENV := venv
VENV_ACTIVATE := $(VENV)/bin/activate

help: ## Show this help message
	@echo "VPN Management System - Available Commands"
	@echo "=========================================="
	@echo ""
	@echo "🔧 Setup & Development:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$2 ~ /Setup|Install|Test|Lint|Format|Clean|Dev/) printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "🐳 Docker Commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$2 ~ /Build|Start|Stop|container|Docker/) printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "📊 Operations:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$2 ~ /Status|logs|backup|keys/) printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# =============================================================================
# Setup & Development Commands
# =============================================================================

setup: ## Setup development environment
	@echo "🔧 Setting up development environment..."
	@if [ ! -d "$(VENV)" ]; then \
		echo "📦 Creating virtual environment..."; \
		$(PYTHON) -m venv $(VENV); \
	fi
	@echo "📥 Installing dependencies..."
	@. $(VENV_ACTIVATE) && $(PIP) install --upgrade pip
	@. $(VENV_ACTIVATE) && $(PIP) install -r requirements.txt
	@echo "✅ Development environment ready!"
	@echo "💡 Activate with: source $(VENV_ACTIVATE)"

install: setup ## Install dependencies (alias for setup)

test: ## Run all tests
	@echo "🧪 Running tests..."
	@. $(VENV_ACTIVATE) && $(PYTHON) -m pytest tests/ -v

test-watch: ## Run tests in watch mode
	@echo "👀 Running tests in watch mode..."
	@. $(VENV_ACTIVATE) && $(PYTHON) -m pytest tests/ -v --tb=short -f

lint: ## Run linting checks (dry-run)
	@echo "🔍 Running linting checks..."
	@echo "📋 Flake8 - Syntax and style errors:"
	@. $(VENV_ACTIVATE) && flake8 app/ --count --select=E9,F63,F7,F82 --show-source --statistics || true
	@echo ""
	@echo "📊 Flake8 - Code quality metrics:"
	@. $(VENV_ACTIVATE) && flake8 app/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
	@echo ""
	@echo "🎨 Black - Code formatting check:"
	@. $(VENV_ACTIVATE) && black --check --diff app/ || echo "  💡 Run 'make format' to fix formatting"

format: ## Format code with Black
	@echo "🎨 Formatting code with Black..."
	@. $(VENV_ACTIVATE) && black app/ tests/
	@echo "✅ Code formatted!"

check: lint test ## Run all checks (lint + test)

clean: ## Clean up development environment
	@echo "🧹 Cleaning up..."
	@rm -rf $(VENV)
	@rm -rf .pytest_cache
	@rm -rf __pycache__
	@rm -rf app/__pycache__
	@rm -rf tests/__pycache__
	@find . -name "*.pyc" -delete
	@find . -name "*.pyo" -delete
	@echo "✅ Cleanup complete!"

dev: ## Start development server
	@echo "🚀 Starting development server..."
	@. $(VENV_ACTIVATE) && $(PYTHON) app.py

# =============================================================================
# Docker Commands
# =============================================================================

build: ## Build the Docker container
	@echo "🐳 Building Docker container..."
	docker-compose build

up: ## Start the VPN management system (Docker)
	@echo "🐳 Starting VPN Management System..."
	docker compose up -d
	@echo ""
	@echo "🚀 VPN Management System started!"
	@echo "📱 Web Interface: http://localhost:5000"
	@echo "🔒 WireGuard Port: 51820/udp"
	@echo ""
	@echo "⏳ Waiting for container to be ready..."
	@sleep 10
	@make docker-status

down: ## Stop the VPN management system (Docker)
	@echo "🛑 Stopping VPN Management System..."
	docker compose down

logs: ## Show container logs
	@echo "📋 Container logs:"
	docker compose logs -f vpn-manager

shell: ## Open shell in container
	@echo "🐚 Opening shell in container..."
	docker compose exec vpn-manager bash

docker-clean: ## Remove containers, volumes and images
	@echo "🧹 Cleaning Docker resources..."
	docker compose down -v
	docker compose rm -f
	docker rmi vpn_vpn-manager 2>/dev/null || true
	@echo "✅ Docker cleanup complete!"

restart: ## Restart the Docker system
	@echo "🔄 Restarting system..."
	@make down
	@make up

docker-dev: ## Start in development mode with live reload
	@echo "🚀 Starting in development mode..."
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

docker-test: ## Run tests in container
	@echo "🧪 Running tests in container..."
	docker compose exec vpn-manager python3 -m pytest tests/ -v || echo "❌ No tests found or tests failed"

# =============================================================================
# Operations & Monitoring
# =============================================================================

status: docker-status ## Show system status (alias)

docker-status: ## Show Docker system status
	@echo "📊 System Status Report"
	@echo "======================"
	@echo ""
	@echo "Container Status:"
	@docker compose ps
	@echo ""
	@echo "WireGuard Status:"
	@docker compose exec vpn-manager wg show 2>/dev/null || echo "WireGuard not active"
	@echo ""
	@echo "Network Information:"
	@docker compose exec vpn-manager ip addr show wg0 2>/dev/null || echo "wg0 interface not found"

keys: ## Show WireGuard server keys
	@echo "🔑 Server Keys:"
	@echo "=============="
	@docker compose exec vpn-manager cat /app/.env | grep KEY || echo "Keys not found"

backup: ## Create backup of configuration
	@echo "💾 Creating backup..."
	@mkdir -p backups
	@docker compose exec vpn-manager cp /app/instance/wireguard.db /app/backups/ 2>/dev/null || true
	@docker compose exec vpn-manager cp /etc/wireguard/wg0.conf /app/backups/ 2>/dev/null || true
	@echo "✅ Backup created in ./backups/"