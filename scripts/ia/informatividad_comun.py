"""Contrato binario y reglas acotadas a preguntas abiertas; conserva símbolos."""
import collections
import json
import unicodedata
from pathlib import Path
from entrenar_sentimiento_beto import ROOT,sha,dump,percent

CONFIG=ROOT/'scripts/ia/informatividad_config_v1.json'
LABELS={'NO_INFORMATIVO':0,'INFORMATIVO':1}

def normalizar(text):
    if not isinstance(text,str):raise ValueError('Se requieren textos, no otros tipos')
    return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())

def regla_ausencia(question,comment,config):
    q,c=normalizar(question),normalizar(comment)
    if not c:return 'COMENTARIO_VACIO'
    # NO se aplican placeholders a NIVEL DE IDIOMA, CERTIFICADO, FORTALEZAS, etc.
    abierta=(('observaci' in q or 'mensaje' in q) and 'docente' in q) or q in config['preguntas_abiertas_exactas']
    if abierta and c in config['ausencias_explicitas']:return 'AUSENCIA_EXPLICITA_EN_PREGUNTA_ABIERTA'
    return None

def leer_particiones(config):
    folder=ROOT/'data/ia/versiones'/config['dataset_version']
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    result={}
    for split in ('train','validation'):
        path=folder/f'informatividad_{split}.jsonl'
        assert sha(path)==manifest['archivos'][path.name]['sha256'],'Hash incorrecto'
        rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        assert len(rows)==manifest['archivos'][path.name]['cantidad']
        assert len({r['id_origen'] for r in rows})==len(rows)
        assert all(r['etiqueta'] in LABELS for r in rows)
        assert dict(collections.Counter(r['etiqueta'] for r in rows))==manifest['archivos'][path.name]['clases']
        result[split]=rows
    for field in ('id_origen','grupo_split'):
        assert not {r[field] for r in result['train']}&{r[field] for r in result['validation']}
    return result,manifest

def metricas(y,pred):
    from sklearn.metrics import accuracy_score,classification_report,confusion_matrix,f1_score
    names=['NO_INFORMATIVO','INFORMATIVO']
    return {'accuracy_raw':float(accuracy_score(y,pred)),'macro_f1_raw':float(f1_score(y,pred,labels=[0,1],average='macro',zero_division=0)),'por_clase':classification_report(y,pred,labels=[0,1],target_names=names,output_dict=True,zero_division=0),'matriz_confusion':confusion_matrix(y,pred,labels=[0,1]).tolist(),'orden_clases':names,'cantidad':len(y),'informativos_marcados_no_informativos':sum(a==1 and b==0 for a,b in zip(y,pred))}

def predecir_filtro(model,config,questions,comments):
    assert len(questions)==len(comments)
    for q,c in zip(questions,comments):normalizar(q);normalizar(c)
    scores=model.predict_proba([q+'\n'+c for q,c in zip(questions,comments)])
    classes=[int(x) for x in model.classes_]
    assert classes==[0,1]
    result=[]
    for q,c,probs in zip(questions,comments,scores):
        rule=regla_ausencia(q,c,config)
        original=int(probs.argmax());chosen=0 if rule else original
        label=next(k for k,v in LABELS.items() if v==chosen)
        result.append({'etiqueta':label,'prediccion_modelo':next(k for k,v in LABELS.items() if v==original),'origen':'REGLA_TAXONOMIA' if rule else 'CLASIFICADOR_TFIDF','regla':rule,'scores_raw_no_calibrados':{k:float(probs[v]) for k,v in LABELS.items()},'score_visible':None if rule else percent(float(probs[chosen]))})
    return result

def cargar_filtro(folder):
    import joblib
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['estado']=='EVALUADO_EXPERIMENTAL'
    assert sha(folder/'modelo_informatividad.joblib')==manifest['sha256_modelo']
    assert sha(folder/'config.json')==manifest['sha256_config']
    assert sha(Path(__file__))==manifest['sha256_codigo_contrato'],'Cambió el contrato; requiere nueva versión'
    config=json.loads((folder/'config.json').read_text(encoding='utf-8'))
    return joblib.load(folder/'modelo_informatividad.joblib'),config,manifest
