/**
 * Snippet inline ejecutado en el <head> antes del primer paint.
 *
 * Lee el estado persistido del store de a11y desde localStorage y aplica
 * las clases al <html> sincronicamente. Esto evita el FOUC entre el HTML
 * server-rendered (que aplica `text-size-md` default) y el render del
 * client (que conoce la preferencia real del usuario).
 *
 * Patrón inspirado en next-themes / tailwindcss-next-themes.
 *
 * IMPORTANTE: la key (`ynara.a11y`) y los campos (`textSize`,
 * `highContrast`, `motion`) deben mantenerse en sync con
 * `stores/a11y.ts`. Si alguno cambia, este script rompe silenciosamente
 * y vuelve el FOUC.
 */
export const a11yInitScript = `(function(){try{
var raw = localStorage.getItem('ynara.a11y');
if(!raw) return;
var parsed = JSON.parse(raw);
var s = parsed && parsed.state ? parsed.state : null;
if(!s) return;
var root = document.documentElement;
if(s.textSize){
  root.classList.remove('text-size-sm','text-size-md','text-size-lg');
  root.classList.add('text-size-'+s.textSize);
}
if(s.highContrast===true) root.classList.add('theme-high-contrast');
if(s.motion==='reduce') root.classList.add('motion-off');
else if(s.motion==='normal') root.classList.add('motion-on');
}catch(e){}})();`;
