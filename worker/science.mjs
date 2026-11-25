import constants from "./constants.json" with {type:"json"};
import {twoline2satrec,propagate,gstime,eciToGeodetic} from "satellite.js";
const rad=Math.PI/180;
export const level=p=>p>=50?"Very high":p>=30?"High":p>=15?"Moderate":p>=5?"Low":"None";
export const sky=e=>e>0?"Daylight":e>-6?"Civil twilight":e>-12?"Nautical twilight":e>-18?"Astronomical twilight":"Dark";
export function sun(lat,lon,date=new Date()){
  const hour=date.getUTCHours()+date.getUTCMinutes()/60+date.getUTCSeconds()/3600;
  const day=Math.floor((date-Date.UTC(date.getUTCFullYear(),0,1))/86400000);
  const g=2*Math.PI/365*(day+(hour-12)/24), c=Math.cos,s=Math.sin;
  const decl=.006918-.399912*c(g)+.070257*s(g)-.006758*c(2*g)+.000907*s(2*g)-.002697*c(3*g)+.00148*s(3*g);
  const eq=229.18*(.000075+.001868*c(g)-.032077*s(g)-.014615*c(2*g)-.040849*s(2*g));
  return Math.asin(Math.min(1,Math.max(-1,s(lat*rad)*s(decl)+c(lat*rad)*c(decl)*c((hour*15+eq/4+lon-180)*rad))))/rad;
}
export function distance(a,b,c,d){
  const h=Math.sin((c-a)*rad/2)**2+Math.cos(a*rad)*Math.cos(c*rad)*Math.sin((d-b)*rad/2)**2;
  return 12742*Math.asin(Math.sqrt(Math.min(1,h)));
}
export function grid(raw){
  if(!raw.coordinates?.length) throw Error("Missing grid");
  const cells=new Uint8Array(360*181), maxima={north:0,south:0};
  for(const [lon,lat,value] of raw.coordinates){
    const y=Math.round(lat),p=Math.min(100,Math.max(0,Math.round(value)));
    if(y< -90 || y>90 || !Number.isFinite(p))continue;
    cells[(90+y)*360+(Math.round(lon)%360+360)%360]=p;
    const side=y>0?"north":"south";
    if(y!==0 && p>maxima[side])maxima[side]=p;
  }
  let bytes="";
  for(let i=0;i<cells.length;i+=4096)bytes+=String.fromCharCode(...cells.subarray(i,i+4096));
  return {cells,view:{width:360,height:181,data:btoa(bytes),encoding:"base64 uint8, row = latitude -90..90, column = longitude 0..359",forecast_time:raw["Forecast Time"],observation_time:raw["Observation Time"],hemisphere_max:maxima}};
}
const cell=(g,y,x)=>g[(Math.min(90,y)+90)*360+(x%360+360)%360];
export function regions(g){
  return constants.regions.map(r=>{
    let max=0,peak_at=null,count=0,active=0;
    for(let y=r.south;y<=r.north;y++)for(let x=r.west;x<=r.east;x++){
      const v=cell(g,y,x);count++;if(v>=5)active++;
      if(v>max){max=v;peak_at=[y,x];}
    }
    return {id:r.id,name:r.name,hemisphere:r.hemisphere,bounds:[[r.south,r.west],[r.north,r.east]],max,peak_at,coverage:Math.round(1000*active/count)/10,level:level(max)};
  }).sort((a,b)=>b.max-a.max||b.coverage-a.coverage);
}
export function location(grid,lat,lon,kp){
  const g=grid.cells,y=Math.floor(lat),x=Math.floor(lon),fx=lon-x,fy=lat-y;
  const row=la=>(1-fx)*cell(g,la,x)+fx*cell(g,la,x+1);
  const p=(1-fy)*row(y)+fy*row(y+1);
  const nearby={max:0,lat,lon,distance_km:null,radius_km:800};
  for(let la=Math.max(-90,y-8);la<=Math.min(90,Math.ceil(lat)+8);la++){
    const dx=Math.min(180,Math.ceil(800/(111*Math.max(.01,Math.cos(la*rad)))));
    for(let lo=x-dx;lo<=Math.ceil(lon)+dx;lo++){
      const v=cell(g,la,lo);
      if(v<=nearby.max)continue;
      const km=distance(lat,lon,la,lo);
      if(km<=800)Object.assign(nearby,{max:v,lat:la,lon:((lo+540)%360)-180,distance_km:Math.round(km)});
    }
  }
  const e=sun(lat,lon),chance=p>=30?"high":p>=10?"moderate":nearby.max>=10?"low":"none";
  let verdict={high:"Aurora likely overhead",moderate:"Aurora possible overhead",low:"Possibly visible low on the "+(lat>=0?"northern":"southern")+" horizon",none:"Aurora unlikely from here right now"}[chance];
  if(chance!=="none"&&e> -6)verdict+=" - but it is too bright to see it now";
  return {lat,lon,probability:Math.round(p*10)/10,level:level(p),nearby,sun_elevation:e,sky:sky(e),chance,verdict,kp,forecast_time:grid.view.forecast_time,computed_at:new Date().toISOString()};
}
export function kpSummary(minute,hist,forecast,now=Date.now()){
  function parse(rows,kind){
    return rows.flatMap(r=>{
      const tag=r.time_tag??r[0],v=r.estimated_kp??r.kp_index??r.Kp??r.kp??r[1];
      if(!tag||v==null||!Number.isFinite(+v)||!Number.isFinite(Date.parse(tag)))return [];
      const time=new Date(tag).toISOString(),kp=+v,g=Math.max(0,Math.min(5,Math.floor(kp+.34)-4));
      return [{time,kp,g,kind:kind??((r.observed??r[2])==="observed"?"observed":Date.parse(tag)<=now?"estimated":"predicted")}];
    }).sort((a,b)=>a.time.localeCompare(b.time));
  }
  function describe(p){
    if(!p)return null;
    const n=Math.round(p.kp),delta=p.kp-n;
    return {...p,label:n+(delta<-.15?"-":delta>.15?"+":"o"),g_label:["G0 Quiet","G1 Minor","G2 Moderate","G3 Strong","G4 Severe","G5 Extreme"][p.g],activity:p.kp>=5?"Storm":p.kp>=4?"Active":p.kp>=3?"Unsettled":"Quiet"};
  }
  const history=parse(hist,"observed"),fc=parse(forecast),last=history.at(-1);
  const past=history.filter(p=>Date.parse(p.time)>=now-86400000);
  const future=fc.filter(p=>p.kind!=="observed"&&Date.parse(p.time)+10800000>now&&Date.parse(p.time)<now+86400000);
  const current=describe(parse(minute,"estimated").at(-1)??last);
  if(!current)throw Error("Missing Kp");
  return {current,last_3h:describe(last),series:fc.length?fc:history,max_24h:past.length?Math.max(...past.map(p=>p.kp)):null,forecast_peak_24h:describe(future.sort((a,b)=>b.kp-a.kp)[0]),source:"NOAA SWPC"};
}
export function orbit(tle,now=new Date()){
  const lines=tle.trim().split(/\r?\n/),i=lines.findIndex(l=>l.startsWith("1 25544"));
  if(i<0||!lines[i+1]?.startsWith("2 25544"))throw Error("Invalid ISS TLE");
  const sat=twoline2satrec(lines[i],lines[i+1]);
  function at(t){
    const state=propagate(sat,t);
    if(!state?.position)throw Error("Propagation failed");
    const p=eciToGeodetic(state.position,gstime(t));
    return {lat:p.latitude/rad,lon:p.longitude/rad,altitude_km:p.height,speed_kmh:Math.round(Math.hypot(...Object.values(state.velocity))*3600)};
  }
  const pos=at(now),track=[];
  for(let m=-46;m<=46;m++){const p=m===0?pos:at(new Date(+now+m*60000));track.push([p.lat,p.lon,m*60]);}
  const dip=Math.acos(6371/(6371+pos.altitude_km));
  return {...pos,track,time:now.toISOString(),footprint_km:Math.round(6371*dip),sunlit:sun(pos.lat,pos.lon,now)>-dip/rad,tle_epoch:new Date((sat.jdsatepoch-2440587.5)*86400000).toISOString()};
}
export function weather(d,lat,lon){
  const c=d.current,h=d.hourly,cloud=c.cloud_cover,vis=c.visibility;
  const hourly=h.time.flatMap((t,i)=>{
    if((t+3600)*1000<=Date.now())return [];
    const date=new Date(t*1000);
    return [{time:date.toISOString(),cloud:h.cloud_cover[i],visibility:h.visibility[i],precip_prob:h.precipitation_probability[i],dark:sun(lat,lon,date)<=-12}];
  }).slice(0,24);
  const clear=(cloud,vis)=>cloud!=null&&cloud<=30&&(vis==null||vis>=10000);
  const e=sun(lat,lon);
  return {lat,lon,current:{cloud,cloud_low:c.cloud_cover_low,cloud_mid:c.cloud_cover_mid,cloud_high:c.cloud_cover_high,visibility:vis,precipitation:c.precipitation,temperature:c.temperature_2m,condition:constants.wmo[c.weather_code]??"Unknown",sky:cloud==null?"Unknown":vis!=null&&vis<2000?"Fog / poor visibility":cloud<20?"Clear":cloud<50?"Partly cloudy":cloud<85?"Mostly cloudy":"Overcast"},darkness:sky(e),dark_now:e<=-12,clear_now:clear(cloud,vis),next_dark_clear:hourly.find(h=>h.dark&&clear(h.cloud,h.visibility))?.time??null,hourly,timezone:d.timezone,timezone_abbreviation:d.timezone_abbreviation,utc_offset_seconds:d.utc_offset_seconds,source:"Open-Meteo"};
}
