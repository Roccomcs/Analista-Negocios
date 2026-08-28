import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [input, destination, previewFlag] = process.argv.slice(2);
if (!input || !destination) throw new Error('Uso: workbook.mjs datos.json salida.xlsx [--preview]');
const data = JSON.parse(await fs.readFile(input, 'utf8'));
const wb = Workbook.create();
const ink = '#17191F', amber = '#FFB300';
const safe = value => typeof value === 'string'
  ? (/^[\s]*[=+@-]/.test(value) ? "'" : '') + value.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '')
  : value ?? '';
const col = n => { let s=''; while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26);}return s; };
const contactIndex = new Map();
for (const c of data.contacts) {
  if (!['instagram','whatsapp','email','phone'].includes(c.kind) || !c.value || /^(candidato|histórico)/.test(c.verification)) continue;
  if (!contactIndex.has(c.business_id)) contactIndex.set(c.business_id, []);
  contactIndex.get(c.business_id).push(c);
}
const contacts = (id,kind) => [...new Set((contactIndex.get(id)||[]).filter(c=>c.kind===kind).map(c=>c.value))].join('\n');
const tracking = new Map(data.tracking.map(t=>[t.business_id,t]));
const proposals = new Map(data.proposals.map(p=>[p.business_id,p]));
const sourceIndex = new Map();
for(const s of data.sources){
  if(!sourceIndex.has(s.business_id))sourceIndex.set(s.business_id,[]);
  if(s.url)sourceIndex.get(s.business_id).push(s.url);
}
const sources = id => [...new Set([...(sourceIndex.get(id)||[]),...(contactIndex.get(id)||[]).map(c=>c.source)])].join('\n');
const ready = data.businesses.filter(b=>contactIndex.has(b.id));
const pending = data.businesses.filter(b=>!contactIndex.has(b.id));
const latest = data.runs.find(r=>r.status!=='en curso' && !['completado','interrumpido'].includes(r.status));

function table(name, title, note, headers, rows, widths, editable, idColumn, revisionColumn) {
  const sheet=wb.worksheets.add(name), end=Math.max(5,rows.length+4), last=col(headers.length);
  sheet.showGridLines=false;
  const all=sheet.getRange(`A1:${last}${end}`);
  all.format.font.name='Aptos'; all.format.font.size=11; all.format.font.color=ink;
  all.format.wrapText=true;
  sheet.getRange('A1:F1').merge(); sheet.getRange('A1').values=[[title]];
  sheet.getRange(`A1:${last}1`).format={fill:ink,font:{bold:true,color:'#FFFFFF',size:18},rowHeight:36};
  sheet.getRange('G1').values=[['Total']]; sheet.getRange('H1').formulas=[[`=COUNTA(${idColumn}5:${idColumn}${end})`]];
  sheet.getRange('H1').setNumberFormat('0');
  sheet.getRange('A2:H2').merge(); sheet.getRange('A2').values=[[note]];
  sheet.getRange(`A2:${last}2`).format={rowHeight:40,font:{size:10,color:'#555D6D'},wrapText:true};
  sheet.getRange('A3:H3').merge();
  sheet.getRange('A3').values=[['© OpenStreetMap contributors · https://www.openstreetmap.org/copyright · Datos públicos; corroborar antes de contactar.']];
  sheet.getRange(`A3:${last}3`).format={rowHeight:28,font:{size:10,color:'#555D6D'}};
  sheet.getRange(`A4:${last}4`).values=[headers];
  if(rows.length)sheet.getRange(`A5:${last}${end}`).values=rows.map(row=>row.map((value,i)=>{
    // artifact-tool otherwise parses digit strings and drops leading zeroes / the + prefix.
    if(value && (headers[i]==='Teléfono' || (headers[i]==='WhatsApp' && /^\+?\d+$/.test(value)))) return "'"+value;
    return safe(value);
  }));
  sheet.tables.add(`A4:${last}${end}`,true,`Tabla${name}`).style='TableStyleLight1';
  sheet.getRange(`A4:${last}4`).format={fill:amber,font:{bold:true,color:ink},rowHeight:30,wrapText:true};
  sheet.getRange(`A5:${last}${end}`).format.verticalAlignment='top';
  widths.forEach((width,i)=>sheet.getRange(`${col(i+1)}1:${col(i+1)}${end}`).format.columnWidth=width);
  for(let i=0;i<rows.length;i++){
    const lines=Math.max(...rows[i].map((v,j)=>String(v??'').split('\n').reduce((sum,line)=>sum+Math.max(1,Math.ceil(line.length/Math.max(8,widths[j]-3))),0)));
    sheet.getRange(`A${i+5}:${last}${i+5}`).format.rowHeight=Math.min(180,Math.max(40,lines*14+8));
  }
  sheet.getRange(`${editable[0]}5:${editable[2]}${end}`).format.fill='#FFF3CB';
  sheet.getRange(`${editable[0]}5:${editable[0]}${end}`).dataValidation={rule:{type:'list',values:data.states}};
  sheet.getRange(`${editable[2]}5:${editable[2]}${end}`).dataValidation={rule:{type:'list',values:['No','Sí']}};
  sheet.getRange(`${editable[2]}5:${editable[2]}${end}`).conditionalFormats.add('containsText',{text:'Sí',format:{fill:'#FCE1E1',font:{color:'#9C2020'}}});
  sheet.getRange(`${idColumn}4:${revisionColumn}${end}`).format.font.color='#777E88';
  sheet.getRange(`${revisionColumn}5:${revisionColumn}${end}`).setNumberFormat('0');
  sheet.freezePanes.freezeRows(4); sheet.freezePanes.freezeColumns(2);
  const count=sheet.getRange('H1').values[0][0];
  if(count!==rows.length)throw new Error(`Conteo incorrecto en ${name}: ${count}/${rows.length}`);
  return {sheet,end};
}

