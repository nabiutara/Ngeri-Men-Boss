"""Start or reuse the local app and keep its server attached to this launcher."""
from pathlib import Path
import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8765'


def health():
    # Local traffic must not be sent through a configured HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(URL + '/api/health', timeout=2) as response:
            data = json.load(response)
            return data if data.get('app') == 'touchline-studio' else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--lan', action='store_true', help='Allow phones and other devices on the same Wi-Fi to connect')
    args = parser.parse_args()
    existing = health()
    if existing:
        if args.lan and not existing.get('network_access'):
            print('Touchline Studio is already running in local-only mode.')
            print('Close the existing launcher window, then start it again for phone access.')
            return 1
        print('Touchline Studio is already running: ' + URL)
        if existing.get('phone_url'):
            print('Phone link (same Wi-Fi): ' + existing['phone_url'])
        if not args.no_browser:
            webbrowser.open(URL)
        return 0
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 8765)) == 0:
            print('Port 8765 is occupied by an unresponsive server or another app.')
            print('No process was stopped. Close the old instance and try again.')
            return 1
    logs = ROOT / 'work'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'server.log'
    with log_path.open('ab') as output:
        log_start = output.tell()
        try:
            process = subprocess.Popen(
                [sys.executable, '-u', str(ROOT / 'server.py'), '--port', '8765'] + (['--lan'] if args.lan else []),
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                close_fds=True,
            )
        except OSError as error:
            print('Could not start the local server: ' + str(error))
            return 1
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        ready = health()
        if ready:
            print('Touchline Studio is ready: ' + URL)
            if ready.get('phone_url'):
                print('Phone link (same Wi-Fi): ' + ready['phone_url'])
                print('Open that link on your phone while it is connected to this Wi-Fi network.', flush=True)
            print('Keep this Touchline window open while using the app.', flush=True)
            print('Closing it stops the local server. Reopen Start Touchline.cmd to restart.', flush=True)
            if not args.no_browser:
                webbrowser.open(URL)
            try:
                code = process.wait()
            except KeyboardInterrupt:
                if process.poll() is None:
                    process.terminate()
                process.wait()
                return 0
            if code:
                print('The local server stopped unexpectedly. Startup log: ' + str(log_path))
            return code
        if process.poll() is not None:
            break
        time.sleep(.25)
    print('Touchline did not become ready. Read the startup log: ' + str(log_path))
    if process.poll() is None:
        process.terminate()
        process.wait()
    # Show only this attempt's output, rather than unrelated errors from old runs.
    with log_path.open('rb') as output:
        output.seek(max(log_start, log_path.stat().st_size - 8192))
        details = output.read().decode('utf-8', errors='replace').strip()
    if details:
        print(details)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
