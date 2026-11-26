"""Descarga fijada de BETO y piloto CPU acotado, exclusivamente con train."""
import argparse
import collections
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import time

ROOT=Path(__file__).resolve().parents[2]
MODEL_ID='dccuchile/bert-base-spanish-wwm-cased'
REVISION='c4d86612f51b4f46759c8390d1798c2febe71b93'
MODEL_DIR=ROOT/'data/ia/modelos/beto_base'/REVISION
DATA=ROOT/'data/ia/versiones/20261112_DATASET_BETO_V2'
LABELS={'NEGATIVO':0,'NEUTRAL':1,'POSITIVO':2}

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def protect(folder):
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'.htaccess').write_text('Require all denied\n',encoding='utf-8')
    (folder/'.gitignore').write_text('*\n',encoding='utf-8')

def setup(offline):
    os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    os.environ['HF_HUB_OFFLINE']='1' if offline else '0'
    os.environ['TRANSFORMERS_OFFLINE']='1' if offline else '0'
    os.environ['TOKENIZERS_PARALLELISM']='false'
    os.environ['HF_HOME']=str(ROOT/'data/ia/cache/huggingface')

def download():
    setup(False)
    from huggingface_hub import hf_hub_download
    import torch
    from safetensors.torch import save_file
    protect(MODEL_DIR)
    if (MODEL_DIR/'manifest_modelo.json').exists():
        verify_model();print('Modelo fijado ya descargado y verificado.',flush=True);return
    files=['README.md','config.json','vocab.txt','tokenizer.json','tokenizer_config.json','special_tokens_map.json','pytorch_model.bin']
    for name in files:
        print('Descargando '+name,flush=True)
        hf_hub_download(repo_id=MODEL_ID,filename=name,revision=REVISION,local_dir=str(MODEL_DIR),token=False)
    # El repositorio fijado sólo publica pesos PyTorch antiguos. Deserializar únicamente
    # tensores con weights_only=True; no ejecutar código ni cargar objetos arbitrarios.
    print('Convirtiendo tensores a safetensors localmente...',flush=True)
    weights=torch.load(MODEL_DIR/'pytorch_model.bin',map_location='cpu',weights_only=True)
    assert isinstance(weights,dict) and weights and all(isinstance(k,str) and isinstance(v,torch.Tensor) for k,v in weights.items())
    save_file({k:v.detach().contiguous().clone() for k,v in weights.items()},str(MODEL_DIR/'model.safetensors'),metadata={'format':'pt'})
    del weights
    dump(MODEL_DIR/'manifest_modelo.json',{'modelo':MODEL_ID,'revision':REVISION,'archivos':{n:sha(MODEL_DIR/n) for n in files+['model.safetensors']},'conversion':'torch.load(weights_only=True) a safetensors; nunca trust_remote_code','modelo_sentimiento_entrenado':False})
    verify_model();print('Descarga y hashes verificados. BETO base aún no ajustado a sentimiento.',flush=True)

def verify_model():
    m=json.loads((MODEL_DIR/'manifest_modelo.json').read_text(encoding='utf-8'))
    assert m['modelo']==MODEL_ID and m['revision']==REVISION
    for name,expected in m['archivos'].items():assert sha(MODEL_DIR/name)==expected,'Modelo local modificado'
    return m

def train_rows():
    manifest=json.loads((DATA/'manifest.json').read_text(encoding='utf-8'))
    path=DATA/'sentimiento_train.jsonl'
    assert sha(path)==manifest['archivos'][path.name]['sha256'],'Hash train incorrecto'
    rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    assert len(rows)==manifest['archivos'][path.name]['cantidad']
    assert len({r['id_origen'] for r in rows})==len(rows)
    assert all(r['etiqueta'] in LABELS for r in rows)
    return rows,manifest