const proposalRows=ready.map(b=>{
  const t=tracking.get(b.id);
  return [b.name,b.zone,contacts(b.id,'instagram'),contacts(b.id,'whatsapp'),contacts(b.id,'email'),contacts(b.id,'phone'),
    b.website,b.address,t.state,t.notes,t.do_not_contact?'Sí':'No',
    (proposals.get(b.id)?.qualified_at||b.created_at).slice(0,10),sources(b.id),b.id,t.revision];
});
const main=table('Propuestas','CADMO · Negocios con contacto',
  'Editar solo Estado, Notas y No contactar (amarillo). Lista acumulada; guardar y cerrar Excel antes de buscar. Teléfono no implica WhatsApp.',
  ['Negocio','Barrio','Instagram','WhatsApp','Correo','Teléfono','Web','Dirección','Estado','Notas','No contactar','Encontrado','Fuente','ID','Revisión'],
  proposalRows,[25,20,36,30,34,23,40,32,19,45,16,15,50,39,12],['I','J','K'],'N','O');
main.sheet.getRange(`F5:F${main.end}`).setNumberFormat('@');
main.sheet.getRange(`L5:L${main.end}`).setNumberFormat('yyyy-mm-dd');
if(latest){
  main.sheet.getRange('I2:M3').merge();
  main.sheet.getRange('I2').values=[[`Última búsqueda: ${latest.qualified}/${latest.requested} propuestas NUEVAS · ${latest.zone} · ${latest.status}. El total incluye búsquedas anteriores.`]];
  main.sheet.getRange('I2:M3').format={wrapText:true,font:{size:11,color:'#555D6D'}};
}
const pendingRows=pending.map(b=>{
  const t=tracking.get(b.id);
  return [b.name,b.zone,b.address,b.website,
    'https://www.google.com/search?q='+encodeURIComponent(`site:instagram.com "${b.name}" "${b.zone}"`),
    t.state,t.notes,t.do_not_contact?'Sí':'No',sources(b.id),b.id,t.revision];
});
table('Pendientes','CADMO · Sin contacto encontrado',
  'No cuentan para la meta. Buscar manualmente por nombre y barrio; un dato ausente no significa que el negocio no lo tenga. Editar solo F:H.',
  ['Negocio','Barrio','Dirección','Web','Buscar Instagram','Estado','Notas','No contactar','Fuente','ID','Revisión'],
  pendingRows,[25,20,32,40,65,19,45,16,50,39,12],['F','G','H'],'J','K');

const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',options:{useRegex:true,maxResults:30},summary:'Validación de fórmulas'});
if(errors.ndjson.includes('"kind":"cell"'))throw new Error('Se detectaron errores de fórmula.');
await fs.mkdir(path.dirname(destination),{recursive:true});
if(previewFlag==='--preview'){
  const folder=path.join(path.dirname(destination),'verificacion');await fs.mkdir(folder,{recursive:true});
  for(const [sheetName,ranges] of Object.entries({Propuestas:['A1:H8','I1:O8'],Pendientes:['A1:H8','I1:K8']})){
    for(let i=0;i<ranges.length;i++){
      const blob=await wb.render({sheetName,range:ranges[i],scale:1.1,format:'png'});
      await fs.writeFile(path.join(folder,`${sheetName}-${i}.png`),new Uint8Array(await blob.arrayBuffer()));
    }
  }
  const inspected=await wb.inspect({kind:'table',range:'Propuestas!A4:H8',include:'values,formulas',tableMaxRows:5,tableMaxCols:8});
  await fs.writeFile(path.join(folder,'checks-contactos.json'),JSON.stringify({errors:errors.ndjson,inspected:inspected.ndjson,propuestas:ready.length,pendientes:pending.length},null,2));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);
const temporary=destination+'.pending.xlsx';await xlsx.save(temporary);
try{await fs.rename(temporary,destination);}catch(error){throw new Error('Cerrá el Excel y volvé a exportar. '+error.message);}
console.log(JSON.stringify({file:destination,propuestas:ready.length,pendientes:pending.length}));
