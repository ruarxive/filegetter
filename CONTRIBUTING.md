# Contributing to Filegetter

Thank you for your interest in contributing to filegetter! This document provides guidelines and instructions for contributing.

## Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/ruarxive/filegetter.git
cd filegetter
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Install package in development mode
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run with Coverage

```bash
pytest --cov=filegetter --cov-report=html --cov-report=term
```

### Run Specific Test File

```bash
pytest tests/test_storage.py
```

### Run Specific Test

```bash
pytest tests/test_storage.py::TestZipFileStorage::test_zip_storage_initialization
```

## Code Quality

### Formatting

We use **Black** for code formatting:

```bash
black filegetter/ tests/
```

### Import Sorting

We use **isort** for import organization:

```bash
isort filegetter/ tests/
```

### Linting

We use **flake8** for linting:

```bash
flake8 filegetter/
```

### Type Checking

We use **mypy** for static type checking:

```bash
mypy filegetter/
```

### Run All Quality Checks

```bash
black --check filegetter/ tests/
isort --check filegetter/ tests/
flake8 filegetter/
mypy filegetter/
pytest --cov=filegetter --cov-fail-under=80
```

## Pre-commit Hooks

We recommend using pre-commit hooks to ensure code quality:

```bash
# Install pre-commit
pip install pre-commit

# Install the hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## Making Changes

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

- Write clear, concise code
- Add tests for new functionality
- Update documentation as needed
- Follow existing code style

### 3. Test Your Changes

```bash
# Run tests
pytest

# Check coverage
pytest --cov=filegetter --cov-report=term

# Run quality checks
black --check filegetter/ tests/
isort --check filegetter/ tests/
flake8 filegetter/
```

### 4. Commit Your Changes

Use clear, descriptive commit messages:

```bash
git add .
git commit -m "Add feature: brief description of changes"
```

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Pull Request Guidelines

- **Title**: Clear, concise description of changes
- **Description**: Detailed explanation of what and why
- **Tests**: All tests must pass
- **Coverage**: Maintain or improve code coverage
- **Documentation**: Update relevant documentation
- **Changelog**: Add entry to CHANGELOG.md under [Unreleased]

## Coding Standards

### Python Style

- Follow PEP 8
- Use type hints where appropriate
- Maximum line length: 88 characters (Black default)
- Write docstrings for all public functions/classes

### Documentation

- Update README.md for user-facing changes
- Update docstrings for API changes
- Add examples for new features
- Keep CHANGELOG.md current

### Testing

- Write tests for all new code
- Aim for >80% code coverage
- Include unit tests and integration tests
- Test edge cases and error conditions

## Project Structure

```
filegetter/
├── filegetter/           # Main package
│   ├── __init__.py      # Package metadata
│   ├── __main__.py      # CLI entry point
│   ├── core.py          # CLI commands
│   ├── common.py        # Utility functions
│   ├── constants.py     # Constants
│   ├── cmds/            # Command implementations
│   │   └── project.py   # FilegetterBuilder
│   └── storage/         # Storage implementations
│       └── __init__.py  # Storage classes
├── tests/               # Test suite
│   ├── conftest.py     # Pytest fixtures
│   ├── test_*.py       # Test modules
│   └── fixtures/       # Test data
├── examples/            # Usage examples
├── README.md
├── CHANGELOG.md
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

## Adding New Features

### Storage Backends

To add a new storage backend:

1. Create class inheriting from `FileStorage` in `filegetter/storage/__init__.py`
2. Implement required methods: `exists()`, `store()`, `close()`
3. Add tests in `tests/test_storage.py`
4. Update documentation

### Source Types

To add a new source type:

1. Add parsing logic in `FilegetterBuilder.run()` in `filegetter/cmds/project.py`
2. Add tests in `tests/test_project.py`
3. Update configuration documentation in README.md

## Getting Help

- **Issues**: Check existing [GitHub issues](https://github.com/ruarxive/filegetter/issues)
- **Discussions**: Start a [GitHub discussion](https://github.com/ruarxive/filegetter/discussions)
- **Email**: Contact ivan@begtin.tech

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help create a welcoming environment

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
