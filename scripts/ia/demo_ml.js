'use strict';
(()=>{
 const get=id=>document.getElementById(id);
 const add=(tag,text,parent)=>{const n=document.createElement(tag);n.textContent=text;parent.append(n);return n;};
 const labels={referencia_fuente:'Referencia: promedio por fuente',control_cobertura:'Control: fuente y cobertura',modelo_sentimiento:'Modelo: añade sentimientos'};
 const names={ESTUDIANTES:'Estudiantes',LENGUAS:'Bilingüismo',JEFE:'Jefe inmediato',CAPELLANIA:'Capellanía',AUTOEVALUACION:'Autoevaluación'};
 const points=raw=>Math.round(raw)+' pp';let data;
 const colors={referencia_fuente:'#a4b0c5',control_cobertura:'#6d8bbd',modelo_sentimiento:'#4665dc'};
 const number=n=>new Intl.NumberFormat('es-CO',{maximumFractionDigits:0}).format(n);
 const svg=(tag,attrs,parent,text)=>{const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,value] of Object.entries(attrs))n.setAttribute(key,value);if(text!==undefined)n.textContent=text;parent.append(n);return n;};
 const interval=n=>n===90?'90–100 %':`${n}–<${n+10} %`;
 function density(values){
  const parent=get('mlDensity');parent.replaceChildren();
  const chart=svg('svg',{viewBox:'0 0 430 390',role:'img','aria-label':'Mapa agrupado de promedios reales y estimados. Cada celda contiene al menos tres casos.'},parent);
  const x=65,y=20,size=300,step=size/8;
  svg('rect',{x,y,width:size,height:size,fill:'#f7f9fd',stroke:'#dfe5f0'},chart);
  for(let i=0;i<=8;i++){const pos=i*step;svg('line',{x1:x+pos,x2:x+pos,y1:y,y2:y+size,stroke:'#e5eaf3'},chart);svg('line',{x1:x,x2:x+size,y1:y+pos,y2:y+pos,stroke:'#e5eaf3'},chart);if(i%2===0){svg('text',{x:x+pos,y:y+size+22,'text-anchor':'middle',class:'ml-axis'},chart,(20+i*10)+' %');svg('text',{x:x-10,y:y+size-pos+4,'text-anchor':'end',class:'ml-axis'},chart,(20+i*10)+' %');}}
  const maximum=Math.max(1,...values.celdas.map(c=>c.casos));
  for(const cell of values.celdas){const rect=svg('rect',{x:x+(cell.real_desde-20)/10*step+1,y:y+size-(cell.estimado_desde-10)/10*step+1,width:step-2,height:step-2,rx:4,fill:'#4665dc',opacity:.22+.73*cell.casos/maximum},chart);svg('title',{},rect,`Real ${interval(cell.real_desde)} · Estimado ${interval(cell.estimado_desde)} · ${number(cell.casos)} casos`);}
  svg('line',{x1:x,y1:y+size,x2:x+size,y2:y,stroke:'#159b89','stroke-width':2,'stroke-dasharray':'6 5'},chart);
  svg('text',{x:x+size/2,y:373,'text-anchor':'middle',class:'ml-axis-label'},chart,'Promedio real · sin ponderar');
  svg('text',{transform:'translate(16 170) rotate(-90)','text-anchor':'middle',class:'ml-axis-label'},chart,'Promedio estimado');
  const shown=values.celdas.reduce((sum,c)=>sum+c.casos,0);
  get('mlDensityNote').textContent=`Rangos de 10 pp. Un tono más intenso indica más casos. Se representan ${number(shown)} de ${number(values.casos)} casos; ${number(values.casos_celdas_no_publicadas)} quedan en celdas con menos de tres casos y ${number(values.predicciones_fuera_escala)} tienen estimaciones fuera de 20–100 %. No se recortan las estimaciones para calcular errores. La diagonal representa coincidencia ideal; la celda no da una predicción individual.`;
 }
 function errors(values){
  const parent=get('mlErrorChart');parent.replaceChildren();
  const labels=['Menos de 2 pp','De 2 a menos de 5 pp','De 5 a menos de 10 pp','De 10 a menos de 20 pp','20 pp o más'];
  const maximum=Math.max(1,...values.histograma_error_absoluto);
  values.histograma_error_absoluto.forEach((n,i)=>{const row=add('div','',parent);row.className='ml-error-row';add('span',labels[i],row);const track=add('div','',row);track.className='ml-error-track';const fill=add('span','',track);fill.style.width=(n/maximum*100)+'%';fill.style.background=i<2?'#159b89':'#8198d3';add('strong',number(n),row);row.title=number(n)+' casos · '+window.DemoFormato.porcentajeSobre(n,values.casos);});
  get('mlErrorNote').textContent=`${number(values.casos_error_hasta_5_pp)} de ${number(values.casos)} casos tuvieron un error de hasta 5 pp (${window.DemoFormato.porcentajeSobre(values.casos_error_hasta_5_pp,values.casos)}). Es una descripción de esta prueba, no un porcentaje general de exactitud.`;
 }
 function sourceComparison(source){
  const parent=get('mlSourceComparison');parent.replaceChildren();
  const sources=source?[source]:Object.keys(data.fuentes);
  const maximum=Math.max(1,...sources.flatMap(s=>Object.values(data.fuentes[s].metricas).map(m=>m.mae_pp_raw)));
  for(const key of sources){const section=add('section','',parent);section.className='ml-source-group';add('h4',names[key],section);for(const [model,metrics] of Object.entries(data.fuentes[key].metricas)){const row=add('div','',section);row.className='ml-method-row';add('span',labels[model],row);const track=add('div','',row);track.className='ml-error-track';const fill=add('span','',track);fill.style.width=(metrics.mae_pp_raw/maximum*100)+'%';fill.style.background=colors[model];add('strong',points(metrics.mae_pp_raw),row);}add('p',number(data.fuentes[key].filas)+' casos · '+number(data.fuentes[key].docentes)+' docentes',section).className='muted';}
 }
 function renderCoverage(source){
  const visual=data.visualizacion;get('mlCoveragePanel').hidden=!visual;
  if(!visual)return;
  const coverage=visual.cobertura,selected=source?coverage.fuentes[source]:coverage.total;
  const parent=get('mlCoverage');parent.replaceChildren();get('mlCoverageRows').replaceChildren();
  for(const [label,n] of [['Casos revisados',selected.revisados],['Excluidos por respuestas',selected.pocas_respuestas],['Excluidos por comentarios',selected.pocos_comentarios],['Excluidos por cobertura de fuente',selected.pocos_docentes_fuente],['Casos incluidos',selected.incluidos]]){const box=add('div','',parent);add('strong',number(n),box);add('span',label,box);}
  get('mlCoverageNote').textContent=`${names[source]||'Todas las fuentes'} · Se incluyó ${window.DemoFormato.porcentajeSobre(selected.incluidos,selected.revisados)} de los casos revisados. Esto no mide representatividad de toda la institución. Mínimos: 5 respuestas cerradas, 3 comentarios informativos y 10 docentes elegibles por fuente.`;
  for(const [key,row] of Object.entries(coverage.fuentes)){if(source&&source!==key)continue;const tr=add('tr','',get('mlCoverageRows'));for(const value of [names[key],row.revisados,row.pocas_respuestas,row.pocos_comentarios,row.pocos_docentes_fuente,row.incluidos])add('td',typeof value==='number'?number(value):value,tr);}
 }
 function charts(source){
  const values=data.visualizacion?.grupos[source||'TOTAL']?.modelos[get('mlModel').value];
  get('mlVisuals').hidden=!values;
  get('mlVisualStatus').textContent=values?'Gráficas de predicciones fuera del ajuste de cada grupo. Selecciona un método para explorarlas.':data.visualizacion?'No hay estimaciones evaluadas para esta fuente. La cobertura explica las exclusiones.':'Este despliegue conserva las métricas, pero aún no incluye el derivado de gráficas. Actualiza la exportación de la demo para mostrarlas.';
  for(const id of ['mlDensity','mlErrorChart','mlSourceComparison'])get(id).replaceChildren();
  if(values){density(values);errors(values);sourceComparison(source);}
  renderCoverage(source);
 }
 function render(){
  if(!data)return;
  const source=get('source').value;
  charts(source);
  get('mlCards').replaceChildren();get('mlRows').replaceChildren();get('mlConclusion').textContent='';
  get('mlLimits').replaceChildren();for(const text of data.limites)add('li',text,get('mlLimits'));
  const selected=source?data.fuentes[source]:{filas:data.filas,docentes:data.docentes,metricas:data.metricas};
  if(!selected){get('mlStatus').textContent='Esta fuente no cumple la cobertura mínima de la prueba ML. No se muestran métricas ni estimaciones para ella.';return;}
  get('mlStatus').textContent=`Exploración fijada de 2026-II · ${names[source]||'Estudiantes y bilingüismo'} · Informatividad revisada · Validación de regresión en cinco grupos sin docentes compartidos entre entrenamiento y validación de cada grupo. Los selectores de histórico y versión de comentarios no recalculan esta prueba.`;
  const metrics=selected.metricas,reference=data.mejor_referencia;
  const base=metrics[reference].mae_pp_raw,full=metrics.modelo_sentimiento.mae_pp_raw;
  const improvement=base?100*(base-full)/base:null;
  for(const [label,value] of [['Docentes en validación',selected.docentes],['Casos docente/fuente',selected.filas],['Error medio con sentimientos',points(full)],['Reducción del error frente al control',window.DemoFormato.porcentaje(improvement)]]){const c=add('section','',get('mlCards'));c.className='panel card';add('span',label,c);add('strong',value,c);}
  for(const [key,row] of Object.entries(metrics)){const tr=add('tr','',get('mlRows'));for(const value of [labels[key],points(row.mae_pp_raw),points(row.rmse_pp_raw)])add('td',value,tr);}
  get('mlConclusion').textContent=full<base?'En esta exploración, añadir sentimientos redujo el error frente al control de fuente y cobertura. Es evidencia preliminar de asociación; no es un porcentaje de exactitud ni una autorización para evaluar personas automáticamente.':'En esta selección, añadir sentimientos no redujo el error frente al control. La referencia sigue siendo preferible en esta comparación; no se activa el modelo.';
 }
 get('source').addEventListener('change',render);
 get('mlModel').addEventListener('change',()=>{if(data)charts(get('source').value);});
 fetch('/api/ml',{headers:{'X-Demo-Token':window.DEMO_TOKEN}}).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.error||'No se pudo verificar la comparación ML.');data=d;render();}).catch(e=>{get('mlStatus').textContent=e.message;get('mlStatus').className='error';});
})();
