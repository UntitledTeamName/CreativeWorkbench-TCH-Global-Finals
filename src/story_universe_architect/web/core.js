/* CharacterOS — portable, dependency-free domain layer. */
(function (root, factory) { const api=factory(); if(typeof module==='object'&&module.exports) module.exports=api; else { root.CharacterOS=api; root.SUA=api; } })(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const clone=o=>JSON.parse(JSON.stringify(o));
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const slug=s=>String(s).normalize('NFKD').replace(/[^a-zA-Z0-9]+/g,'-').replace(/^-|-$/g,'').toLowerCase().slice(0,60)||'story-universe';
function shape(value,schema,path='$',errors=[]){
 if('const' in schema&&value!==schema.const) errors.push(`${path}: expected ${JSON.stringify(schema.const)}`);
 if(schema.enum&&!schema.enum.includes(value))errors.push(`${path}: value is not allowed`);
 const type=schema.type;
 if(type==='object'){
  if(!value||typeof value!=='object'||Array.isArray(value)){errors.push(`${path}: expected object`);return errors;}
  for(const k of schema.required||[])if(!Object.hasOwn(value,k))errors.push(`${path}.${k}: required`);
  for(const [k,v]of Object.entries(value)){if(Object.hasOwn(schema.properties||{},k))shape(v,schema.properties[k],`${path}.${k}`,errors);else if(schema.additionalProperties===false)errors.push(`${path}.${k}: unexpected field`);}
 }else if(type==='array'){
  if(!Array.isArray(value)){errors.push(`${path}: expected array`);return errors;}
  if(value.length<(schema.minItems||0)||value.length>(schema.maxItems??Infinity))errors.push(`${path}: array length outside permitted range`);
  value.slice(0,100).forEach((v,i)=>shape(v,schema.items,`${path}[${i}]`,errors));
 }else if(type==='string'){
  if(typeof value!=='string'){errors.push(`${path}: expected text`);return errors;}
  if(value.length<(schema.minLength||0)||value.length>(schema.maxLength??Infinity)||(schema.minLength>0&&!value.trim()))errors.push(`${path}: text length outside permitted range`);
  if(schema.pattern&&!new RegExp(schema.pattern).test(value))errors.push(`${path}: invalid identifier`);
 }else if(type==='integer'){
  if(!Number.isInteger(value)||value<(schema.minimum??-Infinity)||value>(schema.maximum??Infinity))errors.push(`${path}: expected bounded integer`);
 }
 return errors;
}
function validate(u,schema,archetypes){
 const errors=shape(u,schema); if(errors.length)return {ok:false,errors:errors.slice(0,40),warnings:[]};
 const ids=new Set(),edges=new Set(),pairs=new Set(),allSuggestions=new Set(),proposedChars=new Set(),proposedEdges=new Set();
 for(const c of u.characters){if(ids.has(c.id))errors.push(`Duplicate character id: ${c.id}`);ids.add(c.id);if(archetypes&&!archetypes.some(a=>a.id===c.archetype_id))errors.push(`Unknown archetype: ${c.archetype_id}`);}
 function edge(e,allowed){if(!allowed.has(e.source)||!allowed.has(e.target))errors.push(`Relationship ${e.id} has an unknown endpoint`);if(e.source===e.target)errors.push(`Relationship ${e.id} cannot be a self-edge`);}
 for(const e of u.relationships){if(edges.has(e.id))errors.push(`Duplicate relationship id: ${e.id}`);edges.add(e.id);edge(e,ids);const pair=[e.source,e.target].sort().join('|');if(pairs.has(pair))errors.push(`Use one two-perspective relationship per pair: ${pair}`);pairs.add(pair);}
 for(const p of u.suggestions){
  if(allSuggestions.has(p.id))errors.push(`Duplicate suggestion id: ${p.id}`);allSuggestions.add(p.id);
  if(proposedChars.has(p.character.id))errors.push(`Two suggestions share a character id: ${p.character.id}`);proposedChars.add(p.character.id);
  if(p.status!=='accepted'&&ids.has(p.character.id))errors.push(`Unaccepted suggestion already appears in canon: ${p.id}`);
  if(p.status==='accepted'&&!ids.has(p.character.id))errors.push(`Accepted suggestion missing from canon: ${p.id}`);
  if(archetypes&&!archetypes.some(a=>a.id===p.character.archetype_id))errors.push(`Unknown suggested archetype: ${p.character.archetype_id}`);
  const allowed=new Set([...ids,p.character.id]),local=new Set();
  for(const e of p.relationships){edge(e,allowed);if(e.source!==p.character.id&&e.target!==p.character.id)errors.push(`Suggested edge ${e.id} must connect its new character`);if(local.has(e.id)||proposedEdges.has(e.id))errors.push(`Duplicate proposed edge ${e.id}`);local.add(e.id);proposedEdges.add(e.id);if(p.status!=='accepted'&&edges.has(e.id))errors.push(`Proposed edge id already used: ${e.id}`);if(p.status==='accepted'&&!u.relationships.some(r=>r.id===e.id&&r.source===e.source&&r.target===e.target))errors.push(`Accepted relationship missing or changed endpoints: ${e.id}`);}
 }
 const warnings=[];
 if(u.relationships.length){for(const c of u.characters)if(!u.relationships.some(e=>e.source===c.id||e.target===c.id))warnings.push(`${c.name} has no approved connection. This may be intentional.`);}
 const names=u.characters.map(c=>c.name.toLowerCase());if(new Set(names).size!==names.length)warnings.push('Some characters share a name; IDs remain distinct.');
 return {ok:!errors.length,errors,warnings};
}
function accept(u,id){const v=clone(u),p=v.suggestions.find(s=>s.id===id);if(!p||p.status!=='pending')throw Error('This proposal is not pending.');if(v.characters.length>=10)throw Error('This prototype supports up to ten approved characters.');if(v.characters.some(c=>c.id===p.character.id))throw Error('Character already exists.');v.characters.push(clone(p.character));v.relationships.push(...clone(p.relationships));p.status='accepted';v.revision++;return v;}
function reject(u,id){const v=clone(u),p=v.suggestions.find(s=>s.id===id);if(!p||p.status!=='pending')throw Error('This proposal is not pending.');p.status='rejected';v.revision++;return v;}
function rename(u,id,name){if(!name.trim())throw Error('A name is required.');const v=clone(u),c=v.characters.find(c=>c.id===id);if(!c)throw Error('Character not found.');const old=c.name;function walk(o){if(typeof o==='string')return o.split(old).join(name.trim());if(Array.isArray(o))return o.map(walk);if(o&&typeof o==='object')return Object.fromEntries(Object.entries(o).map(([k,val])=>[k,k==='id'||k==='source'||k==='target'||k==='archetype_id'?val:walk(val)]));return o;}const updated=walk(v);updated.revision++;return updated;}
function stable(value){if(Array.isArray(value))return value.map(stable);if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(k=>[k,stable(value[k])]));return value;}
function same(a,b){return JSON.stringify(stable(a))===JSON.stringify(stable(b));}
function fingerprint(u){ // Detect accidental stale writes, not a cryptographic security primitive.
 const s=JSON.stringify(stable(u));let hash=2166136261;for(let i=0;i<s.length;i++)hash=Math.imul(hash^s.charCodeAt(i),16777619);return (hash>>>0).toString(16).padStart(8,'0');
}
function names(u,id){return u.characters.find(c=>c.id===id)?.name||id;}
function assets(u){
 const v=u.visual,style=`Visual direction: ${v.style}. Palette: ${v.palette.join(', ')}. Lighting: ${v.lighting}. Texture: ${v.texture}. Composition: ${v.composition}. Story tone: ${u.tone}.`;
 const out=[];const add=(id,category,title,prompt,ratio,refs=[])=>out.push({id,category,title,prompt:prompt+'\n\n'+style+'\n\nNo watermarks or generated lettering. Leave intentional text areas blank for later typesetting.',aspect_ratio:ratio,character_ids:refs,revision:u.revision});
 for(const c of u.characters)add('portrait-'+c.id,'portraits',c.name+' · portrait',`Create a character portrait for ${u.format}: “${u.title}”. ${c.appearance}\nNarrative role: ${c.role}. Emotional baseline: ${c.emotional_baseline}. Show a person who wants ${c.core_desire} while fearing ${c.core_fear}\nPose and expression should suggest this contradiction without literal symbolism or diagnostic stereotypes. Bust or half-body; readable silhouette; environment belongs to ${u.setting}.`,'3:4',[c.id]);
 add('scene-establishing','scenes','The world before the conflict',`Establishing environment for “${u.title}”: ${u.setting}\nShow traces of human use and one unoccupied space that suggests an absent person. Emotional function: establish what could be lost. No identifiable real brands.`,'16:9');
 const ranked=[...u.relationships].sort((a,b)=>b.intensity-a.intensity||a.id.localeCompare(b.id));
 for(const [i,e]of ranked.slice(0,2).entries())add('scene-'+e.id,'scenes',i?'After the encounter':'The pressure point',`A narrative environment or two-person scene involving ${names(u,e.source)} and ${names(u,e.target)}. Context: ${u.setting}\nRelationship: ${e.label}. Shared history: ${e.shared_history}\nPossible scene: ${e.breaking_point}\nUse blocking, distance and light to express: ${e.tension}\nEmotional purpose: ${e.story_potential}\nCharacter identity notes: ${u.characters.filter(c=>[e.source,e.target].includes(c.id)).map(c=>c.name+': '+c.appearance).join(' | ')}.`,'16:9',[e.source,e.target]);
 add('ui-card','presentation','Character-card frame',`An empty character-card frame for a ${u.genre} story bible, themed by ${u.setting}. Keep the central portrait area clear, with a quiet lower nameplate area and subtle edge texture. Use the shared palette; restrained and readable. No actual lettering. Do not reproduce a finished game UI.`,'3:4');
 add('ui-divider','presentation','Chapter & pitch divider',`A wide editorial divider/background for “${u.title}”. Abstract environmental traces from ${u.setting}; generous calm negative space on the left for separately added type. Emotional function: anticipation before a shift in relationships. Avoid embedded words or portrait faces.`,'16:9');
 add('ui-controls','presentation','Buttons & navigation motifs',`A coordinated presentation-component sheet: three blank button surfaces, a subtle rule, and four simple abstract navigation motifs for ${u.genre}. Material language from ${v.texture}; high-contrast text-safe centers. No letters or baked-in labels. Intended as visual reference, not accessible working controls.`,'4:3');
 add('moodboard','moodboard','Universe mood board',`A coherent two-by-two reference collage for “${u.title}”. Panel 1: a close detail of hands working in ${u.setting}. Panel 2: the environment after people leave. Panel 3: an ordinary object carrying a shared history. Panel 4: two people separated by a small but meaningful distance.\nUnifying theme: ${u.thematic_thesis}\nEach panel must feel part of the same world, with different scale and focal interest. No labels or typography.`,'1:1');
 return out;
}
function seeds(u){return [...u.relationships].sort((a,b)=>b.intensity-a.intensity||a.id.localeCompare(b.id)).slice(0,5).map((e,i)=>({id:'seed-'+e.id,title:['A debt changes shape','A public choice','The cost of telling','An offer with a boundary','The account that differs'][i],relationship_id:e.id,characters:[e.source,e.target],trigger:e.breaking_point,hook:`${names(u,e.source)} and ${names(u,e.target)} are connected by ${e.label.toLowerCase()}. ${e.tension} ${e.story_potential}`,question:`What does ${names(u,e.source)} risk by pursuing ${e.source_wants} when ${names(u,e.target)} wants ${e.target_wants}?`,basis_revision:u.revision}));}
function gaps(u){const out=[];for(const c of u.characters){const links=u.relationships.filter(e=>e.source===c.id||e.target===c.id);if(!links.length)out.push({title:`${c.name} is structurally isolated`,detail:'No approved edge connects this character. Isolation may be deliberate; a relationship could reveal another side.',id:c.id});}
 const groups={};for(const c of u.characters)(groups[c.archetype_id]??=[]).push(c.name);for(const n of Object.values(groups))if(n.length>1)out.push({title:'Shared communication lens',detail:`${n.join(' and ')} share a lens. Check whether their voice, fear and desire make them distinct. This is not automatically a flaw.`});
 if(u.relationships.length&&!u.relationships.some(e=>e.intensity>=4))out.push({title:'Pressure is currently restrained',detail:'No relationship is marked high pressure. A quiet story can work; choose intensity intentionally rather than adding an antagonist by default.'});
 return out;
}
function castAnalysis(u){
 const chars=u.characters||[],rels=u.relationships||[];
 const deg={};chars.forEach(c=>deg[c.id]=0);
 rels.forEach(r=>{deg[r.source]=(deg[r.source]||0)+1;deg[r.target]=(deg[r.target]||0)+1;});
 let linchpinId=chars[0]?.id,maxD=-1;
 Object.entries(deg).forEach(([id,d])=>{if(d>maxD){maxD=d;linchpinId=id;}});
 const linchpin=chars.find(c=>c.id===linchpinId);
 const powderKeg=[...rels].sort((a,b)=>b.intensity-a.intensity||b.breaking_point?.length-a.breaking_point?.length)[0]||null;
 const sortedDeg=Object.entries(deg).sort((a,b)=>a[1]-b[1]);
 const outsiderId=sortedDeg[0]?.[0];
 const outsider=chars.find(c=>c.id===outsiderId);
 const highPressureCount=rels.filter(r=>r.intensity>=4).length;
 const totalTensionScore=rels.reduce((acc,r)=>acc+(r.intensity||3),0);
 const avgPressure=rels.length?Math.round((totalTensionScore/rels.length)*10)/10:0;
 return {
  linchpin:{character:linchpin,connections:maxD,summary:linchpin?`${linchpin.name} anchors the social web with ${maxD} key connection(s). Severing them fractures the cast into isolated sub-plots.`:'None'},
  powderKeg:{relationship:powderKeg,intensity:powderKeg?.intensity||0,summary:powderKeg?`The highest dynamic pressure (${powderKeg.intensity}/5) between ${names(u,powderKeg.source)} & ${names(u,powderKeg.target)}: “${powderKeg.breaking_point}”`:'No relationships mapped yet.'},
  outsider:{character:outsider,connections:sortedDeg[0]?.[1]||0,summary:outsider?`${outsider.name} holds only ${sortedDeg[0]?.[1]||0} direct connection(s), making them the natural wildcard or unaligned witness.`:'None'},
  metrics:{castSize:chars.length,relationshipCount:rels.length,highPressureCount,avgPressure,thematicThesis:u.thematic_thesis||''}
 };
}
function archetypeConstellation(u){
 const chars=u.characters||[];
 return chars.map((c,i)=>{
  const text=(c.emotional_baseline+' '+c.core_desire+' '+c.core_fear+' '+c.role+' '+c.archetype_label).toLowerCase();
  let x=50,y=50;
  if(/duty|honor|order|protect|law|loyal|mentor|service|truth|calm|exacting/i.test(text))x+=26;
  if(/rebel|chaos|free|rogue|wild|deflect|charm|gambit|instinct|ambitious|break/i.test(text))x-=26;
  if(/selfless|guide|nurture|sacrifice|protect|community|empathy|mediator/i.test(text))y-=26;
  if(/power|ambition|control|survival|fear|distrust|secret|isolated|guarded/i.test(text))y+=26;
  const jitter=((i*17)%15)-7;
  x=Math.max(12,Math.min(88,x+jitter));
  y=Math.max(12,Math.min(88,y+((i*23)%15)-7));
  let quadrant='Uncertain';
  if(x>=50&&y<50)quadrant='Disciplined Altruist';
  else if(x<50&&y<50)quadrant='Maverick Protector';
  else if(x<50&&y>=50)quadrant='Chaotic Individualist';
  else quadrant='Authoritarian Pragmatist';
  return {id:c.id,name:c.name,role:c.role,archetype:c.archetype_label,x,y,quadrant,fear:c.core_fear,desire:c.core_desire};
 });
}
function storyChronology(u){
 const rels=[...u.relationships].sort((a,b)=>b.intensity-a.intensity||a.id.localeCompare(b.id));
 const phases=[
  {act:'Act I · The Fragile Normal',subtitle:'Inciting Disturbance & Latent Friction',color:'var(--accent-2)'},
  {act:'Act II · Rising Compulsion',subtitle:'Collision of Wants & Irrevocable Moves',color:'var(--accent)'},
  {act:'Act III · The Breaking Fracture',subtitle:'Critical Confrontation & Crucible Moment',color:'var(--warn)'},
  {act:'Resolution · The Reshaped Web',subtitle:'The Aftermath & Re-anchored Reality',color:'var(--ok)'}
 ];
 const events=[];
 rels.forEach((r,idx)=>{
  const a=names(u,r.source),b=names(u,r.target);
  if(idx===0){
   events.push({phaseIndex:0,title:`The Latent Schism between ${a} & ${b}`,tag:'Catalyst',summary:r.shared_history,tension:r.tension,characters:[r.source,r.target],intensity:r.intensity});
   events.push({phaseIndex:2,title:`The Crucible: Breaking Point Erupts`,tag:'Climax Event',summary:r.breaking_point,tension:r.tension,characters:[r.source,r.target],intensity:r.intensity});
  }else if(idx===1){
   events.push({phaseIndex:1,title:`${a} Presses Against ${b}`,tag:'Escalation',summary:`${a} pursues “${r.source_wants}” while ${b} demands “${r.target_wants}”.`,tension:r.tension,characters:[r.source,r.target],intensity:r.intensity});
  }else if(idx===2){
   events.push({phaseIndex:1,title:`Divided Loyalties: ${r.label}`,tag:'Complication',summary:`${r.tension} Dramatic potential unfolds: ${r.story_potential}`,tension:r.tension,characters:[r.source,r.target],intensity:r.intensity});
  }else{
   events.push({phaseIndex:3,title:`Repercussions of ${r.label}`,tag:'Fallout',summary:`How the bond between ${a} and ${b} stands reshaped after the crisis.`,tension:r.story_potential,characters:[r.source,r.target],intensity:r.intensity});
  }
 });
 if(!events.length){
  events.push({phaseIndex:0,title:'Establishing the World',tag:'Premise',summary:u.concept,tension:u.thematic_thesis,characters:u.characters.map(c=>c.id).slice(0,2),intensity:3});
 }
 events.sort((e1,e2)=>e1.phaseIndex-e2.phaseIndex);
 return phases.map((p,i)=>({
  ...p,
  events:events.filter(ev=>ev.phaseIndex===i)
 }));
}
function bible(u){const line=s=>String(s).replace(/\r/g,'');return [`# ${line(u.title)}`,`*${u.format} · ${u.genre}*`,`\n## Premise\n${u.concept}`,`\n## Thematic core\n${u.thematic_thesis}`,`\n## Setting and tone\n${u.setting}\n\n${u.tone}`,`\n## Approved cast`,...u.characters.map(c=>`\n### ${c.name}\n**${c.role} — ${c.archetype_label}**\n\n${c.backstory}\n\nCommunication: ${c.communication_style}\n\nEmotional baseline: ${c.emotional_baseline}\n\nDesire: ${c.core_desire}\n\nFear: ${c.core_fear}\n\nTendencies:\n${c.tendencies.map(x=>'- '+x).join('\n')}\n\nVoice samples:\n${c.voice_samples.map(x=>'> '+x).join('\n>\n')}\n\nAppearance: ${c.appearance}`),`\n## Relationship map`,...u.relationships.map(e=>`\n### ${names(u,e.source)} → ${names(u,e.target)}: ${e.label}\n\nShared event: ${e.shared_history}\n\n${names(u,e.source)} wants: ${e.source_wants}\n\n${names(u,e.target)} wants: ${e.target_wants}\n\nTheir interpretations:\n- ${names(u,e.source)}: ${e.source_read}\n- ${names(u,e.target)}: ${e.target_read}\n\nTension: ${e.tension}\n\nBreaking point: ${e.breaking_point}\n\nStory potential: ${e.story_potential}`),`\n## Relationship-derived story seeds`,...seeds(u).map(s=>`\n### ${s.title}\n${s.trigger}\n\n${s.hook}\n\n${s.question}\n\nSource relationship: ${s.relationship_id}`),`\n## Visual direction\n${JSON.stringify(u.visual,null,2)}`,`\n## Provenance and limits\nRevision ${u.revision}; source mode: ${u.provenance.mode}. ${u.provenance.source}\n\nStory seeds and visual prompts are compiled from the approved record, not a separate live model call. No images are generated by this application. Unaccepted proposals are excluded from this bible. Structural checks are not an assessment of literary quality.`].join('\n');}
function promptKit(u,category='all'){return `# ${u.title} — visual asset prompt kit\n\nExport-only. No images generated. Revision ${u.revision}. Suggested aspect ratios are metadata, not model-specific API parameters.\n\n`+assets(u).filter(a=>category==='all'||a.category===category).map(a=>`## ${a.title}\nCategory: ${a.category} · Suggested aspect ratio: ${a.aspect_ratio}\n\n${a.prompt}\n`).join('\n');}
// Standards-compliant stored ZIP with UTF-8 names. Small portable artifacts need no runtime dependency.
const crcTable=Array.from({length:256},(_,n)=>{for(let k=0;k<8;k++)n=(n&1)?0xedb88320^(n>>>1):n>>>1;return n>>>0;});
function zip(files){const enc=new TextEncoder(),parts=[],central=[];let offset=0;
 const header=(n)=>{const a=new Uint8Array(n);return[a,new DataView(a.buffer)];};
 for(const [name,value]of Object.entries(files)){const nb=enc.encode(name),data=typeof value==='string'?enc.encode(value):value;let crc=0xffffffff;for(const b of data)crc=crcTable[(crc^b)&255]^(crc>>>8);crc=(crc^0xffffffff)>>>0;
 const[h,d]=header(30);d.setUint32(0,0x04034b50,true);d.setUint16(4,20,true);d.setUint16(6,0x800,true);d.setUint16(12,33,true);d.setUint32(14,crc,true);d.setUint32(18,data.length,true);d.setUint32(22,data.length,true);d.setUint16(26,nb.length,true);parts.push(h,nb,data);
 const[c,v]=header(46);v.setUint32(0,0x02014b50,true);v.setUint16(4,20,true);v.setUint16(6,20,true);v.setUint16(8,0x800,true);v.setUint16(14,33,true);v.setUint32(16,crc,true);v.setUint32(20,data.length,true);v.setUint32(24,data.length,true);v.setUint16(28,nb.length,true);v.setUint32(42,offset,true);central.push(c,nb);offset+=h.length+nb.length+data.length;}
 const size=central.reduce((n,a)=>n+a.length,0),[end,v]=header(22);v.setUint32(0,0x06054b50,true);v.setUint16(8,Object.keys(files).length,true);v.setUint16(10,Object.keys(files).length,true);v.setUint32(12,size,true);v.setUint32(16,offset,true);
 const all=[...parts,...central,end],buf=new Uint8Array(all.reduce((n,a)=>n+a.length,0));let p=0;for(const a of all){buf.set(a,p);p+=a.length;}return buf;
}
return {clone,esc,slug,shape,validate,accept,reject,rename,same,fingerprint,names,assets,seeds,gaps,castAnalysis,archetypeConstellation,storyChronology,bible,promptKit,zip};
});
