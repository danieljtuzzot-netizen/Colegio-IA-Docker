'use strict';
window.DemoFormato=Object.freeze({
 porcentaje:valor=>typeof valor==='number'&&Number.isFinite(valor)?Math.round(valor)+' %':'Sin base',
 porcentajeSobre:(cantidad,base)=>base>0?Math.round(cantidad*100/base)+' %':'Sin base'
});
