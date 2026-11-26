"""Referencia TF-IDF y entrenamiento CPU de BETO. Nunca lee sentimiento_test.jsonl."""
import argparse
import collections
from datetime import datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import re
import time

from piloto_beto import ROOT,MODEL_DIR,MODEL_ID,REVISION,LABELS,setup,sha,protect,verify_model

CONFIG=ROOT/'scripts/ia/beto_sentimiento_config_v1.json'
BASE=ROOT/'data/ia/entrenamientos'

def dump(path,value):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)

def now():return datetime.now(timezone.utc).isoformat()

def recover_epoch_state(output,state):
    """Recuperar un commit de época si se interrumpió la actualización de estado.json."""
    for folder in sorted(output.glob('epoca_[0-9][0-9]')):
        marker=folder/'estado_al_final.json'
        if not marker.exists():continue
        saved=json.loads(marker.read_text(encoding='utf-8'))
        if saved['epocas_completadas']<=state['epocas_completadas']:continue
        assert all(saved[k]==state[k] for k in ('config_sha256','sha256_train','sha256_validation'))
        hashes=json.loads((folder/'checkpoint_manifest.json').read_text(encoding='utf-8'))
        for name,expected in hashes.items():assert sha(folder/name)==expected,'Checkpoint de reanudación alterado'
        state=saved
    return state

def percent(value):
    return str((Decimal(str(value))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))+' %'

def read_data(config):
    base=ROOT/'data/ia/versiones'/config['dataset_version']
    manifest=json.loads((base/'manifest.json').read_text(encoding='utf-8'))
    result={}
    for split in ('train','validation'):
        path=base/f'sentimiento_{split}.jsonl'
        assert sha(path)==manifest['archivos'][path.name]['sha256'],'Hash de dataset incorrecto'
        rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        assert len(rows)==manifest['archivos'][path.name]['cantidad']
        assert all(r['etiqueta'] in LABELS for r in rows)
        result[split]=rows
    for field in ('id_origen','grupo_split'):
        assert not {r[field] for r in result['train']}&{r[field] for r in result['validation']},'Cruce train-validation'
    assert len({r['id_origen'] for r in result['train']})==len(result['train'])
    assert len({r['id_origen'] for r in result['validation']})==len(result['validation'])
    return result,manifest

def metrics(y,pred):
    from sklearn.metrics import accuracy_score,classification_report,confusion_matrix,f1_score
    order=list(range(3));names=[k for k,v in sorted(LABELS.items(),key=lambda item:item[1])]
    return {'accuracy_raw':float(accuracy_score(y,pred)),'macro_f1_raw':float(f1_score(y,pred,labels=order,average='macro',zero_division=0)),'por_clase':classification_report(y,pred,labels=order,target_names=names,output_dict=True,zero_division=0),'matriz_confusion':confusion_matrix(y,pred,labels=order).tolist(),'orden_clases':names,'cantidad':len(y)}

def baseline(rows,output):
    import joblib
    from sklearn.pipeline import Pipeline,FeatureUnion
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.exceptions import ConvergenceWarning
    import warnings
    clf=Pipeline([
        ('tfidf',FeatureUnion([
            ('palabras',TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True,max_features=30000)),
            ('caracteres',TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=2,sublinear_tf=True,max_features=40000))
        ])),
        ('clasificador',LogisticRegression(max_iter=2000,class_weight='balanced',random_state=42))
    ])
    text=lambda rs:[r['pregunta']+'\n'+r['comentario'] for r in rs]
    train_y=[LABELS[r['etiqueta']] for r in rows['train']]
    val_y=[LABELS[r['etiqueta']] for r in rows['validation']]
    print('Entrenando referencia TF-IDF + regresión logística...',flush=True)
    with warnings.catch_warnings():
        warnings.simplefilter('error',ConvergenceWarning)
        clf.fit(text(rows['train']),train_y)
    pred=clf.predict(text(rows['validation'])).tolist()
    report=metrics(val_y,pred)
    joblib.dump(clf,output/'referencia_tfidf.joblib')
    report.update({'algoritmo':'TFIDF_palabras_caracteres_LogisticRegression','seleccion_hiperparametros':'configuracion_fija_sin_busqueda','entrenado_solo_train':True,'evaluado_solo_validation':True,'sha256_modelo':sha(output/'referencia_tfidf.joblib')})
    dump(output/'referencia_metricas_validation.json',report)
    dump(output/'referencia_predicciones_validation.json',[{'id_origen':r['id_origen'],'real':r['etiqueta'],'predicha':next(k for k,v in LABELS.items() if v==p)} for r,p in zip(rows['validation'],pred)])
    print('Referencia: macro-F1 de validación '+percent(report['macro_f1_raw']),flush=True)
    return report

