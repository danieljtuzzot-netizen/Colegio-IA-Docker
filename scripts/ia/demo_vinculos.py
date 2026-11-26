"""Prepara y verifica vínculos descriptivos por códigos; nunca carga particiones test."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from demo_dashboard import ROOT, checked
from demo_cuantitativo import load_current, validate_current
from piloto_beto import protect

DATASET=ROOT/'data/ia/versiones/20261112_DATASET_BETO_V2'
BASE=ROOT/'data/ia/demo_local/vinculos_20261116_v1'
ORIGINAL=ROOT/'data/ia/lotes/cuatro_fuentes_20261112_v1'
REVISED=ROOT/'data/ia/lotes/revision_cuatro_fuentes_20261112_v2'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def inputs():
    manifest=read(DATASET/'manifest.json'); original=read(ORIGINAL/'manifest.json')
    if manifest['periodo']!='2026-II' or original.get('test_utilizado') is not False or original['particiones']!=['train','validation']:
        raise ValueError('Periodo o particiones fuera de alcance.')
    if sha(DATASET/'entrada_revisada.xlsx')!=manifest['entrada_sha256'] or manifest['entrada_sha256']!=original['sha256_aprobacion_privacidad']:
        raise ValueError('La referencia aprobada cambió.')
    retained={r['id_origen'] for r in read(DATASET/'retenidos_privacidad.json')}
    assignments={r['id_origen']:r['split'] for r in read(DATASET/'asignacion_splits.json')}
    result={}
    for part in ('train','validation'):
        path=DATASET/f'informatividad_{part}.jsonl'
        if sha(path)!=manifest['archivos'][path.name]['sha256'] or sha(path)!=original['sha256_entradas'][part]:
            raise ValueError('La partición autorizada cambió.')
        for line in path.read_text(encoding='utf-8').splitlines():
            row=json.loads(line);ident=row['id_origen']
            if ident in result or ident in retained or assignments.get(ident)!=part:
                raise ValueError('Identificador duplicado, retenido o fuera de partición.')
            result[ident]={'id_origen':ident,'fuente':row['fuente'],'particion':part,
                           'pregunta_sha256':hashlib.sha256(row['pregunta'].encode()).hexdigest(),
                           'comentario_sha256':hashlib.sha256(row['comentario'].encode()).hexdigest()}
    if len(result)!=original['total']:raise ValueError('Cobertura incompleta del lote.')
    return result

def prepare():
    plan=BASE/'plan.json'
    if plan.exists():raise ValueError('Plan existente: no sobrescribir.')
    expected=inputs(); load_current()
    protect(BASE)
    dump(plan,{'periodo':'2026-II','particiones':['train','validation'],'test_utilizado':False,
               'registros':list(expected.values()),'sha256_manifest_dataset':sha(DATASET/'manifest.json'),
               'sha256_manifest_lote':sha(ORIGINAL/'manifest.json')})
    print(json.dumps({'estado':'PLAN_PREPARADO','comentarios':len(expected),'test_utilizado':False}))

def results(folder,name,expected):
    manifest=read(folder/'manifest.json')
    if manifest.get('test_utilizado') is not False or manifest['particiones']!=['train','validation']:
        raise ValueError('Resultados fuera del alcance permitido.')
    path=folder/name
    if sha(path)!=manifest['sha256_archivos'][name]:raise ValueError('El resultado del modelo cambió.')
    rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    by_id={r['id_origen']:r for r in rows}
    if len(rows)!=len(by_id) or set(by_id)!=set(expected):raise ValueError('Cobertura de resultados inconsistente.')
    for ident,row in by_id.items():
        if row['particion']!=expected[ident]['particion'] or row['fuente']!=expected[ident]['fuente']:
            raise ValueError('La fuente o partición no corresponde.')
        if row['informatividad'] not in ('INFORMATIVO','NO_INFORMATIVO') or (row['informatividad']=='NO_INFORMATIVO' and row['sentimiento'] is not None) or (row['informatividad']=='INFORMATIVO' and row['sentimiento'] not in ('POSITIVO','NEGATIVO','NEUTRAL')):
            raise ValueError('Etiqueta de resultado inconsistente.')
    return by_id

def comment_summary(rows):
    sentiments={k:sum(r['sentimiento']==k for r in rows) for k in ('POSITIVO','NEGATIVO','NEUTRAL')}
    info=sum(sentiments.values())
    return {'comentarios':len(rows),'informativos':info,'sin_sentimiento':len(rows)-info,'sentimientos':sentiments}

def build():
    if (BASE/'informe.json').exists():raise ValueError('Informe existente: no sobrescribir.')
    expected=inputs(); export_manifest=read(BASE/'manifest_sql.json')
    if export_manifest.get('estado')!='VINCULOS_SQL_VERIFICADOS' or export_manifest.get('sql_solo_lectura') is not True:
        raise ValueError('Vínculos SQL no verificados.')
    if sha(BASE/'plan.json')!=export_manifest['plan_sha256'] or read(BASE/'plan.json')['registros']!=list(expected.values()):
        raise ValueError('El plan no corresponde a la selección autorizada.')
    mapping=checked(BASE,'mapa_comentarios.json',export_manifest)
    teachers=checked(BASE,'cuantitativo_docentes.json',export_manifest)
    if set(mapping)!=set(expected):raise ValueError('Faltan vínculos.')
    original=results(ORIGINAL,'resultados.jsonl',expected)
    revised=results(REVISED,'resultados_revisados.jsonl',expected)
    current=load_current(); codes={r['codigo'] for r in teachers}
    if len(codes)!=len(teachers):raise ValueError('Códigos duplicados.')
    buckets={code:{source:[] for source in current['fuentes']} for code in codes}
    for ident,link in mapping.items():
        if link['codigo'] not in codes or link['periodo']!='2026-II' or link['fuente']!=expected[ident]['fuente']:
            raise ValueError('Relación ambigua o fuera de periodo/fuente.')
        buckets[link['codigo']][link['fuente']].append(ident)
    output=[]
    for teacher in sorted(teachers,key=lambda r:r['codigo']):
        validate_current({**current,'total':teacher['total'],'fuentes':teacher['fuentes'],
                          'cerradas_snapshot':teacher['total']['respuestas'],'cerradas_fuera_agregado':0})
        sources={}
        for source,numeric in teacher['fuentes'].items():
            ids=buckets[teacher['codigo']][source]
            sources[source]={'cuantitativo':numeric,'comentarios':{'original':comment_summary([original[i] for i in ids]),'revisado':comment_summary([revised[i] for i in ids])}}
        output.append({'codigo':teacher['codigo'],'periodo':'2026-II','cuantitativo_total':teacher['total'],'fuentes':sources})
    if sum(r['cuantitativo_total']['respuestas'] for r in output)!=current['total']['respuestas']:
        raise ValueError('Cobertura cuantitativa incompleta.')
    for source,total in current['fuentes'].items():
        if sum(r['fuentes'][source]['cuantitativo']['respuestas'] for r in output)!=total['respuestas'] or sum(r['fuentes'][source]['cuantitativo']['suma_raw'] for r in output)!=total['suma_raw']:
            raise ValueError('Fuente cuantitativa incompleta.')
    report={'estado':'VINCULACION_VERIFICADA','periodo':'2026-II','fecha_snapshot':current['fecha_utc'],
            'docentes':output,'comentarios_vinculados':len(expected),'respuestas_cerradas':current['total']['respuestas'],
            'docentes_con_comentarios':sum(any(s['comentarios']['revisado']['comentarios'] for s in r['fuentes'].values()) for r in output),
            'alcance':'Códigos seudónimos locales, no anonimización garantizada. Unión por respuesta original, docente, fuente y periodo, con hashes de pregunta y comentario. Sólo muestra autorizada train/validation. Sin comentarios en muestra no significa ausencia de comentarios institucionales. Promedios sin ponderar; sentimientos propuestos por BETO. No es correlación ML, ranking ni calificación institucional.',
            'versiones_modelos':read(ORIGINAL/'manifest.json')['versiones'],'test_utilizado':False,'produccion_activada':False}
    dump(BASE/'informe.json',report)
    manifest={'estado':'VINCULACION_VERIFICADA','periodo':'2026-II','sql_solo_lectura':True,'test_utilizado':False,
              'sha256_archivos':{'informe.json':sha(BASE/'informe.json')},'sha256_manifest_sql':sha(BASE/'manifest_sql.json'),
              'comentarios':len(expected),'respuestas':current['total']['respuestas']}
    dump(BASE/'manifest.json',manifest)
    print(json.dumps({'estado':manifest['estado'],'docentes':len(output),'docentes_con_comentarios':report['docentes_con_comentarios'],'comentarios':len(expected),'respuestas':current['total']['respuestas']}))

def load_links():
    manifest=read(BASE/'manifest.json')
    if manifest.get('estado')!='VINCULACION_VERIFICADA' or manifest.get('test_utilizado') is not False or manifest.get('sql_solo_lectura') is not True:
        raise ValueError('Informe no verificado.')
    report=checked(BASE,'informe.json',manifest)
    if report.get('periodo')!='2026-II' or report.get('estado')!='VINCULACION_VERIFICADA':raise ValueError('Periodo incorrecto.')
    if sha(BASE/'manifest_sql.json')!=manifest['sha256_manifest_sql']:
        raise ValueError('La evidencia SQL cambió.')
    sql_manifest=read(BASE/'manifest_sql.json')
    if sha(ROOT/'data/ia/demo_local/cuantitativo_20261116_v1/resumen.json')!=sql_manifest['snapshot_cuantitativo_sha256']:
        raise ValueError('El snapshot cuantitativo ya no corresponde al informe.')
    codes=[r['codigo'] for r in report['docentes']]
    if len(set(codes))!=len(codes) or any(not re.fullmatch(r'DOC-[A-F0-9]{12}',c) for c in codes):
        raise ValueError('Códigos locales inválidos.')
    if sum(r['cuantitativo_total']['respuestas'] for r in report['docentes'])!=manifest['respuestas']:
        raise ValueError('Cobertura numérica incompleta.')
    for version in ('original','revisado'):
        if sum(s['comentarios'][version]['comentarios'] for t in report['docentes'] for s in t['fuentes'].values())!=manifest['comentarios']:
            raise ValueError('Cobertura de comentarios incompleta.')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('accion',choices=['preparar','construir']);args=parser.parse_args()
    (prepare if args.accion=='preparar' else build)()
