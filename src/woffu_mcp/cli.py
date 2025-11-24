"""
CLI utilities for Woffu MCP Server setup and configuration.
"""

import argparse
import json
import sys
from pathlib import Path


CLAUDE_CODE_CONFIG = ".claude/mcp.json"
CLAUDE_DESKTOP_CONFIG_MAC = "~/Library/Application Support/Claude/claude_desktop_config.json"
CLAUDE_DESKTOP_CONFIG_WIN = "%APPDATA%\\Claude\\claude_desktop_config.json"


def print_banner():
    """Print setup banner."""
    print()
    print("=" * 60)
    print("  Woffu MCP Server - Setup")
    print("=" * 60)
    print()


def print_token_instructions():
    """Print instructions for obtaining the token."""
    print("Para obtener tu token de Woffu:")
    print()
    print("  1. Inicia sesión en https://app.woffu.com")
    print("  2. Abre DevTools (F12)")
    print("  3. Ve a Application → Cookies → https://app.woffu.com")
    print("  4. Busca la cookie 'woffu.token'")
    print("  5. Copia el valor (empieza con 'eyJ...')")
    print()
    print("  O ejecuta en la consola del navegador:")
    print("  document.cookie.split(';').find(c => c.trim().startsWith('woffu.token=')).split('=')[1]")
    print()


def print_userid_instructions():
    """Print instructions for obtaining the user ID."""
    print("Para obtener tu User ID:")
    print()
    print("  - Decodifica el token en https://jwt.io")
    print("  - Busca el campo 'UserId' en el payload")
    print()


def get_user_input(prompt: str, default: str = "") -> str:
    """Get user input with optional default."""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    else:
        while True:
            result = input(f"{prompt}: ").strip()
            if result:
                return result
            print("  Este campo es obligatorio.")


def generate_mcp_config(token: str, user_id: str, base_url: str) -> dict:
    """Generate MCP server configuration."""
    config = {
        "mcpServers": {
            "woffu": {
                "command": "python",
                "args": ["-m", "woffu_mcp.server"],
                "env": {
                    "WOFFU_TOKEN": token,
                    "WOFFU_USER_ID": user_id,
                }
            }
        }
    }

    if base_url != "https://app.woffu.com":
        config["mcpServers"]["woffu"]["env"]["WOFFU_BASE_URL"] = base_url

    return config


def run_setup():
    """Run interactive setup wizard."""
    print_banner()

    # Token
    print_token_instructions()
    token = get_user_input("Pega tu token (woffu.token)")

    if not token.startswith("eyJ"):
        print("\n⚠️  Advertencia: El token debería empezar con 'eyJ' (formato JWT)")
        confirm = input("¿Continuar de todos modos? [s/N]: ").strip().lower()
        if confirm != 's':
            print("Cancelado.")
            return

    print()

    # User ID
    print_userid_instructions()
    user_id = get_user_input("Tu User ID")

    print()

    # Base URL
    base_url = get_user_input(
        "URL base de Woffu",
        default="https://app.woffu.com"
    )

    print()
    print("-" * 60)
    print()

    # Generate config
    config = generate_mcp_config(token, user_id, base_url)
    config_json = json.dumps(config, indent=2)

    print("Configuración generada:")
    print()
    print(config_json)
    print()

    # Ask where to save
    print("¿Dónde quieres guardar la configuración?")
    print()
    print("  1. Claude Code (.claude/mcp.json)")
    print("  2. Solo mostrar (copiar manualmente)")
    print()

    choice = input("Opción [1]: ").strip() or "1"

    if choice == "1":
        save_to_claude_code(config)
    else:
        print()
        print("Copia la configuración anterior en tu archivo de configuración MCP.")

    print()
    print("✅ ¡Configuración completada!")
    print()
    print("Reinicia Claude Code para cargar el servidor MCP de Woffu.")
    print()


def save_to_claude_code(new_config: dict):
    """Save or merge configuration to Claude Code config file."""
    config_path = Path(CLAUDE_CODE_CONFIG)

    # Create directory if needed
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config if present
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = {}
    else:
        existing = {}

    # Merge configs
    if "mcpServers" not in existing:
        existing["mcpServers"] = {}

    existing["mcpServers"]["woffu"] = new_config["mcpServers"]["woffu"]

    # Save
    with open(config_path, 'w') as f:
        json.dump(existing, f, indent=2)

    print()
    print(f"✅ Guardado en {config_path}")


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Woffu MCP Server - Time tracking integration for Claude"
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run interactive setup wizard to configure the MCP server"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information"
    )

    args = parser.parse_args()

    if args.version:
        from . import __version__
        print(f"woffu-mcp-server v{__version__}")
        return

    if args.setup:
        run_setup()
        return

    # Default: run the MCP server
    from .server import main as server_main
    server_main()


if __name__ == "__main__":
    main()
