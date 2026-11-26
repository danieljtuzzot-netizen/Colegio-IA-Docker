'use strict';
(()=>{
 const get=id=>document.getElementById(id);
 const add=(tag,text,parent)=>{const n=document.createElement(tag);n.textContent=text;parent.append(n);return n;};
 const names={ESTUDIANTES:'Estudiantes',JEFE:'Jefe inmediato',LENGUAS:'Bilingüismo',CAPELLANIA:'Capellanía',AUTOEVALUACION:'Autoevaluación',PENDIENTE_DE_RESOLVER:'Fuente pendiente de resolver'};
 const pct=window.DemoFormato.porcentaje;let bundle;
 let current;
 function render(){
  if(!bundle)return;
  const data=bundle.versiones[get('quantVersion').value];
  const recent=get('quantVersion').value==='actual';
  const source=get('source').value;
  const rows=Object.entries(data.fuentes).filter(([code])=>!source||source===code);
  const selected=source?data.fuentes[source]:data.total;
  current={data,rows,recent};get('quantCsv').disabled=false;
  get('quantScope').textContent=data.alcance;
  get('quantRows').replaceChildren();get('quantCards').replaceChildren();
  if(!selected){get('quantStatus').textContent='No hay agregado para esta fuente.';return;}
  get('quantStatus').textContent=recent?`Extracción guardada: ${new Date(data.fecha_utc).toLocaleDateString('es-CO')} · Periodo ${data.periodo} · ${names[source]||'Todas las fuentes, incluida autoevaluación'}`:`Corte histórico: ${data.fecha_corte} · Fuente: ${names[source]||'Todas, incluida autoevaluación y fuente pendiente'} · Sin desglose por periodo`;
  for(const [label,value] of [['Respuestas numéricas',selected.respuestas],['Promedio descriptivo sin ponderar',pct(selected.porcentaje_descriptivo_raw)],[recent?'Docentes con respuestas':'Respuestas sin fuente resuelta',recent?selected.docentes_cantidad:(source?(source==='PENDIENTE_DE_RESOLVER'?selected.respuestas:0):(data.fuentes.PENDIENTE_DE_RESOLVER?.respuestas||0))]]){const card=add('section','',get('quantCards'));card.className='panel card';add('span',label,card);add('strong',typeof value==='number'?window.DashboardUI.number(value):value,card);}
  for(const [code,row] of rows){const tr=add('tr','',get('quantRows'));for(const value of [names[code],row.respuestas,pct(row.porcentaje_descriptivo_raw)])add('td',typeof value==='number'?window.DashboardUI.number(value):value,tr);}
  get('quantDistribution').replaceChildren();
  if(source&&!recent){add('p','La auditoría histórica no contiene distribución de notas por fuente. No se desglosa para esta selección.',get('quantDistribution'));return;}
  window.DashboardUI.histogram(get('quantDistribution'),selected.distribucion,selected.respuestas);
 }
 get('source').addEventListener('change',render);get('quantVersion').addEventListener('change',render);
 get('quantCsv').onclick=()=>{if(!current)return;const {data,rows,recent}=current;const table=[['version','periodo','fecha_snapshot','fuente','respuestas','promedio_descriptivo_sin_ponderar'],...rows.map(([code,row])=>[recent?'snapshot_actual':'historico',data.periodo,data.fecha_utc||data.fecha_corte,names[code],row.respuestas,pct(row.porcentaje_descriptivo_raw)])];const content='\ufeff'+table.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([content],{type:'text/csv;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download=recent?'calificaciones_snapshot_2026_II.csv':'calificaciones_historico_20261027.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 fetch('/api/cuantitativo',{headers:{'X-Demo-Token':window.DEMO_TOKEN}}).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.error||'No se pudo cargar el histórico cuantitativo.');bundle=d;get('quantVersion').value=d.predeterminada;render();}).catch(e=>{get('quantStatus').textContent=e.message;get('quantStatus').className='error';get('quantScope').textContent='Agregados no disponibles. No se sustituyen por ceros ni valores simulados.';});
})();
