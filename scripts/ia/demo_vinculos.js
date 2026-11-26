'use strict';
(()=>{
 const get=id=>document.getElementById(id);
 const add=(tag,text,parent,doc=document)=>{const n=doc.createElement(tag);n.textContent=text;parent.append(n);return n;};
 const names={ESTUDIANTES:'Estudiantes',JEFE:'Jefe inmediato',LENGUAS:'Bilingüismo',CAPELLANIA:'Capellanía',AUTOEVALUACION:'Autoevaluación'};
 const pct=window.DemoFormato.porcentaje;
 const scope='Calificaciones y comentarios de 2026-II por docente. El promedio no aplica ponderaciones institucionales y los sentimientos son propuestas de BETO sobre una muestra revisada. Sin comentarios en la muestra no demuestra ausencia de comentarios institucionales. No se calcula una nota híbrida.';
 let data,current;
 function render(){
  if(!data)return;
  const teacher=data.docentes.find(r=>r.codigo===get('teacherCode').value);
  const version=get('version').value,source=get('source').value;
  const rows=Object.entries(teacher.fuentes).filter(([code])=>!source||code===source);
  const numeric=source?teacher.fuentes[source].cuantitativo:teacher.cuantitativo_total;
  const comments={comentarios:0,informativos:0,sin_sentimiento:0,sentimientos:{POSITIVO:0,NEGATIVO:0,NEUTRAL:0}};
  for(const [,row] of rows){const c=row.comentarios[version];for(const k of ['comentarios','informativos','sin_sentimiento'])comments[k]+=c[k];for(const k of Object.keys(comments.sentimientos))comments.sentimientos[k]+=c.sentimientos[k];}
  current={teacher,version,source,rows,numeric,comments};
  get('teacherScope').textContent=scope;
  get('teacherStatus').textContent=`${teacher.codigo} · Periodo ${teacher.periodo} · Fuente: ${names[source]||'Todas, incluida autoevaluación'} · Comentarios: ${version==='revisado'?'Con revisión de informatividad':'Propuesta original'} · Snapshot cuantitativo: ${data.fecha_snapshot}. Esta vista siempre usa el snapshot verificado de 2026-II; el selector de histórico no la modifica.`;
  get('teacherCards').replaceChildren();get('teacherRows').replaceChildren();get('teacherSentiments').replaceChildren();
  for(const [label,value] of [['Respuestas cerradas',numeric.respuestas],['Promedio descriptivo sin ponderar',pct(numeric.porcentaje_descriptivo_raw)],['Comentarios en muestra',comments.comentarios],['Informativos con sentimiento',comments.informativos]]){const c=add('section','',get('teacherCards'));c.className='panel card';add('span',label,c);add('strong',typeof value==='number'?window.DashboardUI.number(value):value,c);}
  for(const [code,row] of rows){const c=row.comentarios[version],tr=add('tr','',get('teacherRows'));for(const value of [names[code],row.cuantitativo.respuestas,pct(row.cuantitativo.porcentaje_descriptivo_raw),c.comentarios,c.sin_sentimiento,c.sentimientos.POSITIVO,c.sentimientos.NEGATIVO,c.sentimientos.NEUTRAL,c.comentarios?'Muestra disponible':'Sin comentarios en la muestra'])add('td',typeof value==='number'?window.DashboardUI.number(value):value,tr);}
  if(!comments.informativos)add('p','No hay comentarios informativos en esta selección; no se asigna sentimiento NEUTRAL por ausencia.',get('teacherSentiments'));
  else for(const [key,label,color] of [['POSITIVO','Positivo','#168e79'],['NEGATIVO','Negativo','#cf675a'],['NEUTRAL','Neutral','#6d8db2']]){const n=comments.sentimientos[key];const line=add('div','',get('teacherSentiments'));line.className='row';add('span',label,line);add('strong',`${n} · ${window.DemoFormato.porcentajeSobre(n,comments.informativos)}`,line);const bar=add('div','',get('teacherSentiments'));bar.className='bar';const fill=add('span','',bar);fill.style.width=(n/comments.informativos*100)+'%';fill.style.background=color;}
  get('teacherCsv').disabled=false;get('teacherReport').disabled=false;
 }
 function download(content,type,name){const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 get('teacherCode').onchange=render;get('source').addEventListener('change',render);get('version').addEventListener('change',render);
 get('teacherCsv').onclick=()=>{if(!current)return;const {teacher,version,rows}=current;const table=[['codigo_docente','periodo','fuente','snapshot','version_comentarios','respuestas_cerradas','promedio_descriptivo_visible','comentarios_muestra','informativos','sin_sentimiento','positivos','negativos','neutrales'],...rows.map(([code,r])=>{const c=r.comentarios[version];return [teacher.codigo,teacher.periodo,names[code],data.fecha_snapshot,version,r.cuantitativo.respuestas,pct(r.cuantitativo.porcentaje_descriptivo_raw),c.comentarios,c.informativos,c.sin_sentimiento,c.sentimientos.POSITIVO,c.sentimientos.NEGATIVO,c.sentimientos.NEUTRAL];})];download('\ufeff'+table.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n'),'text/csv;charset=utf-8',teacher.codigo+'_2026_II.csv');};
 get('teacherReport').onclick=()=>{
  if(!current)return;
  const {teacher,version,source,rows,numeric,comments}=current;
  const doc=document.implementation.createHTMLDocument('Informe descriptivo '+teacher.codigo);doc.documentElement.lang='es';
  const meta=doc.createElement('meta');meta.setAttribute('charset','utf-8');doc.head.prepend(meta);
  const viewport=doc.createElement('meta');viewport.name='viewport';viewport.content='width=device-width, initial-scale=1';doc.head.append(viewport);
  add('style','body{font:15px system-ui;color:#183650;margin:32px auto;max-width:1100px;padding:0 20px;line-height:1.6}h1{font-size:27px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #dce5ef;padding:9px;text-align:left}th{background:#edf4fa}.table{overflow:auto}small{color:#586d82}@media print{body{margin:0;max-width:none}table{font-size:11px}tr{break-inside:avoid}}',doc.head,doc);
  const root=doc.body;
  add('h1','Informe descriptivo de evaluación',root,doc);
  add('p',`${teacher.codigo} · Periodo ${teacher.periodo} · Fuente: ${names[source]||'Todas, incluida autoevaluación'}`,root,doc);
  add('p',`Snapshot cuantitativo: ${data.fecha_snapshot} · Versión de comentarios: ${version==='revisado'?'Con revisión de informatividad':'Propuesta automática original'} · Generado: ${new Date().toLocaleString('es-CO')}`,root,doc);
  add('p',`${numeric.respuestas} respuestas cerradas · Promedio descriptivo sin ponderar: ${pct(numeric.porcentaje_descriptivo_raw)} · ${comments.comentarios} comentarios en la muestra · ${comments.informativos} informativos con sentimiento.`,root,doc);
  add('h2','Resultados por fuente',root,doc);
  const wrap=add('div','',root,doc);wrap.className='table';const table=add('table','',wrap,doc),head=add('thead','',table,doc),header=add('tr','',head,doc);
  for(const label of ['Fuente','Respuestas cerradas','Promedio sin ponderar','Comentarios muestra','Sin sentimiento','Positivos','Negativos','Neutrales'])add('th',label,header,doc);
  const body=add('tbody','',table,doc);
  for(const [code,row] of rows){const c=row.comentarios[version],tr=add('tr','',body,doc);for(const v of [names[code],row.cuantitativo.respuestas,pct(row.cuantitativo.porcentaje_descriptivo_raw),c.comentarios,c.sin_sentimiento,c.sentimientos.POSITIVO,c.sentimientos.NEGATIVO,c.sentimientos.NEUTRAL])add('td',v,tr,doc);}
  add('h2','Alcance e interpretación',root,doc);add('p',scope,root,doc);
  add('p','La autoevaluación participa en las respuestas cerradas. La muestra de comentarios sólo incluye estudiantes, jefe inmediato, bilingüismo y capellanía. Los ceros no permiten afirmar ausencia de comentarios en la institución. Los sentimientos no se convierten en calificaciones ni se mezclan con el promedio numérico.',root,doc);
  add('small',`Modelos: ${Object.entries(data.versiones_modelos).map(([k,v])=>k+': '+v).join(' · ')}. No es una evaluación independiente de los modelos ni una decisión sobre incentivos.`,root,doc);
  download('<!doctype html>\n'+doc.documentElement.outerHTML,'text/html;charset=utf-8',teacher.codigo+'_informe_2026_II.html');
 };
 fetch('/api/vinculos',{headers:{'X-Demo-Token':window.DEMO_TOKEN}}).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.error||'No se pudo cargar la vinculación.');data=d;get('teacherCode').replaceChildren();for(const row of data.docentes){const o=add('option',row.codigo,get('teacherCode'));o.value=row.codigo;}get('teacherCoverage').textContent=`Vinculación verificada: ${data.docentes.length} códigos · ${data.docentes_con_comentarios} con comentarios en muestra · ${data.comentarios_vinculados} comentarios · ${data.respuestas_cerradas} respuestas cerradas. Los códigos no son un ranking.`;render();window.dispatchEvent(new CustomEvent('dashboard:links',{detail:data}));}).catch(error=>{get('teacherStatus').textContent=error.message;get('teacherStatus').className='error';get('teacherScope').textContent='La vinculación no está disponible. No se infieren correspondencias ni se simulan resultados.';});
})();
