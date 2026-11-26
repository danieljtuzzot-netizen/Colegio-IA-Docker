'use strict';
(()=>{
 const get=id=>document.getElementById(id);
 const add=(tag,text,parent)=>{const n=document.createElement(tag);n.textContent=text;parent.append(n);return n;};
 const names={ESTUDIANTES:'Estudiantes',JEFE:'Jefe inmediato',LENGUAS:'Bilingüismo',CAPELLANIA:'Capellanía'};
 let serial=0;
 get('queryAnswer').style.whiteSpace='pre-line';
 fetch('/api/motores',{headers:{'X-Demo-Token':window.DEMO_TOKEN}}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(data=>{const option=get('queryMotor').querySelector('[value="vllm"]');option.disabled=!data.vllm;option.textContent=data.vllm_config?.etiqueta||'vLLM · Experimental';get('queryMotorNote').textContent=data.vllm?`Modelo configurado: ${data.vllm_config?.repositorio||'piloto'}. Las respuestas requieren revisión humana.`:'vLLM no está habilitado en esta configuración.';if(!get('queryMotor').dataset.changed)get('queryMotor').value=data.predeterminado;}).catch(()=>{});
 function clearHeld(){get('queryHeld').replaceChildren();get('queryHeldDetails').hidden=true;get('queryEvidenceDetails').hidden=true;get('queryEvidenceDetails').open=false;get('queryFixCategory').hidden=true;get('queryAnswerNote').hidden=true;}
 function invalidate(){serial++;get('queryEmpty').hidden=false;get('queryOutcome').hidden=true;get('queryEvidence').replaceChildren();clearHeld();get('queryAnswer').textContent='';get('queryTrace').textContent='';get('queryStatus').textContent='Filtros o consulta modificados. Ejecuta una nueva consulta.';}
 get('source').addEventListener('change',invalidate);get('themeCategory').addEventListener('change',invalidate);get('queryText').addEventListener('input',invalidate);get('queryMode').addEventListener('change',invalidate);
 get('queryMotor').addEventListener('change',()=>{get('queryMotor').dataset.changed='1';invalidate();});
 get('queryExample').onchange=()=>{if(get('queryExample').value){get('queryText').value=get('queryExample').value;invalidate();}};
 get('queryForm').onsubmit=async event=>{
  event.preventDefault();const attempt=++serial;
  const payload={pregunta:get('queryText').value,fuente:get('source').value,categoria:get('themeCategory').value,modo_recuperacion:get('queryMode').value,motor:get('queryMotor').value};
  get('queryStatus').className='';
  get('queryEmpty').hidden=true;get('queryOutcome').hidden=false;get('querySubmit').disabled=true;get('queryAnswer').textContent='';get('queryEvidence').replaceChildren();clearHeld();get('queryTrace').textContent='';get('queryStatus').textContent=`Buscando evidencia y consultando ${payload.motor==='vllm'?'vLLM experimental':'Ollama'} local… Puede tardar varios minutos en CPU.`;
  try{
   const response=await fetch('/api/consultar',{method:'POST',headers:{'Content-Type':'application/json','X-Demo-Token':window.DEMO_TOKEN},body:JSON.stringify(payload)});
   const data=await response.json();if(!response.ok)throw Error(data.error||'No se pudo completar la consulta.');if(attempt!==serial)return;
   get('queryStatus').textContent=data.estado==='RESPUESTA_CON_EVIDENCIA'?'Respuesta elaborada con evidencia del piloto':data.estado.replaceAll('_',' ');
   get('queryAnswer').textContent=(data.recuperacion?.aviso?data.recuperacion.aviso+' ':'')+data.respuesta;
   get('queryAnswerNote').hidden=data.estado!=='RESPUESTA_CON_EVIDENCIA';
   get('queryEvidenceDetails').hidden=!data.evidencias.length;
   get('queryEvidenceSummary').textContent=`Ver comentarios de respaldo (${data.evidencias.length})`;
   if(data.categoria_sugerida){const fix=get('queryFixCategory');fix.hidden=false;fix.textContent=`Cambiar a ${data.categoria_sugerida} y consultar`;fix.onclick=()=>{get('queryCategory').value=data.categoria_sugerida;get('queryCategory').dispatchEvent(new Event('change'));get('queryForm').requestSubmit();};}
   for(const row of data.evidencias){const box=add('section','',get('queryEvidence'));box.className='panel';add('h3',`${names[row.fuente]} · ${row.categoria} · ${(row.tema||'Sin tema').replaceAll('_',' ')}`,box);const q=add('blockquote',row.cita,box);q.style.whiteSpace='pre-wrap';q.style.overflowWrap='anywhere';add('p',`Referencia: ${row.segmento_id} · Comentario: ${row.comentario_id}`,box).className='muted';}
   const held=data.revision_pertinencia?.apartados_para_revision||[];
   get('queryHeldDetails').hidden=!held.length;
   for(const item of held){const row=item.evidencia;const section=add('section','',get('queryHeld'));section.className='panel';add('h3',`${names[row.fuente]} · ${(row.tema||row.categoria).replaceAll('_',' ')}`,section);add('p',item.motivo,section).className='muted';const quote=add('blockquote',row.cita,section);quote.style.whiteSpace='pre-wrap';quote.style.overflowWrap='anywhere';add('small',`Referencia: ${row.segmento_id} · Conservada para revisión; no forma parte de la respuesta.`,section);}
   get('queryTrace').textContent=`Consulta: ${payload.pregunta} · Fuente: ${names[payload.fuente]||'Todas'} · Categoría: ${payload.categoria||'Todas'} · Periodo: ${data.periodo} · Segmentos disponibles: ${data.segmentos_disponibles} · Candidatos: ${data.candidatos_recuperados} · Recuperación: ${data.recuperacion?.modo||'LEXICO'} · Coincidencias semánticas: ${data.recuperacion?.coincidencias_semanticas||0} · Coincidencias por palabras: ${data.recuperacion?.coincidencias_lexicas||0} · Embeddings: ${data.recuperacion?.modelo_embeddings||'No usados'} · Método: ${data.metodo} · Selección LLM completada: ${data.llm_ejecutado?'Sí':'No'} · Modelo de selección: ${data.modelo} · Lote: ${data.lote}. La similitud vectorial no es probabilidad de acierto.`;
   get('queryTrace').textContent+=` Control de pertinencia aplicado: ${data.revision_pertinencia?.aplicada?'Sí':'No'} · Candidatos apartados: ${held.length} · Candidatos permitidos para LLM: ${data.candidatos_enviados_llm}. La guarda no certifica pertinencia general.`;
   get('queryTrace').textContent+=` Síntesis completada: ${data.sintesis_ejecutada?'Sí':'No'} · Categoría aplicada: ${data.categoria_aplicada||'Todas'}${data.categoria_inferida?' (deducida de la pregunta)':''}. Las referencias válidas no garantizan que la interpretación sea correcta.`;
   get('queryTrace').textContent+=` Motor: ${data.motor||'ollama'} · Modelo: ${data.modelo_repositorio||data.modelo}. Los modelos de Ollama y vLLM son distintos: esta prueba no compara motores con el mismo modelo.`;
  }catch(error){if(attempt===serial){get('queryStatus').textContent=error.message;get('queryStatus').className='error';}}
  finally{get('querySubmit').disabled=false;}
 };
})();
