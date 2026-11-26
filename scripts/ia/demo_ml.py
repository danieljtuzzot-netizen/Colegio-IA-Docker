"""Entrega métricas congeladas; no carga modelos ni calcula predicciones individuales."""
import hashlib
import json
import math
from demo_dashboard import ROOT, checked

FOLDER=ROOT/'data/ia/ml/exploracion_20261116_v1'

def load_summary():
    manifest=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('estado')!='EXPLORACION_COMPLETADA' or manifest.get('produccion_activada') is not False:
        raise ValueError('Exploración fuera de alcance.')
    if hashlib.sha256((ROOT/'data/ia/demo_local/vinculos_20261116_v1/informe.json').read_bytes()).hexdigest()!=manifest['sha256_informe_vinculado']:
        raise ValueError('Los datos vinculados cambiaron.')
    data=checked(FOLDER,'resumen.json',manifest)
    protocol=checked(FOLDER,'protocolo_previo.json',manifest)
    if (data.get('periodo')!='2026-II' or data.get('test_nlp_utilizado') is not False
        or data.get('prediccion_temporal') is not False or data.get('produccion_activada') is not False
        or protocol.get('ajuste_hiperparametros') is not False):
        raise ValueError('Contrato de evaluación inválido.')
    if any(fold['cruces_docentes']!=0 for fold in data['folds']) or sum(f['filas_validacion'] for f in data['folds'])!=data['filas']:
        raise ValueError('Validación agrupada inconsistente.')
    for metrics in [data['metricas'],*[row['metricas'] for row in data['fuentes'].values()]]:
        if set(metrics)!={'referencia_fuente','control_cobertura','modelo_sentimiento'}:
            raise ValueError('Falta una referencia de comparación.')
        if any(not math.isfinite(v) for row in metrics.values() for v in row.values()):
            raise ValueError('Métrica no finita.')
    from ml_visualizacion import OUTPUT,load
    if OUTPUT.exists():
        return {**data,'visualizacion':load(data)}
    return {**data,'visualizacion':None}
