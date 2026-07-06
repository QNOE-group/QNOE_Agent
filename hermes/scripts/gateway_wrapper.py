#!/usr/bin/env python3
"""QNOE gateway wrapper — discovers plugins before gateway config loading.

Hermes's GatewayRunner.__init__() calls load_gateway_config() which parses
platform names via Platform(name). Plugin platforms need to be in the
platform_registry BEFORE this happens, otherwise Platform("teams_polling")
raises ValueError and the platform is silently skipped.

This wrapper forces plugin discovery first, then starts the gateway.
"""

import os
import sys
import logging

logger = logging.getLogger(__name__)


def main():
    # 1. Discover plugins early so platform_registry is populated
    #    before GatewayRunner.__init__ -> load_gateway_config() parses
    #    Platform("teams_polling") via the _missing_() hook.
    try:
        from hermes_cli.plugins import discover_plugins
        discover_plugins()
    except Exception as e:
        logger.warning("Early plugin discovery failed: %s", e)

    # 2. Verify Platform("teams_polling") resolves after discovery
    try:
        from gateway.config import Platform
        Platform("teams_polling")
    except Exception as e:
        logger.error("Platform('teams_polling') failed after discovery: %s", e)

    # 3. Start the gateway — use cmd_gateway directly to avoid
    #    main() re-importing and potentially resetting state.
    sys.argv = ["hermes", "gateway", "run", "--replace", "-v"]
    from hermes_cli.main import main as hermes_main
    hermes_main()


if __name__ == "__main__":
    main()
