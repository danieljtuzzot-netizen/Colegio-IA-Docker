"""Candidata por cláusulas: prueba sintética de desarrollo, sin test ni activación."""
import json
import re
from pathlib import Path
from piloto_beto import ROOT,protect,sha,dump
from entrenar_sentimiento_beto import percent
from desarrollo_ollama_v3 import SYSTEM,LABELS
from ollama_resumen_local import MODEL,PIN,managed_server,local_model,request

def clauses(text):
    separators=list(re.finditer(r'(?<=[.!?])\s+|\bpero\b|\baunque\b|\bsin embargo\b|\s+y\s+',text,re.I))
    spans=[];start=0
    for stop,end in [(m.start(),m.end()) for m in separators]+[(len(text),len(text))]:
        a=start;b=stop
        while a<b and text[a].isspace():a+=1
        while b>a and text[b-1].isspace():b-=1
        if b>a:spans.append({'inicio':a,'fin':b,'texto':text[a:b]})
        start=end
    return spans or [{'inicio':0,'fin':len(text),'texto':text}]

def combine(labels):
    if 'MIXTO' in labels or {'FORTALEZA','OPORTUNIDAD'}<=set(labels):return 'MIXTO'
    for label in ('OPORTUNIDAD','FORTALEZA','CONTEXTO'): 
        if label in labels:return label
    return 'ABSTENCION'

def run():
    source=ROOT/'data/ia/desarrollo/ollama_sintetico_20261116_v1';v3=ROOT/'data/ia/desarrollo/ollama_sintetico_v3_20261116_v1'
    out=ROOT/'data/ia/desarrollo/ollama_sintetico_v4_20261116_v1';assert not out.exists()
    m=json.loads((v3/'manifest.json').read_text(encoding='utf-8'))
    for name,h in m['sha256_archivos'].items():assert sha(v3/name)==h
    examples=json.loads((source/'ejemplos_sinteticos.json').read_text(encoding='utf-8'))
    assert sha(source/'ejemplos_sinteticos.json')==m['sha256_ejemplos']
    managed_server();tag,_=local_model();assert tag['digest']==m['digest']==json.loads(PIN.read_text(encoding='utf-8'))['digest']
    protect(out);results=[];cache={}
    for row in examples:
        payload=json.loads((v3/(row['id']+'_solicitud.json')).read_text(encoding='utf-8'))
        response=json.loads((v3/(row['id']+'_respuesta.json')).read_text(encoding='utf-8'))
        assert payload['system']==SYSTEM and json.loads(payload['prompt'])=={'comentario':row['comentario']}
        cache[row['comentario']]=json.loads(response['response'])['categoria']
    calls=0
    for row in examples:
        parts=clauses(row['comentario']);predicted=[]
        for n,part in enumerate(parts):
            assert row['comentario'][part['inicio']:part['fin']]==part['texto']
            if part['texto'] in cache:label=cache[part['texto']]
            else:
                payload={'model':MODEL,'system':SYSTEM,'prompt':json.dumps({'comentario':part['texto']},ensure_ascii=False),'format':{'type':'object','properties':{'categoria':{'type':'string','enum':LABELS}},'required':['categoria'],'additionalProperties':False},'stream':False,'keep_alive':'5m','options':{'temperature':0,'seed':42,'num_ctx':4096,'num_predict':80,'num_thread':4,'num_gpu':0}}
                stem=row['id']+'_'+str(n);dump(out/(stem+'_solicitud.json'),payload)
                response=request('/api/generate',payload,timeout=300);dump(out/(stem+'_respuesta.json'),response);calls+=1
                value=json.loads(response['response']);assert response['done'] and response['done_reason']=='stop' and set(value)=={'categoria'} and value['categoria'] in LABELS
                label=value['categoria'];cache[part['texto']]=label
            predicted.append({**part,'categoria':label})
        results.append({'id':row['id'],'esperado':row['esperado'],'predicho':combine([p['categoria'] for p in predicted]),'clausulas':predicted})
        dump(out/'resultados.json',results);print(json.dumps({'v4_procesados':len(results),'total':25,'llamadas_nuevas':calls}),flush=True)
    summary={'n':25,'coincidencias':sum(r['esperado']==r['predicho'] for r in results),'llamadas_nuevas':calls,'por_clase':{l:{'n':5,'coincidencias':sum(r['esperado']==r['predicho'] for r in results if r['esperado']==l)} for l in LABELS}}
    dump(out/'resumen_raw.json',summary)
    lines=['# Candidata v4: cláusulas en desarrollo sintético','', 'Batería inventada y utilizada durante el ajuste. No es evaluación independiente ni rendimiento institucional. Las predicciones idénticas de v3 se reutilizan por texto exacto; las cláusulas nuevas se infieren con el mismo modelo y parámetros.','',f"Acuerdo sintético: {summary['coincidencias']}/25 ({percent(summary['coincidencias']/25)}).",'', '| Clase | Aciertos |','|---|---:|']
    lines += [f"| {l} | {r['coincidencias']}/5 |" for l,r in summary['por_clase'].items()]
    lines += ['', 'La separación conserva posiciones originales, pero puede alterar el alcance de negaciones, sarcasmo o contexto. Esto exige pruebas de regresión adicionales; no activar como reemplazo. El siguiente paso debe usar datos reales de desarrollo, no el test consumido ni la reserva restante.']
    (out/'INFORME_DESARROLLO.md').write_text('\n'.join(lines),encoding='utf-8')
    dump(out/'manifest.json',{'estado':'COMPLETADO_DESARROLLO_SINTETICO','sha256_script':sha(Path(__file__)),'sha256_cache_origen':sha(v3/'manifest.json'),'sha256_ejemplos':sha(source/'ejemplos_sinteticos.json'),'test_abierto':False,'produccion_activada':False,'digest':tag['digest'],'sha256_archivos':{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name not in ('manifest.json','.gitignore','.htaccess')}})

if __name__=='__main__':run()
