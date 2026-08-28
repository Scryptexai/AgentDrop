import{a as f,c as m}from"./chunk-UYECY7GO.js";import{a as F}from"./chunk-QYKSQVW7.js";import"./chunk-BEHZPJCX.js";import{F as w,Y as R}from"./chunk-DUJ52DSR.js";import"./chunk-KBNJM4OI.js";import"./chunk-SOGKDHYT.js";import"./chunk-K3AOJOH2.js";import"./chunk-K7BQY6A2.js";import"./chunk-QS2ATNL5.js";import"./chunk-GSQXVZTV.js";import"./chunk-ZSNMIKX2.js";import"./chunk-DOPYNHEM.js";import"./chunk-5EDJ4LKT.js";import"./chunk-P6I4TB7G.js";import"./chunk-Y6HGW6N6.js";import"./chunk-FFXJHUIX.js";import"./chunk-PA2NRDYY.js";import"./chunk-DAY5B7BQ.js";import"./chunk-BYF7EDTR.js";import"./chunk-GC7AVPC5.js";import"./chunk-WPYMVR7W.js";import"./chunk-AKMCTSIB.js";import"./chunk-WY4XLJUZ.js";import"./chunk-RMX4JBML.js";import"./chunk-NY2WZVO4.js";import"./chunk-YJH5PDWC.js";import"./chunk-4DKS3LI2.js";import"./chunk-ANAHPWN4.js";import"./chunk-MRETTCTD.js";import"./chunk-EOII3ZM4.js";import"./chunk-DMM54ENI.js";import"./chunk-4AQPJCXC.js";import"./chunk-MQ2XFQME.js";import"./chunk-NGKKVVYY.js";import"./chunk-YQNIGRQS.js";import{c as T,d as b}from"./chunk-TO2UYJWM.js";import{Za as s}from"./chunk-7ALUQBE3.js";import{c as t}from"./chunk-5G7Z362D.js";import"./chunk-HRSMUG5A.js";import"./chunk-WMGJCMXX.js";import"./chunk-KS7AKYDM.js";import"./chunk-V5YF4BWK.js";import"./chunk-UMKDODOO.js";import"./chunk-QNZ4IKWZ.js";import"./chunk-VR544T5V.js";import"./chunk-VD23BAEF.js";import"./chunk-QTITVYLP.js";import"./chunk-FRT7J7NM.js";import"./chunk-PN6ZWBOX.js";import"./chunk-UPPQC44E.js";import"./chunk-OJPBMZQC.js";import"./chunk-IEJ4AK6Z.js";import"./chunk-CYENH7PC.js";import"./chunk-TRFSSUYO.js";import"./chunk-HOPOVBCB.js";import"./chunk-BIP7RNCZ.js";import"./chunk-WXTMIUXL.js";import{Nb as B,qb as l,xb as x}from"./chunk-XGDWTOSO.js";import"./chunk-YNSFZ5VB.js";import{Hb as I,e as M,f as h,s as C,sb as a}from"./chunk-4ZV6PABP.js";import"./chunk-V2YZXVTC.js";import"./chunk-PPRUN2KR.js";import"./chunk-U7OZEJ4F.js";import"./chunk-ZRGHR2IN.js";import{a as d,g as c,i as y,n as g}from"./chunk-TSHWMJEM.js";y();g();var k=c(M(),1);var n=c(h(),1),E=t.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow-y: scroll;
`,N=t.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 90px;
`,S=t(s).attrs({size:28,weight:500,color:a.colors.legacy.textBase})`
  margin: 16px;
`,V=t(s).attrs({size:14,weight:400,lineHeight:17,color:a.colors.legacy.textDiminished})`
  max-width: 275px;

  span {
    color: white;
  }
`,$=d(({networkId:o,token:r})=>{let{t:e}=C(),{handleHideModalVisibility:p}=R(),u=(0,k.useCallback)(()=>{p("insufficientBalance")},[p]),v=o&&x(B(l.getChainID(o))),{canBuy:P,openBuy:D}=w({caip19:v||"",context:"modal",analyticsEvent:"fiatOnrampFromInsufficientBalance",entryPoint:"insufficientBalance"}),i=o?l.getTokenSymbol(o):e("tokens");return(0,n.jsxs)(E,{children:[(0,n.jsx)("div",{children:(0,n.jsxs)(N,{children:[(0,n.jsx)(F,{type:"failure",backgroundWidth:75}),(0,n.jsx)(S,{children:e("insufficientBalancePrimaryText",{tokenSymbol:i})}),(0,n.jsx)(V,{children:e("insufficientBalanceSecondaryText",{tokenSymbol:i})}),r?(0,n.jsxs)(I,{borderRadius:8,gap:1,marginTop:32,width:"100%",children:[(0,n.jsx)(f,{label:e("insufficientBalanceRemaining"),children:(0,n.jsx)(m,{color:a.colors.legacy.spotNegative,children:`${r.balance} ${i}`})}),(0,n.jsx)(f,{label:e("insufficientBalanceRequired"),children:(0,n.jsx)(m,{children:`${r.required} ${i}`})})]}):null]})}),P?(0,n.jsx)(b,{primaryText:e("buyAssetInterpolated",{tokenSymbol:i}),onPrimaryClicked:D,secondaryText:e("commandCancel"),onSecondaryClicked:u}):(0,n.jsx)(T,{onClick:u,children:e("commandCancel")})]})},"InsufficientBalance"),X=$;export{$ as InsufficientBalance,X as default};
//# sourceMappingURL=InsufficientBalance-DPEKG5HL.js.map
