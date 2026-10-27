// Pass 2: manual cleanup rules, using the app's own parser/resolver loaded from ../index.html
// usage: node tools/cleanup.js stage1.json liftlog-import.json [ohp_barbell_from YYYY-MM-DD]
const fs=require("fs"),path=require("path"),vm=require("vm");
const html=fs.readFileSync(path.join(__dirname,"..","index.html"),"utf8");
const js=html.match(/<script>([\s\S]*)<\/script>/)[1];
const core=js.split("/* ===================== rendering helpers")[0];
const ek=js.slice(js.indexOf("const entryKey"),js.indexOf("\nfunction renderLog"));
const ctx={console,localStorage:{getItem:()=>null,setItem:()=>{}},esc:s=>s};vm.createContext(ctx);
vm.runInContext(core+ek+"\nthis.A={facts,parseToken,dropEntries,setDb:d=>{db=d}};",ctx);
const A=ctx.A;

const [inp,out,ohpFrom]=process.argv.slice(2);
const J=JSON.parse(fs.readFileSync(inp,"utf8")),db={workouts:J.workouts,aliases:{}};A.setDb(db);
const log={},n=k=>log[k]=(log[k]||0)+1,has=(e,m)=>(e.mods||[]).includes(m),rest=(e,drop)=>(e.mods||[]).filter(m=>!drop.includes(m));
function rename(w,e,name){const L=w.raw.split("\n"),i=e.lines[0],t=L[i].trim().split(/\s+/),j=t.findIndex(A.parseToken);L[i]=j>0?[name,...t.slice(j)].join(" "):name;w.raw=L.join("\n")}
function negate(w,e){const L=w.raw.split("\n");e.lines.forEach(i=>{L[i]=L[i].split(/\s+/).map(t=>A.parseToken(t)?t.replace(/(\d+x)(\d+(?:\.\d+)?)(?=\+|$)/g,(m,a,b)=>+b>0?a+"-"+b:m):t).join(" ")});w.raw=L.join("\n")}

A.facts();
for(const w of db.workouts)A.dropEntries(w,e=>{
  if(!e.ex){n("deleted unmapped");return true}
  if((e.ex==="dips"||e.ex==="pullup")&&has(e,"New machine")){n("deleted new-machine dips/pull-ups");return true}
  return false});
A.facts();
for(const w of db.workouts)[...w._entries].reverse().forEach(e=>{   // bottom-up keeps line indexes valid
  if(e.ex==="pullup"&&has(e,"Band")){negate(w,e);rename(w,e,["Έλξεις",...rest(e,["Band"])].join(" "));n("band pull-ups → assisted")}
  else if(e.ex==="row"&&has(e,"New machine")){rename(w,e,["Κωπηλατικό",...rest(e,["New machine","Good machine"]),"Good machine"].join(" "));n("row new machine → good machine")}
  else if(ohpFrom&&e.ex==="ohp"&&w.date>=ohpFrom){rename(w,e,"OHP Barbell");n("OHP from "+ohpFrom+" → barbell")}
});
db.workouts.forEach(w=>delete w._entries);
fs.writeFileSync(out,JSON.stringify({app:"liftlog",version:1,workouts:db.workouts,weights:J.weights||[]},null,1));
console.log(log);
