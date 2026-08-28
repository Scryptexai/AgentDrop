import{a as q}from"./chunk-PRHRMRYG.js";import{A as C,I,e as p,m as O}from"./chunk-DMM54ENI.js";import{b as c,d as y}from"./chunk-5G7Z362D.js";import{k as a}from"./chunk-VN4H36TG.js";import{Ha as f}from"./chunk-V5YF4BWK.js";import{b as l}from"./chunk-PN6ZWBOX.js";import{a as T}from"./chunk-OJPBMZQC.js";import{Ac as u,Dc as m,Dh as k,Sh as w,uc as E,zc as d,zg as x}from"./chunk-XGDWTOSO.js";import{sb as b}from"./chunk-4ZV6PABP.js";import{s as _}from"./chunk-V2YZXVTC.js";import{I as S,J as R,i as v}from"./chunk-PPRUN2KR.js";import{a as s,i as o,j as n,n as r}from"./chunk-TSHWMJEM.js";o();r();var B=k({authRepository:a,queryClient:f});o();r();var re=new w(l,a,B,{queryClient:f});o();r();var me=new E({store:q({isWriter:!1}),adapters:[new x({baseUrl:s(()=>v(),"baseUrl"),fetch(e,t){return _.bearer(!0).fetch(e,t)}})]});o();r();var h,J=new T,M=s(()=>{if(n.ENVIRONMENT!=="e2e")return null;let e=globalThis.__PHANTOM_E2E_SEEDLESS_JUICEBOX_CLIENT__;return e||null},"getE2EJuiceboxClientOverride"),D=s(async()=>{let e=M();return e||h||(h=new O(new I),h)},"juiceboxClient"),H={storage:J,authRepository:a,juiceboxClient:D},z=s(()=>{if(n.ENVIRONMENT!=="e2e")return null;let e=globalThis.__PHANTOM_E2E_SEEDLESS_REPOSITORY_OVERRIDES__;return e||null},"getE2ESeedlessRepositoryOverrides"),P=C(H),g={...P,recover:s(async e=>{let t=z()?.recover;return t?await t(e):await P.recover(e)},"recover")};g.subscribe(p.RotationResult,({type:e,didRotate:t})=>{let i=`Se*dless Bundle Rotation Result: ${e}, didRotate: ${t}`;m.addBreadcrumb(u.Seedless,i,d.Info),l.capture("seedlessBundleRotationResult",{data:{type:e,didRotate:t}})});g.subscribe(p.RecoverResult,({type:e,reason:t})=>{let i=`Se*dless Bundle Recover Result: ${e}`;t&&(i+=`, reason: ${t}`),m.addBreadcrumb(u.Seedless,i,d.Info),l.capture("seedlessBundleRecoverResult",{data:{type:e,reason:t}})});g.subscribe(p.BackupResult,({type:e,didBackup:t})=>{let i=`Se*dless Bundle Backup Result: ${e}, didBackup: ${t}`;m.addBreadcrumb(u.Seedless,i,d.Info),l.capture("seedlessBundleBackupResult",{data:{type:e,didBackup:t}})});o();r();o();r();var j=function(e,t){return Object.defineProperty?Object.defineProperty(e,"raw",{value:t}):e.raw=t,e},A=c(L||(L=j([`
/* http://meyerweb.com/eric/tools/css/reset/
   v5.0.1 | 20191019
   License: none (public domain)
*/

html, body, div, span, applet, object, iframe,
h1, h2, h3, h4, h5, h6, p, blockquote, pre,
a, abbr, acronym, address, big, cite, code,
del, dfn, em, img, ins, kbd, q, s, samp,
small, strike, strong, sub, sup, tt, var,
b, u, i, center,
dl, dt, dd, menu, ol, ul, li,
fieldset, form, label, legend,
table, caption, tbody, tfoot, thead, tr, th, td,
article, aside, canvas, details, embed,
figure, figcaption, footer, header, hgroup,
main, menu, nav, output, ruby, section, summary,
time, mark, audio, video {
  margin: 0;
  padding: 0;
  border: 0;
  font-size: 100%;
  font: inherit;
  vertical-align: baseline;
}
/* HTML5 display-role reset for older browsers */
article, aside, details, figcaption, figure,
footer, header, hgroup, main, menu, nav, section {
  display: block;
}
/* HTML5 hidden-attribute fix for newer browsers */
*[hidden] {
    display: none;
}
body {
  line-height: 1;
}
menu, ol, ul {
  list-style: none;
}
blockquote, q {
  quotes: none;
}
blockquote:before, blockquote:after,
q:before, q:after {
  content: '';
  content: none;
}
table {
  border-collapse: collapse;
  border-spacing: 0;
}
`],[`
/* http://meyerweb.com/eric/tools/css/reset/
   v5.0.1 | 20191019
   License: none (public domain)
*/

html, body, div, span, applet, object, iframe,
h1, h2, h3, h4, h5, h6, p, blockquote, pre,
a, abbr, acronym, address, big, cite, code,
del, dfn, em, img, ins, kbd, q, s, samp,
small, strike, strong, sub, sup, tt, var,
b, u, i, center,
dl, dt, dd, menu, ol, ul, li,
fieldset, form, label, legend,
table, caption, tbody, tfoot, thead, tr, th, td,
article, aside, canvas, details, embed,
figure, figcaption, footer, header, hgroup,
main, menu, nav, output, ruby, section, summary,
time, mark, audio, video {
  margin: 0;
  padding: 0;
  border: 0;
  font-size: 100%;
  font: inherit;
  vertical-align: baseline;
}
/* HTML5 display-role reset for older browsers */
article, aside, details, figcaption, figure,
footer, header, hgroup, main, menu, nav, section {
  display: block;
}
/* HTML5 hidden-attribute fix for newer browsers */
*[hidden] {
    display: none;
}
body {
  line-height: 1;
}
menu, ol, ul {
  list-style: none;
}
blockquote, q {
  quotes: none;
}
blockquote:before, blockquote:after,
q:before, q:after {
  content: '';
  content: none;
}
table {
  border-collapse: collapse;
  border-spacing: 0;
}
`]))),Oe=y(N||(N=j(["",""],["",""])),A),$=A,L,N;var G=c`
  ::-webkit-scrollbar {
    background: ${b.colors.legacy.areaBase};
    width: 7px;
  }

  ::-webkit-scrollbar-thumb {
    background: ${b.colors.legacy.elementBase};
    border-radius: 8px;
  }
`,U=c`
  ::-webkit-scrollbar {
    display: none;
  }
  * {
    scrollbar-width: none; /* Also needed to disable scrollbar Firefox */
  }
`,Ne=y`
    ${$}

    body, html, * {
        box-sizing: border-box;
        font-family: 'Inter', 'Roboto', Arial;
        user-select: none;
        color: currentColor;
        -moz-osx-font-smoothing: grayscale;
        text-rendering: optimizeSpeed;
        -webkit-font-smoothing: antialiased;
    }
    input, textarea {
        -webkit-user-select: text;
        -khtml-user-select: text;
        -moz-user-select: text;
        -ms-user-select: text;
        user-select: text;
    }
    body {
        color: ${b.colors.legacy.textBase};
        background: ${e=>e.backgroundColor};
        min-height: 100vh;
        margin: 0;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    *:focus, *:focus-within {
        outline-color: transparent !important;
        outline-style: none !important;
        outline-width: 0px !important;
    }

    ${S||R?U:G}
`;export{B as a,re as b,me as c,g as d,Ne as e};
//# sourceMappingURL=chunk-OE5DBXFB.js.map
