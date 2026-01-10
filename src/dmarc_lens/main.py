"""
Main CLI entry point for DMARC Lens.
"""

import argparse
import sys
from typing import Optional

from dmarc_lens import __version__


def main(argv: Optional[list] = None) -> int:
    """
    Main entry point for the DMARC Lens CLI.
    
    Args:
        argv: Command line arguments (defaults to sys.argv)
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = argparse.ArgumentParser(
        description="DMARC Lens - Analyze and visualize DMARC email security reports"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"DMARC Lens {__version__}"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Parse command (placeholder for future implementation)
    parse_parser = subparsers.add_parser("parse", help="Parse DMARC reports")
    parse_parser.add_argument("file", help="DMARC report file to parse")
    
    # Analyze command (placeholder for future implementation)
    analyze_parser = subparsers.add_parser("analyze", help="Analyze DMARC data")
    analyze_parser.add_argument("--domain", help="Domain to analyze")
    
    args = parser.parse_args(argv)
    
    if not args.command:
        parser.print_help()
        return 1
    
    # TODO: Implement command handlers in subsequent tasks
    print(f"Command '{args.command}' not yet implemented")
    return 0


if __name__ == "__main__":
    sys.exit(main())