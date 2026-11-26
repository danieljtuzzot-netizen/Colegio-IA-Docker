"""Almacenamiento explícito y exportación de revisiones de la demo, separado de modelos."""
import csv
import io
import json
import secrets
import threading
import time
from datetime import datetime,timezone
from piloto_beto import ROOT,protect

STORE=ROOT/'data/ia/demo_local/revisiones'
PENDING={}
MUTEX=threading.RLock()
TYPES={'FORTALEZA','OPORTUNIDAD','MIXTO','CONTEXTO','ABSTENCION'}

def register(question,comment,result):
    if result.get('estado')=='RETENIDO_PRIVACIDAD':return result
    with MUTEX:
        now=time.time()
        for key in list(PENDING):
            if now-PENDING[key]['created']>3600:del PENDING[key]
        while len(PENDING)>=100:del PENDING[next(iter(PENDING))]
        ident=secrets.token_hex(16)
        PENDING[ident]={'created':now,'pregunta':question,'comentario':comment,'propuesta_original':json.loads(json.dumps(result)),'revisiones':[]}
        return {**result,'analisis_id':ident}

def validate_review(data):
    if set(data)!={'analisis_id','informatividad','sentimiento','tipo','ambiguo','mixto','motivo','privacidad_confirmada'}:raise ValueError('Campos de revisión inválidos.')
    if data['privacidad_confirmada'] is not True:raise ValueError('Confirma que el texto es ficticio o que su privacidad fue revisada antes de guardarlo.')
    if not isinstance(data['analisis_id'],str):raise ValueError('Identificador inválido.')
    for field,allowed in [('informatividad',{'INFORMATIVO','NO_INFORMATIVO'}),('sentimiento',{'','POSITIVO','NEGATIVO','NEUTRAL'}),('tipo',TYPES),('ambiguo',{'SI','NO'}),('mixto',{'SI','NO'})]:
        if not isinstance(data[field],str) or data[field] not in allowed:raise ValueError('Completa correctamente el campo '+field+'.')
    if not isinstance(data['motivo'],str) or not 3<=len(data['motivo'].strip())<=1000:raise ValueError('Escribe un motivo de entre 3 y 1000 caracteres.')
    if data['informatividad']=='NO_INFORMATIVO' and (data['sentimiento'] or data['tipo']!='ABSTENCION' or data['mixto']!='NO'):
        raise ValueError('NO_INFORMATIVO requiere sentimiento vacío, tipo ABSTENCION y Mixto = NO.')
    if data['informatividad']=='INFORMATIVO' and not data['sentimiento']:raise ValueError('Para guardar INFORMATIVO debes adjudicar el sentimiento; si no puedes, déjalo sin guardar para revisión.')
    if (data['tipo']=='MIXTO')!=(data['mixto']=='SI'):raise ValueError('El tipo MIXTO y Mixto = SI deben coincidir.')
    if data['mixto']=='SI' and data['ambiguo']!='SI':raise ValueError('Según la guía vigente, los mixtos requieren Ambiguo = SI.')
    return {k:data[k].strip() for k in ('informatividad','sentimiento','tipo','ambiguo','mixto','motivo')}

def save(data):
    decision=validate_review(data)
    with MUTEX:
        case=PENDING.get(data['analisis_id'])
        if case is None or time.time()-case['created']>3600:raise ValueError('El análisis expiró o pertenece a otra sesión del servidor. Analiza el comentario de nuevo.')
        if case['revisiones'] and case['revisiones'][-1]['revision_humana']==decision:return case['revisiones'][-1]
        original=case['propuesta_original']
        changed=[k for k in ('informatividad','sentimiento','tipo') if decision[k]!=(original.get(k) or '')]
        record={'revision_id':secrets.token_hex(16),'analisis_id':data['analisis_id'],'version_revision':len(case['revisiones'])+1,
            'fecha_utc':datetime.now(timezone.utc).isoformat(),'pregunta':case['pregunta'],'comentario':case['comentario'],
            'propuesta_original':original,'revision_humana':decision,'campos_corregidos':changed,
            'resultado':'CORREGIDO' if changed else 'ACEPTADO','origen':'REVISION_EXPLICITA_EN_DEMO_LOCAL',
            'privacidad_confirmada_por_operador':True,'gold_independiente':False,'produccion_activada':False}
        protect(STORE)
        path=STORE/(record['revision_id']+'.json')
        with path.open('x',encoding='utf-8') as file:json.dump(record,file,ensure_ascii=False,indent=2)
        case['revisiones'].append(record)
        return record

def records():
    with MUTEX:
        if not STORE.exists():return []
        result=[json.loads(p.read_text(encoding='utf-8')) for p in STORE.glob('*.json')]
        return sorted(result,key=lambda r:r['fecha_utc'],reverse=True)

def safe_cell(value):
    s='' if value is None else str(value)
    return "'"+s if s.lstrip().startswith(('=','+','-','@')) or s.startswith(('\t','\r','\n')) else s

def csv_export(rows):
    output=io.StringIO(newline='');writer=csv.writer(output)
    writer.writerow(['revision_id','analisis_id','version_revision','fecha_utc','pregunta','comentario','informatividad_modelo','sentimiento_modelo','tipo_modelo','tipo_experimental','informatividad_humana','sentimiento_humano','tipo_humano','ambiguo','mixto','motivo','resultado','versiones_modelos','modelo_ollama'])
    for r in rows:
        p=r['propuesta_original'];h=r['revision_humana']
        values=[r['revision_id'],r['analisis_id'],r['version_revision'],r['fecha_utc'],r['pregunta'],r['comentario'],p.get('informatividad'),p.get('sentimiento'),p.get('tipo'),p.get('tipo_experimental'),h['informatividad'],h['sentimiento'],h['tipo'],h['ambiguo'],h['mixto'],h['motivo'],r['resultado'],json.dumps(p.get('versiones',{}),ensure_ascii=False),p.get('ollama_modelo')]
        writer.writerow([safe_cell(v) for v in values])
    return ('\ufeff'+output.getvalue()).encode('utf-8')
