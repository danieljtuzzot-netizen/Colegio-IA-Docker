"""Ruta experimental de desarrollo; nunca reemplaza automáticamente la salida actual."""
import re

# Indicadores acotados para revisión de desarrollo, no diccionario definitivo de sentimiento.
CRITICISM=re.compile(r'\b(?:deber[ií]a|debe|necesit\w*|falta\w*|confus\w*|tarde|demora\w*|cuesta|dificult\w*|mejorar|recomiend\w*)\b',re.I)

def propose(baseline,clauses):
    if baseline not in ('FORTALEZA','OPORTUNIDAD'):
        return baseline
    praise=any(c['categoria']=='FORTALEZA' for c in clauses)
    criticism=any(c['categoria']=='OPORTUNIDAD' and CRITICISM.search(c['texto']) for c in clauses)
    return 'MIXTO' if praise and criticism else baseline
