"""Comprobación previa y servidor en primer plano, sin launchers de Windows."""
import json
import os
from pathlib import Path
import sys
from http.server import ThreadingHTTPServer
from piloto_beto import ROOT,protect,sha
from demo_entorno import SETTINGS


def verify_artifacts():
    from demo_dashboard import load_dashboard
    from demo_cuantitativo import load_views
    from demo_vinculos import load_links
    from demo_ml import load_summary
    from demo_temas import load_themes
    from rag_semantico import verify_model,load_index
    from clasificar_comentario import ClasificadorComentarios
    load_dashboard();load_views();load_links();load_summary();themes=load_themes()
    verify_model();load_index(themes['evidencias'])
    pipeline=ClasificadorComentarios()
    checkpoint=(pipeline.beto_folder/pipeline.beto_state['mejor_checkpoint']).resolve()
    if not checkpoint.is_relative_to(pipeline.beto_folder.resolve()):raise ValueError('Checkpoint fuera de ruta.')
    for name,expected in pipeline.beto_state['hashes_mejor_checkpoint'].items():
        if Path(name).name!=name or sha(checkpoint/name)!=expected:raise ValueError('Checkpoint alterado.')
    # Recarga real: detecta paquetes o modelos incompatibles entre Windows y Linux.
    pipeline._load_beto()
    from rag_semantico import encoder
    encoder().encode(['Ejemplo ficticio sobre recursos educativos.'])
    return pipeline


def main():
    if not SETTINGS['docker']:raise ValueError('Este inicio sólo es para Docker.')
    import demo_local
    demo_local.PIPELINE=verify_artifacts()
    from ollama_resumen_local import request,local_model,PIN,BASE
    tag,_=local_model()
    pin=json.loads(PIN.read_text(encoding='utf-8'))
    if tag['digest']!=pin['digest']:raise ValueError('Modelo Ollama distinto.')
    version=request('/api/version')['version']
    if version!=pin['ollama_version']:raise ValueError('Versión Ollama distinta de la validada.')
    runtime=ROOT/'data/ia/demo_local/revisiones/runtime'
    protect(runtime)
    (runtime/'ollama.json').write_text(json.dumps({'host':BASE,'version':version,'cloud_disabled':True,
        'configuracion':'Servicio Ollama aislado por compose.ia.yaml; OLLAMA_NO_CLOUD=1'}),encoding='utf-8')
    print('Demo Docker verificada. Abrir http://localhost:8766/dashboard',flush=True)
    ThreadingHTTPServer((SETTINGS['bind'],SETTINGS['port']),demo_local.Handler).serve_forever()


if __name__=='__main__':
    try:main()
    except Exception as error:
        print('ARRANQUE DOCKER DETENIDO: '+type(error).__name__+'. Revisar montaje y versiones; no se muestran datos privados.',file=sys.stderr)
        sys.exit(1)
