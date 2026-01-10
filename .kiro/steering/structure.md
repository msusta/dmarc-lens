# Project Structure

## Current Structure
```
dmarc-lens/
├── .git/                    # Git repository
├── .kiro/                   # Kiro framework configuration
│   ├── settings/
│   │   └── mcp.json        # MCP server configuration
│   └── steering/           # Project steering documents
├── .vscode/
│   └── settings.json       # VS Code workspace settings
```

## Recommended Structure
*Python-based DMARC analysis tool*

```
dmarc-lens/
├── src/
│   ├── dmarc_lens/             # Main package
│   │   ├── __init__.py
│   │   ├── parsers/            # DMARC report parsers
│   │   ├── analyzers/          # Analysis logic
│   │   ├── visualizers/        # Data visualization
│   │   ├── models/             # Data models
│   │   ├── utils/              # Utility functions
│   │   └── main.py             # CLI entry point
├── tests/                      # Test files
│   ├── unit/
│   ├── integration/
│   └── fixtures/               # Test data
├── docs/                       # Documentation
├── scripts/                    # Utility scripts
├── requirements.txt            # Python dependencies
├── setup.py                    # Package setup
├── .kiro/                      # Kiro configuration
├── .vscode/                    # VS Code settings
└── README.md                   # Project documentation
```

## Organization Principles
- Keep source code in `src/dmarc_lens/` package
- Separate concerns with dedicated modules for parsing, analysis, and visualization
- Use type hints throughout for better code quality
- Follow PEP 8 style guidelines
- Maintain clear separation between data models and business logic

## File Naming Conventions
- Use snake_case for Python files and directories
- Use PascalCase for class names
- Use UPPER_CASE for constants
- Prefix test files with `test_`