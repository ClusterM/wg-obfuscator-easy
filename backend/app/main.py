"""
Copyright (C) 2025 Alexey Cluster <cluster@cluster.wtf>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

"""Main application entry point"""

import os
import signal
import atexit
import logging

from .config import ConfigManager
from .config.constants import API_PORT
from .auth import TokenManager
from .wireguard import WireGuardManager
from .obfuscator import ObfuscatorManager, ObfuscatorLogs
from .clients import ClientManager
from .api import create_app
from .services import ServiceManager
from .utils import get_external_ip, get_external_port, initialize_config, check_and_set_system_timezone
from .exceptions import ServiceError

# Configure logging to stdout/stderr (Docker-friendly)
# Docker collects logs from stdout/stderr, so we don't need file logging
# LOG_LEVEL can be: DEBUG, INFO, WARNING, ERROR, CRITICAL
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Only log to stdout/stderr for Docker
    ]
)

# Suppress Werkzeug development server messages unless in DEBUG mode
if log_level > logging.DEBUG:
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
else:
    logging.getLogger('werkzeug').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Flag to prevent multiple cleanup calls
_cleanup_called = False
def cleanup_on_exit(wg_manager, obfuscator_manager):
    """Cleanup function called on application exit"""
    global _cleanup_called
    if _cleanup_called:
        return
    _cleanup_called = True
    
    logger.info("Shutting down...")
    try:
        obfuscator_manager.stop()
        wg_manager.stop()
        logger.info("Cleanup complete")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


def main():
    """Main application entry point"""
    logger.info("Starting WireGuard Obfuscator Easy API...")
    
    # Initialize managers
    config_manager = ConfigManager()
    token_manager = TokenManager()
    
    # Get external IP and port
    try:
        external_ip = get_external_ip()
        external_port = get_external_port()
    except Exception as e:
        logger.error(f"Failed to get external IP/port: {e}")
        return 1
    
    # Initialize configuration
    try:
        initialize_config(config_manager)
    except Exception as e:
        logger.error(f"Failed to initialize configuration: {e}")
        return 1

    # Check and set system timezone if needed
    try:
        if check_and_set_system_timezone():
            logger.info("System timezone was corrected to match saved configuration.")
    except Exception as e:
        logger.error(f"Failed to check system timezone: {e}")
        # Continue with application startup despite timezone check failure
    
    # Initialize WireGuard and Obfuscator managers
    config = config_manager.main
    wg_manager = WireGuardManager(config['wg_interface'])
    obfuscator_logs = ObfuscatorLogs()
    obfuscator_manager = ObfuscatorManager(obfuscator_logs)
    
    # Initialize client manager
    client_manager = ClientManager(config_manager, wg_manager, obfuscator_manager)
    
    # Register cleanup handlers
    def cleanup():
        cleanup_on_exit(wg_manager, obfuscator_manager)
    
    atexit.register(cleanup)
    
    # Handle SIGINT (Ctrl+C) and SIGTERM
    def signal_handler(signum, frame):
        cleanup()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Generate configs and start services
    try:
        service_manager = ServiceManager(
            config_manager,
            client_manager,
            wg_manager,
            obfuscator_manager,
            external_ip,
            external_port
        )
        service_manager.generate_configs()
        # Only start services if WireGuard is enabled
        if config.get('enabled', True):
            service_manager.restart_services()
            logger.info("Services started successfully")
        else:
            logger.info("WireGuard is disabled, services not started")
    except ServiceError as e:
        logger.warning(f"Failed to start services on startup: {e}")
        logger.info("Application will continue, but services may not be running")
    
    # Create Flask application
    app = create_app(
        config_manager,
        client_manager,
        wg_manager,
        obfuscator_manager,
        token_manager,
        external_ip,
        external_port
    )
    
    # Get Flask configuration
    use_reloader = os.getenv("USE_RELOADER", "false").lower() == "true"
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    
    # Start Flask server
    try:
        logger.info(f"Starting Flask server on 0.0.0.0:{API_PORT} (HTTP)")
        # Suppress Werkzeug and Flask startup messages
        import sys
        
        # Redirect stdout/stderr temporarily to suppress Flask startup messages
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        # Create a filter that only allows our logger messages
        class LogFilter:
            def __init__(self, original):
                self.original = original
                self.allow_patterns = []
            
            def write(self, text):
                # Block Werkzeug/Flask startup messages
                if any(x in text for x in ['Running on', 'WARNING: This is a development server', '* ']):
                    return
                # Allow everything else (errors, etc.)
                self.original.write(text)
            
            def flush(self):
                self.original.flush()
        
        # Only filter if not in debug mode (to allow debugging)
        if not debug:
            sys.stdout = LogFilter(original_stdout)
            sys.stderr = LogFilter(original_stderr)
        
        try:
            # For production, use threaded mode for concurrent request handling
            threaded = os.getenv("FLASK_THREADED", "true").lower() == "true"
            app.run(
                host='0.0.0.0', 
                port=API_PORT, 
                debug=debug, 
                use_reloader=use_reloader, 
                threaded=threaded
            )
        finally:
            # Restore original stdout/stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr
    except Exception as e:
        logger.error(f"Flask server error: {e}")
        return 1
    finally:
        cleanup()
    
    return 0


if __name__ == '__main__':
    exit(main())

