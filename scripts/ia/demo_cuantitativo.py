"""Agregados cuantitativos históricos; sin datos personales ni unión inferida con NLP."""
import hashlib
import json
import math
from pathlib import Path
from demo_dashboard import ROOT, checked

SOURCE = ROOT/'data/ia/versiones/20261027_MULTIFUENTE'
FOLDER = ROOT/'data/ia/demo_local/historico_cuantitativo_20261027_v1'
CURRENT = ROOT/'data/ia/demo_local/cuantitativo_20261116_v1'
SOURCES = {'ESTUDIANTES','AUTOEVALUACION','JEFE','LENGUAS','CAPELLANIA','PENDIENTE_DE_RESOLVER'}

def derive(report):
    sources={}
    for code, row in report['promedio_fuente_raw'].items():
        n, mean=row['cantidad'], row['promedio_raw']
        if code not in SOURCES or type(n) is not int or n<=0 or not isinstance(mean,(int,float)) or not math.isfinite(mean) or not 1<=mean<=5:
            raise ValueError('Agregado histórico inválido.')
        sources[code]={'respuestas':n,'porcentaje_descriptivo_raw':mean/5*100}
    distribution=report['conteo_calificacion']
    if set(distribution)!={'1','2','3','4','5'} or any(type(n) is not int or n<0 for n in distribution.values()):
        raise ValueError('Distribución histórica inválida.')
    count=sum(distribution.values())
    if not count or count!=sum(r['respuestas'] for r in sources.values()):
        raise ValueError('Conteos históricos inconsistentes.')
    total=sum(int(k)*n for k,n in distribution.items())/count/5*100
    combined=sum(r['porcentaje_descriptivo_raw']*r['respuestas'] for r in sources.values())/count
    if not math.isclose(total,combined,abs_tol=1e-8):raise ValueError('Promedios históricos inconsistentes.')
    return {'fuentes':sources,'total':{'respuestas':count,'porcentaje_descriptivo_raw':total,'distribucion':distribution},
            'fecha_corte':'2026-10-27','periodo':'NO_DESAGREGADO_EN_ESTE_ARTEFACTO',
            'metodo':'PROMEDIO_DESCRIPTIVO_RESPUESTAS_ESCALA_1_5_SIN_PONDERAR',
            'alcance':'Histórico de auditoría del 27 de octubre de 2026. Incluye registros con periodo o fuente pendientes de resolver. No se filtra por el periodo 2026-II del dashboard ni se une a la muestra de comentarios. Son promedios de respuestas, no resultados oficiales ponderados ni indicadores de desempeño individual.',
            'resultado_institucional_oficial':False,'datos_en_vivo':False,'produccion_activada':False}

def load_quantitative():
    manifest=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('estado')!='DERIVADO_HISTORICO_VERIFICADO' or manifest.get('fecha_corte')!='2026-10-27':
        raise ValueError('Histórico no verificado.')
    for name,digest in manifest['sha256_origen'].items():
        if name not in ('reporte_calidad.json','dataset_comentarios.manifest.json') or hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('El origen histórico cambió.')
    data=checked(FOLDER,'resumen.json',manifest)
    original=json.loads((SOURCE/'reporte_calidad.json').read_text(encoding='utf-8'))
    if data!=derive(original):raise ValueError('Derivado inconsistente con la auditoría.')
    return data

