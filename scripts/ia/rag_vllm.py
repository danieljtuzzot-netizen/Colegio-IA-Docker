"""Adaptador opcional del piloto CPU; destino y modelo cerrados, sin fallback."""
import json
import os
import urllib.request

MODEL = 'qwen-piloto-05b'
BASE = 'http://vllm:8000'


def configuration():
    variant = os.environ.get('IA_VLLM_VARIANT', '05b')
    if variant not in ('05b', '15b'):
        raise ValueError('Variante vLLM no permitida.')
    return {'variante': variant, 'modelo': 'qwen-piloto-' + variant,
            'repositorio': 'Qwen/Qwen2.5-' + ('1.5B' if variant == '15b' else '0.5B') + '-Instruct',
            'etiqueta': 'vLLM · Qwen ' + ('1.5B' if variant == '15b' else '0.5B') + ' · Experimental'}


def enabled():
    return os.environ.get('IA_RUNTIME') == 'docker' and os.environ.get('IA_VLLM_ENABLED') == '1'


def reference_ids(schema):
    if isinstance(schema, dict) and schema.get('type') == 'array' and schema.get('uniqueItems') is True:
        items = schema.get('items', {})
        ids = items.get('enum') if isinstance(items, dict) else None
        if isinstance(ids, list) and ids and all(isinstance(ref, str) for ref in ids) and len(set(ids)) == len(ids):
            return ids
    return None


def synthesis_schema(schema):
    properties = schema.get('properties', {}) if isinstance(schema, dict) else {}
    return (set(properties) == {'insuficiente', 'afirmaciones'}
            and properties['insuficiente'].get('type') == 'boolean'
            and properties['afirmaciones'].get('type') == 'array')


def decode_transport(value, schema):
    if synthesis_schema(schema):
        if not isinstance(value, dict) or set(value) != {'afirmaciones'} or not isinstance(value['afirmaciones'], list):
            raise ValueError('Contrato de transporte de sintesis invalido.')
        claims = decode_transport(value['afirmaciones'], schema['properties']['afirmaciones'])
        return {'insuficiente': not claims, 'afirmaciones': claims}
    ids = reference_ids(schema)
    if ids is not None:
        if not isinstance(value, dict) or set(value) != set(ids) or any(type(flag) is not bool for flag in value.values()):
            raise ValueError('Mapa de referencias incompleto o ajeno a la evidencia.')
        selected = [ref for ref in ids if value[ref]]
        if not schema.get('minItems', 0) <= len(selected) <= schema.get('maxItems', len(ids)):
            raise ValueError('Cantidad de referencias invalida.')
        return selected
    if isinstance(value, dict) and isinstance(schema, dict):
        properties = schema.get('properties', {})
        return {key: decode_transport(item, properties.get(key, {})) for key, item in value.items()}
    if isinstance(value, list) and isinstance(schema, dict):
        return [decode_transport(item, schema.get('items', {})) for item in value]
    return value


def strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Clave JSON duplicada.')
        value[key] = item
    return value


def compatible_schema(value):
    """XGrammar del piloto no admite uniqueItems; la aplicación valida unicidad.

    Devuelve una copia: no altera el contrato usado por Ollama ni sus validadores.
    """
    if isinstance(value, list):
        return [compatible_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    if synthesis_schema(value):
        return {'type': 'object',
                'properties': {'afirmaciones': compatible_schema(value['properties']['afirmaciones'])},
                'required': ['afirmaciones'], 'additionalProperties': False}
    ids = reference_ids(value)
    if ids is not None:
        return {'type': 'object', 'properties': {ref: {'type': 'boolean'} for ref in ids},
                'required': list(ids), 'additionalProperties': False}
    result = {}
    for key, item in value.items():
        if key == 'uniqueItems':
            continue
        # Las claves de properties y $defs son nombres, no palabras del esquema.
        if key in ('properties', '$defs', 'definitions') and isinstance(item, dict):
            result[key] = {name: compatible_schema(child) for name, child in item.items()}
        else:
            result[key] = compatible_schema(item)
    return result


def generate(system, prompt, schema, max_tokens):
    if not enabled():
        raise RuntimeError('vLLM no está habilitado para esta demo.')
    model = configuration()['modelo']
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise RuntimeError('Redirección no permitida.')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(BASE + '/v1/models', timeout=10) as response:
        models = json.load(response)
    if model not in {row.get('id') for row in models.get('data', [])}:
        raise RuntimeError('Modelo del piloto no disponible.')
    payload = {'model': model, 'stream': False, 'temperature': 0, 'seed': 42,
               'max_tokens': min(max_tokens, 650),
               'messages': [{'role': 'system', 'content': system +
                    ' En el esquema de salida, referencias es un objeto: marca true para cada ID que respalda la respuesta y false para los demas. '
                    'Incluye cada clave exactamente una vez. No devuelvas una lista. Usa solo los IDs del esquema.'},
                    {'role': 'user', 'content': prompt}],
               'structured_outputs': {'json': compatible_schema(schema)}}
    req = urllib.request.Request(BASE + '/v1/chat/completions',
                                 data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    with opener.open(req, timeout=300) as response:
        result = json.load(response)
    choices = result.get('choices')
    if result.get('model') != model or not isinstance(choices, list) or len(choices) != 1 or choices[0].get('finish_reason') != 'stop':
        raise RuntimeError('Generación incompleta o modelo distinto del piloto.')
    content = choices[0].get('message', {}).get('content')
    if not isinstance(content, str):
        raise ValueError('Falta respuesta textual.')
    return decode_transport(json.loads(content, object_pairs_hook=strict_object), schema)
