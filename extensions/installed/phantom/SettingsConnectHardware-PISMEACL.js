import{a as N,c as F,d as G,g as I}from"./chunk-TSJ6PMEV.js";import{a as x}from"./chunk-SAJWOXAM.js";import"./chunk-QYKSQVW7.js";import{a as D}from"./chunk-YD22W6KZ.js";import"./chunk-HGXMWG3Q.js";import"./chunk-BGASWDKC.js";import"./chunk-2VVCGFMA.js";import"./chunk-3YVUKAA2.js";import"./chunk-DUJ52DSR.js";import"./chunk-KBNJM4OI.js";import"./chunk-SOGKDHYT.js";import"./chunk-K3AOJOH2.js";import"./chunk-K7BQY6A2.js";import"./chunk-QS2ATNL5.js";import"./chunk-GSQXVZTV.js";import{a as L}from"./chunk-ZSNMIKX2.js";import"./chunk-DOPYNHEM.js";import"./chunk-5EDJ4LKT.js";import"./chunk-P6I4TB7G.js";import"./chunk-Y6HGW6N6.js";import"./chunk-FFXJHUIX.js";import"./chunk-PA2NRDYY.js";import"./chunk-DAY5B7BQ.js";import"./chunk-BYF7EDTR.js";import"./chunk-GC7AVPC5.js";import"./chunk-WPYMVR7W.js";import"./chunk-AKMCTSIB.js";import{a as C}from"./chunk-WY4XLJUZ.js";import"./chunk-RMX4JBML.js";import"./chunk-YX7XP3TR.js";import"./chunk-NY2WZVO4.js";import"./chunk-YJH5PDWC.js";import"./chunk-4DKS3LI2.js";import"./chunk-ANAHPWN4.js";import"./chunk-MRETTCTD.js";import"./chunk-J7X5PYFL.js";import"./chunk-GZNR77BH.js";import"./chunk-EOII3ZM4.js";import"./chunk-DMM54ENI.js";import"./chunk-4AQPJCXC.js";import"./chunk-MQ2XFQME.js";import"./chunk-NGKKVVYY.js";import"./chunk-YQNIGRQS.js";import"./chunk-TO2UYJWM.js";import{q as _}from"./chunk-7ALUQBE3.js";import{c as s}from"./chunk-5G7Z362D.js";import{a as y}from"./chunk-QQJPKFTO.js";import"./chunk-HRSMUG5A.js";import"./chunk-WMGJCMXX.js";import"./chunk-KS7AKYDM.js";import"./chunk-V5YF4BWK.js";import"./chunk-UMKDODOO.js";import"./chunk-QNZ4IKWZ.js";import"./chunk-VR544T5V.js";import"./chunk-VD23BAEF.js";import"./chunk-QTITVYLP.js";import"./chunk-FRT7J7NM.js";import"./chunk-PN6ZWBOX.js";import"./chunk-UPPQC44E.js";import"./chunk-OJPBMZQC.js";import"./chunk-IEJ4AK6Z.js";import"./chunk-CYENH7PC.js";import{A as O,s as $}from"./chunk-TRFSSUYO.js";import"./chunk-HOPOVBCB.js";import"./chunk-BIP7RNCZ.js";import"./chunk-WXTMIUXL.js";import"./chunk-XGDWTOSO.js";import"./chunk-YNSFZ5VB.js";import{$b as T,C as E,U as P,Xb as R,e as z,f as u,sb as e}from"./chunk-4ZV6PABP.js";import"./chunk-V2YZXVTC.js";import"./chunk-PPRUN2KR.js";import"./chunk-U7OZEJ4F.js";import"./chunk-ZRGHR2IN.js";import{a as g,g as l,i as n,n as i}from"./chunk-TSHWMJEM.js";n();i();var f=l(z(),1);n();i();n();i();var M=s(C)`
  cursor: pointer;
  width: 24px;
  height: 24px;
  transition: background-color 200ms ease;
  background-color: ${t=>t.$isExpanded?e.colors.legacy.black:e.colors.legacy.elementAccent} !important;
  :hover {
    background-color: ${e.colors.legacy.gray};
    svg {
      fill: white;
    }
  }
  svg {
    fill: ${t=>t.$isExpanded?"white":e.colors.legacy.textDiminished};
    transition: fill 200ms ease;
    position: relative;
    ${t=>t.top?`top: ${t.top}px;`:""}
    ${t=>t.right?`right: ${t.right}px;`:""}
  }
`;var o=l(u(),1),K=s(L).attrs({justify:"space-between"})`
  background-color: ${e.colors.legacy.areaBase};
  padding: 10px 16px;
  border-bottom: 1px solid ${e.colors.legacy.borderDiminished};
  height: 46px;
  opacity: ${t=>t.opacity??"1"};
`,Q=s.div`
  display: flex;
  margin-left: 10px;
  > * {
    margin-right: 10px;
  }
`,W=s.div`
  width: 24px;
  height: 24px;
`,X=g(({onBackClick:t,totalSteps:c,currentStepIndex:d,isHidden:m,showBackButtonOnFirstStep:r,showBackButton:S=!0})=>(0,o.jsxs)(K,{opacity:m?0:1,children:[S&&(r||d!==0)?(0,o.jsx)(M,{right:1,onClick:t,children:(0,o.jsx)(_,{})}):(0,o.jsx)(W,{}),(0,o.jsx)(Q,{children:E(c).map(p=>{let h=p<=d?e.colors.legacy.spotBase:e.colors.legacy.elementAccent;return(0,o.jsx)(C,{diameter:12,color:h},p)})}),(0,o.jsx)(W,{})]}),"StepHeader");n();i();var a=l(u(),1),Z=g(()=>{let{mutateAsync:t}=O(),{hardwareStepStack:c,pushStep:d,popStep:m,currentStep:r,setOnConnectHardwareAccounts:S,setOnConnectHardwareDone:b,setExistingAccounts:p}=N(),{data:h=[],isFetched:H,isError:v}=$(),w=P(c,(k,q)=>k?.length===q.length),J=c.length>(w??[]).length,B=w?.length===0,U={initial:{x:B?0:J?150:-150,opacity:B?1:0},animate:{x:0,opacity:1},exit:{opacity:0},transition:{duration:.2}},V=(0,f.useCallback)(()=>{r()?.props.preventBack||(r()?.props.onBackCallback&&r()?.props.onBackCallback?.(),m())},[r,m]);return D(()=>{S(async k=>{await t(k),await y.set(x,!await y.get(x))}),b(()=>self.close()),d((0,a.jsx)(I,{}))},c.length===0),(0,f.useEffect)(()=>{p({data:h,isFetched:H,isError:v})},[h,H,v,p]),(0,a.jsxs)(F,{children:[(0,a.jsx)(X,{totalSteps:3,onBackClick:V,showBackButton:!r()?.props.preventBack,currentStepIndex:c.length-1}),(0,a.jsx)(R,{mode:"wait",children:(0,a.jsx)(T.div,{style:{display:"flex",flexGrow:1},...U,children:(0,a.jsx)(G,{children:r()})},`${c.length}_${w?.length}`)})]})},"SettingsConnectHardware"),Tt=Z;export{Tt as default};
//# sourceMappingURL=SettingsConnectHardware-PISMEACL.js.map
