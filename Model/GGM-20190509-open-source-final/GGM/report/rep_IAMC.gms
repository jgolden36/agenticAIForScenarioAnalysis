*Create report for IIASA platform
set       taux2(cn) "Selected traders reported separately"                     /NOR,RUS,DZA,QAT,USA/
          taux3(cn) "Need a set without RUS which is both region and country"  /NOR,    DZA,QAT,USA/
;

*Trade between regions
rep_IAMC_supply('GGM','%case%',rro,rri,yrep)=          sum((t,n,d)$(map_cn_rgn(t,rro) AND map_n_rgn(n,rri)),Q_S.l(t,n,d,yrep)*mcmd2bcm(d));

*Trade by specific traders "taux2"
rep_IAMC_supply('GGM','%case%',t,  rri,yrep)$taux2(t)= sum((n,d)$  (                      map_n_rgn(n,rri)),Q_S.l(t,n,d,yrep)*mcmd2bcm(d));

*Substract trade from specific traders from regional trade values to eliminate double counting
rep_IAMC_supply('GGM','%case%',rro,rri,yrep)=rep_IAMC_supply('GGM','%case%',rro,rri,yrep)-  sum(taux3$map_cn_rgn(taux3,rro),rep_IAMC_supply('GGM','%case%',taux3,rri,yrep));


*Other values for IAMC report:
rep_IAMC('GGM','%case%',cn,'prod', yrep)=  sum((t,n,r,d) $map_n_cn(n,cn), Q_P.l(t,n,r,d,yrep)*mcmd2bcm(d));
rep_IAMC('GGM','%case%',cn,'cons', yrep)=  sum((t,n,d)   $map_n_cn(n,cn), Q_S.l(t,n,d,yrep)  *mcmd2bcm(d));
rep_IAMC('GGM','%case%',cn,'stor', yrep)=  sum((t,n,w,d) $map_n_cn(n,cn), F_X.l(t,n,w,d,yrep)*mcmd2bcm(d));
rep_IAMC('GGM','%case%',cn,'price',yrep)$(rep_IAMC('GGM','%case%',cn,'cons',yrep)>0.1)=sum((n,d)$map_n_cn(n,cn), price(n,d,yrep)*cons(n,d,yrep)*mcmd2bcm(d))/rep_IAMC('GGM','%case%',cn,'cons',yrep);

rep_IAMC('GGM','%case%',cn,'pipe+',yrep)= sum((t,ap,n,d)$(map_n_cn(n,cn) AND a_e(ap,n) AND NOT is_same_cn(ap)), F_A.l(t,ap,d,yrep)*(1-l_a(ap))*mcmd2bcm(d));
rep_IAMC('GGM','%case%',cn,'LNG+', yrep)= sum((t,ar,n,d)$(map_n_cn(n,cn) AND a_e(ar,n)), F_A.l(t,ar,d,yrep)*(1-l_a(ar))*mcmd2bcm(d));

rep_IAMC('GGM','%case%',cn,'pipe-',yrep)=-sum((t,ap,n,d)$(map_n_cn(n,cn) AND a_s(ap,n) AND NOT is_same_cn(ap)), F_A.l(t,ap,d,yrep)            *mcmd2bcm(d));
rep_IAMC('GGM','%case%',cn,'LNG-', yrep)=-sum((t,al,n,d)$(map_n_cn(n,cn) AND a_s(al,n)), F_A.l(t,al,d,yrep)            *mcmd2bcm(d));

rep_IAMC('GGM','%case%',cn,'trade+',yrep)=rep_IAMC('GGM','%case%',cn,'pipe+',yrep)+rep_IAMC('GGM','%case%',cn,'LNG+',yrep);
rep_IAMC('GGM','%case%',cn,'trade-',yrep)=rep_IAMC('GGM','%case%',cn,'pipe-',yrep)+rep_IAMC('GGM','%case%',cn,'LNG-',yrep);

rep_IAMC('GGM','%case%',cn,'pipe', yrep)= rep_IAMC('GGM','%case%',cn,'pipe+',yrep)+ rep_IAMC('GGM','%case%',cn,'pipe-',yrep);
rep_IAMC('GGM','%case%',cn,'LNG',  yrep)= rep_IAMC('GGM','%case%',cn,'LNG+',yrep)+  rep_IAMC('GGM','%case%',cn,'LNG-',yrep);
rep_IAMC('GGM','%case%',cn,'trade',yrep)= rep_IAMC('GGM','%case%',cn,'trade+',yrep)+rep_IAMC('GGM','%case%',cn,'trade-',yrep);

