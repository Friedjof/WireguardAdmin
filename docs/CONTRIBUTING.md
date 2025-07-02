# Contributing to WireGuard Management System

We love your input! We want to make contributing to this project as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## Development Process

We use GitHub to host code, to track issues and feature requests, as well as accept pull requests.

### Pull Requests Process

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
6. Issue that pull request!

## Any contributions you make will be under the MIT Software License

In short, when you submit code changes, your submissions are understood to be under the same [MIT License](http://choosealicense.com/licenses/mit/) that covers the project. Feel free to contact the maintainers if that's a concern.

## Report bugs using GitHub's [issue tracker](https://github.com/your-username/wireguard-management/issues)

We use GitHub issues to track public bugs. Report a bug by [opening a new issue](https://github.com/your-username/wireguard-management/issues/new).

### Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

## Development Setup

### Prerequisites

- Python 3.8+
- Docker and Docker Compose
- WireGuard tools
- Git

### Local Development

```bash
# Clone your fork
git clone https://github.com/your-username/wireguard-management.git
cd wireguard-management

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Setup pre-commit hooks
pre-commit install

# Copy environment template
cp .env.example .env
# Edit .env with your configuration

# Run tests
python -m pytest

# Start development server
python app.py
```

### Code Style

We use the following tools to maintain code quality:

- **Black** for code formatting
- **flake8** for linting
- **mypy** for type checking
- **bandit** for security analysis

Run before committing:

```bash
# Format code
black app/ tests/

# Lint code
flake8 app/ tests/

# Type checking
mypy app/

# Security check
bandit -r app/
```

### Testing

We aim for high test coverage. Please include tests for new functionality:

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=app

# Run specific test file
python -m pytest tests/test_models.py

# Run integration tests
python -m pytest tests/integration/
```

### Documentation

- Update README.md for new features
- Add docstrings to new functions/classes
- Update API documentation for new endpoints
- Add examples for new functionality

## Coding Standards

### Python Code

- Follow PEP 8 style guide
- Use type hints where appropriate
- Write clear, descriptive variable and function names
- Add docstrings to all public functions and classes
- Keep functions small and focused

### Frontend Code

- Use modern JavaScript (ES6+)
- Follow consistent indentation (2 spaces)
- Use meaningful variable names
- Add comments for complex logic
- Test in multiple browsers

### Database Changes

- Create migration scripts for schema changes
- Test migrations both up and down
- Document any breaking changes
- Consider backward compatibility

## Security Considerations

This project handles VPN configurations and firewall rules, so security is paramount:

- Never commit real private keys or sensitive data
- Validate all user inputs
- Use parameterized queries for database operations
- Follow principle of least privilege
- Document security implications of changes

## Feature Development

### Before starting work on a new feature:

1. Check if there's already an issue for it
2. If not, create an issue to discuss the feature
3. Wait for feedback from maintainers
4. Create a branch from `main`
5. Implement the feature
6. Add tests
7. Update documentation
8. Submit a pull request

### Feature Branch Naming

Use descriptive branch names:

- `feature/websocket-monitoring`
- `bugfix/peer-deletion-error`
- `docs/api-documentation`
- `refactor/database-models`

### Commit Messages

Write clear commit messages:

```
Add real-time traffic monitoring via WebSockets

- Implement WebSocket manager for live updates
- Add traffic graph visualization with Chart.js
- Update frontend to handle real-time data
- Add configuration for update intervals

Fixes #123
```

## Release Process

1. Update version in `app/__init__.py`
2. Update CHANGELOG.md
3. Create release tag
4. Build and test Docker image
5. Deploy to staging
6. Deploy to production
7. Create GitHub release

## License

By contributing, you agree that your contributions will be licensed under its MIT License.

## Questions?

Don't hesitate to ask questions by creating an issue or reaching out to the maintainers.

Thank you for contributing! 🎉