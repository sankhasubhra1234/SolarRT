(() => {
const intro=document.querySelector('#auroraEntrance');
const canvas=document.querySelector('#auroraSky');
const ctx=canvas.getContext('2d');
const header=document.querySelector('.topbar');
const skip=document.querySelector('#skipEntrance');
const replay=document.querySelector('.replay-aurora');
let timer, closing=false, resolveEntrance;
window.solarEntranceFinished=new Promise(resolve=>{resolveEntrance=resolve});
const motion=matchMedia('(prefers-reduced-motion: reduce)');
let width,height,frame,last=0,time=0;
const glyphs=' .,:;i!|/+=*';
const skyCanvas=document.createElement('canvas');
const beams=[];
function cacheScene(){
 skyCanvas.width=canvas.width;skyCanvas.height=canvas.height;
 const sky=skyCanvas.getContext('2d');
 sky.scale(canvas.width/width,canvas.height/height);
 const gradient=sky.createLinearGradient(0,0,0,height);
 gradient.addColorStop(0,'#040914');gradient.addColorStop(.7,'#0d2634');gradient.addColorStop(1,'#070e19');
 sky.fillStyle=gradient;sky.fillRect(0,0,width,height);
 sky.fillStyle='#adcdd1';sky.font='10px monospace';
 for(let i=1;i<150;i++){
   sky.globalAlpha=.25+.45*(i%5)/4;
   sky.fillText(i%13===0?'+':'.',width*((i*.618034)%1),height*((i*i*.17731)% .85));
 }
 // Rasterize the glyphs once. Move each complete ray at subpixel precision.
 beams.length=0;
 const columns=Math.max(2,Math.min(205,Math.ceil(width/6)));
 for(let layer=2;layer>=0;layer--){
   for(let col=0;col<columns;col++){
     const u=col/(columns-1), phase=u*8.5+layer*1.6;
     const ray=document.createElement('canvas');
     ray.width=20;ray.height=316;
     const ink=ray.getContext('2d');
     ink.font='17px monospace';
     const hue=147+layer*24+36*Math.sin(phase*.65);
     for(let row=0;row<25;row++){
       const v=row/24, power=Math.pow(1-v,1.55);
       ink.globalAlpha=power;
       ink.fillStyle='hsl('+(hue+v*73)+' 89% '+(58+power*24)+'%)';
       ink.fillText(glyphs[1+Math.floor(power*(7+3*Math.cos(col*.48)**2))],2,308-row*12);
     }
     beams.push({ray,u,phase,col,layer});
   }
 }
}
function draw(t){
 if(!ctx)return;
 ctx.drawImage(skyCanvas,0,0,width,height);
 const glyphWidth=Math.max(8,Math.min(14,width/100));
 for(const {ray,u,phase,col,layer} of beams){
   const a=phase+t*.18;
   const fold=Math.sin(a+1.7*Math.sin(a*.66));
   const depth=1.2+layer*.21+.27*fold;
   const x=width*(.5+(u-.5)*2.1/depth);
   const base=height*(.47+.17*Math.sin(a*.74)+.1*fold-layer*.07);
   const beam=.55+.45*Math.cos(col*.48+fold)**2;
   const length=height*(.23+.16*beam)/depth;
   ctx.globalAlpha=beam*(.75+.25*Math.sin(a*3+t*.65))*(1-layer*.18);
   ctx.drawImage(ray,x,base-length,glyphWidth/depth,length);
 }
 ctx.globalAlpha=1;
}
function resize(){
 width=Math.max(1,canvas.clientWidth);height=Math.max(1,canvas.clientHeight);
 const scale=Math.min(devicePixelRatio||1,1.6);
 canvas.width=Math.round(width*scale);canvas.height=Math.round(height*scale);
 ctx?.setTransform(scale,0,0,scale,0,0);cacheScene();draw(time);
}
function animate(now){
 time+=last?Math.min(.05,(now-last)/1000):0;last=now;draw(time);
 frame=requestAnimationFrame(animate);
}
function sync(){
 cancelAnimationFrame(frame);last=0;
 if(!motion.matches&&!document.hidden)frame=requestAnimationFrame(animate);
}

function finish(){
 clearTimeout(timer);
 intro.close();
 header.prepend(canvas);
 closing=false;
 resize();
 resolveEntrance();
}
function leave(){
 if(closing || !intro.open)return;
 closing=true;
 clearTimeout(timer);
 intro.classList.add('fading');
 if(motion.matches)finish();
 else timer=setTimeout(finish,1600);
}
function begin(){
 intro.classList.remove('fading');
 intro.prepend(canvas);
 intro.showModal();
 resize();
 timer=setTimeout(leave,5200);
}
skip.onclick=leave;
replay.onclick=begin;
intro.addEventListener('cancel',event=>{event.preventDefault();leave()});
document.addEventListener('visibilitychange',sync);
motion.addEventListener('change',()=>{sync();if(motion.matches && intro.open)finish()});
new ResizeObserver(resize).observe(canvas);
if(motion.matches || !ctx)finish();
else begin();
sync();
})();
