"""Configuración cerrada: loopback local o servicios de la composición Docker."""
import os
import re
from urllib.parse import urlsplit


def settings(environ=None):
    env = os.environ if environ is None else environ
    mode = env.get('IA_RUNTIME', 'local')
    if mode not in {'local', 'docker'}:
        raise ValueError('Entorno de demo no admitido.')
    container = mode == 'docker'
    port = 8766 if container else 8765
    hosts = {f'localhost:{port}', f'127.0.0.1:{port}'}
    origins = {None, f'http://localhost:{port}', f'http://127.0.0.1:{port}'}
    public = env.get('IA_PUBLIC_ORIGIN', '')
    if public:
        parsed = urlsplit(public)
        hostname = parsed.hostname or ''
        if (not container or public != 'https://' + hostname or parsed.scheme != 'https' or parsed.netloc != hostname
                or parsed.path or parsed.query or parsed.fragment or len(hostname)>253
                or '.' not in hostname or hostname.endswith(('.localhost', '.local'))
                or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+', hostname)
                or re.fullmatch(r'[0-9.]+', hostname)):
            raise ValueError('IA_PUBLIC_ORIGIN exige un unico dominio HTTPS sin ruta, puerto ni comodines, en Docker.')
        hosts.add(hostname)
        origins.add(public)
    return {
        'docker': container, 'port': port,
        'bind': '0.0.0.0' if container else '127.0.0.1',
        'ollama': 'http://ollama:11434' if container else 'http://127.0.0.1:11435',
        'hosts': hosts,
        'origins': origins,
    }


SETTINGS = settings()
