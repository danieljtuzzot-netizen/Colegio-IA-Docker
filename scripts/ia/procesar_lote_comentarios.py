"""Procesa muestra revisada train/validation; test nunca es entrada de este comando."""
import argparse
import collections
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import time
from clasificar_comentario import ClasificadorComentarios
from informatividad_comun import ROOT,sha,dump,percent,leer_particiones
from piloto_beto import protect
from validar_excel_revisores import read_book,SHEETS

BASE=ROOT/'data/ia/lotes'
SOURCES={'ESTUDIANTES':'Estudiantes','JEFE':'Jefe inmediato','LENGUAS':'Bilingüismo','CAPELLANIA':'Capellanía'}

def load_inputs(config,parts):
    splits,manifest=leer_particiones(config)
    base=ROOT/'data/ia/versiones'/config['dataset_version']
    workbook=base/'entrada_revisada.xlsx'
    assert sha(workbook)==manifest['entrada_sha256'],'La copia de aprobación cambió'
    book=read_book(workbook)
    privacy={cells['A']:cells.get('H','') for name in SHEETS for n,(cells,formulas) in book[name][0].items() if n>=7 and cells.get('A')}
    excluded={r['id_origen'] for r in json.loads((base/'retenidos_privacidad.json').read_text(encoding='utf-8'))}
    assignment={r['id_origen']:r['split'] for r in json.loads((base/'asignacion_splits.json').read_text(encoding='utf-8'))}
    result=[]
    for split in parts:
        for row in splits[split]:
            ident=row['id_origen']
            assert assignment[ident]==split and split!='test'
            assert privacy[ident]=='SI' and ident not in excluded,'Registro retenido o privacidad pendiente'
            result.append({**row,'particion':split})
    assert len({r['id_origen'] for r in result})==len(result)
    return result,manifest

def summarize(decisions):
    def aggregate(rows):
        total=len(rows);info=sum(r['informatividad']=='INFORMATIVO' for r in rows)
        sentiments=collections.Counter(r['sentimiento'] for r in rows if r['sentimiento'] is not None)
        review=sum(r['requiere_revision_humana'] for r in rows)
        no_info=sum(r['informatividad']=='NO_INFORMATIVO' for r in rows)
        assert total==info+no_info and info==sum(sentiments.values()) and review<=no_info
        return {'procesados':total,'informativos_propuestos':info,'no_informativos_propuestos':no_info,'pendientes_revision':review,'sentimientos':{k:sentiments[k] for k in ('POSITIVO','NEUTRAL','NEGATIVO')},'porcentaje_sobre_informativos_raw':{k:100*sentiments[k]/info if info else None for k in ('POSITIVO','NEUTRAL','NEGATIVO')},'truncados_para_modelo':sum(bool(r['sentimiento_detalle'] and r['sentimiento_detalle']['comentario_truncado_para_modelo']) for r in rows)}
    return {'total':aggregate(decisions),'fuentes':{code:aggregate([r for r in decisions if r['fuente']==code]) for code in SOURCES},'particiones':{part:aggregate([r for r in decisions if r['particion']==part]) for part in sorted({r['particion'] for r in decisions})}}

