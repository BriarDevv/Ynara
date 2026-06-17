/**
 * Snippets inline ejecutados en el <head> antes del primer paint.
 *
 * Leen el estado persistido de los stores (a11y y tema) desde
 * localStorage y aplican las clases al <html> sincronicamente. Esto
 * evita el FOUC entre el HTML server-rendered (text-size-md default,
 * data-theme="light") y el render del client (que conoce la
 * preferencia real del usuario).
 *
 * Patrón inspirado en next-themes / tailwindcss-next-themes.
 *
 * IMPORTANTE: las keys (`ynara.a11y`, `ynara.theme`) y sus campos
 * (`textSize`, `highContrast`, `motion`, `theme`) deben mantenerse en
 * sync con `stores/a11y.ts` y `stores/theme.ts`. Si alguno cambia,
 * estos scripts rompen silenciosamente y vuelve el FOUC.
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

/**
 * Pre-paint del tema (§16 #4): Noche es el default server-rendered
 * (`<html>` ya trae `.theme-dark` + `data-theme="dark"`). Si el usuario
 * eligió **claro**, esta rama le saca la clase antes del primer paint —
 * sin esto hay flash oscuro→claro en cada carga para ese usuario. Sin
 * preferencia persistida, no toca nada (queda en Noche).
 */
export const themeInitScript = `(function(){try{
var raw = localStorage.getItem('ynara.theme');
if(!raw) return;
var parsed = JSON.parse(raw);
var s = parsed && parsed.state ? parsed.state : null;
if(!s) return;
var root = document.documentElement;
if(s.theme==='dark'){
  root.classList.add('theme-dark');
  root.setAttribute('data-theme','dark');
}else if(s.theme==='light'){
  root.classList.remove('theme-dark');
  root.setAttribute('data-theme','light');
}
}catch(e){}})();`;
