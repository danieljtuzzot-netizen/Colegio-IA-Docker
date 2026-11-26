"""Congela una muestra nueva para el piloto; sólo train/validation con privacidad SI."""
import argparse
import collections
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from piloto_beto import ROOT,protect,sha,dump
from procesar_lote_comentarios import load_inputs,SOURCES
from piloto_sintesis_comentarios import eligible

PREVIOUS=ROOT/'data/ia/llm/sintesis_comentarios_20261112_v1'
SOURCE=ROOT/'data/ia/lotes/revision_cuatro_fuentes_20261112_v2'
PERSONAL=re.compile(r'\b(?:salud|pensional\w*|pensi[oó]n\w*|enfermedad\w*|diagn[oó]stico\w*)\b',re.I)

def normalized(text):
    return ' '.join(re.sub(r'\W+',' ',unicodedata.normalize('NFKC',text).casefold()).split())

def context():
    config=json.loads((ROOT/'scripts/ia/informatividad_config_v1.json').read_text(encoding='utf-8'))
    inputs,ds=load_inputs(config,['train','validation'])
    prior=json.loads((PREVIOUS/'manifest.json').read_text(encoding='utf-8'))
    for name,key in [('entrada_local.json','sha256_entrada'),('trazabilidad_privada.json','sha256_trazabilidad')]:
        assert sha(PREVIOUS/name)==prior[key]
    old=json.loads((PREVIOUS/'entrada_local.json').read_text(encoding='utf-8'))
    mapping=json.loads((PREVIOUS/'trazabilidad_privada.json').read_text(encoding='utf-8'))
    byid={r['id_origen']:r for r in inputs}
    excluded_ids={r['id_origen'] for r in mapping}
    assert len(excluded_ids)==len(old)==12
    for r,m in zip(old,mapping):
        assert r['id']==m['id'] and byid[m['id_origen']]['comentario']==r['texto']
    groups={byid[i]['grupo_split'] for i in excluded_ids}
    texts={normalized(r['texto']) for r in old}
    manifest=json.loads((SOURCE/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['estado']=='COMPLETADO' and not manifest['test_utilizado']
    assert ds['entrada_sha256']==manifest['sha256_copia_revisada']
    path=SOURCE/'resultados_revisados.jsonl'
    assert sha(path)==manifest['sha256_archivos'][path.name]
    decisions={r['id_origen']:r for r in map(json.loads,path.read_text(encoding='utf-8').splitlines())}
    assert set(decisions)==set(byid)
    return inputs,ds,decisions,excluded_ids,groups,texts

def permitted(row,decisions,ids,groups,texts):
    return (row['id_origen'] not in ids and row['grupo_split'] not in groups and normalized(row['comentario']) not in texts
        and decisions[row['id_origen']]['informatividad']=='INFORMATIVO' and eligible(row['comentario'])
        and not PERSONAL.search(row['comentario']))

def prepare(sample_id):
    folder=ROOT/'data/ia/llm'/sample_id
    assert not folder.exists(),'No sobrescribir muestras'
    inputs,ds,decisions,ids,groups,texts=context()
    selected=[];mapping=[];used_groups=set();used_texts=set();available={}
    for source in SOURCES:
        candidates=[r for r in inputs if r['fuente']==source and permitted(r,decisions,ids,groups,texts)]
        candidates.sort(key=lambda r:hashlib.sha256(('muestra_nueva_20261113:'+r['id_origen']).encode()).hexdigest())
        available[source]=len(candidates);chosen=[]
        def add(row):
            chosen.append(row);used_groups.add(row['grupo_split']);used_texts.add(normalized(row['comentario']))
        def fresh(row):return row['grupo_split'] not in used_groups and normalized(row['comentario']) not in used_texts
        for label in ('NEGATIVO','NEUTRAL','POSITIVO'):
            match=next((r for r in candidates if decisions[r['id_origen']]['sentimiento']==label and fresh(r)),None)
            if match:add(match)
        for row in candidates:
            if len(chosen)>=3:break
            if fresh(row):add(row)
        assert len(chosen)==3,'Cobertura insuficiente; no recurrir a test'
        for row in chosen:
            ident=f'N{len(selected)+1:03d}'
            selected.append({'id':ident,'fuente':source,'texto':row['comentario']})
            mapping.append({'id':ident,'id_origen':row['id_origen'],'grupo_split':row['grupo_split'],'particion':row['particion']})
    protect(folder)
    dump(folder/'entrada_local.json',selected);dump(folder/'trazabilidad_privada.json',mapping)
    manifest={'estado':'MUESTRA_CONGELADA','dataset':'20261112_DATASET_BETO_V2','registros':len(selected),
        'por_fuente':dict(collections.Counter(r['fuente'] for r in selected)),'candidatos_elegibles_por_fuente':available,
        'seleccion':'DETERMINISTA_COBERTURA_SENTIMIENTOS_BETO_NO_REPRESENTATIVA','privacidad_si_revalidada':True,
        'anonimato_completo_certificado':False,'test_utilizado':False,'produccion_activada':False,
        'sha256_aprobacion_privacidad':ds['entrada_sha256'],'sha256_resultados_fuente':sha(SOURCE/'resultados_revisados.jsonl'),
        'sha256_muestra_previa':sha(PREVIOUS/'entrada_local.json'),'sha256_script_seleccion':sha(Path(__file__)),
        'comentarios_ya_usados_en_beto':True,'parafrasis_no_detectadas_posibles':True,
        'sha256_archivos':{n:sha(folder/n) for n in ['entrada_local.json','trazabilidad_privada.json']}}
    dump(folder/'manifest.json',manifest)
    load(sample_id)
    print(json.dumps({'estado':manifest['estado'],'registros':len(selected),'por_fuente':manifest['por_fuente'],'test_utilizado':False}))

def load(sample_id):
    assert re.fullmatch(r'[A-Za-z0-9_-]{1,64}',sample_id)
    folder=ROOT/'data/ia/llm'/sample_id
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['estado']=='MUESTRA_CONGELADA' and not manifest['test_utilizado']
    for name,expected in manifest['sha256_archivos'].items():
        assert '/' not in name and '\\' not in name and sha(folder/name)==expected
    inputs,ds,decisions,ids,groups,texts=context();byid={r['id_origen']:r for r in inputs}
    assert ds['entrada_sha256']==manifest['sha256_aprobacion_privacidad']
    assert sha(SOURCE/'resultados_revisados.jsonl')==manifest['sha256_resultados_fuente']
    assert sha(PREVIOUS/'entrada_local.json')==manifest['sha256_muestra_previa']
    rows=json.loads((folder/'entrada_local.json').read_text(encoding='utf-8'))
    mapping=json.loads((folder/'trazabilidad_privada.json').read_text(encoding='utf-8'))
    assert len(rows)==len(mapping)==manifest['registros']==12
    assert len({r['id'] for r in rows})==len({r['id_origen'] for r in mapping})==len({r['grupo_split'] for r in mapping})==12
    assert len({normalized(r['texto']) for r in rows})==12
    for r,m in zip(rows,mapping):
        original=byid[m['id_origen']]
        assert r['id']==m['id'] and r['texto']==original['comentario'] and r['fuente']==original['fuente']
        assert m['grupo_split']==original['grupo_split'] and m['particion']==original['particion'] and m['particion']!='test'
        assert permitted(original,decisions,ids,groups,texts)
    assert dict(collections.Counter(r['fuente'] for r in rows))==manifest['por_fuente']=={s:3 for s in SOURCES}
    return rows,ds

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--muestra',required=True);args=parser.parse_args()
    assert re.fullmatch(r'[A-Za-z0-9_-]{1,64}',args.muestra)
    prepare(args.muestra)
