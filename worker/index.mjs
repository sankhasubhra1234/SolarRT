import constants from "./constants.json" with {type:"json"};
import {grid,regions,location,kpSummary,orbit,distance,weather} from "./science.mjs";
const noaa="https://services.swpc.noaa.gov";
const cloudRoot="https://view.eumetsat.int/geoserver";
const shared=new Map();
class HttpError extends Error {constructor(status,message){super(message);this.status=status;}}
function json(value,status=200){return Response.json(value,{status,headers:{...constants.headers,"Cache-Control":"no-store"}});}
async function source(url,ttl,format="json",timeout=15000){
  const res=await fetch(url,{signal:AbortSignal.timeout(timeout),headers:{"User-Agent":"SolarRT/2 (+https://github.com/sankhasubhra1234/SolarRT)"},cf:{cacheEverything:true,cacheTtlByStatus:{"200-299":ttl,"400-599":0}}});
  if(!res.ok)throw Error("Upstream failed");
  return format==="text"?res.text():res.json();
}
async function cached(key,ttl,load,maxStale=21600){
  const prev=shared.get(key),age=prev?(Date.now()-prev.time)/1000:Infinity;
  if(age<ttl)return {data:prev.data,age_seconds:age,stale:false};
  try{
    const data=await load();
    shared.set(key,{time:Date.now(),data});
    return {data,age_seconds:0,stale:false};
  }catch(error){
    if(age<=maxStale)return {data:prev.data,age_seconds:age,stale:true};
    throw error;
  }
}
const aurora=()=>cached("aurora",300,async()=>grid(await source(noaa+"/json/ovation_aurora_latest.json",300)));
const kp=()=>cached("kp",60,async()=>{
  const parts=await Promise.all(["/json/planetary_k_index_1m.json","/products/noaa-planetary-k-index.json","/products/noaa-planetary-k-index-forecast.json"].map((path,i)=>source(noaa+path,i?600:60).catch(()=>[])));
  return kpSummary(...parts);
});
function coordinates(params){
  return ["lat","lon"].map((k,i)=>{
    const s=params.get(k),n=Number(s);
    if(!s?.trim()||!Number.isFinite(n)||Math.abs(n)>[90,180][i])throw new HttpError(422,"Invalid coordinates");
    return n;
  });
}
function unpack(result){return {...result.data,stale:result.stale,age_seconds:result.age_seconds};}
const health={status:"ok",app:"SolarRT",version:"2.0.0",edition:"web"};
const usageEvents = new Set(["arrival","view","locate","pick_map","theme","about","test_alert","center_iss","iss","clouds","search"]);
export class SolarStore{
  constructor(ctx){this.ctx=ctx;}
  async fetch(req){
    const store=this.ctx.storage,path=new URL(req.url).pathname;
    if(path.startsWith("/count/")){
      const event=path.slice(7);
      if(req.method!=="POST" || !usageEvents.has(event))return json({detail:"Unknown event"},400);
      const sql=store.sql;
      if(!this.usageReady){
        sql.exec("CREATE TABLE IF NOT EXISTS daily_events(day TEXT, event TEXT, total INTEGER NOT NULL, PRIMARY KEY(day,event))");
        sql.exec(`CREATE VIEW IF NOT EXISTS daily_traffic AS SELECT day,
          SUM(CASE WHEN event='arrival' THEN total ELSE 0 END) AS visits,
          SUM(CASE WHEN event IN ('arrival','view') THEN total ELSE 0 END) AS page_views,
          SUM(CASE WHEN event NOT IN ('arrival','view','search') THEN total ELSE 0 END) AS feature_clicks,
          SUM(CASE WHEN event='search' THEN total ELSE 0 END) AS searches
          FROM daily_events GROUP BY day ORDER BY day DESC`);
        this.usageReady=true;
      }
      sql.exec("INSERT INTO daily_events VALUES(date('now'), ?, 1) ON CONFLICT(day,event) DO UPDATE SET total=total+1",event);
      return new Response(null,{status:204});
    }
    if(path==="/geo"){
      const now=Date.now();
      const allowed=await store.transaction(async tx=>{
        if(now-(await tx.get("geoLast")??0)<1000)return false;
        await tx.put("geoLast",now);return true;
      });
      return json({allowed});
    }
    if(req.method==="GET"){
      const rows=Array.from((await store.list({prefix:"fb:",reverse:true,limit:500})).values());
      const by_rating=Object.fromEntries([1,2,3,4,5].map(n=>[n,rows.filter(r=>r.rating===n).length]));
      return json({entries:rows,count:rows.length,by_rating,average:rows.length?rows.reduce((s,r)=>s+r.rating,0)/rows.length:null});
    }
    const entry=await req.json();
    const stored=await store.transaction(async tx=>{
      const total=await tx.get("bytes")??0,size=new TextEncoder().encode(JSON.stringify(entry)).length;
      if(total+size>20*1024*1024)return false;
      await tx.put("fb:"+entry.time+":"+entry.id,entry);
      await tx.put("bytes",total+size);return true;
    });
    return stored?json({ok:true,id:entry.id,forwarded:false},201):json({detail:"Feedback storage full"},503);
  }
}
async function feedback(req,env,ip,store){
  if(req.method==="GET"){
    const enc=new TextEncoder(),digest=s=>crypto.subtle.digest("SHA-256",enc.encode(s));
    if(!env.ADMIN_TOKEN||!crypto.subtle.timingSafeEqual(await digest(req.headers.get("Authorization")??""),await digest("Bearer "+env.ADMIN_TOKEN)))throw new HttpError(403,"Admin token required");
    return store.fetch("https://internal/feedback");
  }
  if(!(await env.POST_LIMIT.limit({key:ip})).success)throw new HttpError(429,"Too many submissions");
  const reader=req.body?.getReader(),decoder=new TextDecoder();
  if(!reader)throw new HttpError(422,"Missing feedback");
  let size=0,body="";
  for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>8192){await reader.cancel();throw new HttpError(413,"Request too large");}body+=decoder.decode(value,{stream:true});}
  let entry;try{entry=JSON.parse(body+decoder.decode());}catch{throw new HttpError(422,"Invalid feedback");}
  if(!Number.isInteger(entry?.rating)||entry.rating<1||entry.rating>5)throw new HttpError(422,"Invalid rating");
  const clean={rating:entry.rating,id:crypto.randomUUID(),time:new Date().toISOString(),rating_label:["","Terrible","Bad","Okay","Good","Love it"][entry.rating]};
  for(const [k,max] of Object.entries({comment:2000,contact:200,edition:20,version:20})){
    const v=entry[k]??(k==="edition"?"web":"");
    if(typeof v!=="string"||v.length>max)throw new HttpError(422,"Invalid feedback field");
    clean[k]=v.trim();
  }
  return store.fetch("https://internal/feedback",{method:"POST",body:JSON.stringify(clean)});
}
export default {async fetch(req,env){
  const u=new URL(req.url),p=u.pathname,q=u.searchParams;
  if(!p.startsWith("/api/"))return env.ASSETS.fetch(req);
  try{
    if(p.startsWith("/api/count/")){
      if(req.method!=="POST")throw new HttpError(405,"POST required");
      if(req.headers.get("Origin")!==u.origin)throw new HttpError(403,"Same-origin events only");
      const event=p.slice(11);
      if(!usageEvents.has(event))throw new HttpError(400,"Unknown event");
      const ip=req.headers.get("CF-Connecting-IP")??"unknown";
      if(!(await env.API_LIMIT.limit({key:"usage:"+ip})).success)throw new HttpError(429,"Too many events");
      return await env.STORE.getByName("usage").fetch("https://internal/count/"+event,{method:"POST"});
    }
    if(req.method!=="GET"&&!(req.method==="POST"&&p==="/api/feedback"))throw new HttpError(405,"Method not allowed");
    if(p==="/api/health")return json(health);
    const ip=req.headers.get("CF-Connecting-IP")??"unknown";
    if(!(await env.API_LIMIT.limit({key:ip})).success)throw new HttpError(429,"Too many requests");
    const store=env.STORE.getByName("solar");
    if(p==="/api/status")return json({...health,features:{iss_caching:true,stale_data:true,dst_safe_weather:true,feedback_forward:false}});
    if(p==="/api/feedback")return await feedback(req,env,ip,store);
    if(p==="/api/kp")return json(unpack(await kp()));
    if(["/api/location","/api/aurora","/api/regions"].includes(p)){
      const coords=p==="/api/location"?coordinates(q):null;
      const {data,age_seconds,stale}=await aurora();
      const result=coords?location(data,...coords,(await kp().catch(()=>null))?.data.current??null):p==="/api/regions"?{forecast_time:data.view.forecast_time,regions:regions(data.cells)}:data.view;
      return json({...result,age_seconds,stale});
    }
    if(p==="/api/iss"){
      const coords=q.has("lat")||q.has("lon")?coordinates(q):null;
      const tle=await cached("tle",21600,async()=>{
        for(const url of ["https://www.amsat.org/tle/current/nasabare.txt","https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE","https://api.wheretheiss.at/v1/satellites/25544/tles?format=text"]){
          const t=await source(url,21600,"text",3500).catch(()=>"");
          const pair=t.match(/^1 25544[^\r\n]*\r?\n2 25544[^\r\n]*/m);
          if(pair)return pair[0];
        }
        throw Error("Orbit unavailable");
      },86400);
      const snap=await cached("iss",10,()=>orbit(tle.data),120);
      const out=unpack(snap);
      out.stale ||= tle.stale;
      if(coords){const d=distance(...coords,out.lat,out.lon);out.observer={distance_km:Math.round(d),in_view:d<=out.footprint_km};}
      return json(out);
    }
    if(p==="/api/weather"){
      const [lat,lon]=coordinates(q);
      const query=new URLSearchParams({latitude:lat.toFixed(2),longitude:lon.toFixed(2),current:"cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high,visibility,precipitation,weather_code,temperature_2m,is_day",hourly:"cloud_cover,visibility,precipitation_probability",forecast_hours:"30",timezone:"auto",timeformat:"unixtime"});
      return json({...weather(await source("https://api.open-meteo.com/v1/forecast?"+query,600),lat,lon),stale:false,age_seconds:0});
    }
    if(p==="/api/clouds"){
      const result=await cached("clouds",900,async()=>{
        const xml=await source(cloudRoot+"/mumi/worldcloudmap_ir108/ows?service=WMS&version=1.3.0&request=GetCapabilities",900,"text");
        return xml.match(/<Dimension\b[^>]*\bname="time"[^>]*>/i)?.[0].match(/\bdefault="([^"]+)"/)?.[1]??null;
      }).catch(()=>({data:null,stale:true,age_seconds:0}));
      return json({wms_url:cloudRoot+"/ows",layer:"mumi:worldcloudmap_ir108",time:result.data,stale:result.stale,age_seconds:result.age_seconds,attribution:"Clouds © EUMETSAT"});
    }
    if(p==="/api/geocode"||p==="/api/reverse"){
      const search=p.endsWith("geocode"),args=new URLSearchParams({format:"jsonv2"});
      if(search){const term=q.get("q")?.trim();if(!term||term.length<2||term.length>120)throw new HttpError(422,"Invalid place name");args.set("q",term);args.set("limit","5");}
      else{const [lat,lon]=coordinates(q);args.set("lat",lat.toFixed(2));args.set("lon",lon.toFixed(2));args.set("zoom","10");}
      if(!(await (await store.fetch("https://internal/geo")).json()).allowed)throw new HttpError(429,"Please retry in a second");
      const data=await source("https://nominatim.openstreetmap.org/"+(search?"search":"reverse")+"?"+args,86400);
      return json(search?{results:data.map(r=>({name:r.display_name,lat:+r.lat,lon:+r.lon}))}:{name:data.display_name??null});
    }
    throw new HttpError(404,"Unknown endpoint");
  }catch(e){return json({detail:e instanceof HttpError?e.message:"Data source temporarily unavailable"},e instanceof HttpError?e.status:503);}
}};