rep_IAMC('GGM','%case%',cn,'capexog-P+',yrep)= sum((ap,n)$(map_n_cn(n,cn) AND a_e(ap,n) AND NOT is_same_cn(ap)),  cap_a(ap,yrep)   *(1-l_a(ap)))*.365;
rep_IAMC('GGM','%case%',cn,'capexog-P-',yrep)= sum((ap,n)$(map_n_cn(n,cn) AND a_s(ap,n) AND NOT is_same_cn(ap)),  cap_a(ap,yrep)               )*.365;
rep_IAMC('GGM','%case%',cn,'capexog-R', yrep)= sum((ar,n)$(map_n_cn(n,cn) AND a_e(ar,n)),  cap_a(ar,yrep)   *(1-l_a(ar)))*.365;
rep_IAMC('GGM','%case%',cn,'capexog-L', yrep)= sum((al,n)$(map_n_cn(n,cn) AND a_s(al,n)),  cap_a(al,yrep)               )*.365;
rep_IAMC('GGM','%case%',cn,'capexog-WG',yrep)= sum((n,w)$  map_n_cn(n,cn),                 cap_w(n,w,yrep)              )*.183/days_d('L');

rep_IAMC('GGM','%case%',cn,'expans-P+',yrep)=  sum((ap,n)$(map_n_cn(n,cn) AND a_e(ap,n) AND NOT is_same_cn(ap)),  d_a.l(ap,yrep)   *(1-l_a(ap)))*.365;
rep_IAMC('GGM','%case%',cn,'expans-P-',yrep)=  sum((ap,n)$(map_n_cn(n,cn) AND a_s(ap,n) AND NOT is_same_cn(ap)),  d_a.l(ap,yrep)               )*.365;
rep_IAMC('GGM','%case%',cn,'expans-R', yrep)=  sum((ar,n)$(map_n_cn(n,cn) AND a_s(ar,n)),  d_a.l(ar,yrep)   *(1-l_a(ar)))*.365;
rep_IAMC('GGM','%case%',cn,'expans-L', yrep)=  sum((al,n)$(map_n_cn(n,cn) AND a_s(al,n)),  d_a.l(al,yrep)               )*.365;
rep_IAMC('GGM','%case%',cn,'expans-WG',yrep)=  sum((n,w)$  map_n_cn(n,cn),                 d_w.l(n,w,yrep)              )*.183/days_d('L');

rep_IAMC('GGM','%case%',cn,'captot-P+',yrep)=  rep_IAMC('GGM','%case%',cn,'capexog-P+',yrep)+sum(y$(ORD(y)<ORD(yrep)),rep_IAMC('GGM','%case%',cn,'expans-P+',y));
rep_IAMC('GGM','%case%',cn,'captot-P-',yrep)=  rep_IAMC('GGM','%case%',cn,'capexog-P-',yrep)+sum(y$(ORD(y)<ORD(yrep)),rep_IAMC('GGM','%case%',cn,'expans-P-',y));
rep_IAMC('GGM','%case%',cn,'captot-R', yrep)=  rep_IAMC('GGM','%case%',cn,'capexog-R', yrep)+sum(y$(ORD(y)<ORD(yrep)),rep_IAMC('GGM','%case%',cn,'expans-R', y));
rep_IAMC('GGM','%case%',cn,'captot-L', yrep)=  rep_IAMC('GGM','%case%',cn,'capexog-L', yrep)+sum(y$(ORD(y)<ORD(yrep)),rep_IAMC('GGM','%case%',cn,'expans-L', y));
rep_IAMC('GGM','%case%',cn,'captot-WG',yrep)=  rep_IAMC('GGM','%case%',cn,'capexog-WG',yrep)+sum(y$(ORD(y)<ORD(yrep)),rep_IAMC('GGM','%case%',cn,'expans-WG',y));

rep_IAMC('GGM','%case%',cn,'util-P+',yrep)$(rep_IAMC('GGM','%case%',cn,'captot-P+',yrep)>0.1)= rep_IAMC('GGM','%case%',cn,'pipe+',yrep)/rep_IAMC('GGM','%case%',cn,'captot-P+',yrep);
rep_IAMC('GGM','%case%',cn,'util-P-',yrep)$(rep_IAMC('GGM','%case%',cn,'captot-P-',yrep)>0.1)=-rep_IAMC('GGM','%case%',cn,'pipe-',yrep)/rep_IAMC('GGM','%case%',cn,'captot-P-',yrep);
rep_IAMC('GGM','%case%',cn,'util-R', yrep)$(rep_IAMC('GGM','%case%',cn,'captot-R',yrep) >0.1)= rep_IAMC('GGM','%case%',cn,'LNG+',yrep)/ rep_IAMC('GGM','%case%',cn,'captot-R',yrep);
rep_IAMC('GGM','%case%',cn,'util-L', yrep)$(rep_IAMC('GGM','%case%',cn,'captot-L',yrep) >0.1)=-rep_IAMC('GGM','%case%',cn,'LNG-',yrep)/ rep_IAMC('GGM','%case%',cn,'captot-L',yrep);
rep_IAMC('GGM','%case%',cn,'util-WG',yrep)$(rep_IAMC('GGM','%case%',cn,'captot-WG',yrep)>0.1)= rep_IAMC('GGM','%case%',cn,'stor',yrep)/ rep_IAMC('GGM','%case%',cn,'captot-WG',yrep);

