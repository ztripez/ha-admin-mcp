# Contributing to HA MCP Admin

Thank you for your interest in contributing to HA MCP Admin!

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/ztripez/ha-admin-mcp.git
   cd ha-admin-mcp
   ```

2. **Install in Home Assistant**
   
   For development, symlink the component to your Home Assistant config:
   ```bash
   ln -s $(pwd)/custom_components/ha_mcp_admin ~/.homeassistant/custom_components/ha_mcp_admin
   ```
   
   Then restart Home Assistant.

3. **Set up testing environment**
   
   You'll need:
   - A running Home Assistant instance (local or accessible)
   - A long-lived access token for testing
   - Python 3.12+ for running test scripts

## Testing

### Smoke Tests

Basic connectivity and single tool test:

```bash
python custom_components/ha_mcp_admin/scripts/mcp_smoke_test.py \
  --url http://localhost:8123/api/mcp_admin \
  --token YOUR_TOKEN
```

### Regression Tests

Full test suite (read-only by default):

```bash
python custom_components/ha_mcp_admin/scripts/mcp_regression_test.py \
  --url http://localhost:8123/api/mcp_admin \
  --token YOUR_TOKEN
```

Full lifecycle tests (includes writes):

```bash
python custom_components/ha_mcp_admin/scripts/mcp_regression_test.py \
  --url http://localhost:8123/api/mcp_admin \
  --token YOUR_TOKEN \
  --allow-destructive
```

## Code Style

This project follows Home Assistant's coding standards:

- **Python**: 3.12+
- **Style**: Black formatting, isort for imports
- **Type hints**: Required for all functions and methods
- **Docstrings**: Required for all public methods
- **Async/await**: Use async operations for all I/O

### Running Linters

If you're developing in the home-assistant-core environment:

```bash
# From home-assistant-core root
pylint custom_components/ha_mcp_admin
mypy custom_components/ha_mcp_admin
```

## Adding New Tools

To add a new MCP tool:

1. **Create or update a tool file** in `custom_components/ha_mcp_admin/tools/`

2. **Define the tool schema** with proper type hints:
   ```python
   async def my_new_tool(
       hass: HomeAssistant,
       param1: str,
       param2: int | None = None,
   ) -> dict[str, Any]:
       """Description of what this tool does."""
       # Implementation
   ```

3. **Register the tool** in `custom_components/ha_mcp_admin/tools/__init__.py`:
   ```python
   from .my_module import my_new_tool
   
   TOOLS = [
       # ... existing tools ...
       my_new_tool,
   ]
   ```

4. **Add tests** in the regression test suite

## Submitting Changes

1. **Fork the repository** on GitHub

2. **Create a feature branch**
   ```bash
   git checkout -b feature/my-new-feature
   ```

3. **Make your changes**
   - Follow code style guidelines
   - Add tests for new functionality
   - Update documentation if needed

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add feature: description of changes"
   ```
   
   Commit message format:
   - Use imperative mood ("Add feature" not "Added feature")
   - First line: brief summary (50 chars or less)
   - Blank line, then detailed explanation if needed

5. **Push to your fork**
   ```bash
   git push origin feature/my-new-feature
   ```

6. **Open a Pull Request** on GitHub
   - Describe what the PR does
   - Reference any related issues
   - Include test results if applicable

## Pull Request Guidelines

- Keep changes focused - one feature/fix per PR
- Update documentation for user-facing changes
- Add tests for new functionality
- Ensure all tests pass
- Respond to review feedback promptly

## Bug Reports

When filing a bug report, please include:

- Home Assistant version
- Component version
- Steps to reproduce
- Expected behavior
- Actual behavior
- Relevant logs (with sensitive data removed)

## Feature Requests

For feature requests, please describe:

- The use case for the feature
- How it would work from a user perspective
- Any alternative solutions you've considered

## Questions?

Feel free to open an issue for questions or discussion!

## License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.
