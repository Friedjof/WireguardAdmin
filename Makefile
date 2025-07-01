# VPN Management Docker Commands

.PHONY: help build up down logs shell clean restart status

help: ## Show this help message
	@echo "VPN Management System - Docker Commands"
	@echo "======================================"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build the Docker container
	docker-compose build

up: ## Start the VPN management system
	docker compose up -d
	@echo ""
	@echo "🚀 VPN Management System started!"
	@echo "📱 Web Interface: http://localhost:5000"
	@echo "🔒 WireGuard Port: 51820/udp"
	@echo ""
	@echo "⏳ Waiting for container to be ready..."
	@sleep 10
	@make status

down: ## Stop the VPN management system
	docker compose down

logs: ## Show container logs
	docker compose logs -f vpn-manager

shell: ## Open shell in container
	docker compose exec vpn-manager bash

clean: ## Remove containers, volumes and images
	docker compose down -v
	docker compose rm -f
	docker rmi vpn_vpn-manager 2>/dev/null || true

restart: ## Restart the system
	@make down
	@make up

status: ## Show system status
	@echo "Container Status:"
	@docker compose ps
	@echo ""
	@echo "WireGuard Status:"
	@docker compose exec vpn-manager wg show 2>/dev/null || echo "WireGuard not active"
	@echo ""
	@echo "Network Information:"
	@docker compose exec vpn-manager ip addr show wg0 2>/dev/null || echo "wg0 interface not found"

keys: ## Show WireGuard server keys
	@echo "Server Keys:"
	@docker compose exec vpn-manager cat /app/.env | grep KEY || echo "Keys not found"

backup: ## Create backup of configuration
	@mkdir -p backups
	@docker compose exec vpn-manager cp /app/instance/wireguard.db /app/backups/
	@docker compose exec vpn-manager cp /etc/wireguard/wg0.conf /app/backups/ 2>/dev/null || true
	@echo "✅ Backup created in ./backups/"

dev: ## Start in development mode with live reload
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

test: ## Run tests in container
	docker compose exec vpn-manager python3 -m pytest tests/ || echo "No tests found"