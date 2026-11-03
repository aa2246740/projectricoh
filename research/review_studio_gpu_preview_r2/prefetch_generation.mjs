import {pathToFileURL} from 'node:url';
const [folder,scenario]=process.argv.slice(2);
const calls={api:[],fetch:[],engine:[]};
globalThis.engineLog=calls.engine;
Object.defineProperty(globalThis,'navigator',{value:{gpu:{}},configurable:true});
globalThis.createImageBitmap=async()=>({width:120,height:80,close(){}});
const REC={kind:'builtin',unit:'jlaunch',slot:2,levels:{}};
const info=id=>({enabled:true,raw:{url:`/api/photos/${id}/raw?v=1`,layer:[100,80],full:[200,160]},raw_reason:null,jpg:{url:`/api/photos/${id}/camera-jpg?v=1`},scene:{A:[[1,0,0],[0,1,0],[0,0,1]],b:[0,0,0]}});
globalThis.apiStub=async url=>{calls.api.push(url);const m=url.match(/^\/api\/photos\/([^/]+)\/(gpu|edit)$/);if(!m)throw new Error(url);return m[2]==='gpu'?info(m[1]):{recipe:REC};};
let releaseOld,oldStarted=false;
const old=new Promise(resolve=>{releaseOld=resolve;});
const body=key=>({ok:true,status:200,headers:{get:k=>k==='X-GXR-Bake'?encodeURIComponent(JSON.stringify({key,nx:2,ny:2,origin:[0,0],step:1})):null},arrayBuffer:async()=>new ArrayBuffer(16),blob:async()=>({})});
globalThis.fetch=async url=>{
 calls.fetch.push(url);
 if(url.includes('/bake')){if(url.includes('dv=v1')){oldStarted=true;return old;}return body('K2');}
 return body('source');
};
const {state,emit}=await import(pathToFileURL(folder+'/state.js'));
const gs=await import(pathToFileURL(folder+'/gpu_stage.js'));
state.settings={gpu_preview:true};state.camdata={dataVersion:'v1'};
state.photos=[{id:'P',sidecar_rev:0},{id:'N',sidecar_rev:1}];
const view=id=>({photo:{id,name:id},ed:{v2:true,lut:null,geometry:{},frame:{style:'none'},stamp:{enabled:false}}});
const ctx=recipe=>({stage:'final',recipe,adjust:{},curve:null,geometry:{},crop:null,geometryKey:'p'});
const turn=()=>new Promise(setImmediate);
async function settle(v,c){let way;for(let i=0;i<30;i++){way=gs.route(v,c,()=>{});await turn();if(way!=='wait')return way;}return way;}
const p=view('P');
const before=await settle(p,ctx(null));await turn();await turn();
if(!oldStarted)throw new Error('Old neighbour prefetch did not actually start');
state.camdata={dataVersion:'v2'};emit('camdata-changed');
const current=await settle(p,ctx(null));await turn();await turn();
releaseOld(scenario==='late-success'?body('K1'):{ok:false,status:503});
await turn();await turn();
const n=view('N');const final=await settle(n,ctx(REC));
const added=calls.engine.filter(c=>c[0]==='addBake').map(c=>c[1]);
const look=[...calls.engine].reverse().find(c=>c[0]==='setLook')?.[1];
const out={scenario,before,current,oldStarted,final,added,look,bakeUrls:calls.fetch.filter(u=>u.includes('/bake')),scope:'Actual gpu_stage.js/state.js; deterministic transport and GPU test double; no physical GPU claim'};
out.pass=before==='gpu'&&current==='gpu'&&final==='gpu'&&JSON.stringify(added)==='["K2"]'&&look.recipe==='K2';
console.log(JSON.stringify(out));if(!out.pass)process.exitCode=1;
