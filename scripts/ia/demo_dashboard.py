"""Lectura de agregados verificados; no accede a textos ni al conjunto test."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'data/ia/lotes'
LOTS = {
    'revisado': ('revision_cuatro_fuentes_20261112_v2', 'resumen_revisado.json', 'validacion_revision.json'),
    'original': ('cuatro_fuentes_20261112_v1', 'resumen.json', 'validacion_lote.json'),
}

def checked(folder, name, manifest):
    content = (folder / name).read_bytes()
    if hashlib.sha256(content).hexdigest() != manifest['sha256_archivos'][name]:
        raise ValueError('El agregado no coincide con su evidencia de integridad.')
    return json.loads(content)

def load_dashboard():
    output = {}
    for key, (directory, summary, validation) in LOTS.items():
        folder = BASE / directory
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        proof = json.loads((folder / validation).read_text(encoding='utf-8'))
        if manifest.get('estado') != 'COMPLETADO' or proof.get('estado') != 'APROBADO' or proof.get('test_excluido') is not True:
            raise ValueError('El lote no está validado para esta presentación.')
        if manifest.get('particiones') != ['train', 'validation']:
            raise ValueError('Particiones ajenas al alcance permitido.')
        totals = checked(folder, summary, manifest)
        for row in [totals['total'], *totals['fuentes'].values()]:
            if sum(row['sentimientos'].values()) != row['informativos_propuestos'] or row['informativos_propuestos'] + row['no_informativos_propuestos'] != row['procesados']:
                raise ValueError('Conteos inconsistentes.')
        if sum(row['procesados'] for row in totals['fuentes'].values()) != totals['total']['procesados']:
            raise ValueError('Cobertura inconsistente.')
        output[key] = {'lote': directory, 'periodo': '2026-II', 'dataset': manifest['dataset'], 'versiones': manifest['versiones'], **totals}
    return {'lotes': output, 'produccion_activada': False, 'alcance': 'Muestra revisada de train/validation. No representa toda la institución ni mide desempeño docente. La revisión resuelve informatividad; los sentimientos siguen siendo propuestas del modelo.'}
