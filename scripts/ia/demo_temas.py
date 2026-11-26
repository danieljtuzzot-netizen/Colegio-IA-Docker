"""Expone únicamente citas de la síntesis autorizada, sin consultar corpus ni test."""
import json
from demo_dashboard import ROOT, checked

FOLDER = ROOT / 'data/ia/llm/sintesis_fuentes_revisada_20261113_v1'
SOURCES = {'ESTUDIANTES', 'JEFE', 'LENGUAS', 'CAPELLANIA'}

def load_themes():
    manifest = json.loads((FOLDER / 'manifest.json').read_text(encoding='utf-8'))
    if (manifest.get('estado') != 'SINTESIS_REVISADA_POR_AUTORIZACION_USUARIO'
            or manifest.get('referencia_autorizacion') != 'AUTORIZACION_CHAT_TEMAS_20261113'
            or manifest.get('test_utilizado') is not False
            or manifest.get('retenidos_liberados') is not False):
        raise ValueError('La síntesis no corresponde al alcance autorizado.')
    proof = checked(FOLDER, 'validacion_cierre.json', manifest)
    if proof.get('estado') != 'APROBADO_APLICACION_AUTORIZADA' or proof.get('asignaciones_pendientes') != 0:
        raise ValueError('Síntesis pendiente de validación.')
    evidence = checked(FOLDER, 'evidencia_aprobada.json', manifest)
    themes = checked(FOLDER, 'temas_revisados.json', manifest)
    by_id = {row['id']: row for row in evidence}
    theme_map = {row['id']: row['tema'] for row in themes}
    if len(by_id) != len(evidence) or len(theme_map) != len(themes):
        raise ValueError('Referencias duplicadas.')
    thematic = {row['id'] for row in evidence if row['categoria'] in ('FORTALEZA', 'OPORTUNIDAD')}
    if set(theme_map) != thematic:
        raise ValueError('Cobertura temática inconsistente.')
    if (len(evidence) != manifest['segmentos_aprobados'] or len(themes) != manifest['asignaciones_tematicas']
            or len({row['comentario'] for row in evidence}) != manifest['comentarios']):
        raise ValueError('Cobertura del piloto inconsistente.')
    rows = []
    for row in evidence:
        if row['fuente'] not in SOURCES or row['categoria'] not in ('FORTALEZA','OPORTUNIDAD','CONTEXTO','ABSTENCION'):
            raise ValueError('Categoría o fuente ajena al piloto.')
        rows.append({'segmento_id': row['id'], 'comentario_id': row['comentario'], 'fuente': row['fuente'],
                     'categoria': row['categoria'], 'tema': theme_map.get(row['id']), 'cita': row['texto']})
    return {'periodo': '2026-II', 'lote': FOLDER.name, 'comentarios': manifest['comentarios'],
            'segmentos': len(rows), 'asignaciones_tematicas': len(themes), 'evidencias': rows,
            'revision_independiente_certificada': False, 'produccion_activada': False,
            'alcance': 'Piloto autorizado de 22 comentarios y 41 segmentos; 37 asignaciones temáticas. No equivale al lote de 2.695 comentarios ni representa prevalencia institucional. Un comentario puede aportar a varios temas. No es una evaluación independiente.'}
