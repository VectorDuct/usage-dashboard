"""Run with python -m usage_dashboard [--config config.json]."""
import argparse
import os
import threading
from . import __version__
from .config import load_config
from .server import Dashboard, make_server


def main():
    parser = argparse.ArgumentParser(description='Read-only model usage dashboard')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--config', help='JSON config file; defaults to synthetic demo mode')
    parser.add_argument('--host', help='Override listen host')
    parser.add_argument('--port', type=int, help='Override listen port')
    parser.add_argument('--check', action='store_true', help='Validate configuration without fetching or writing data')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        cfg = load_config(args.config)
        if args.port is not None and not 1 <= args.port <= 65535:
            raise ValueError('Invalid port')
    except (ValueError, TypeError, KeyError, OSError):
        parser.exit(2, 'Invalid configuration. Check the documented field types and file permissions.\n')
    if args.check:
        print('Configuration valid (no data fetched).')
        return
    app = Dashboard(cfg)
    server = make_server(app, host=args.host, port=args.port)
    worker = threading.Thread(target=app.run, name='usage-sampler', daemon=True)
    worker.start()
    print(f'Usage Dashboard {__version__} listening on port {server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop.set()
        server.server_close()
        worker.join(timeout=cfg['timeout'] * 2 + 1)


if __name__ == '__main__':
    main()
