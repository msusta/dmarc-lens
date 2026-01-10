# Technology Stack

## Development Environment
- **Language**: Python 3.8+
- **AI Assistant**: Kiro Agent for development assistance
- **Editor**: VS Code with Kiro integration
- **Version Control**: Git with GitHub remote (msusta/dmarc-lens)

## MCP Integration
- AWS Knowledge MCP Server configured for AWS documentation access
- HTTP-based MCP server at `https://knowledge-mcp.global.api.aws`

## Python Stack
- **Package Management**: uv with pyproject.toml
- **Testing**: pytest for unit and integration tests
- **Linting**: flake8 or ruff for code quality
- **Formatting**: black for code formatting
- **Type Checking**: mypy for static type analysis
- **Lambda Python framework**: Powertools for AWS Lambda

## Common Commands

```bash
# Environment setup
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Development commands
pip install -r requirements.txt  # Install dependencies
python -m pytest                 # Run tests
python -m flake8 src/            # Run linting
python -m black src/             # Format code
python -m mypy src/              # Type checking
python src/main.py               # Run application
```

## Configuration Files
- `.kiro/settings/mcp.json` - MCP server configuration
- `.vscode/settings.json` - VS Code workspace settings
- `.git/config` - Git repository configuration