"""Derivados agregados de predicciones OOF congeladas; no entrena ni publica filas."""
import collections
import hashlib
import json
import math
from demo_dashboard import ROOT, checked
from piloto_beto import protect

SOURCE=ROOT/'data/ia/ml/exploracion_20261116_v1'
OUTPUT=ROOT/'data/ia/ml/visualizacion_20261117_v1'
MODELS=('referencia_fuente','control_cobertura','modelo_sentimiento')
SOURCES={'ESTUDIANTES','LENGUAS','JEFE','CAPELLANIA','AUTOEVALUACION'}
ERROR_LIMITS=(2,5,10,20)
MIN_CELL=3


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate(rows,model):
    histogram=[0]*5;cells=collections.Counter();outside=0;within=0
    for row in rows:
        actual=row['objetivo_raw'];pred=row[model+'_raw']
        if type(actual) not in (int,float) or type(pred) not in (int,float) or not math.isfinite(actual) or not math.isfinite(pred) or not 20<=actual<=100:
            raise ValueError('Predicción congelada inválida.')
        error=abs(pred-actual)
        histogram[next((i for i,limit in enumerate(ERROR_LIMITS) if error<limit),4)]+=1
        within+=error<=5
        if not 20<=pred<=100:
            outside+=1;continue
        cells[(min(7,int((actual-20)//10)),min(7,int((pred-20)//10)))]+=1
    visible=[{'real_desde':20+x*10,'estimado_desde':20+y*10,'casos':n} for (x,y),n in sorted(cells.items()) if n>=MIN_CELL]
    withheld=sum(n for n in cells.values() if n<MIN_CELL)
    return {'casos':len(rows),'histograma_error_absoluto':histogram,'casos_error_hasta_5_pp':within,
            'celdas':visible,'casos_celdas_no_publicadas':withheld,'predicciones_fuera_escala':outside}


def coverage(report,protocol,summary):
    counts={source:{'revisados':0,'pocas_respuestas':0,'pocos_comentarios':0,'pocos_docentes_fuente':0,'incluidos':0} for source in SOURCES}
    eligible=collections.Counter()
    for teacher in report['docentes']:
        for source in SOURCES:
            row=teacher['fuentes'][source];out=counts[source];out['revisados']+=1
            if row['cuantitativo']['respuestas']<protocol['min_respuestas_cerradas']:out['pocas_respuestas']+=1
            elif row['comentarios']['revisado']['informativos']<protocol['min_comentarios_informativos']:out['pocos_comentarios']+=1
            else:eligible[source]+=1
    for source,n in eligible.items():
        key='incluidos' if n>=protocol['min_docentes_por_fuente'] else 'pocos_docentes_fuente'
        counts[source][key]=n
    total={key:sum(row[key] for row in counts.values()) for key in next(iter(counts.values()))}
    if total['incluidos']!=summary['filas']:raise ValueError('Cobertura ajena al experimento.')
    expected={'pocas_respuestas':'POCAS_RESPUESTAS_CERRADAS','pocos_comentarios':'POCOS_COMENTARIOS_INFORMATIVOS','pocos_docentes_fuente':'POCOS_DOCENTES_POR_FUENTE'}
    if any(total[key]!=summary['exclusiones_secuenciales'].get(reason,0) for key,reason in expected.items()):raise ValueError('Exclusiones distintas de las congeladas.')
    for source,row in counts.items():
        if row['incluidos']!=summary['fuentes'].get(source,{}).get('filas',0):raise ValueError('Fuente inconsistente.')
    return {'total':total,'fuentes':counts}


def derive(rows,report,protocol,summary):
    if len(rows)!=summary['filas'] or len({r['codigo'] for r in rows})!=summary['docentes'] or len({(r['codigo'],r['fuente']) for r in rows})!=len(rows):
        raise ValueError('Filas congeladas inconsistentes.')
    if {r['fuente'] for r in rows}!=set(summary['fuentes']):raise ValueError('Fuentes distintas.')
    groups={}
    for key,items in [('TOTAL',rows),*[(source,[r for r in rows if r['fuente']==source]) for source in sorted(summary['fuentes'])]]:
        expected=summary if key=='TOTAL' else summary['fuentes'][key]
        if len(items)!=expected['filas']:raise ValueError('Cantidad por fuente inválida.')
        groups[key]={'modelos':{model:aggregate(items,model) for model in MODELS}}
        for model in MODELS:
            errors=[r[model+'_raw']-r['objetivo_raw'] for r in items]
            measured={'mae_pp_raw':sum(abs(e) for e in errors)/len(errors),'rmse_pp_raw':math.sqrt(sum(e*e for e in errors)/len(errors))}
            if any(not math.isclose(value,expected['metricas'][model][name],abs_tol=1e-8) for name,value in measured.items()):raise ValueError('Errores distintos de las métricas congeladas.')
    return {'version':'ml_visualizacion_20261117_v1','periodo':summary['periodo'],'origen':'PREDICCIONES_OOF_CONGELADAS',
            'ancho_celda_pp':10,'minimo_casos_celda':MIN_CELL,'grupos':groups,'cobertura':coverage(report,protocol,summary),
            'entrenamiento_ejecutado':False,'prediccion_temporal':False,'produccion_activada':False,
            'alcance':'Celdas agregadas de al menos tres casos, sin códigos ni predicciones individuales. El histograma incluye todos los casos. No garantiza anonimato ni evaluación independiente.'}


def validate(data,summary):
    if (data.get('periodo')!=summary['periodo'] or data.get('entrenamiento_ejecutado') is not False
        or data.get('produccion_activada') is not False or data.get('prediccion_temporal') is not False
        or data.get('ancho_celda_pp')!=10 or data.get('minimo_casos_celda')!=MIN_CELL
        or set(data.get('grupos',{}))!={'TOTAL',*summary['fuentes']}):raise ValueError('Derivado fuera de alcance.')
    for key,group in data['grupos'].items():
        expected=summary if key=='TOTAL' else summary['fuentes'][key]
        if set(group['modelos'])!=set(MODELS):raise ValueError('Modelo ausente.')
        for values in group['modelos'].values():
            n=values['casos'];hist=values['histograma_error_absoluto']
            if n!=expected['filas'] or len(hist)!=5 or any(type(v) is not int or v<0 for v in hist) or sum(hist)!=n:raise ValueError('Histograma inconsistente.')
            for field in ['casos_error_hasta_5_pp','casos_celdas_no_publicadas','predicciones_fuera_escala']:
                if type(values[field]) is not int or not 0<=values[field]<=n:raise ValueError('Conteo inválido.')
            cells=values['celdas']
            if len({(c['real_desde'],c['estimado_desde']) for c in cells})!=len(cells):raise ValueError('Celda duplicada.')
            if any(set(c)!={'real_desde','estimado_desde','casos'} or type(c['casos']) is not int or c['casos']<MIN_CELL or any(c[f] not in range(20,100,10) for f in ['real_desde','estimado_desde']) for c in cells):raise ValueError('Celda no publicable.')
            if sum(c['casos'] for c in cells)+values['casos_celdas_no_publicadas']+values['predicciones_fuera_escala']!=n:raise ValueError('Cobertura del gráfico inconsistente.')
    cov=data['cobertura'];keys={'revisados','pocas_respuestas','pocos_comentarios','pocos_docentes_fuente','incluidos'}
    if set(cov['fuentes'])!=SOURCES:raise ValueError('Cobertura incompleta.')
    for row in [cov['total'],*cov['fuentes'].values()]:
        if set(row)!=keys or any(type(v) is not int or v<0 for v in row.values()) or row['revisados']!=sum(v for k,v in row.items() if k!='revisados'):raise ValueError('Flujo de cobertura inválido.')
    if cov['total']['incluidos']!=summary['filas'] or any(cov['total'][k]!=sum(r[k] for r in cov['fuentes'].values()) for k in keys):raise ValueError('Total de cobertura inconsistente.')
    for source,row in cov['fuentes'].items():
        if row['incluidos']!=summary['fuentes'].get(source,{}).get('filas',0):raise ValueError('Cobertura por fuente distinta.')
    return data


def load(summary):
    manifest=json.loads((OUTPUT/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('estado')!='DERIVADO_AGREGADO_VERIFICADO' or manifest.get('sha256_resumen_origen')!=sha(SOURCE/'resumen.json'):
        raise ValueError('Gráficos desactualizados respecto al experimento.')
    return validate(checked(OUTPUT,'graficas.json',manifest),summary)


def build():
    if OUTPUT.exists():raise ValueError('La versión existe; no sobrescribir.')
    manifest=json.loads((SOURCE/'manifest.json').read_text(encoding='utf-8'))
    from demo_ml import load_summary
    from demo_vinculos import load_links
    summary=load_summary();protocol=checked(SOURCE,'protocolo_previo.json',manifest)
    rows=checked(SOURCE,'predicciones_oof_privadas.json',manifest)
    data=validate(derive(rows,load_links(),protocol,summary),summary)
    protect(OUTPUT)
    (OUTPUT/'graficas.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    proof={'estado':'DERIVADO_AGREGADO_VERIFICADO','sha256_resumen_origen':sha(SOURCE/'resumen.json'),
           'sha256_predicciones_origen':sha(SOURCE/'predicciones_oof_privadas.json'),
           'sha256_archivos':{'graficas.json':sha(OUTPUT/'graficas.json')},'entrenamiento_ejecutado':False,'test_nlp_utilizado':False}
    (OUTPUT/'manifest.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps({'estado':proof['estado'],'casos':summary['filas'],'codigos_publicados':False,'entrenamiento_ejecutado':False}))


if __name__=='__main__':build()
