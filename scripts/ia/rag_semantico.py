"""Embeddings locales y recuperación híbrida sobre el piloto autorizado, sin nube."""
import argparse
import hashlib
import json
import os
from datetime import datetime,timezone
from pathlib import Path
import threading
from demo_dashboard import ROOT
from demo_temas import load_themes
from piloto_beto import protect

REPO='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
REVISION='e8f8c211226b894fcb81acc59f3b34ba3efd5f42'
MODEL_FOLDER=ROOT/'data/ia/modelos/minilm_semantico'/REVISION
INDEX_FOLDER=ROOT/'data/ia/rag/indice_piloto_20261116_v1'
FILES=['config.json','model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json',
       'sentence_bert_config.json','1_Pooling/config.json','modules.json','README.md']
WEIGHTS_SHA='eaa086f0ffee582aeb45b36e34cdd1fe2d6de2bef61f8a559a1bbc9bd955917b'
DIMENSIONS=384
MAX_LENGTH=128
MIN_COSINE=0.35
RRF_K=60
_MODEL=None
_LOCK=threading.RLock()

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def fingerprint(rows):return hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def download():
    os.environ['HF_HUB_DISABLE_TELEMETRY']='1';os.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1';os.environ['HF_HUB_DISABLE_XET']='1'
    from huggingface_hub import HfApi,hf_hub_download
    if (MODEL_FOLDER/'manifest_local.json').exists():
        verify_model();print('Modelo fijado ya verificado.');return
    protect(MODEL_FOLDER)
    cache=ROOT/'data/ia/cache/minilm_hub';protect(cache)
    info=HfApi(token=False).model_info(REPO,revision=REVISION,files_metadata=True)
    if info.sha!=REVISION:raise ValueError('Revisión del repositorio distinta.')
    metadata={row.rfilename:row for row in info.siblings}
    hashes={}
    for name in FILES:
        print('Descargando archivo público: '+name,flush=True)
        path=Path(hf_hub_download(REPO,name,revision=REVISION,local_dir=str(MODEL_FOLDER),cache_dir=str(cache),token=False))
        row=metadata[name];digest=sha(path)
        if row.lfs:
            if digest!=row.lfs.sha256:raise ValueError('Huella LFS distinta.')
        else:
            content=path.read_bytes()
            if hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest()!=row.blob_id:
                raise ValueError('Huella Git del archivo distinta.')
        if name=='model.safetensors' and digest!=WEIGHTS_SHA:raise ValueError('Pesos no corresponden a la revisión fijada.')
        hashes[name]=digest
    dump(MODEL_FOLDER/'manifest_local.json',{'estado':'MODELO_PUBLICO_FIJADO','repositorio':REPO,'revision':REVISION,
        'sha256_archivos':hashes,'trust_remote_code':False,'safetensors':True,'comentarios_enviados':False})
    verify_model();print(json.dumps({'estado':'MODELO_PUBLICO_FIJADO','revision':REVISION,'archivos':len(hashes)}))

def verify_model():
    manifest=read(MODEL_FOLDER/'manifest_local.json')
    if manifest.get('repositorio')!=REPO or manifest.get('revision')!=REVISION or set(manifest['sha256_archivos'])!=set(FILES):
        raise ValueError('Modelo fuera de la revisión aprobada.')
    for name,digest in manifest['sha256_archivos'].items():
        if sha(MODEL_FOLDER/name)!=digest:raise ValueError('Archivo del modelo alterado.')
    if manifest['sha256_archivos']['model.safetensors']!=WEIGHTS_SHA:raise ValueError('Pesos distintos.')

class Encoder:
    def __init__(self):
        verify_model()
        os.environ['HF_HUB_DISABLE_TELEMETRY']='1';os.environ['TOKENIZERS_PARALLELISM']='false'
        import torch
        from transformers import AutoTokenizer,AutoModel
        torch.set_num_threads(4)
        self.torch=torch
        self.tokenizer=AutoTokenizer.from_pretrained(str(MODEL_FOLDER),local_files_only=True,trust_remote_code=False)
        self.model=AutoModel.from_pretrained(str(MODEL_FOLDER),local_files_only=True,trust_remote_code=False,use_safetensors=True).to('cpu').eval()

    def encode(self,texts):
        import numpy as np
        torch=self.torch;vectors=[]
        for start in range(0,len(texts),16):
            batch=self.tokenizer(texts[start:start+16],padding=True,truncation=True,max_length=MAX_LENGTH,return_tensors='pt')
            with torch.inference_mode():
                hidden=self.model(**batch).last_hidden_state
                mask=batch['attention_mask'].unsqueeze(-1).to(hidden.dtype)
                pooled=(hidden*mask).sum(dim=1)/mask.sum(dim=1).clamp(min=1e-9)
                normalized=torch.nn.functional.normalize(pooled,p=2,dim=1)
                vectors.append(normalized.cpu().numpy())
        result=np.concatenate(vectors).astype('float32')
        if result.shape!=(len(texts),DIMENSIONS) or not np.isfinite(result).all():raise ValueError('Embeddings inválidos.')
        return result

def encoder():
    global _MODEL
    with _LOCK:
        if _MODEL is None:_MODEL=Encoder()
        return _MODEL

def document_text(row):return (row['tema'] or row['categoria']).replace('_',' ')+'\n'+row['cita']

