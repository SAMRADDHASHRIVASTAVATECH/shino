/* Companion player • dependency-free ES module. Assets resolve relative to this file. */
export async function createCompanion(element, {baseURL=new URL('./',import.meta.url), reducedMotion=matchMedia('(prefers-reduced-motion: reduce)').matches}={}) {
 const root=new URL(baseURL,document.baseURI);const response=await fetch(new URL('manifest.json',root));if(!response.ok)throw Error('Cannot load companion manifest');const manifest=await response.json();
 const el=document.createElement('div');element.append(el);el.setAttribute('role','img');Object.assign(el.style,{width:'100%',aspectRatio:'1',backgroundSize:'400% 100%',backgroundRepeat:'no-repeat',imageRendering:'pixelated'});
 let timer,serial=0,state=null,disposed=false;const cache=new Map();
 async function setState(id){if(disposed)throw Error('Player is disposed');const s=manifest.states[id];if(!Object.hasOwn(manifest.states,id))throw Error('Unknown companion state: '+id);const rev=++serial;clearTimeout(timer);
 const url=new URL(s.sprite,root).href;if(!cache.has(url)){const img=new Image();img.src=url;cache.set(url,img.decode().catch(e=>{cache.delete(url);throw e}));}await cache.get(url);if(disposed||serial!==rev)return;
 state=id;el.style.backgroundSize=`${s.frames*100}% 100%`;el.setAttribute('aria-label',s.label);el.style.backgroundImage=`url("${url}")`;let f=0;function tick(){if(serial!==rev||disposed)return;el.style.backgroundPosition=`${reducedMotion?0:f*100/(s.frames-1)}% 0`;if(reducedMotion&&s.loop)return;timer=setTimeout(()=>{f++;if(f===s.frames&&!s.loop){setState(s.next).catch(console.error);return;}f%=s.frames;tick()},s.frameMs)}tick();}
 await setState(manifest.initial);return {setState,dispatch(event){if(!Object.hasOwn(manifest.events,event))return Promise.resolve(false);return setState(manifest.events[event]).then(()=>true)},get state(){return state},manifest,destroy(){disposed=true;++serial;clearTimeout(timer);el.remove();cache.clear()}};
}