def run(steps,run_id,max_length):
    setup(True)
    import torch
    import psutil
    from transformers import AutoTokenizer,AutoModelForSequenceClassification
    model_manifest=verify_model()
    rows,dataset_manifest=train_rows()
    output=ROOT/'data/ia/pilotos'/run_id
    assert not output.exists(),'La ejecución ya existe; use otro --ejecucion. No sobrescribir.'
    protect(output)
    torch.set_num_threads(min(4,os.cpu_count() or 1));torch.manual_seed(42)
    rng=random.Random(42)
    report={'estado':'EN_CURSO','objetivo':'VIABILIDAD_TECNICA_NO_CALIDAD','modelo':MODEL_ID,'revision':REVISION,'dataset':'20261112_DATASET_BETO_V2','sha256_train':dataset_manifest['archivos']['sentimiento_train.jsonl']['sha256'],'sha256_manifest_modelo':sha(MODEL_DIR/'manifest_modelo.json'),'dispositivo':'cpu','batch_size':2,'max_length':max_length,'pasos_solicitados':steps,'semilla':42,'learning_rate':2e-5,'label2id':LABELS,'validation_utilizada':False,'test_utilizado':False,'pesos_publicados_produccion':False,'modelo_final':False,'pasos':[]}
    dump(output/'resultado_piloto.json',report)
    print('Cargando tokenizer local...',flush=True)
    tokenizer=AutoTokenizer.from_pretrained(str(MODEL_DIR),local_files_only=True,trust_remote_code=False)
    counts=collections.Counter();lengths=[];question_overflow=[]
    for r in rows:
        encoded=tokenizer(r['pregunta'],r['comentario'],truncation=False,verbose=False)
        length=len(encoded['input_ids']);lengths.append(length)
        if length>max_length:counts['ejemplos_con_truncamiento']+=1
        if len(tokenizer(r['pregunta'],add_special_tokens=False)['input_ids'])+3>=max_length:question_overflow.append(r['id_origen'])
    assert not question_overflow,'Pregunta demasiado larga para truncation=only_second'
    report['tokenizacion_train']={'total':len(rows),'longitud_maxima':max(lengths),'ejemplos_con_truncamiento':counts['ejemplos_con_truncamiento'],'porcentaje_truncamiento_raw':100*counts['ejemplos_con_truncamiento']/len(rows)}
    # Selección reproducible con cobertura de las tres clases, sólo desde train.
    buckets={label:[r for r in rows if r['etiqueta']==label] for label in LABELS}
    for bucket in buckets.values():rng.shuffle(bucket)
    selected=[]
    for i in range(steps*2):
        label=list(LABELS)[i%3];selected.append(buckets[label].pop())
    dump(output/'seleccion_train_ids.json',[{'id_origen':r['id_origen'],'etiqueta':r['etiqueta']} for r in selected])
    print('Cargando BETO local y creando cabeza de tres clases...',flush=True)
    start=time.perf_counter()
    model,loading=AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR),local_files_only=True,trust_remote_code=False,use_safetensors=True,num_labels=3,id2label={v:k for k,v in LABELS.items()},label2id=LABELS,output_loading_info=True)
    # La cabeza de clasificación es nueva; todos los pesos existentes del encoder deben cargar.
    assert not [k for k in loading.get('missing_keys',[]) if not k.startswith(('classifier.','bert.pooler.'))], 'Pesos del encoder ausentes'
    report['carga_segundos_raw']=time.perf_counter()-start
    report['carga_pesos']={k:sorted(loading.get(k,[])) for k in ('missing_keys','unexpected_keys','mismatched_keys')}
    dump(output/'resultado_piloto.json',report)
    model.to('cpu');model.train()
    optimizer=torch.optim.AdamW(model.parameters(),lr=2e-5)
    process=psutil.Process();peak=process.memory_info().rss
    for step in range(steps):
        batch=selected[step*2:step*2+2]
        encoded=tokenizer([r['pregunta'] for r in batch],[r['comentario'] for r in batch],truncation='only_second',padding='max_length',max_length=max_length,return_tensors='pt')
        encoded['labels']=torch.tensor([LABELS[r['etiqueta']] for r in batch],dtype=torch.long)
        optimizer.zero_grad(set_to_none=True);start=time.perf_counter()
        loss=model(**encoded).loss
        assert torch.isfinite(loss),'Pérdida no finita'
        loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.0,error_if_nonfinite=True);optimizer.step()
        seconds=time.perf_counter()-start;memory=process.memory_info();peak=max(peak,memory.rss,getattr(memory,'peak_wset',0))
        entry={'paso':step+1,'loss_raw':float(loss.detach()),'grad_norm_raw':float(norm),'segundos_raw':seconds,'rss_mib_raw':memory.rss/1024**2}
        report['pasos'].append(entry);dump(output/'resultado_piloto.json',report)
        print(f'Paso {step+1}/{steps} completado. Tiempo: {seconds:.0f} s. RAM proceso: {memory.rss/1024**2:.0f} MiB.',flush=True)
    print('Guardando checkpoint de piloto en safetensors...',flush=True)
    save_start=time.perf_counter();model.save_pretrained(output/'checkpoint_piloto',safe_serialization=True);tokenizer.save_pretrained(output/'checkpoint_piloto')
    report['guardado_segundos_raw']=time.perf_counter()-save_start
    del optimizer,model
    # Comprobar que el checkpoint guardado vuelve a cargar sin red.
    restored=AutoModelForSequenceClassification.from_pretrained(output/'checkpoint_piloto',local_files_only=True,use_safetensors=True,trust_remote_code=False)
    assert restored.config.label2id==LABELS
    restored.eval()
    with torch.no_grad():
        logits=restored(**{k:v for k,v in encoded.items() if k!='labels'}).logits
    assert logits.shape==(2,3) and torch.isfinite(logits).all()
    seconds=sum(p['segundos_raw'] for p in report['pasos'])/steps
    report.update({'estado':'APROBADO','pasos_completados':steps,'ejemplos_procesados':len(selected),'segundos_por_paso_media_raw':seconds,'pico_ram_proceso_mib_raw':peak/1024**2,'estimacion_una_epoca_horas_raw':seconds*math.ceil(len(rows)/2)/3600,'limite_estimacion':'Extrapolación de pocos pasos con longitud y batch fijos; no incluye evaluación ni guardado. No garantiza duración real.','recarga_checkpoint':'APROBADA','checkpoint_sha256':{p.name:sha(p) for p in (output/'checkpoint_piloto').iterdir() if p.is_file()},'versiones':{p:importlib.metadata.version(p) for p in ['torch','transformers','safetensors','tokenizers']}})
    dump(output/'resultado_piloto.json',report)
    print(json.dumps({k:report[k] for k in ['estado','pasos_completados','test_utilizado','modelo_final','recarga_checkpoint']},ensure_ascii=True))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='accion',required=True)
    sub.add_parser('descargar')
    pilot=sub.add_parser('ejecutar')
    pilot.add_argument('--pasos',type=int,default=3,choices=range(1,11))
    pilot.add_argument('--ejecucion',required=True)
    pilot.add_argument('--max-length',type=int,default=128,choices=[64,128,256])
    args=parser.parse_args()
    if args.accion=='descargar':download()
    else:
        import re
        assert re.fullmatch(r'[A-Za-z0-9_-]{1,64}',args.ejecucion),'Identificador inválido'
        existed=(ROOT/'data/ia/pilotos'/args.ejecucion).exists()
        try:
            run(args.pasos,args.ejecucion,args.max_length)
        except Exception as error:
            output=ROOT/'data/ia/pilotos'/args.ejecucion/'resultado_piloto.json'
            if not existed and output.exists():
                result=json.loads(output.read_text(encoding='utf-8'))
                # No modificar una ejecución anterior si la causa fue nombre repetido.
                if result.get('estado')=='EN_CURSO':
                    result.update({'estado':'FALLIDO','tipo_error':type(error).__name__})
                    dump(output,result)
            raise
