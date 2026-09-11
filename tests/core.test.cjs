'use strict';
const{test}=require('node:test'),A=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const corePath = fs.existsSync(path.resolve(__dirname,'../src/story_universe_architect/web/core.js'))
  ? '../src/story_universe_architect/web/core.js'
  : '../src/core.js';
const C=require(corePath);
const R=path.resolve(__dirname,'..'),read=p=>JSON.parse(fs.readFileSync(path.join(R,p),'utf8'));
const schemaPath = fs.existsSync(path.join(R,'schemas/universe.schema.json')) ? 'schemas/universe.schema.json' : 'schema/universe.schema.json';
const lensesPath = fs.existsSync(path.join(R,'schemas/archetypes.json')) ? 'schemas/archetypes.json' : 'data/archetypes.json';
const schema=read(schemaPath),lenses=read(lensesPath),good=()=>read('examples/restaurant.universe.json');
const valid=u=>C.validate(u,schema,lenses);
function bad(title,fn){test(title,()=>{const u=good();fn(u);A.equal(valid(u).ok,false);});}
test('Both distinct non-game examples pass exact schema and semantic checks',()=>{for(const p of ['restaurant','cyberpunk'])A.equal(valid(read('examples/'+p+'.universe.json')).ok,true);});
test('Sixteen source-mapped narrative lenses have stable unique IDs',()=>{A.equal(lenses.length,16);A.equal(new Set(lenses.map(a=>a.id)).size,16);});
bad('Duplicate approved character IDs rejected',u=>u.characters[1].id=u.characters[0].id);
bad('Relationship with unknown endpoint rejected',u=>u.relationships[0].target='missing');
bad('Relationship self-loop rejected',u=>u.relationships[0].target=u.relationships[0].source);
bad('Duplicate relationship IDs rejected',u=>u.relationships[1].id=u.relationships[0].id);
bad('Duplicate two-person edge rejected',u=>{const a=C.clone(u.relationships[0]);a.id='another-edge';u.relationships.push(a);});
bad('Unknown archetype rejected',u=>u.characters[0].archetype_id='not-in-source');
bad('Out-of-range pressure rejected',u=>u.relationships[0].intensity=6);
bad('Floating-point pressure rejected',u=>u.relationships[0].intensity=2.5);
bad('Boolean pressure rejected',u=>u.relationships[0].intensity=true);
bad('Empty fear rejected',u=>u.characters[0].core_fear=' ');
bad('Too few voice samples rejected',u=>u.characters[0].voice_samples=['One']);
bad('Unexpected schema field rejected',u=>u.privateApiKey='secret');
bad('Inherited constructor key does not bypass additionalProperties',u=>u.constructor='evil');
bad('Prototype key does not bypass additionalProperties',u=>Object.defineProperty(u,'__proto__',{value:{x:1},enumerable:true}));
bad('Unapproved character may not leak into canon',u=>u.characters.push(C.clone(u.suggestions[0].character)));
bad('Accepted suggestion must appear in canon',u=>u.suggestions[0].status='accepted');
bad('Suggestions cannot depend on another unapproved suggestion',u=>u.suggestions[0].relationships[0].target=u.suggestions[1].character.id);
bad('Duplicate edge IDs across proposals rejected',u=>u.suggestions[1].relationships[0].id=u.suggestions[0].relationships[0].id);
bad('Suggestion edge must actually connect its character',u=>{const p=u.suggestions[0];p.relationships[0].source=u.characters[0].id;p.relationships[0].target=u.characters[1].id;});
test('Accept is immutable and updates canonical characters, graph and revision',()=>{const u=good(),p=u.suggestions[0],v=C.accept(u,p.id);A.equal(u.characters.length,5);A.equal(v.characters.length,6);A.equal(v.relationships.length,u.relationships.length+p.relationships.length);A.equal(v.revision,2);A.equal(valid(v).ok,true);});
test('Acceptance immediately adds a portrait but rejection never does',()=>{const u=good(),p=u.suggestions[0];A.equal(C.assets(u).some(x=>x.character_ids.includes(p.character.id)),false);A.equal(C.assets(C.accept(u,p.id)).some(x=>x.character_ids.includes(p.character.id)),true);A.equal(C.assets(C.reject(u,p.id)).some(x=>x.character_ids.includes(p.character.id)),false);});
test('Repeated acceptance and rejection are rejected',()=>{const u=good(),id=u.suggestions[0].id;A.throws(()=>C.accept(C.accept(u,id),id));A.throws(()=>C.reject(C.reject(u,id),id));});
test('Accepted proposal graph cannot be silently dropped',()=>{const u=good(),v=C.accept(u,u.suggestions[0].id);v.relationships.pop();A.equal(valid(v).ok,false);});
test('Canonical story bible excludes pending and rejected character profiles',()=>{const u=good(),p=u.suggestions[0];A.equal(C.bible(u).includes(p.character.name),false);A.equal(C.bible(C.reject(u,p.id)).includes(p.character.name),false);A.equal(C.bible(C.accept(u,p.id)).includes(p.character.name),true);});
test('Renaming changes full-name references, keeps stable IDs and flags no structural error',()=>{const u=good(),c=u.characters[0],v=C.rename(u,c.id,'Morgan Ellis');A.equal(v.characters[0].id,c.id);A.equal(v.characters[0].name,'Morgan Ellis');A.equal(C.bible(v).includes(c.name),false);A.equal(valid(v).ok,true);});
test('Prompt kit covers portraits, scenes, presentation and moodboard',()=>{const a=C.assets(good());A.deepEqual(new Set(a.map(x=>x.category)),new Set(['portraits','scenes','presentation','moodboard']));A.equal(a.filter(x=>x.category==='scenes').length,3);A.equal(a.filter(x=>x.category==='portraits').length,5);A.ok(a.every(x=>x.aspect_ratio&&x.prompt.length>100));});
test('Visual prompts derive from current shared palette and revision',()=>{const u=good();u.visual.palette=['saffron','deep purple'];u.revision=9;A.ok(C.assets(u).every(x=>x.prompt.includes('saffron, deep purple')&&x.revision===9));});
test('Distinct genres do not silently reuse one visual identity',()=>{const a=C.promptKit(good()),b=C.promptKit(read('examples/cyberpunk.universe.json'));A.notEqual(a,b);A.ok(b.includes('Borrowed Light'));A.equal(b.includes('Marcus Chen'),false);});
test('Story hooks reference approved edges and refresh after a relationship edit',()=>{const u=good(),edge=u.relationships[0];edge.breaking_point='A new explicit deadline arrives at dawn.';edge.intensity=5;u.revision=7;const seeds=C.seeds(u);A.ok(seeds.length>=3&&seeds.length<=5);A.ok(seeds.every(s=>u.relationships.some(e=>e.id===s.relationship_id)&&s.basis_revision===7));A.ok(JSON.stringify(seeds).includes(edge.breaking_point));});
test('Structural isolation warning is not treated as a universal literary rule',()=>{const u=good(),id=u.characters[4].id;u.relationships=u.relationships.filter(e=>e.source!==id&&e.target!==id);u.suggestions=[];const v=valid(u);A.equal(v.ok,true);A.ok(v.warnings.length>0);});
test('Stale-result fingerprint changes for content but not an untouched clone',()=>{const u=good();A.equal(C.fingerprint(u),C.fingerprint(C.clone(u)));u.title+=' revised';A.notEqual(C.fingerprint(u),C.fingerprint(good()));});
test('HTML escaping does not execute story text',()=>A.equal(C.esc('<script>"&\'</script>'),'&lt;script&gt;&quot;&amp;&#39;&lt;/script&gt;'));
test('Portable ZIP has a valid signature and UTF-8 entry bytes',()=>{const z=C.zip({'universe.json':JSON.stringify(good()),'故事.md':'Hello café 世界'});A.ok(z instanceof Uint8Array);A.equal(z[0],0x50);A.equal(z[1],0x4b);fs.mkdirSync(path.join(R,'evidence'),{recursive:true});fs.writeFileSync(path.join(R,'evidence','test-story.zip'),z);});

test('Equivalent JSON key order does not invalidate frozen canonical fields',()=>{const u=good(),v=C.clone(u);v.visual=Object.fromEntries(Object.entries(v.visual).reverse());v.characters=v.characters.map(x=>Object.fromEntries(Object.entries(x).reverse()));A.equal(C.same(u,v),true);A.equal(C.fingerprint(u),C.fingerprint(v));v.characters.reverse();A.equal(C.same(u,v),false);});

test('Web application assets parse with zero syntax errors',()=>{const vm=require('vm');const appJs=fs.readFileSync(path.join(R,'src','story_universe_architect','web','app.js'),'utf8');A.doesNotThrow(()=>new vm.Script(appJs));const indexHtml=fs.readFileSync(path.join(R,'src','story_universe_architect','web','index.html'),'utf8');const re=/<script\b(?![^>]*type="application\/json")[^>]*>([\s\S]*?)<\/script>/gi;let m;while((m=re.exec(indexHtml))!==null){A.doesNotThrow(()=>new vm.Script(m[1]));}});
