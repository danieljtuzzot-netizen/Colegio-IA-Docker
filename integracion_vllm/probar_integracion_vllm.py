"""Prueba del asistente integrado: sólo piloto autorizado, sin guardar consultas."""
import json
import re
import sys
import urllib.request
from rag_respuestas import validate_answer

QUESTION='¿Qué fortaleza describe el comentario sobre el dominio y uso de plataformas educativas?'


def validate_result(result, expected):
    if result.get('motor')!='vllm' or result.get('modelo')!=expected:
        raise RuntimeError('Motor/modelo inesperado.')
    state=result.get('estado')
    if state not in ('RESPUESTA_CON_EVIDENCIA','EVIDENCIA_INSUFICIENTE') or result.get('sintesis_ejecutada') is not True:
        raise RuntimeError('Etapa no completada con respuesta o abstencion valida: '+str(state))
    claims=result.get('afirmaciones')
    validate_answer({'insuficiente':state=='EVIDENCIA_INSUFICIENTE','afirmaciones':claims},result.get('evidencias',[]))
    if state=='RESPUESTA_CON_EVIDENCIA' and not result.get('evidencias'):
        raise ValueError('Respuesta sin evidencias.')
    return state


def main():
    base='http://127.0.0.1:8766'
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(base+'/dashboard',timeout=10) as response:
        token=re.search("window.DEMO_TOKEN='([^']+)'",response.read().decode()).group(1)
    headers={'X-Demo-Token':token,'Content-Type':'application/json'}
    with opener.open(urllib.request.Request(base+'/api/motores',headers=headers),timeout=10) as response:
        config=json.load(response)
        if not config.get('vllm'):raise RuntimeError('Integracion vLLM no habilitada.')
        expected=config['vllm_config']['modelo']
        print('Modelo configurado:',expected,flush=True)
    print('Consulta acotada a lo que describe un comentario, sin evaluar al profesorado en general.',flush=True)
    payload={'pregunta':QUESTION,
             'fuente':'JEFE','categoria':'FORTALEZA','modo_recuperacion':'hibrido','motor':'vllm'}
    request=urllib.request.Request(base+'/api/consultar',data=json.dumps(payload).encode(),headers=headers)
    with opener.open(request,timeout=650) as response:result=json.load(response)
    print('Estado recibido:',result.get('estado'),flush=True)
    state=validate_result(result,expected)
    if state=='EVIDENCIA_INSUFICIENTE':
        print('La API y el contrato de abstencion son validos; el modelo no genero afirmaciones.')
        print('La prueba de respuesta positiva queda PENDIENTE. No se modifica ni se fuerza la abstencion.')
        return 2
    print('Asistente con vLLM: respuesta y referencias estructurales APROBADAS.')
    print('Revisar fidelidad del contenido en el dashboard. No certifica precision general.')
    return 0


if __name__=='__main__':sys.exit(main())
