*Create report for geo_maps tool
set
    gaux "Geo maps auxiliary set"
         / prod,cons,trade,pipe,LNG
           expcum-P+,expcum-P-,expcum-L,expcum-R,expcum-WG,
           captot-P+,captot-P-,captot-L,captot-R,captot-WG
         /
;

LOOP{(y,cn,rgn)$(yrep(y) AND rgn_rep(rgn) AND map_cn_rgn(cn,rgn)),
  rep_geo_map('%case%',rgn,cn,y,'prod') =        SUM((t,n,r,d) $map_n_cn(n,cn),                Q_P.l(t,n,r,d,y)            *mcmd2bcm(d));
  rep_geo_map('%case%',rgn,cn,y,'cons') =        SUM((t,n,d)   $map_n_cn(n,cn),                Q_S.l(t,n,d,y)              *mcmd2bcm(d));
  rep_geo_map('%case%',rgn,cn,y,'pipe') =        SUM((t,ap,n,d)$(map_n_cn(n,cn) AND a_e(ap,n)), F_A.l(t,ap,d,y)*(1-l_a(ap))*mcmd2bcm(d))
                                                -SUM((t,ap,n,d)$(map_n_cn(n,cn) AND a_s(ap,n)), F_A.l(t,ap,d,y)            *mcmd2bcm(d));

  rep_geo_map('%case%',rgn,cn,y,'LNG') =         SUM((t,ar,n,d)$(map_n_cn(n,cn) AND a_e(ar,n)), F_A.l(t,ar,d,y)*(1-l_a(ar))*mcmd2bcm(d))
                                                -SUM((t,al,n,d)$(map_n_cn(n,cn) AND a_s(al,n)), F_A.l(t,al,d,y)            *mcmd2bcm(d));
  rep_geo_map('%case%',rgn,cn,y,'trade') =       rep_geo_map('%case%',rgn,cn,y,'pipe')+rep_geo_map('%case%',rgn,cn,y,'LNG');

  rep_geo_map('%case%',rgn,cn,y,'expcum-P+') =   SUM((ap,n)$(map_n_cn(n,cn) AND a_e(ap,n)),                SUM(y2$(ORD(y2)<ORD(y)), d_a.l(ap,y2)) *(1-l_a(ap)))*.365;
  rep_geo_map('%case%',rgn,cn,y,'expcum-R') =    SUM((ar,n)$(map_n_cn(n,cn) AND a_s(ar,n)),                SUM(y2$(ORD(y2)<ORD(y)), d_a.l(ar,y2)) *(1-l_a(ar)))*.365;

  rep_geo_map('%case%',rgn,cn,y,'captot-P+') =   SUM((ap,n)$(map_n_cn(n,cn) AND a_e(ap,n)), (cap_a(ap,y) + SUM(y2$(ORD(y2)<ORD(y)), d_a.l(ap,y2)))*(1-l_a(ap)))*.365;
  rep_geo_map('%case%',rgn,cn,y,'captot-R') =    SUM((ar,n)$(map_n_cn(n,cn) AND a_s(ar,n)), (cap_a(ar,y) + SUM(y2$(ORD(y2)<ORD(y)), d_a.l(ar,y2)))*(1-l_a(ar)))*.365;

  rep_geo_map('%case%',rgn,cn,y,'expcum-P-') =   SUM((ap,n)$(map_n_cn(n,cn) AND a_s(ap,n)),                SUM(y2$(ORD(y2)<ORD(y)), d_a.l(ap,y2))             )*.365;
  rep_geo_map('%case%',rgn,cn,y,'expcum-L') =    SUM((al,n)$(map_n_cn(n,cn) AND a_s(al,n)),                SUM(y2$(ORD(y2)<ORD(y)), d_a.l(al,y2))             )*.365;

  rep_geo_map('%case%',rgn,cn,y,'captot-P-') =   SUM((ap,n)$(map_n_cn(n,cn) AND a_s(ap,n)), (cap_a(ap,y) + SUM(y2$(ORD(y2)<ORD(y)), d_a.l(ap,y2)))            )*.365;
  rep_geo_map('%case%',rgn,cn,y,'captot-L') =    SUM((al,n)$(map_n_cn(n,cn) AND a_s(al,n)), (cap_a(al,y) + SUM(y2$(ORD(y2)<ORD(y)), d_a.l(al,y2)))            )*.365;

  rep_geo_map('%case%',rgn,cn,y,'expcum-WG') =   SUM((n,w)$map_n_cn(n,cn),                SUM(y2$(ORD(y2)<ORD(y)), d_w.l(n,w,y2)))*.183/days_d('L');
  rep_geo_map('%case%',rgn,cn,y,'captot-WG') =   SUM((n,w)$map_n_cn(n,cn), cap_w(n,w,y) + SUM(y2$(ORD(y2)<ORD(y)), d_w.l(n,w,y2)))*.183/days_d('L');

  rep_geo_trade('%case%',rro,t,rgn,cn,y)$map_cn_rgn(t,rro) = SUM((n,d)$map_n_cn(n,cn), Q_S.l(t,n,d,y)*mcmd2bcm(d));
};

*Make Norway its own region
rep_geo_trade('%case%','NOR','NOR',rgn,cn,y)=rep_geo_trade('%case%','ROE','NOR',rgn,cn,y);
rep_geo_map  ('%case%','NOR','NOR',y,gaux)=  rep_geo_map  ('%case%','ROE','NOR',y,gaux);

rep_geo_trade('%case%','ROE','NOR',rgn,cn,y)=0;
rep_geo_map  ('%case%','ROE','NOR',y,gaux)=  0;

*Delete domestic deliveries from trade flow report
rep_geo_trade('%case%',rgn,t,rgn,cn,y)=0;
rep_geo_trade('%case%','NOR','NOR','ROE','NOR',y)=0;
