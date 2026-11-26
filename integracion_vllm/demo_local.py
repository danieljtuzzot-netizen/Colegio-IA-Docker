"""Demo sólo en loopback; guarda revisiones locales únicamente por acción explícita."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import json
from pathlib import Path
import re
import secrets
import threading
import time
from clasificar_comentario import ClasificadorComentarios
from piloto_extraccion_comentarios import SYSTEM,PERSONAL,segments,schema,validate,aggregate
from ollama_resumen_local import ROOT,MODEL,PIN,managed_server,local_model,request
from demo_entorno import SETTINGS
import demo_revisiones as reviews

PORT=SETTINGS['port']
TOKEN=secrets.token_urlsafe(32)
LOCK=threading.Lock()
PIPELINE=None
PAGE=Path(__file__).with_name('demo_local.html')

def analyze(question,comment,experimental=False):
    global PIPELINE
    if type(experimental) is not bool:raise ValueError('Opción experimental inválida.')
    if not isinstance(question,str) or not question.strip() or len(question)>1000:raise ValueError('Escribe una pregunta de hasta 1000 caracteres.')
    if not isinstance(comment,str) or len(comment)>1500:raise ValueError('El comentario admite hasta 1500 caracteres.')
    if PERSONAL.search(comment+' '+question) or re.search(r'@|https?://|\d[\d\s()+-]{6,}\d',comment+' '+question):
        return {'estado':'RETENIDO_PRIVACIDAD','mensaje':'Usa un ejemplo ficticio sin datos personales o sensibles.','requiere_revision_humana':True}
    start=time.perf_counter()
    if PIPELINE is None:PIPELINE=ClasificadorComentarios()
    beto=PIPELINE.clasificar(question,comment)
    result={'estado':'EXPERIMENTAL','informatividad':beto['informatividad'],'sentimiento':beto['sentimiento'],
        'tipo':None,'segmentos':[],'versiones':beto['versiones'],'ollama_modelo':MODEL,'requiere_revision_humana':True,
        'beto_ejecutado':beto['beto_ejecutado'],'accion':beto['accion'],'produccion_activada':False,'avisos':[]}
    if beto['informatividad']=='NO_INFORMATIVO':
        result['avisos'].append('El filtro propone retener este comentario. No se elimina y requiere revisión; el sentimiento permanece vacío.')
    try:
        managed_server();tag,_=local_model();assert tag['digest']==json.loads(PIN.read_text(encoding='utf-8'))['digest']
        if not comment.strip():result['tipo']='ABSTENCION'
        else:
            items=segments(comment)
            payload={'model':MODEL,'system':SYSTEM,'prompt':json.dumps({'segmentos':[{'id':s['id'],'texto':s['texto']} for s in items]},ensure_ascii=False),
                'format':schema(items),'stream':False,'keep_alive':'5m','options':{'temperature':0,'seed':42,'num_ctx':4096,'num_predict':300,'num_thread':4,'num_gpu':0}}
            response=request('/api/generate',payload,timeout=180)
            assert response.get('done') and response.get('done_reason')=='stop'
            value=json.loads(response['response']);validate(value,items)
            byid={s['id']:s for s in items};result['tipo']=aggregate(value['analisis'])
            result['segmentos']=[{'id':r['segmento'],'categoria':r['categoria'],'texto':byid[r['segmento']]['texto']} for r in value['analisis']]
    except Exception:
        result['avisos'].append('El análisis de tipo no produjo una salida válida. Se conservan los resultados disponibles de BETO; revisa Ollama local.')
    if experimental and result['tipo'] in ('MIXTO','CONTEXTO','ABSTENCION'):
        result['tipo_experimental']=result['tipo']
        result['avisos'].append('La ruta experimental conserva esta categoría sin realizar inferencias adicionales.')
    if experimental and result['tipo'] in ('FORTALEZA','OPORTUNIDAD'):
        try:
            from desarrollo_ollama_v4 import clauses
            from desarrollo_ollama_v3 import SYSTEM as CLAUSE_SYSTEM,LABELS
            from candidata_mixtos_conservadora import propose
            parts=[]
            for part in clauses(comment):
                payload={'model':MODEL,'system':CLAUSE_SYSTEM,'prompt':json.dumps({'comentario':part['texto']},ensure_ascii=False),
                    'format':{'type':'object','properties':{'categoria':{'type':'string','enum':LABELS}},'required':['categoria'],'additionalProperties':False},
                    'stream':False,'keep_alive':'5m','options':{'temperature':0,'seed':42,'num_ctx':4096,'num_predict':80,'num_thread':4,'num_gpu':0}}
                response=request('/api/generate',payload,timeout=180);value=json.loads(response['response'])
                assert response.get('done') and response.get('done_reason')=='stop' and set(value)=={'categoria'} and value['categoria'] in LABELS
                parts.append({**part,'categoria':value['categoria']})
            result['tipo_experimental']=propose(result['tipo'],parts)
            result['avisos'].append('La detección de mixtos es una candidata de desarrollo sin validación independiente; no reemplaza el tipo actual.')
        except Exception:result['avisos'].append('La comparación experimental no pudo completarse; el resultado actual se conserva.')
    result['segundos_raw']=time.perf_counter()-start
    return result

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,status,value,html=False):
        data=value.encode('utf-8') if html else json.dumps(value,ensure_ascii=False).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type','text/html; charset=utf-8' if html else 'application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.end_headers();self.wfile.write(data)
    def allowed(self):return self.headers.get('Host') in SETTINGS['hosts']
    def authorized(self):
        return self.headers.get('X-Demo-Token')==TOKEN and self.headers.get('Origin') in SETTINGS['origins']
    def do_GET(self):
        if not self.allowed():return self.reply(403,{'error':'Host no permitido'})
        if self.path=='/':return self.reply(200,PAGE.read_text(encoding='utf-8').replace('__TOKEN__',TOKEN),True)
        if self.path=='/dashboard':return self.reply(200,PAGE.with_name('demo_dashboard.html').read_text(encoding='utf-8').replace('__TOKEN__',TOKEN),True)
        if self.path=='/api/motores':
            if not self.authorized():return self.reply(403,{'error':'Sesión local requerida.'})
            from rag_vllm import enabled,configuration
            config=configuration()
            return self.reply(200,{'ollama':True,'vllm':enabled(),
                                  'predeterminado':'vllm' if enabled() and config['variante']=='15b' else 'ollama',
                                  'vllm_config':config})
        if self.path in ('/dashboard.css','/dashboard-ui.js'):
            filename,content_type={'/dashboard.css':('demo_dashboard.css','text/css; charset=utf-8'),'/dashboard-ui.js':('demo_dashboard_ui.js','application/javascript; charset=utf-8')}[self.path]
            content=PAGE.with_name(filename).read_bytes();self.send_response(200);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(content);return
        if self.path=='/ml.js':
            content=PAGE.with_name('demo_ml.js').read_bytes();self.send_response(200);self.send_header('Content-Type','application/javascript; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(content);return
        if self.path=='/api/ml':
            if not self.authorized():return self.reply(403,{'error':'Recarga la página para iniciar la sesión local.'})
            try:
                from demo_ml import load_summary
                return self.reply(200,load_summary())
            except Exception:return self.reply(503,{'error':'No se pudo verificar la exploración ML congelada.'})
        if self.path=='/vinculos.js':
            content=PAGE.with_name('demo_vinculos.js').read_bytes();self.send_response(200);self.send_header('Content-Type','application/javascript; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(content);return
        if self.path=='/api/vinculos':
            if not self.authorized():return self.reply(403,{'error':'Recarga la página para iniciar la sesión local.'})
            try:
                from demo_vinculos import load_links
                return self.reply(200,load_links())
            except Exception:return self.reply(503,{'error':'No se pudo verificar el informe vinculado por docente.'})
        if self.path=='/formato.js':
            content=PAGE.with_name('demo_formato.js').read_bytes();self.send_response(200);self.send_header('Content-Type','application/javascript; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(content);return
        if self.path=='/cuantitativo.js':
            content=PAGE.with_name('demo_cuantitativo.js').read_bytes();self.send_response(200);self.send_header('Content-Type','application/javascript; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(content);return
        if self.path=='/api/cuantitativo':
            if not self.authorized():return self.reply(403,{'error':'Recarga la página para iniciar la sesión local.'})
            try:
                from demo_cuantitativo import load_views
                return self.reply(200,load_views())
            except Exception:return self.reply(503,{'error':'No se pudieron verificar los agregados cuantitativos.'})
        if self.path=='/consultas.js':
            content=PAGE.with_name('demo_consultas.js').read_bytes();self.send_response(200);self.send_header('Content-Type','application/javascript; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(content);return
        if self.path=='/temas.js':
            content=PAGE.with_name('demo_temas.js').read_bytes();self.send_response(200);self.send_header('Content-Type','application/javascript; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(content);return
        if self.path=='/api/temas':
            if not self.authorized():return self.reply(403,{'error':'Recarga la página para iniciar la sesión local.'})
            try:
                from demo_temas import load_themes
                return self.reply(200,load_themes())
            except Exception:return self.reply(503,{'error':'No se pudo verificar la síntesis autorizada. No se muestran citas parciales.'})
        if self.path=='/dashboard.js':
            content=PAGE.with_name('demo_dashboard.js').read_bytes();self.send_response(200);self.send_header('Content-Type','application/javascript; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(content);return
        if self.path=='/api/dashboard':
            if not self.authorized():return self.reply(403,{'error':'Recarga la página para iniciar la sesión local.'})
            try:
                from demo_dashboard import load_dashboard
                return self.reply(200,load_dashboard())
            except Exception:return self.reply(503,{'error':'No se pudieron verificar los agregados del lote. No se muestran datos parciales.'})
        if self.path=='/app.js':
            content=PAGE.with_suffix('.js').read_bytes();self.send_response(200);self.send_header('Content-Type','application/javascript; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(content);return
        if self.path=='/health':return self.reply(200,{'estado':'LISTO','demo_local':True,'beto_cargado':PIPELINE is not None,'produccion_activada':False})
        if self.path in ('/api/revisiones','/api/exportar.csv','/api/exportar.json'):
            if not self.authorized():return self.reply(403,{'error':'Recarga la página para iniciar la sesión local.'})
            try:rows=reviews.records()
            except Exception:return self.reply(503,{'error':'No se pudo leer el historial local.'})
            if self.path=='/api/exportar.csv':
                content=reviews.csv_export(rows);self.send_response(200)
                self.send_header('Content-Type','text/csv; charset=utf-8');self.send_header('Content-Disposition','attachment; filename="revisiones_demo.csv"');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
            return self.reply(200,{'revisiones':rows,'produccion_activada':False})
        self.reply(404,{'error':'Ruta no disponible'})
    def do_POST(self):
        if not self.allowed() or self.path not in ('/api/analizar','/api/revisar','/api/consultar'):return self.reply(403,{'error':'Ruta no permitida'})
        if self.headers.get('X-Demo-Token')!=TOKEN:return self.reply(403,{'error':'Recarga la página para iniciar la sesión local.'})
        if self.headers.get('Origin') not in SETTINGS['origins']:return self.reply(403,{'error':'Origen no permitido'})
        try:
            n=int(self.headers.get('Content-Length','0'));assert 0<n<=12000
            data=json.loads(self.rfile.read(n));assert isinstance(data,dict)
            if self.path=='/api/analizar':assert {'pregunta','comentario'}<=set(data)<={'pregunta','comentario','experimental'}
        except Exception:return self.reply(400,{'error':'Solicitud inválida.'})
        if self.path=='/api/revisar':
            try:return self.reply(200,{'revision':reviews.save(data),'guardado_local':True})
            except ValueError as exc:return self.reply(400,{'error':str(exc)})
            except Exception:return self.reply(503,{'error':'No se pudo guardar la revisión local.'})
        if not LOCK.acquire(blocking=False):return self.reply(429,{'error':'Hay un análisis en curso. Espera a que termine.'})
        try:
            if self.path=='/api/consultar':
                from demo_consultas import consult
                return self.reply(200,consult(data))
            result=analyze(data['pregunta'],data['comentario'],data.get('experimental',False))
            self.reply(200,reviews.register(data['pregunta'],data['comentario'],result))
        except ValueError as exc:self.reply(400,{'error':str(exc)})
        except Exception:self.reply(503,{'error':'No se pudo completar el análisis local. Revisa la instalación de los modelos.'})
        finally:LOCK.release()

if __name__=='__main__':
    ThreadingHTTPServer((SETTINGS['bind'],PORT),Handler).serve_forever()