def report_markdown(output,state,reference):
    lines=['# Entrenamiento experimental de sentimiento','',
           'Estado: '+state['estado']+'. Test reservado. Resultados sobre validación, no evaluación final independiente.','',
           '| Modelo | Accuracy | Macro-F1 |','| --- | ---: | ---: |',
           '| TF-IDF + regresión logística | '+percent(reference['accuracy_raw'])+' | '+percent(reference['macro_f1_raw'])+' |']
    if state.get('mejor_validation'):
        m=state['mejor_validation'];lines.append('| BETO, mejor época '+str(state['mejor_epoca'])+' | '+percent(m['accuracy_raw'])+' | '+percent(m['macro_f1_raw'])+' |')
        lines.extend(['','| Clase | Precision | Recall | F1 | Ejemplos |','| --- | ---: | ---: | ---: | ---: |'])
        for label in ('NEGATIVO','NEUTRAL','POSITIVO'):
            d=m['por_clase'][label]
            lines.append('| '+label+' | '+percent(d['precision'])+' | '+percent(d['recall'])+' | '+percent(d['f1-score'])+' | '+str(int(d['support']))+' |')
        lines.extend(['','Matriz de confusión: filas reales, columnas predichas.','',
                      '| Real / predicha | NEGATIVO | NEUTRAL | POSITIVO |','| --- | ---: | ---: | ---: |'])
        for label,values in zip(('NEGATIVO','NEUTRAL','POSITIVO'),m['matriz_confusion']):lines.append('| '+label+' | '+' | '.join(str(n) for n in values)+' |')
    lines.extend(['','Los porcentajes visibles están redondeados a enteros. Los JSON conservan los valores raw.',
                  'Las etiquetas tienen origen mixto IA/humano. No hay prueba gold independiente ni activación del portal.'])
    (output/'INFORME_VALIDACION.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def run(run_id,smoke=False,resume=False):
    setup(True)
    import torch
    import psutil
    from transformers import AutoTokenizer,AutoModelForSequenceClassification,DataCollatorWithPadding,get_linear_schedule_with_warmup
    from torch.utils.data import DataLoader
    config=json.loads(CONFIG.read_text(encoding='utf-8'))
    assert config['test_reserved'] and config['class_weight']=='balanced_train_only'
    assert config['epochs']==3 and config['batch_size']==4
    verify_model()
    rows,manifest=read_data(config)
    if smoke:
        for split,count in [('train',4),('validation',3)]:
            rows[split]=[r for label in LABELS for r in [x for x in rows[split] if x['etiqueta']==label][:count]]
        config['epochs']=1
    assert psutil.disk_usage(str(ROOT)).free>8*1024**3,'Se requieren al menos 8 GiB libres para checkpoints'
    output=BASE/run_id
    if resume:
        assert output.exists() and not smoke
        state=json.loads((output/'estado.json').read_text(encoding='utf-8'))
        assert state['estado'] in ('EN_CURSO','INTERRUMPIDO','FALLIDO') and not state['smoke']
        state=recover_epoch_state(output,state)
        assert state['config_sha256']==sha(CONFIG)
        assert state['sha256_train']==manifest['archivos']['sentimiento_train.jsonl']['sha256'] and state['sha256_validation']==manifest['archivos']['sentimiento_validation.jsonl']['sha256']
        reference=json.loads((output/'referencia_metricas_validation.json').read_text(encoding='utf-8'))
    else:
        assert not output.exists(),'Ejecución existente: usar otro nombre o reanudar'
        protect(output)
        state={'estado':'EN_CURSO','inicio_utc':now(),'ultima_actualizacion_utc':now(),'smoke':smoke,'dataset':config['dataset_version'],'cantidad_train':len(rows['train']),'cantidad_validation':len(rows['validation']),'modelo':MODEL_ID,'revision':REVISION,'config':config,'config_sha256':sha(CONFIG),'sha256_train':manifest['archivos']['sentimiento_train.jsonl']['sha256'],'sha256_validation':manifest['archivos']['sentimiento_validation.jsonl']['sha256'],'label2id':LABELS,'epocas_completadas':0,'mejor_epoca':None,'mejor_validation':None,'historial':[],'test_utilizado':False,'produccion_activada':False,'versiones':{p:importlib.metadata.version(p) for p in ['torch','transformers','scikit-learn','tokenizers','safetensors']}}
        dump(output/'estado.json',state)
        dump(output/'ids_utilizados.json',{s:[r['id_origen'] for r in rs] for s,rs in rows.items()})
        reference=baseline(rows,output)
    torch.set_num_threads(min(config['cpu_threads'],os.cpu_count() or 1));torch.manual_seed(config['seed']);random.seed(config['seed'])
    tokenizer=AutoTokenizer.from_pretrained(str(MODEL_DIR),local_files_only=True,trust_remote_code=False)
    def encode(rs):
        enc=tokenizer([r['pregunta'] for r in rs],[r['comentario'] for r in rs],truncation='only_second',max_length=config['max_length'],padding=False)
        return [{**{k:v[i] for k,v in enc.items()},'labels':LABELS[r['etiqueta']]} for i,r in enumerate(rs)]
    encoded_train=encode(rows['train']);encoded_val=encode(rows['validation'])
    counts=collections.Counter(LABELS[r['etiqueta']] for r in rows['train'])
    weights=torch.tensor([len(rows['train'])/(3*counts[i]) for i in range(3)],dtype=torch.float32)
    state['class_weights_train_raw']=weights.tolist()
    collator=DataCollatorWithPadding(tokenizer,pad_to_multiple_of=8,return_tensors='pt')
    val_loader=DataLoader(encoded_val,batch_size=config['eval_batch_size'],shuffle=False,num_workers=0,collate_fn=collator)
    batches=math.ceil(len(encoded_train)/config['batch_size']);total_steps=batches*config['epochs']
    start_epoch=int(state['epocas_completadas'])
    initial_path=output/f'epoca_{start_epoch:02d}'/'modelo' if start_epoch else MODEL_DIR
    print('Cargando encoder y clasificador en CPU...',flush=True)
    model=AutoModelForSequenceClassification.from_pretrained(str(initial_path),local_files_only=True,trust_remote_code=False,use_safetensors=True,num_labels=3,id2label={v:k for k,v in LABELS.items()},label2id=LABELS).to('cpu')
    optimizer=torch.optim.AdamW(model.parameters(),lr=config['learning_rate'],weight_decay=config['weight_decay'])
    scheduler=get_linear_schedule_with_warmup(optimizer,num_warmup_steps=round(total_steps*config['warmup_ratio']),num_training_steps=total_steps)
    if start_epoch:
        saved=torch.load(output/f'epoca_{start_epoch:02d}'/'optimizador.pt',weights_only=True,map_location='cpu')
        optimizer.load_state_dict(saved['optimizer']);scheduler.load_state_dict(saved['scheduler']);torch.set_rng_state(saved['torch_rng'])
    process=psutil.Process();peak=process.memory_info().rss
    criterion=torch.nn.CrossEntropyLoss(weight=weights)
    state['estado']='EN_CURSO';state['ultima_actualizacion_utc']=now();dump(output/'estado.json',state)
    for epoch in range(start_epoch+1,config['epochs']+1):
        generator=torch.Generator().manual_seed(config['seed']+epoch)
        loader=DataLoader(encoded_train,batch_size=config['batch_size'],shuffle=True,generator=generator,num_workers=0,collate_fn=collator)
        model.train();epoch_start=time.perf_counter();sum_loss=0.0
        for step,batch in enumerate(loader,1):
            optimizer.zero_grad(set_to_none=True)
            labels=batch.pop('labels');logits=model(**batch).logits
            loss=criterion(logits,labels)
            assert torch.isfinite(loss),'Pérdida no finita'
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),config['max_grad_norm'],error_if_nonfinite=True)
            optimizer.step();scheduler.step();sum_loss+=float(loss.detach())
            memory=process.memory_info();peak=max(peak,memory.rss,getattr(memory,'peak_wset',0))
            if step==1 or step%25==0 or step==batches:
                state.update({'epoca_en_curso':epoch,'paso_en_epoca':step,'pasos_por_epoca':batches,'perdida_media_lotes_raw':sum_loss/step,'pico_ram_mib_raw':peak/1024**2,'ultima_actualizacion_utc':now()})
                dump(output/'estado.json',state)
                print(f'Epoca {epoch}/{config["epochs"]}: paso {step}/{batches}',flush=True)
        train_seconds=time.perf_counter()-epoch_start
        print(f'Evaluando epoca {epoch} solo en validation...',flush=True)
        model.eval();pred=[];ys=[]
        with torch.no_grad():
            for batch in val_loader:
                labels=batch.pop('labels');logits=model(**batch).logits
                assert torch.isfinite(logits).all()
                pred.extend(logits.argmax(dim=1).tolist());ys.extend(labels.tolist())
        val=metrics(ys,pred)
        epoch_path=output/f'.epoca_{epoch:02d}_incompleta_{time.time_ns()}';epoch_path.mkdir(exist_ok=False)
        model.save_pretrained(epoch_path/'modelo',safe_serialization=True);tokenizer.save_pretrained(epoch_path/'modelo')
        torch.save({'optimizer':optimizer.state_dict(),'scheduler':scheduler.state_dict(),'torch_rng':torch.get_rng_state()},epoch_path/'optimizador.pt')
        dump(epoch_path/'metricas_validation.json',val)
        dump(epoch_path/'predicciones_validation.json',[{'id_origen':r['id_origen'],'fuente':r['fuente'],'real':r['etiqueta'],'predicha':next(k for k,v in LABELS.items() if v==p)} for r,p in zip(rows['validation'],pred)])
        state['historial'].append({'epoca':epoch,'validation_macro_f1_raw':val['macro_f1_raw'],'validation_accuracy_raw':val['accuracy_raw'],'media_perdida_lotes_raw':sum_loss/batches,'entrenamiento_segundos_raw':train_seconds})
        if state['mejor_validation'] is None or val['macro_f1_raw']>state['mejor_validation']['macro_f1_raw']:
            state['mejor_epoca']=epoch;state['mejor_validation']=val
        state.update({'epocas_completadas':epoch,'ultima_actualizacion_utc':now()})
        # Publicar la carpeta de época sólo cuando todos sus archivos estén guardados.
        hashes={str(p.relative_to(epoch_path)).replace('\\','/'):sha(p) for p in epoch_path.rglob('*') if p.is_file()}
        dump(epoch_path/'checkpoint_manifest.json',hashes)
        dump(epoch_path/'estado_al_final.json',state)
        epoch_path.rename(output/f'epoca_{epoch:02d}')
        dump(output/'estado.json',state)
        report_markdown(output,state,reference)
        print('Epoca '+str(epoch)+': macro-F1 validation '+percent(val['macro_f1_raw']),flush=True)
    best_path=output/f'epoca_{state["mejor_epoca"]:02d}'/'modelo'
    del optimizer,scheduler,model
    # Recargar el mejor, no simplemente el último checkpoint.
    best=AutoModelForSequenceClassification.from_pretrained(str(best_path),local_files_only=True,trust_remote_code=False,use_safetensors=True)
    assert best.config.label2id==LABELS
    best.eval()
    with torch.no_grad():
        batch=next(iter(val_loader));batch.pop('labels');check=best(**batch).logits
    assert torch.isfinite(check).all() and check.shape[1]==3
    state.update({'estado':'COMPLETADO','final_utc':now(),'mejor_checkpoint':str(best_path.relative_to(output)).replace('\\','/'),'recarga_mejor_checkpoint':'APROBADA','mejora_macro_f1_validation_raw':state['mejor_validation']['macro_f1_raw']-reference['macro_f1_raw'],'hashes_mejor_checkpoint':{p.name:sha(p) for p in best_path.iterdir() if p.is_file()}})
    dump(output/'estado.json',state);report_markdown(output,state,reference)
    print(json.dumps({'estado':'COMPLETADO','smoke':smoke,'mejor_epoca':state['mejor_epoca'],'test_utilizado':False},ensure_ascii=True),flush=True)

