import{a as v,b as Q}from"./chunk-SNOK75QJ.js";import{a as M}from"./chunk-GSQXVZTV.js";import{a as b}from"./chunk-ZSNMIKX2.js";import"./chunk-GC7AVPC5.js";import{a as x}from"./chunk-WPYMVR7W.js";import{g as E}from"./chunk-AKMCTSIB.js";import"./chunk-ANAHPWN4.js";import"./chunk-MRETTCTD.js";import{b as R}from"./chunk-EOII3ZM4.js";import{c as C}from"./chunk-TO2UYJWM.js";import{Za as k}from"./chunk-7ALUQBE3.js";import{c as s}from"./chunk-5G7Z362D.js";import"./chunk-HRSMUG5A.js";import{b as I}from"./chunk-QTITVYLP.js";import"./chunk-CYENH7PC.js";import"./chunk-TRFSSUYO.js";import{Ie as N,Xd as S,qb as u}from"./chunk-XGDWTOSO.js";import"./chunk-YNSFZ5VB.js";import{Rb as h,e as P,f,s as T,sb as c}from"./chunk-4ZV6PABP.js";import"./chunk-V2YZXVTC.js";import"./chunk-PPRUN2KR.js";import"./chunk-U7OZEJ4F.js";import"./chunk-ZRGHR2IN.js";import{a as D,g as a,i as l,n as g}from"./chunk-TSHWMJEM.js";l();g();var H=a(Q(),1),m=a(P(),1);l();g();var y=a(P(),1);var F=a(f(),1),$=s(C).attrs({borderRadius:"100px",width:"auto",fontSize:14,fontWeight:600})`
  flex-shrink: 0;
  padding: 5px 12px;
`,B=y.default.memo(n=>{let{copyText:e,className:d}=n,{buttonText:t,copy:r}=v(e),p=(0,y.useCallback)(A=>{A.stopPropagation(),r()},[r]);return(0,F.jsx)($,{className:d,onClick:p,theme:"primary",children:t})});var o=a(f(),1),L=s(x).attrs({align:"center",justify:"space-between"})`
  height: 100%;
`,O=s(H.default)`
  padding: 8px;
  background: ${c.colors.legacy.white};
  border-radius: 6px;
`,z=s(b).attrs({align:"center",justify:"space-between"})`
  box-shadow: inset 0px 0px 4px rgba(0, 0, 0, 0.25);
  padding: 12px 15px;
  background: ${c.colors.legacy.areaAccent};
  border: 1px solid ${c.colors.legacy.borderDiminished};
  border-radius: 6px;
`,K=s(x).attrs({align:"center"})`
  ${z} {
    margin-top: 32px;
    margin-bottom: 11px;
  }
`,U=s(b)`
  p:first-child {
    margin-right: 6px;
  }
`,W=D(n=>{let{accountName:e,walletAddress:d,address:t,symbol:r,onClose:p,networkID:A}=n,w=r||(t?N(t):void 0),{t:i}=T();return{i18nStrings:(0,m.useMemo)(()=>({depositAssetInterpolated:i("depositAssetDepositInterpolated",{tokenSymbol:w}),learnMore:i("commandLearnMore2"),transferFromExchange:i("depositAssetTransferFromExchange"),depositAssetShareAddressError1:i("sendInvalidQRCodeLoadingError1"),depositAssetShareAddressError2:i("sendInvalidQRCodeLoadingError2"),close:i("commandClose")}),[i,w]),accountName:e,walletAddress:d,networkID:A,onClose:p}},"useProps"),Y=m.default.memo(n=>{let{i18nStrings:e,accountName:d,walletAddress:t,networkID:r,onClose:p}=n;return(0,o.jsxs)(L,{children:[(0,o.jsx)(E,{children:e.depositAssetInterpolated}),(0,o.jsx)(K,{children:t?(0,o.jsxs)(o.Fragment,{children:[(0,o.jsx)(O,{value:t,size:160}),(0,o.jsxs)(z,{children:[(0,o.jsx)(U,{children:(0,o.jsx)(M,{name:d,publicKey:t})}),(0,o.jsx)(B,{copyText:t})]}),(0,o.jsxs)(k,{size:14,color:c.colors.legacy.textDiminished,lineHeight:20,children:[(0,o.jsxs)(I,{i18nKey:"depositAssetQRCodeInterpolated",values:{network:u.getNetworkName(r)},children:["Use to receive tokens on the ",u.getNetworkName(r)," network only."]}),u.isBitcoinNetworkID(r)?(0,o.jsxs)(o.Fragment,{children:[" ",(0,o.jsx)(k,{size:14,lineHeight:20,onClick:()=>R({url:S}),children:e.learnMore})]}):null]})]}):(0,o.jsxs)(o.Fragment,{children:[(0,o.jsx)(h,{align:"center",font:"textSmSemibold",children:e.depositAssetShareAddressError1}),(0,o.jsx)(h,{align:"center",font:"textMd",children:e.depositAssetShareAddressError2})]})}),(0,o.jsx)(x,{children:(0,o.jsx)(C,{onClick:p,children:e.close})})]})}),j=m.default.memo(n=>{let e=W(n);return(0,o.jsx)(Y,{...e})}),Co=j;export{Co as default};
//# sourceMappingURL=DepositAddressPage-4VFQ36WU.js.map