def validate_current(data):
    if data.get('estado')!='COMPLETADO' or data.get('periodo')!='2026-II' or data.get('sql_solo_lectura') is not True or data.get('resultado_institucional_oficial') is not False:
        raise ValueError('Snapshot fuera del alcance permitido.')
    if set(data['fuentes'])!=SOURCES-{'PENDIENTE_DE_RESOLVER'}:
        raise ValueError('Fuentes incompletas o no permitidas.')
    for row in [data['total'],*data['fuentes'].values()]:
        count=row['respuestas']; distribution=row['distribucion']
        if type(count) is not int or count<0 or set(distribution)!={'1','2','3','4','5'}:
            raise ValueError('Distribución inválida.')
        if any(type(n) is not int or n<0 for n in distribution.values()) or sum(distribution.values())!=count:
            raise ValueError('Conteos inválidos.')
        weighted=sum(int(k)*n for k,n in distribution.items())
        if type(row['suma_raw']) is not int or weighted!=row['suma_raw']:
            raise ValueError('Suma numérica inconsistente.')
        raw=row['porcentaje_descriptivo_raw']
        if (not count and raw is not None) or (count and (not isinstance(raw,(int,float)) or not math.isfinite(raw) or not math.isclose(raw,weighted/count/5*100,abs_tol=1e-8))):
            raise ValueError('Promedio numérico inconsistente.')
        teachers=row['docentes_cantidad']
        if type(teachers) is not int or not 0<=teachers<=count:
            raise ValueError('Conteo de docentes inválido.')
    total=data['total']; sources=list(data['fuentes'].values())
    if total['respuestas']!=sum(r['respuestas'] for r in sources) or total['suma_raw']!=sum(r['suma_raw'] for r in sources):
        raise ValueError('Cobertura inconsistente.')
    if any(total['distribucion'][k]!=sum(r['distribucion'][k] for r in sources) for k in total['distribucion']):
        raise ValueError('Distribución entre fuentes inconsistente.')
    if not max(r['docentes_cantidad'] for r in sources)<=total['docentes_cantidad']<=sum(r['docentes_cantidad'] for r in sources):
        raise ValueError('Cobertura de docentes inconsistente.')
    if data['cerradas_snapshot']!=total['respuestas']+data['cerradas_fuera_agregado'] or data['cerradas_fuera_agregado']<0:
        raise ValueError('Cobertura del snapshot inconsistente.')

def load_current():
    manifest=json.loads((CURRENT/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('estado')!='COMPLETADO' or manifest.get('periodo')!='2026-II' or manifest.get('sql_solo_lectura') is not True or manifest.get('datos_personales_exportados') is not False:
        raise ValueError('Exportación no autorizada para esta vista.')
    data=checked(CURRENT,'resumen.json',manifest)
    validate_current(data)
    return {**data,'datos_en_vivo':False,'produccion_activada':False}

def load_views():
    return {'versiones':{'actual':load_current(),'historico':load_quantitative()},'predeterminada':'actual'}

def prepare():
    if FOLDER.exists():raise ValueError('La versión existe; no se sobrescribe.')
    report=json.loads((SOURCE/'reporte_calidad.json').read_text(encoding='utf-8'))
    source_manifest=json.loads((SOURCE/'dataset_comentarios.manifest.json').read_text(encoding='utf-8'))
    if (report['huella_snapshot']!=source_manifest['huella_snapshot'] or report['consulta_sha256']!=source_manifest['consulta_sha256'] or source_manifest.get('solo_lectura_sql') is not True):
        raise ValueError('La auditoría no corresponde al snapshot registrado.')
    data=derive(report)
    FOLDER.mkdir(parents=True)
    (FOLDER/'.htaccess').write_text('Require all denied\n',encoding='utf-8')
    (FOLDER/'.gitignore').write_text('*\n',encoding='utf-8')
    (FOLDER/'resumen.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={'estado':'DERIVADO_HISTORICO_VERIFICADO','fecha_corte':'2026-10-27',
              'huella_snapshot':report['huella_snapshot'],
              'sha256_origen':{name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() for name in ('reporte_calidad.json','dataset_comentarios.manifest.json')},
              'sha256_archivos':{'resumen.json':hashlib.sha256((FOLDER/'resumen.json').read_bytes()).hexdigest()},
              'mariadb_consultada':False,'datos_personales_exportados':False}
    (FOLDER/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    load_quantitative()
    print(json.dumps({'estado':manifest['estado'],'respuestas':data['total']['respuestas'],'fuentes':len(data['fuentes']),'mariadb_consultada':False}))

if __name__=='__main__':prepare()
