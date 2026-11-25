import {cpSync,copyFileSync,mkdirSync,readFileSync,writeFileSync} from "node:fs";
const src = new URL("../solarrt/static/",import.meta.url);
const out = new URL("./public/",import.meta.url);
mkdirSync(out,{recursive:true});
cpSync(src,new URL("static/",out),{recursive:true});
copyFileSync(new URL("index.html",src),new URL("index.html",out));
copyFileSync(new URL("favicon.svg",src),new URL("favicon.svg",out));
const {headers}=JSON.parse(readFileSync(new URL("./constants.json",import.meta.url)));
writeFileSync(new URL("_headers",out),"/*\n"+Object.entries(headers).map(([key,value])=>"  "+key+": "+value).join("\n")+"\n");
