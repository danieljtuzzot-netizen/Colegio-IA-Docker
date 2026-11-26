'use strict';
(()=>{
 const get=id=>document.getElementById(id);
 const add=(tag,text,parent)=>{const n=document.createElement(tag);n.textContent=text;parent.append(n);return n;};
 const sourceNames={ESTUDIANTES:'Estudiantes',JEFE:'Jefe inmediato',LENGUAS:'Bilingüismo',CAPELLANIA:'Capellanía'};
 let data;
 function render(){
  if(!data)return;
  const source=get('source').value, category=get('themeCategory').value;
  const rows=data.evidencias.filter(r=>(!source||r.fuente===source)&&(!category||r.categoria===category));
  get('themeScope').textContent=data.alcance;
  get('themeCount').textContent=`Selección del piloto: ${new Set(rows.map(r=>r.comentario_id)).size} comentarios distintos · ${rows.length} segmentos. Categorías y citas revisadas; temas aplicados por autorización. Esta sección es independiente de la versión original/revisada del lote de sentimiento.`;
  const groups=new Map();
  for(const row of rows){const key=JSON.stringify([row.fuente,row.categoria,row.tema]);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);}
  const target=get('themeGroups');target.replaceChildren();
  if(!rows.length)add('p','No hay evidencia en el piloto para esta selección.',target);
  for(const entries of groups.values()){
   const first=entries[0], section=add('section','',target);section.className='panel';
   const title=(first.tema||'Sin asignación temática').replaceAll('_',' ');
   add('h3',`${sourceNames[first.fuente]} · ${first.categoria} · ${title}`,section);
   add('p',`${new Set(entries.map(r=>r.comentario_id)).size} comentarios distintos · ${entries.length} segmentos`,section).className='muted';
   for(const entry of entries){const quote=add('blockquote',entry.cita,section);quote.style.whiteSpace='pre-wrap';quote.style.overflowWrap='anywhere';add('small',`Referencia: ${entry.segmento_id}`,section).className='muted';}
  }
  get('themeTrace').textContent=`Periodo ${data.periodo} · Lote ${data.lote} · Citas literales conservadas · Sin calificaciones ni inferencias nuevas`;
 }
 get('source').addEventListener('change',render);get('themeCategory').addEventListener('change',render);
 fetch('/api/temas',{headers:{'X-Demo-Token':window.DEMO_TOKEN}}).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.error||'No se pudo cargar la síntesis.');data=d;render();}).catch(e=>{get('themeCount').textContent=e.message;get('themeCount').className='error';get('themeScope').textContent='Síntesis no disponible. No se muestran citas sin verificar.';});
})();