def predict(run_id,question,comment):
    setup(True)
    import torch
    from transformers import AutoTokenizer,AutoModelForSequenceClassification
    output=BASE/run_id;state=json.loads((output/'estado.json').read_text(encoding='utf-8'))
    assert state['estado']=='COMPLETADO' and not state['smoke'],'Se requiere ejecución completa, no smoke'
    folder=output/state['mejor_checkpoint']
    for name,expected in state['hashes_mejor_checkpoint'].items():assert sha(folder/name)==expected
    torch.set_num_threads(4)
    tokenizer=AutoTokenizer.from_pretrained(str(folder),local_files_only=True,trust_remote_code=False)
    model=AutoModelForSequenceClassification.from_pretrained(str(folder),local_files_only=True,use_safetensors=True,trust_remote_code=False).eval()
    encoded=tokenizer(question,comment,truncation='only_second',max_length=state['config']['max_length'],return_tensors='pt')
    with torch.no_grad():prob=torch.softmax(model(**encoded).logits,dim=-1)[0]
    index=int(prob.argmax());label=next(k for k,v in LABELS.items() if v==index)
    print(json.dumps({'estado':'EXPERIMENTAL','etiqueta':label,'score_visible':percent(float(prob[index])),'scores_raw_no_calibrados':{k:float(prob[v]) for k,v in LABELS.items()},'aplica_solo_a_comentarios_informativos':True},ensure_ascii=True))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('accion',choices=['smoke','entrenar','reanudar','estado','predecir'])
    parser.add_argument('--ejecucion',required=True)
    parser.add_argument('--pregunta');parser.add_argument('--comentario')
    args=parser.parse_args()
    assert re.fullmatch(r'[A-Za-z0-9_-]{1,64}',args.ejecucion),'Nombre inválido'
    if args.accion=='estado':
        print((BASE/args.ejecucion/'estado.json').read_text(encoding='utf-8'))
    elif args.accion=='predecir':
        assert args.pregunta and args.comentario
        predict(args.ejecucion,args.pregunta,args.comentario)
    else:
        existed=(BASE/args.ejecucion).exists()
        try:run(args.ejecucion,smoke=args.accion=='smoke',resume=args.accion=='reanudar')
        except (Exception,KeyboardInterrupt) as error:
            path=BASE/args.ejecucion/'estado.json'
            if path.exists() and (not existed or args.accion=='reanudar'):
                state=json.loads(path.read_text(encoding='utf-8'))
                if state['estado']!='COMPLETADO':
                    state.update({'estado':'INTERRUMPIDO' if isinstance(error,KeyboardInterrupt) else 'FALLIDO','tipo_error':type(error).__name__,'ultima_actualizacion_utc':now()});dump(path,state)
            raise
