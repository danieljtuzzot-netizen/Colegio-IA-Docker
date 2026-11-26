"""Guardas de tecnología y documentación; no certifican pertinencia general."""
import re
import unicodedata

VERSION='guarda_aspectos_acotados_v2'
DOCUMENTS={'documentacion','documentos','planeacion','planeaciones','planificacion','planificaciones',
           'planes de clase','plan de clase','programaciones','planeamiento'}
DEADLINES={'retraso','retrasos','puntual','puntuales','puntualmente','oportuno','oportuna','oportunamente',
           'a tiempo','plazo','plazos','demora','demoras','sin retrasos','tardia','tardias','tarde'}
TECH={
    'ordenador','ordenadores','computador','computadores','computadora','computadoras',
    'informatica','informatico','informaticos','tecnologia','tecnologias','tecnologico','tecnologicos',
    'digital','digitales','plataforma','plataformas','audiovisual','audiovisuales','software',
    'arukay','ibec','sistema uno',
}
OTHER_ASPECTS={
    'INGLES':{'ingles','bilinguismo','linguaskill','certificacion'},
    'TRATO':{'trato','respeto','grosero','empatia','preferencias'},
    'PLANIFICACION':{'planeacion','planeaciones','planificacion','planeamiento','documentacion'},
    'ESPIRITUALIDAD':{'espiritualidad','oracion','fe','dios','espiritual'},
    'DIDACTICA':{'didactica','metodologia','pedagogia','dinamicas','divertidas','divertidos'},
    'MANEJO_GRUPO':{'disciplina','convivencia','manejo de grupo','manejo del grupo'},
}

def normalize(text):
    value=''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))
    return ' '+' '.join(re.findall(r'[a-z0-9]+',value))+' '

def has(text,terms):return any(' '+term+' ' in text for term in terms)

def review_candidates(question,candidates):
    query=normalize(question)
    technology=has(query,TECH)
    other=[topic for topic,terms in OTHER_ASPECTS.items() if has(query,terms)]
    documentation=has(query,DOCUMENTS) and not technology and not any(topic!='PLANIFICACION' for topic in other)
    deadline=documentation and has(query,DEADLINES)
    tech_applied=technology and not other
    applied=tech_applied or documentation
    kept=[];held=[]
    for row in candidates:
        supported=row.get('tema')=='TECNOLOGIA' or has(normalize(row['cita']),TECH)
        cite=normalize(row['cita'])
        if documentation and (not has(cite,DOCUMENTS) or (deadline and not has(cite,DEADLINES))):
            held.append({'evidencia':row,'motivo':'La consulta trata documentación'+(' y plazos de entrega' if deadline else '')+'; la cita no menciona explícitamente ese aspecto. Se aparta para revisión, sin concluir que el tema esté ausente.'})
        elif tech_applied and not supported:
            held.append({'evidencia':row,'motivo':'La consulta es tecnológica; la cita no tiene tema revisado ni vocabulario explícito de tecnología.'})
        else:kept.append(row)
    return kept,{'version':VERSION,'aplicada':applied,'aspecto':'DOCUMENTACION_Y_PLAZOS' if deadline else 'DOCUMENTACION' if documentation else 'TECNOLOGIA' if technology else None,
                 'otros_aspectos_detectados':other,'candidatos_antes':len(candidates),'candidatos_permitidos':len(kept),
                 'apartados_para_revision':held,'certifica_pertinencia_general':False,
                 'alcance':'Reglas acotadas de tecnología y documentación/plazos; no clasificación semántica universal. En documentación se exige vocabulario explícito, con posibles falsos negativos que requieren revisión. Las consultas con múltiples aspectos conservan la selección para revisión humana.'}
