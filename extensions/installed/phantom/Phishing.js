import{a as ro,b as K}from"./chunk-CKQ37DRC.js";import{a as A}from"./chunk-MQ2XFQME.js";import"./chunk-NGKKVVYY.js";import{a as G}from"./chunk-YQNIGRQS.js";import"./chunk-TO2UYJWM.js";import{Za as p,d as M,n as z}from"./chunk-7ALUQBE3.js";import{a as $,c}from"./chunk-5G7Z362D.js";import"./chunk-6LRU67JW.js";import{h as _,k as J}from"./chunk-VN4H36TG.js";import{a as x}from"./chunk-QQJPKFTO.js";import"./chunk-HRSMUG5A.js";import"./chunk-WMGJCMXX.js";import"./chunk-KS7AKYDM.js";import"./chunk-V5YF4BWK.js";import"./chunk-UMKDODOO.js";import"./chunk-QNZ4IKWZ.js";import{b as R,f as F}from"./chunk-VR544T5V.js";import"./chunk-VD23BAEF.js";import{b as I}from"./chunk-QTITVYLP.js";import"./chunk-FRT7J7NM.js";import"./chunk-PN6ZWBOX.js";import{a as N}from"./chunk-UPPQC44E.js";import{a as E}from"./chunk-OJPBMZQC.js";import{V as D}from"./chunk-IEJ4AK6Z.js";import"./chunk-CYENH7PC.js";import"./chunk-TRFSSUYO.js";import{nb as to}from"./chunk-HOPOVBCB.js";import"./chunk-BIP7RNCZ.js";import"./chunk-WXTMIUXL.js";import{Bc as U,Uc as P,Yb as T,Yc as l}from"./chunk-XGDWTOSO.js";import"./chunk-YNSFZ5VB.js";import{e as v,f as m,s as C,sb as f}from"./chunk-4ZV6PABP.js";import"./chunk-V2YZXVTC.js";import"./chunk-PPRUN2KR.js";import"./chunk-U7OZEJ4F.js";import"./chunk-ZRGHR2IN.js";import{a as e,g as i,i as a,n as s}from"./chunk-TSHWMJEM.js";a();s();var No=i(v(),1);var Y=i(ro(),1);a();s();var h=i(v(),1);a();s();var Q=i(to(),1);var o=i(m(),1),g=f.colors.legacy.spotNegative,io=c.div`
  position: fixed;
  top: 0;
  left: 0;
  height: 100%;
  width: 100%;
  background-color: ${f.colors.brand.white};
  padding: clamp(24px, 16vh, 256px) 24px;
  box-sizing: border-box;
`,eo=c.div`
  margin-bottom: 24px;
  padding-bottom: 8vh;
`,no=c.div`
  max-width: 100ch;
  margin: auto;

  * {
    text-align: left;
  }
`,H=c.a`
  text-decoration: underline;
  color: ${g};
`,u=new E,V=e(({origin:t,subdomain:n,source:w})=>{let{t:d}=C(),Z=t?F(t):"",k=w||Z,j=t??"",L=new URL(j),O=L.hostname,W=n==="true"?O:k,S=(0,Q.toUnicode)(W),oo=e(async()=>{if(n==="true"){let y=await u.get(l.UserWhitelistSubdomains),r=JSON.parse(`${y}`);r?r.push(O):r=[O],r=[...new Set(r)],u.set(l.UserWhitelistSubdomains,JSON.stringify(r))}else{let y=await u.get(l.UserWhitelistedOrigins),r=JSON.parse(`${y}`);r?r.push(k):r=[k],r=[...new Set(r)],u.set(l.UserWhitelistedOrigins,JSON.stringify(r))}["http:","https:"].includes(L.protocol)&&self.location.assign(t)},"handleClick");return(0,o.jsx)(io,{children:(0,o.jsxs)(no,{children:[(0,o.jsx)(eo,{children:(0,o.jsx)(z,{width:128,fill:f.colors.brand.white})}),(0,o.jsx)(p,{size:30,color:g,weight:"600",children:d("blocklistOriginDomainIsBlocked",{domainName:S||d("blocklistOriginThisDomain")})}),(0,o.jsx)(p,{color:g,children:d("blocklistOriginSiteIsMalicious")}),(0,o.jsx)(p,{color:g,children:(0,o.jsxs)(I,{i18nKey:"blocklistOriginCommunityDatabaseInterpolated",children:["This site has been flagged as part of a",(0,o.jsx)(H,{href:R,rel:"noopener",target:"_blank",children:"community-maintained database"}),"of known phishing websites and scams. If you believe the site has been flagged in error,",(0,o.jsx)(H,{href:R,rel:"noopener",target:"_blank",children:"please file an issue"}),"."]})}),W?(0,o.jsx)(p,{color:g,onClick:oo,hoverUnderline:!0,children:d("blocklistOriginIgnoreWarning",{domainName:S})}):(0,o.jsx)(o.Fragment,{})]})})},"BlocklistOrigin");var b=i(m(),1),ao=e(()=>{let t;try{t=new URLSearchParams(self.location.search).get("origin")||"",new URL(t)}catch{t=""}return t},"getOriginParam"),so=e(()=>new URLSearchParams(self.location.search).get("subdomain")||"","getSubdomainParam"),mo=e(()=>new URLSearchParams(self.location.search).get("source")||"","getSourceParam"),X=e(()=>{let t=(0,h.useMemo)(()=>ao(),[]),n=(0,h.useMemo)(()=>so(),[]),w=(0,h.useMemo)(()=>mo(),[]);return(0,b.jsx)(M,{future:{v7_startTransition:!0},children:(0,b.jsx)(A,{children:(0,b.jsx)(V,{origin:t,subdomain:n,source:w})})})},"Blocklist");var B=i(m(),1);N();T([[P,x]]);U.init({provider:K});await D(x);await _("frontend",J);var lo=document.getElementById("root"),co=(0,Y.createRoot)(lo);co.render((0,B.jsx)($,{theme:G,children:(0,B.jsx)(X,{})}));
//# sourceMappingURL=Phishing.js.map
