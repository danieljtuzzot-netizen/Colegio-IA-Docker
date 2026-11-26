"""Prueba HTTP desde el host después de docker compose up; no guarda consultas."""
import argparse
import json
import re
import urllib.request


def main(infer=False):
    base='http://127.0.0.1:8766'
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(base+'/dashboard',timeout=10) as response:html=response.read().decode('utf-8')
    token=re.search("window.DEMO_TOKEN='([^']+)'",html).group(1)
    headers={'X-Demo-Token':token}
    for route in ['health','api/dashboard','api/cuantitativo','api/vinculos','api/ml','api/temas']:
        with opener.open(urllib.request.Request(base+'/'+route,headers=headers),timeout=15) as response:json.load(response)
        print(route+': OK')
    body={'pregunta':'¿Qué oportunidades hay en tecnología?','fuente':'JEFE','categoria':'FORTALEZA','modo_recuperacion':'hibrido'}
    def query(data):
        req=urllib.request.Request(base+'/api/consultar',data=json.dumps(data).encode(),headers={**headers,'Content-Type':'application/json'})
        with opener.open(req,timeout=400) as response:return json.load(response)
    result=query(body)
    if result['estado']!='FILTRO_INCOMPATIBLE' or result['llm_ejecutado']:raise ValueError('Contrato de filtros incorrecto.')
    print('Conflicto de filtros sin inferencia: OK')
    if infer:
        result=query({**body,'pregunta':'¿El profesorado sabe emplear ordenadores en el aula?','categoria':'FORTALEZA'})
        if result['estado']!='RESPUESTA_CON_EVIDENCIA' or not result['sintesis_ejecutada'] or not result['evidencias']:
            raise ValueError('Inferencia sin respuesta respaldada.')
        print('Síntesis real con referencias: OK (no certifica calidad general)')
        req=urllib.request.Request(base+'/api/analizar',data=json.dumps({'pregunta':'Escriba una observación sobre su docente.','comentario':'Explica con claridad y responde nuestras dudas.'}).encode(),headers={**headers,'Content-Type':'application/json'})
        with opener.open(req,timeout=400) as response:result=json.load(response)
        if not result.get('beto_ejecutado') or not result.get('tipo'):raise ValueError('Inferencia BETO/Ollama incompleta.')
        print('BETO + tipo Ollama con ejemplo ficticio: OK')
    print('Prueba Docker completada. Producción no activada.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--inferencia',action='store_true')
    main(parser.parse_args().inferencia)
