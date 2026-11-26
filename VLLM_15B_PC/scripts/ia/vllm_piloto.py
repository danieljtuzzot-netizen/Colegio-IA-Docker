"""Preparar y servir sólo un modelo público fijado; nunca carga datos del colegio."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

REPO='Qwen/Qwen2.5-0.5B-Instruct'
REVISION='7ae557604adf67be50417f59c2c2f167def9a775'
ALIAS='qwen-piloto-05b'
FOLDER=Path('/models/qwen-piloto-05b')
VARIANT=os.environ.get('VLLM_PILOT_VARIANT','05b')
if VARIANT=='15b':
    REPO='Qwen/Qwen2.5-1.5B-Instruct'
    REVISION='989aa7980e4cf806f80c7fef2b1adb7bc71aa306'
    ALIAS='qwen-piloto-15b'
    FOLDER=Path('/models/qwen-piloto-15b')
elif VARIANT!='05b':
    raise ValueError('Variante del piloto no permitida.')
FILES={'config.json','generation_config.json','model.safetensors','tokenizer.json',
       'tokenizer_config.json','vocab.json','merges.txt','README.md','LICENSE'}


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def verify(folder=FOLDER):
    manifest=json.loads((folder/'piloto_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('repositorio')!=REPO or manifest.get('revision')!=REVISION or set(manifest.get('sha256_archivos',{}))!=FILES:
        raise ValueError('Modelo ajeno al piloto.')
    for name,digest in manifest['sha256_archivos'].items():
        if sha(folder/name)!=digest:raise ValueError('Modelo alterado o incompleto.')
    return manifest


def prepare():
    if (FOLDER/'piloto_manifest.json').exists():
        verify();print('Modelo público existente verificado.');return
    from huggingface_hub import HfApi,hf_hub_download
    metadata=HfApi(token=False).model_info(REPO,revision=REVISION,files_metadata=True)
    if metadata.sha!=REVISION:raise ValueError('Revisión pública inesperada.')
    by_name={f.rfilename:f for f in metadata.siblings}
    FOLDER.mkdir(parents=True,exist_ok=True)
    hashes={}
    for name in sorted(FILES):
        path=Path(hf_hub_download(REPO,name,revision=REVISION,local_dir=str(FOLDER),token=False))
        file=by_name[name]
        if file.lfs:
            if sha(path)!=file.lfs.sha256:raise ValueError('Hash LFS incorrecto.')
        else:
            content=path.read_bytes()
            if hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest()!=file.blob_id:
                raise ValueError('Hash Git incorrecto.')
        hashes[name]=sha(path)
    (FOLDER/'piloto_manifest.json').write_text(json.dumps({'repositorio':REPO,'revision':REVISION,
        'sha256_archivos':hashes,'datos_colegio_utilizados':False,'estado':'MODELO_PUBLICO_VERIFICADO'},indent=2),encoding='utf-8')
    verify();print('Modelo público descargado y verificado. No se usaron datos del colegio.')


def command():
    args = ['vllm','serve',str(FOLDER),'--served-model-name',ALIAS,'--host','0.0.0.0',
            '--port','8000','--dtype','float32','--max-model-len','2048','--max-num-seqs','1',
            '--enforce-eager','--generation-config','vllm','--disable-log-requests',
            '--disable-log-outputs','--disable-uvicorn-access-log','--disable-log-stats',
            '--structured-outputs-config',json.dumps({'backend':'xgrammar','disable_any_whitespace':True},separators=(',',':'))]
    if VARIANT=='15b':
        args += ['--max-num-batched-tokens','256','--enable-chunked-prefill']
    return args


def serve():
    flags=Path('/proc/cpuinfo').read_text(encoding='utf-8').casefold().split()
    if 'avx2' not in flags and 'avx512f' not in flags:raise RuntimeError('CPU sin instrucciones requeridas.')
    verify()
    # Ruta local; la red de inferencia es interna y HF permanece offline.
    print('Piloto '+ALIAS+': XGrammar con JSON compacto configurado en el servidor.',flush=True)
    os.execvp('vllm',command())


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('accion',choices=['preparar','servir'])
    try:(prepare if parser.parse_args().accion=='preparar' else serve)()
    except Exception as error:
        print('PILOTO DETENIDO: '+type(error).__name__+'. Revisar CPU, memoria y modelo público.',file=sys.stderr)
        sys.exit(1)
