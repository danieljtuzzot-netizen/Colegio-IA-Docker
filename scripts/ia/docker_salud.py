"""Healthcheck sin inferencia, credenciales ni impresión de datos."""
import json
import urllib.request


def main():
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:8766/health',timeout=3) as response:
        state=json.load(response)
    if state.get('estado')!='LISTO' or state.get('produccion_activada') is not False:
        raise RuntimeError('Demo no lista.')


if __name__=='__main__':main()