def build_index():
    import numpy as np
    if INDEX_FOLDER.exists():raise ValueError('Índice existente: no sobrescribir.')
    rows=load_themes()['evidencias'];model=encoder()
    texts=[document_text(row) for row in rows]
    lengths=[len(model.tokenizer(text,add_special_tokens=True,truncation=False)['input_ids']) for text in texts]
    vectors=model.encode(texts);protect(INDEX_FOLDER)
    np.save(INDEX_FOLDER/'vectores.npy',vectors,allow_pickle=False)
    dump(INDEX_FOLDER/'referencias.json',[r['segmento_id'] for r in rows])
    dump(INDEX_FOLDER/'manifest.json',{'estado':'INDICE_AUTORIZADO_COMPLETADO','periodo':'2026-II',
        'fecha_utc':datetime.now(timezone.utc).isoformat(),'repositorio':REPO,'revision':REVISION,
        'segmentos':len(rows),'dimensiones':DIMENSIONS,'max_tokens':MAX_LENGTH,
        'segmentos_truncados':sum(n>MAX_LENGTH for n in lengths),'min_coseno_operativo':MIN_COSINE,
        'umbral_calibrado':False,'fusion':'RRF','rrf_k':RRF_K,'motor':'NUMPY_COSENO_EXACTO',
        'evidencia_sha256':fingerprint(rows),'test_utilizado':False,'produccion_activada':False,
        'sha256_manifest_modelo':sha(MODEL_FOLDER/'manifest_local.json'),
        'sha256_archivos':{name:sha(INDEX_FOLDER/name) for name in ('vectores.npy','referencias.json')}})
    print(json.dumps({'estado':'INDICE_AUTORIZADO_COMPLETADO','segmentos':len(rows),'dimensiones':DIMENSIONS,
                      'segmentos_truncados':sum(n>MAX_LENGTH for n in lengths),'test_utilizado':False}))

def load_index(full_rows):
    import numpy as np
    manifest=read(INDEX_FOLDER/'manifest.json')
    if (manifest.get('estado')!='INDICE_AUTORIZADO_COMPLETADO' or manifest.get('revision')!=REVISION
        or manifest.get('repositorio')!=REPO or manifest.get('dimensiones')!=DIMENSIONS
        or manifest.get('max_tokens')!=MAX_LENGTH or manifest.get('min_coseno_operativo')!=MIN_COSINE
        or manifest.get('rrf_k')!=RRF_K
        or manifest.get('test_utilizado') is not False or manifest.get('periodo')!='2026-II'
        or manifest.get('evidencia_sha256')!=fingerprint(full_rows)):
        raise ValueError('Índice distinto de la evidencia autorizada.')
    if manifest['sha256_manifest_modelo']!=sha(MODEL_FOLDER/'manifest_local.json'):raise ValueError('Configuración del modelo distinta.')
    for name in ('vectores.npy','referencias.json'):
        if sha(INDEX_FOLDER/name)!=manifest['sha256_archivos'][name]:raise ValueError('Índice alterado.')
    ids=read(INDEX_FOLDER/'referencias.json');vectors=np.load(INDEX_FOLDER/'vectores.npy',allow_pickle=False)
    if (ids!=[r['segmento_id'] for r in full_rows] or len(set(ids))!=len(ids)
        or vectors.shape!=(len(ids),DIMENSIONS) or vectors.dtype!=np.float32
        or not np.isfinite(vectors).all() or not np.allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-5)):
        raise ValueError('Estructura vectorial inválida.')
    return ids,vectors,manifest

def fuse(rows,semantic,lexical,limit):
    by_id={row['segmento_id']:row for row in rows};scores={};cosines=dict(semantic)
    for ranking in ([ident for ident,score in semantic],[r['segmento_id'] for r in lexical]):
        for rank,ident in enumerate(ranking,start=1):
            if ident not in by_id:raise ValueError('Referencia ajena a los filtros.')
            scores[ident]=scores.get(ident,0)+1/(RRF_K+rank)
    ordered=sorted(scores,key=lambda ident:(-scores[ident],-cosines.get(ident,-1),ident))[:limit]
    return [by_id[ident] for ident in ordered],scores

def hybrid(question,rows,lexical,limit=5):
    full_rows=load_themes()['evidencias'];by_id={row['segmento_id']:row for row in full_rows}
    if any(row!=by_id.get(row['segmento_id']) for row in rows):raise ValueError('Evidencia fuera del piloto autorizado.')
    ids,vectors,manifest=load_index(full_rows)
    if not rows:return [],{'modo':'HIBRIDO','coincidencias_semanticas':0,'coincidencias_lexicas':0}
    positions={ident:i for i,ident in enumerate(ids)}
    # Los filtros se aplican antes de puntuar y ordenar, nunca después del top-k.
    with _LOCK:query=encoder().encode([question])[0]
    filtered=vectors[[positions[r['segmento_id']] for r in rows]]
    cosines=filtered@query
    semantic=sorted([(r['segmento_id'],float(score)) for r,score in zip(rows,cosines) if score>=MIN_COSINE],key=lambda pair:(-pair[1],pair[0]))[:10]
    result,scores=fuse(rows,semantic,lexical,limit)
    return result,{'modo':'HIBRIDO','modelo_embeddings':REPO,'revision':REVISION,'dimensiones':DIMENSIONS,
                  'coincidencias_semanticas':len(semantic),'coincidencias_lexicas':len(lexical),
                  'umbral_coseno_raw':MIN_COSINE,'umbral_calibrado':False,'coseno_raw':dict(semantic),
                  'fusion_rrf_raw':scores,'motor':manifest['motor']}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('accion',choices=['descargar','indexar']);args=parser.parse_args()
    (download if args.accion=='descargar' else build_index)()
