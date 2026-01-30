# Contributing to Project Management

Thank you for your interest in contributing! This document provides guidelines
and instructions for contributing to this project.

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- Make (optional, but recommended)

### Quick Setup

```bash
# Clone the repository
git clone <repository-url>
cd project-management

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies and setup pre-commit hooks
make setup

# Or manually:
pip install -e ".[dev]"
pre-commit install
```

## Development Workflow

### 1. Code Formatting

We use `black` for code formatting and `ruff` for linting:

```bash
# Format all code
make format

# Or manually:
black .
ruff check --fix .
```

### 2. Type Checking

We use `mypy` for static type checking:

```bash
make type-check

# Or manually:
mypy *.py
```

### 3. Running Tests

```bash
# Run all tests
make test

# Run tests with coverage report
make test-cov

# Run specific test file
pytest tests/test_issue_parser.py

# Run specific test
pytest tests/test_issue_parser.py::test_issue_creation
```

### 4. Pre-commit Hooks

Pre-commit hooks run automatically before each commit. To run them manually:

```bash
make pre-commit

# Or manually:
pre-commit run --all-files
```

## Code Standards

### Python Style Guide

- Follow PEP 8
- Maximum line length: 100 characters
- Use type hints where appropriate
- Write docstrings for all public functions and classes

### Commit Messages

Follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Example:**

```
feat(scheduler): add validation for negative durations

Add ValueError when task duration is negative to prevent
invalid scheduling scenarios.

Closes #123
```

### Testing Guidelines

1. **Write tests for new features**

   - Unit tests for individual functions
   - Integration tests for workflows

1. **Maintain test coverage**

   - Aim for >80% coverage
   - Critical paths should have 100% coverage

1. **Test naming convention**

   - `test_<function_name>_<scenario>`
   - Example: `test_schedule_task_with_dependencies`

1. **Use fixtures**

   - Define reusable test data in `conftest.py`
   - Keep tests DRY (Don't Repeat Yourself)

### Documentation

1. **Docstrings**

   ```python
   def function_name(param1: str, param2: int) -> bool:
       """
       Brief description of function.

       Args:
           param1: Description of param1
           param2: Description of param2

       Returns:
           Description of return value

       Raises:
           ValueError: When param2 is negative
       """
   ```

1. **README Updates**

   - Update README.md when adding new features
   - Include usage examples
   - Update configuration sections

1. **Architecture Documentation**

   - Update ARCHITECTURE.md for significant changes
   - Document design decisions
   - Explain trade-offs

## Pull Request Process

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Changes

- Write code following style guidelines
- Add/update tests
- Update documentation
- Run pre-commit hooks

### 3. Commit Changes

```bash
git add .
git commit -m "feat(module): description"
```

### 4. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:

- Clear description of changes
- Link to related issues
- Screenshots (if UI changes)
- Test results

### 5. Code Review

- Address review comments
- Keep commits clean (squash if needed)
- Ensure CI passes

## Project Structure

```
project-management/
├── jira_client.py           # Jira API client
├── issue_parser.py          # Issue parsing & graphs
├── scheduler.py             # Task scheduling
├── dag_exporter.py          # Graph visualization
├── epic_timeline_estimator.py  # Main tool 1
├── engineer_optimization.py    # Main tool 2
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── conftest.py         # Shared fixtures
│   ├── test_issue_parser.py
│   └── test_scheduler.py
├── pyproject.toml          # Project configuration
├── .pre-commit-config.yaml # Pre-commit hooks
├── Makefile                # Development commands
└── README.md               # User documentation
```

## Common Tasks

### Adding a New Feature

1. Create feature branch
1. Write tests first (TDD)
1. Implement feature
1. Update documentation
1. Run full test suite
1. Submit PR

### Fixing a Bug

1. Create issue describing bug
1. Write test that reproduces bug
1. Fix the bug
1. Verify test passes
1. Submit PR referencing issue

### Updating Dependencies

```bash
# Update a specific package
pip install --upgrade package-name

# Update pyproject.toml
# Test thoroughly
# Update requirements.txt if needed
```

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help others learn and grow

## License

By contributing, you agree that your contributions will be licensed under the
MIT License.

______________________________________________________________________

Thank you for contributing! 🎉
