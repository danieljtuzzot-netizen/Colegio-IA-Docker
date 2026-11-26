"""Prueba 1.5B con evidencia ficticia; no certifica fidelidad ni calidad general."""
import json
import sys
import time
import urllib.request
sys.path.insert(0, '/config')
from vllm_piloto import ALIAS


def payload():
    return {'model':ALIAS,'temperature':0,'seed':42,'stream':False,'max_tokens':650,
        'messages':[
            {'role':'system','content':'Redacta una respuesta explicativa en español, con tus palabras, en tres oraciones y unas 60 palabras. Contesta directamente, explica el respaldo y delimita su alcance. Usa solo la evidencia ficticia; no inventes efectos en el aprendizaje, resultados, causas o recomendaciones. La observacion no demuestra que los estudiantes adquieran habilidades o competencias: no lo afirmes. No llames excepcion a una observacion individual: solo indica que su alcance se limita a ese caso. No copies literalmente la cita. Devuelve el JSON del esquema.'},
            {'role':'user','content':'Pregunta: ¿Qué fortalezas aparecen sobre plataformas educativas? Evidencia ficticia F1: Una observación sobre un docente indica que domina las plataformas educativas y explica a sus estudiantes cómo utilizarlas. Es una sola observación, no una medición de todo el colegio.'}],
        'structured_outputs':{'json':{'type':'object','properties':{
            'respuesta':{'type':'string'},'referencias':{'type':'object','properties':{'F1':{'type':'boolean'}},'required':['F1'],'additionalProperties':False}},
            'required':['respuesta','referencias'],'additionalProperties':False}}}


def main():
    if ALIAS!='qwen-piloto-15b':raise RuntimeError('Esta prueba requiere el candidato 1.5B.')
    base='http://127.0.0.1:8000'
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(base+'/v1/models',timeout=10) as response:models=json.load(response)
    if ALIAS not in {row.get('id') for row in models.get('data',[])}:raise RuntimeError('Modelo candidato no disponible.')
    started=time.perf_counter()
    print('Prueba de redaccion: JSON compacto debe estar configurado en el servidor.',flush=True)
    req=urllib.request.Request(base+'/v1/chat/completions',data=json.dumps(payload()).encode(),headers={'Content-Type':'application/json'})
    with opener.open(req,timeout=600) as response:value=json.load(response)
    choices=value.get('choices',[])
    print('Modelo esperado:',ALIAS,flush=True)
    print('Modelo recibido:',value.get('model'),flush=True)
    print('Fin de generacion:',[choice.get('finish_reason') for choice in choices],flush=True)
    print('Uso de tokens:',json.dumps(value.get('usage'),ensure_ascii=True),flush=True)
    print('Segundos de la peticion:',round(time.perf_counter()-started),flush=True)
    # Esta prueba sólo usa el ejemplo ficticio fijo definido arriba.
    for choice in choices:
        print('Contenido ficticio recibido:',repr(choice.get('message',{}).get('content','')[:5000]),flush=True)
    if value.get('model')!=ALIAS:raise RuntimeError('El modelo devuelto no coincide con el candidato fijado.')
    if len(choices)!=1:raise RuntimeError('Cantidad de respuestas inesperada.')
    if choices[0].get('finish_reason')!='stop':raise RuntimeError('Generacion sin cierre completo: '+str(choices[0].get('finish_reason')))
    answer=json.loads(choices[0]['message']['content'])
    if set(answer)!={'respuesta','referencias'} or not isinstance(answer['respuesta'],str) or not 80<=len(answer['respuesta'])<=1200 or answer['referencias']!={'F1':True}:
        raise ValueError('Respuesta sin formato o referencia requerida.')
    print('Candidato 1.5B: API, respuesta completa y referencia APROBADAS.')
    print('RESPUESTA FICTICIA:',answer['respuesta'])
    print('Segundos de esta peticion:',round(time.perf_counter()-started))
    print('Revisar: responde la pregunta, reformula sin copiar y no inventa efectos ni generaliza. No es una certificacion de calidad.')


if __name__=='__main__':main()
