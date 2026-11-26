'use strict';
const $=id=>document.getElementById(id);
let current=null;
const examples=['','Agradezco los ejercicios prácticos porque me ayudan a aprender.','Necesita indicar con anticipación los materiales de la actividad.','Las actividades son interesantes. Debería entregar antes las instrucciones.','La sesión se realiza los jueves en el laboratorio.','Sin comentarios.'];
async function api(path,body){
 const response=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Demo-Token':window.DEMO_TOKEN},...(body?{body:JSON.stringify(body)}:{})});
 const data=await response.json();if(!response.ok)throw Error(data.error||'Error de la demo local');return data;
}
function invalidate(){current=null;$('review').hidden=true;}
$('example').onchange=()=>{$('comment').value=examples[$('example').selectedIndex];invalidate();};
for(const id of ['comment','question','experimental'])$(id).addEventListener('input',invalidate);
$('analyze').onclick=async()=>{
 const button=$('analyze');button.disabled=true;invalidate();$('status').className='step';$('status').textContent='Analizando localmente… La primera carga puede tardar.';
 for(const id of ['info','sentiment','kind'])$(id).textContent='…';$('evidence').replaceChildren();$('warnings').textContent='';
 // Congelar el texto de esta solicitud; no vincular el resultado a ediciones posteriores.
 const input={pregunta:$('question').value,comentario:$('comment').value,experimental:$('experimental').checked};
 try{
  const data=await api('/api/analizar',input);$('raw').textContent=JSON.stringify(data,null,2);
  $('info').textContent=data.informatividad||'Retenido';$('sentiment').textContent=data.sentimiento||'Sin sentimiento';$('kind').textContent=data.tipo||'Pendiente';
  $('warnings').textContent=data.mensaje||(data.avisos||[]).join(' ');if(data.tipo_experimental)$('warnings').textContent+=' Propuesta experimental: '+data.tipo_experimental+'.';
  for(const item of data.segmentos||[]){const div=document.createElement('div');div.className='evidence';div.textContent=item.id+' · '+item.categoria+'\n'+item.texto;$('evidence').append(div);}
  const unchanged=input.pregunta===$('question').value&&input.comentario===$('comment').value&&input.experimental===$('experimental').checked;
  if(data.analisis_id&&unchanged){
   current=data;$('review').hidden=false;$('reviewText').textContent=input.comentario;
   $('rInfo').value=data.informatividad||'';$('rSent').value=data.sentimiento||'';$('rType').value=data.tipo||'';
   $('rAmb').value='';$('rMixed').value='';$('rReason').value='';$('privacy').checked=false;$('reviewStatus').textContent='Confirma o corrige los campos y explica tu criterio. Guardar conserva también la propuesta original.';
  }
  $('status').textContent=data.estado==='RETENIDO_PRIVACIDAD'?'Texto retenido: usa un ejemplo ficticio.':unchanged?'Análisis terminado. Completa la revisión humana.':'Análisis terminado para el texto anterior. Analiza de nuevo el texto editado.';
 }catch(error){$('status').className='step error';$('status').textContent=error.message;for(const id of ['info','sentiment','kind'])$(id).textContent='—';}
 finally{button.disabled=false;}
};
$('saveReview').onclick=async()=>{
 if(!current)return;$('saveReview').disabled=true;
 try{
  const data=await api('/api/revisar',{analisis_id:current.analisis_id,informatividad:$('rInfo').value,sentimiento:$('rSent').value,tipo:$('rType').value,ambiguo:$('rAmb').value,mixto:$('rMixed').value,motivo:$('rReason').value,privacidad_confirmada:$('privacy').checked});
  $('reviewStatus').className='step';$('reviewStatus').textContent='Guardado localmente · '+data.revision.resultado+' · versión '+data.revision.version_revision+'. La propuesta del modelo se conserva.';await loadHistory();
 }catch(error){$('reviewStatus').className='step error';$('reviewStatus').textContent=error.message;}
 finally{$('saveReview').disabled=false;}
};
async function loadHistory(){
 try{
  const data=await api('/api/revisiones');const rows=data.revisiones;$('historyRows').replaceChildren();
  $('historySummary').textContent=new Set(rows.map(r=>r.analisis_id)).size+' análisis revisados · '+rows.length+' versiones guardadas';
  for(const r of rows.slice(0,30)){
   const tr=document.createElement('tr');
   for(const text of [new Date(r.fecha_utc).toLocaleString(),r.comentario.slice(0,90),r.propuesta_original.sentimiento||'—',r.revision_humana.sentimiento||'—',r.propuesta_original.tipo||'—',r.revision_humana.tipo,r.resultado+' · v'+r.version_revision]){const td=document.createElement('td');td.textContent=text;tr.append(td);}
   $('historyRows').append(tr);
  }
 }catch(error){$('historySummary').textContent=error.message;}
}
async function download(format){
 try{
  const response=await fetch('/api/exportar.'+format,{headers:{'X-Demo-Token':window.DEMO_TOKEN}});
  if(!response.ok){const r=await response.json();throw Error(r.error);}
  const blob=await response.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='revisiones_demo.'+format;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }catch(error){$('historySummary').textContent=error.message;}
}
$('exportCsv').onclick=()=>download('csv');$('exportJson').onclick=()=>download('json');$('refresh').onclick=loadHistory;loadHistory();
