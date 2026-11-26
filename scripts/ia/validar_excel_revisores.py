"""Valida los libros de revisión humana sin ejecutar fórmulas ni consultar MariaDB."""
import hashlib
import json
import posixpath
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
SHEETS = {'Estudiantes': 'ESTUDIANTES', 'Jefe inmediato': 'JEFE', 'Bilingüismo': 'LENGUAS', 'Capellanía': 'CAPELLANIA'}
FIELDS = ['id_origen','pregunta','comentario','informatividad','sentimiento','privacidad_revisada','ambiguo','mixto','observacion_etiquetado','id_evaluacion','id_pregunta','id_profesor','periodo','fuente_evaluacion','grupo_texto','fecha_respuesta','estado_etiquetado']
EDITABLE = {'informatividad','sentimiento','privacidad_revisada','ambiguo','mixto','observacion_etiquetado'}

def unescape(s):
    return re.sub(r'_x([0-9A-Fa-f]{4})_', lambda m: chr(int(m[1],16)), s)

def read_book(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            shared = [unescape(''.join(e.itertext())) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si', NS)]
        rels = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        result = {}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet', NS):
            target = rels[sheet.attrib[RID]]
            target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            if not target.startswith('xl/') or '..' in target.split('/'):
                raise ValueError('Relación fuera del libro')
            xml = ET.fromstring(z.read(target)); rows = {}
            for row in xml.findall('s:sheetData/s:row', NS):
                values = {}; formulas = set()
                for cell in row.findall('s:c', NS):
                    col = re.sub(r'\d','',cell.attrib['r']); v = cell.find('s:v', NS)
                    value = '' if v is None or v.text is None else v.text
                    if cell.attrib.get('t') == 's': value = shared[int(value)]
                    elif cell.attrib.get('t') == 'inlineStr': value = unescape(''.join(cell.find('s:is', NS).itertext()))
                    if cell.find('s:f', NS) is not None: formulas.add(col)
                    if cell.attrib.get('t') == 'e': raise ValueError('Error Excel en celda '+cell.attrib['r'])
                    values[col] = value
                rows[int(row.attrib['r'])] = (values, formulas)
            result[sheet.attrib['name']] = (rows, xml)
        return result

def validate(base):
    manifest = json.loads((base/'manifest_muestra_excel.json').read_text(encoding='utf-8'))
    source_path = base/'muestra_excel.json'
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != manifest['muestra_sha256']:
        raise ValueError('Muestra base alterada')
    source = {r['id_origen']:r for r in json.loads(source_path.read_text(encoding='utf-8'))}
    if len(source) != manifest['cantidad']: raise ValueError('IDs base duplicados')
    summary = {}; idsets = []; errors = []
    for reviewer in [1,2]:
        book = read_book(base/f'revision_revisor_{reviewer}.xlsx')
        if set(book) != {'Instrucciones',*SHEETS}: raise ValueError('Pestañas distintas de las esperadas')
        seen = set(); counts = Counter(); complete = 0; filled = 0
        for title, code in SHEETS.items():
            rows, xml = book[title]
            if list(rows[6][0].values()) != FIELDS: raise ValueError('Cabecera alterada')
            if len(xml.findall('s:dataValidations/s:dataValidation', NS)) != 5: raise ValueError('Faltan listas de validación')
            pane = xml.find('s:sheetViews/s:sheetView/s:pane', NS)
            if pane is None or float(pane.attrib.get('ySplit',0)) != 6: raise ValueError('Cabecera sin inmovilizar')
            for number,(cells,formulas) in rows.items():
                if number < 7: continue
                record = {k:cells.get(chr(65+i),'') for i,k in enumerate(FIELDS)}
                if not any(record[k] for k in ['id_origen','pregunta','comentario']): continue
                ident = record['id_origen']
                if ident not in source or ident in seen: raise ValueError('ID duplicado o ajeno a la muestra')
                seen.add(ident); original = source[ident]
                if record['fuente_evaluacion'] != code: raise ValueError('Fuente incorrecta en pestaña')
                for i,key in enumerate(FIELDS[:-1]):
                    if chr(65+i) in formulas: raise ValueError('Fórmula en un dato o etiqueta humana')
                    if key not in EDITABLE and record[key] != original.get(key,''): raise ValueError('Dato original modificado: '+key)
                i,s,p,a,m,o = [record[k] for k in ['informatividad','sentimiento','privacidad_revisada','ambiguo','mixto','observacion_etiquetado']]
                issues = []
                if i not in ('','INFORMATIVO','NO_INFORMATIVO'): issues.append('INFORMATIVIDAD_INVALIDA')
                if s not in ('','POSITIVO','NEUTRAL','NEGATIVO'): issues.append('SENTIMIENTO_INVALIDO')
                if i != 'INFORMATIVO' and s: issues.append('SENTIMIENTO_NO_APLICA')
                if i == 'INFORMATIVO' and not s: issues.append('SENTIMIENTO_FALTA')
                if any(v not in ('','SI','NO') for v in (p,a,m)): issues.append('SI_NO_INVALIDO')
                if m == 'SI' and (a != 'SI' or not o.strip()): issues.append('MIXTO_INCOMPLETO')
                if issues: errors.append({'revisor':reviewer,'id_origen':ident,'motivos':issues})
                if any(record[k] for k in EDITABLE): filled += 1
                if not issues and i and p == 'SI' and a and m: complete += 1
                counts[code] += 1
        if seen != set(manifest['ids']) or dict(counts) != manifest['fuentes']: raise ValueError('Muestra incompleta o distribución distinta')
        idsets.append(seen)
        summary[f'revisor_{reviewer}'] = {'registros':len(seen),'fuentes':dict(counts),'filas_con_edicion':filled,'completos':complete,'pendientes':len(seen)-complete}
    if idsets[0] != idsets[1]: raise ValueError('Revisores con muestras distintas')
    result = {'estado':'APROBADO' if not errors else 'REVISAR_ETIQUETAS','archivos':summary,'inconsistencias':errors,'apto_entrenamiento':False}
    (base/'validacion_excel.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__ == '__main__':
    try:
        version = sys.argv[1]
        if not re.fullmatch(r'[0-9]{8}_[A-Za-z0-9_-]{1,40}',version): raise ValueError('Versión inválida')
        base = Path(__file__).resolve().parents[2]/'data/ia/versiones'/version/'beto'
        result = validate(base)
        print(json.dumps({k:v for k,v in result.items() if k != 'inconsistencias'},ensure_ascii=False))
        raise SystemExit(0 if result['estado']=='APROBADO' else 1)
    except (ValueError,KeyError,IndexError,OSError,zipfile.BadZipFile) as e:
        print('VALIDACION_FALLIDA: '+type(e).__name__); raise SystemExit(1)