def report(folder,summary,metadata):
    total=summary['total']
    lines=['# Resumen local de comentarios procesados','',
           'Periodo 2026-II. Resultado experimental de una muestra ya utilizada en desarrollo. No es una evaluación de calidad ni representa a toda la institución.','',
           'Particiones: '+', '.join(metadata['particiones'])+'. Test permanece reservado. Sólo se incluyeron registros con privacidad SI; los 14 NO permanecen fuera.','',
           '| Fuente | Procesados | Positivo | Neutral | Negativo | Pendientes de revisión |',
           '| --- | ---: | ---: | ---: | ---: | ---: |']
    for code,title in SOURCES.items():
        r=summary['fuentes'][code];s=r['sentimientos']
        lines.append('| '+title+' | '+' | '.join(str(v) for v in [r['procesados'],s['POSITIVO'],s['NEUTRAL'],s['NEGATIVO'],r['pendientes_revision']])+' |')
    s=total['sentimientos']
    lines.append('| **Total** | '+' | '.join(str(v) for v in [total['procesados'],s['POSITIVO'],s['NEUTRAL'],s['NEGATIVO'],total['pendientes_revision']])+' |')
    lines.extend(['','## Distribución entre informativos propuestos','',
                  'Base: '+str(total['informativos_propuestos'])+' comentarios que el filtro permitió pasar a BETO. No incluye los pendientes de informatividad.',''])
    for label in ('POSITIVO','NEUTRAL','NEGATIVO'):
        visible=percent(total['sentimientos'][label]/total['informativos_propuestos']) if total['informativos_propuestos'] else 'No aplica'
        lines.append('- '+label+': '+str(total['sentimientos'][label])+' ('+visible+').')
    lines.extend(['','## Revisión pendiente','',
                  str(total['pendientes_revision'])+' propuestas NO_INFORMATIVO quedan sin sentimiento y pendientes de revisión. No se borró ningún registro.',
                  'La cola privada incluye ID, pregunta, comentario y propuesta. Una propuesta del filtro no confirma la informatividad ni debe cambiar la etiqueta histórica automáticamente.',
                  'Esta cola revisa propuestas del modelo; no reabre ni invalida las etiquetas ya aprobadas. Contrastar con las referencias existentes, sin volver a etiquetar sólo por discrepancia.',
                  'El filtro retuvo 15 informativos por error en la validación anterior; por eso no está aprobado para descarte automático.',
                  'Los porcentajes visibles se redondean a enteros y pueden no sumar exactamente 100 %. Los valores raw permanecen en resumen.json.',
                  '', '## Interpretación','',
                  'Estos conteos describen predicciones automáticas sobre train/validation. No son porcentajes de desempeño docente ni nuevas calificaciones institucionales.',
                  'Las fuentes están representadas según la muestra seleccionada, con sobrerrepresentación de fuentes minoritarias. No extrapolar a todo el corpus.',
                  'No se generaron resúmenes LLM, recomendaciones personales, ranking de docentes ni resultados publicados en el portal.',
                  '', '## Archivos','',
                  '- resultados.jsonl: decisiones por ID, sin reproducir textos en el archivo técnico.',
                  '- cola_revision_privada.jsonl: textos originales sólo de casos retenidos para revisar localmente.',
                  '- resumen.json: conteos y porcentajes raw por fuente y partición.',
                  '- manifest.json: alcance, versiones y hashes.'])
    (folder/'RESUMEN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def run(run_id,parts):
    assert parts and len(set(parts))==len(parts) and set(parts)<={'train','validation'}
    pipeline=ClasificadorComentarios()
    rows,source_manifest=load_inputs(pipeline.config,parts)
    output=BASE/run_id
    assert not output.exists(),'Lote existente; usar otro identificador'
    protect(output)
    started=time.perf_counter()
    state={'estado':'EN_CURSO','procesados':0,'total':len(rows),'inicio_utc':datetime.now(timezone.utc).isoformat(),'particiones':parts,'test_utilizado':False,'produccion_activada':False}
    dump(output/'estado.json',state)
    metadata={'dataset':pipeline.config['dataset_version'],'periodo':'2026-II','particiones':parts,'fuentes':list(SOURCES),'versiones':{'pipeline':'comentarios_v1','filtro':pipeline.filtro_id,'beto':pipeline.beto_id,'reglas':pipeline.config['reglas_version']},'sha256_entradas':{part:source_manifest['archivos'][f'informatividad_{part}.jsonl']['sha256'] for part in parts},'sha256_aprobacion_privacidad':source_manifest['entrada_sha256'],'test_utilizado':False,'retenidos_privacidad_excluidos':source_manifest['retenidos_privacidad'],'evaluacion_desempeno':False,'representa_toda_institucion':False,'produccion_activada':False}
    dump(output/'alcance.json',metadata)
    decisions=[];queue_count=0
    with (output/'resultados.jsonl').open('w',encoding='utf-8',newline='\n') as results, (output/'cola_revision_privada.jsonl').open('w',encoding='utf-8',newline='\n') as queue:
        for start in range(0,len(rows),64):
            chunk=rows[start:start+64]
            predictions=pipeline.clasificar_lote([r['pregunta'] for r in chunk],[r['comentario'] for r in chunk])
            for row,pred in zip(chunk,predictions):
                record={'id_origen':row['id_origen'],'fuente':row['fuente'],'particion':row['particion'],**pred}
                assert record['informatividad']=='INFORMATIVO' or (record['sentimiento'] is None and not record['beto_ejecutado'])
                decisions.append(record);results.write(json.dumps(record,ensure_ascii=False)+'\n')
                if pred['requiere_revision_humana']:
                    queue_count+=1
                    queue.write(json.dumps({'id_origen':row['id_origen'],'fuente':row['fuente'],'particion':row['particion'],'pregunta':row['pregunta'],'comentario':row['comentario'],'informatividad_propuesta':pred['informatividad'],'revision_estado':'PENDIENTE','motivo':'PROPUESTA_NO_INFORMATIVO_SIN_BORRAR'},ensure_ascii=False)+'\n')
            results.flush();queue.flush();os.fsync(results.fileno());os.fsync(queue.fileno())
            state.update({'procesados':len(decisions),'pendientes_revision':queue_count,'segundos_raw':time.perf_counter()-started})
            dump(output/'estado.json',state)
            print(f'Procesados {len(decisions)}/{len(rows)}; pendientes de revisión: {queue_count}',flush=True)
    summary=summarize(decisions)
    assert summary['total']['procesados']==len(rows) and summary['total']['pendientes_revision']==queue_count
    dump(output/'resumen.json',summary);report(output,summary,metadata)
    state.update({'estado':'COMPLETADO','final_utc':datetime.now(timezone.utc).isoformat()});dump(output/'estado.json',state)
    dump(output/'manifest.json',{**metadata,'estado':'COMPLETADO','total':len(rows),'pendientes_revision':queue_count,'sha256_archivos':{name:sha(output/name) for name in ['resultados.jsonl','cola_revision_privada.jsonl','resumen.json','RESUMEN.md','alcance.json','estado.json']}})
    print(json.dumps({'estado':'COMPLETADO','procesados':len(rows),'pendientes_revision':queue_count,'test_utilizado':False},ensure_ascii=True))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ejecucion',required=True)
    parser.add_argument('--particiones',nargs='+',choices=['train','validation'],default=['train','validation'])
    args=parser.parse_args()
    assert re.fullmatch(r'[A-Za-z0-9_-]{1,64}',args.ejecucion)
    existed=(BASE/args.ejecucion).exists()
    try:run(args.ejecucion,args.particiones)
    except (Exception,KeyboardInterrupt) as error:
        # Los resultados parciales no reciben manifest COMPLETADO. Nunca reutilizarlos como lote final.
        state_path=BASE/args.ejecucion/'estado.json'
        if not existed and state_path.exists():
            state=json.loads(state_path.read_text(encoding='utf-8'))
            state.update({'estado':'INTERRUMPIDO' if isinstance(error,KeyboardInterrupt) else 'FALLIDO','tipo_error':type(error).__name__})
            dump(state_path,state)
        raise
