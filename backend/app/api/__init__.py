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

"""API endpoints module"""

import os
from flask import Flask, send_from_directory
from flask_cors import CORS


def get_web_prefix():
    """Get web prefix from environment variable, defaulting to empty string"""
    prefix = os.getenv('WEB_PREFIX', '').strip()
    # Ensure prefix starts with / and doesn't end with /
    if prefix:
        if not prefix.startswith('/'):
            prefix = '/' + prefix
        if prefix.endswith('/'):
            prefix = prefix.rstrip('/')
    return prefix

def create_app(config_manager, client_manager, wg_manager, obfuscator_manager, 
               token_manager, external_ip, external_port, traffic_stats_collector=None):
    """
    Create and configure Flask application
    
    Args:
        config_manager: ConfigManager instance
        client_manager: ClientManager instance
        wg_manager: WireGuardManager instance
        obfuscator_manager: ObfuscatorManager instance
        token_manager: TokenManager instance
        external_ip: External IP address
        external_port: External port number
        traffic_stats_collector: TrafficStatsCollector instance (optional)
        
    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    # Enable CORS for all routes and origins
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # Get web prefix from environment
    web_prefix = get_web_prefix()
    
    # Store managers in app context
    app.config_manager = config_manager
    app.client_manager = client_manager
    app.wg_manager = wg_manager
    app.obfuscator_manager = obfuscator_manager
    app.token_manager = token_manager
    app.external_ip = external_ip
    app.external_port = external_port
    app.web_prefix = web_prefix
    app.traffic_stats_collector = traffic_stats_collector
    
    # Register blueprints with prefix (API routes must be registered first)
    from . import auth, config_routes, clients, stats, health
    app.register_blueprint(auth.bp, url_prefix=web_prefix + '/api/auth')
    app.register_blueprint(config_routes.bp, url_prefix=web_prefix + '/api/config')
    app.register_blueprint(clients.bp, url_prefix=web_prefix + '/api/clients')
    app.register_blueprint(stats.bp, url_prefix=web_prefix + '/api')
    app.register_blueprint(health.bp, url_prefix=web_prefix)
    
    # Serve frontend static files (catch-all route, must be last)
    static_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static')
    
    # Route for root prefix path
    @app.route(web_prefix + '/', defaults={'path': ''})
    @app.route(web_prefix + '/<path:path>')
    def serve_frontend(path):
        # Don't serve API routes as static files
        if path.startswith('api/'):
            return {'error': 'Not found'}, 404
        
        # If path exists as a file, serve it
        if path and os.path.exists(os.path.join(static_folder, path)):
            return send_from_directory(static_folder, path)
        
        # Otherwise serve index.html for client-side routing
        # Inject web prefix script into HTML and fix asset paths
        index_path = os.path.join(static_folder, 'index.html')
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Replace absolute asset paths with prefixed paths if prefix is set
            if web_prefix:
                # Replace absolute paths that don't already start with the prefix
                import re
                # Match absolute paths (starting with /) that don't already have the prefix
                def add_prefix(match):
                    attr = match.group(1)  # href or src
                    path = match.group(2)  # the path
                    # Only add prefix if path doesn't already start with it
                    if not path.startswith(web_prefix):
                        return f'{attr}="{web_prefix}{path}"'
                    return match.group(0)
                
                # Replace href="/path" and src="/path" but not already prefixed paths
                html_content = re.sub(r'(href|src)="(/[^"]+)"', add_prefix, html_content)
            
            # Insert script before closing head tag to set web prefix
            prefix_script = f'''
    <script>
        window.__WEB_PREFIX__ = {repr(web_prefix)};
    </script>'''
            
            if '</head>' in html_content:
                html_content = html_content.replace('</head>', prefix_script + '\n  </head>', 1)
            elif '<body>' in html_content:
                html_content = html_content.replace('<body>', prefix_script + '\n  <body>', 1)
            else:
                html_content = prefix_script + '\n' + html_content
            
            from flask import Response
            return Response(html_content, mimetype='text/html')
        
        return {'error': 'Not found'}, 404
    
    return app

