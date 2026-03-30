*Create intermediate results for all arcs:
LOOP{(rgn_o,cno,n_o,rgn_i,cni,n_i,a)$(map_n_cn_rgn(n_o,cno,rgn_o) AND map_n_cn_rgn(n_i,cni,rgn_i) AND map_a_n_n(a,n_o,n_i)),

  rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'capexog',yrep)$(NOT is_v(a))= .365*cap_a(a,yrep);
  rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'expans',yrep)$(NOT is_v(a))=  .365*d_a.l(a,yrep);
  rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'delmax',yrep)$(NOT is_v(a))=  .365*d_a_max(a,yrep);
  rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'expcum',yrep)$(NOT is_v(a))=  .365*sum(y2$(ORD(y2)<ORD(yrep)), d_a.l(a,y2));
  rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'captot',yrep)=                rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'capexog',yrep)+rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'expcum',yrep);
  rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'capnet',yrep)=                rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'captot',yrep)*(1-l_a(a));
  rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'usage-L',yrep)$(NOT is_v(a))= .365*sum((t),F_A.l(t,a,'L',yrep));
  rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'usage-H',yrep)$(NOT is_v(a))= .365*sum((t),F_A.l(t,a,'H',yrep));
  rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'usage-P',yrep)$(NOT is_v(a))= .365*sum((t),F_A.l(t,a,'P',yrep));
  rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'usage',yrep)$(NOT is_v(a))=   sum((t,d),F_A.l(t,a,d,yrep)*mcmd2bcm(d));
  rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'util%',yrep)=                 rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'usage',yrep)/(rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a,'captot',yrep)+1E-4);
}
;
*Create pipeline specific report:
LOOP{(rgn_o,cno,rgn_i,cni)$(map_cn_rgn(cno,rgn_o) AND map_cn_rgn(cni,rgn_i)),

  rep_infra_pipe('%case%',rgn_o,cno,rgn_i,cni, aaux1, yrep)= sum((a,n_o,n_i)$(is_pip(a) AND map_a_n_n(a,n_o,n_i) AND map_n_cn(n_o,cno) AND map_n_cn(n_i,cni)), rep_arc('%case%',rgn_o,cno,n_o,rgn_i,cni,n_i,a, aaux1,yrep));
  rep_infra_pipe('%case%',rgn_o,cno,rgn_i,cni,'util%',yrep)= rep_infra_pipe('%case%',rgn_o,cno,rgn_i,cni,'usage',yrep)/(rep_infra_pipe('%case%',rgn_o,cno,rgn_i,cni,'captot',yrep)+1E-4);
}
;
*Create liquefaction and regasification specific reports:
LOOP{(rgn,cn)$(map_cn_rgn(cn,rgn)),

  rep_infra_liq(  '%case%',rgn,cn,aaux1,yrep)= sum((a,n_o,n_i)$(is_liq(a) AND map_a_n_n(a,n_o,n_i) AND map_n_cn(n_o,cn) AND map_n_cn(n_i,cn)), rep_arc('%case%', rgn, cn,n_o,'LIQ',cn,n_i,a,aaux1,yrep));
  rep_infra_regas('%case%',rgn,cn,aaux1,yrep)= sum((a,n_o,n_i)$(is_reg(a) AND map_a_n_n(a,n_o,n_i) AND map_n_cn(n_o,cn) AND map_n_cn(n_i,cn)), rep_arc('%case%','REG',cn,n_o, rgn, cn,n_i,a,aaux1,yrep));

  rep_infra_liq  ('%case%',rgn,cn,'util%',yrep)= rep_infra_liq  ('%case%',rgn,cn,'usage',yrep)/(rep_infra_liq  ('%case%',rgn,cn,'captot',yrep)+1E-4);
  rep_infra_regas('%case%',rgn,cn,'util%',yrep)= rep_infra_regas('%case%',rgn,cn,'usage',yrep)/(rep_infra_regas('%case%',rgn,cn,'captot',yrep)+1E-4);
};

*Create storage report:
LOOP{(rgn,cn,w)$(map_cn_rgn(cn,rgn) AND map_w_cn(w,cn)),

  rep_infra_stor('%case%',rgn,cn,w,'WG','capexog',yrep)= (183/days_d('L'))*sum(n$map_n_cn(n,cn),cap_w  (n,w,yrep));
  rep_infra_stor('%case%',rgn,cn,w,'WG','expans',yrep)=  (183/days_d('L'))*sum(n$map_n_cn(n,cn),d_w.l  (n,w,yrep));
  rep_infra_stor('%case%',rgn,cn,w,'WG','delmax',yrep)=  (183/days_d('L'))*sum(n$map_n_cn(n,cn),d_w_max(n,w,yrep));
  rep_infra_stor('%case%',rgn,cn,w,'WG','expcum',yrep)=  (183/days_d('L'))*sum((n,y2)$(map_n_cn(n,cn) AND ORD(y2)<ORD(yrep)), d_w.l(n,w, y2));
  rep_infra_stor('%case%',rgn,cn,w,'WG','captot',yrep)=   rep_infra_stor('%case%',rgn,cn,w,'WG','capexog',yrep) + rep_infra_stor('%case%',rgn,cn,w,'WG','expcum',yrep);
  rep_infra_stor('%case%',rgn,cn,w,'WG','usage',yrep)=   (183/days_d('L'))*sum((t,n,d)$map_n_cn(n,cn), days_d(d)*F_X.l(t,n,w,d,yrep));
  rep_infra_stor('%case%',rgn,cn,w,'WG','util%',yrep)=    rep_infra_stor('%case%',rgn,cn,w,'WG','usage',yrep)/(rep_infra_stor('%case%',rgn,cn,w,'WG','captot',yrep)+1E-4);

  rep_infra_stor('%case%',rgn,cn,w,'Extr','capexog',yrep)=  sum(n$map_n_cn(n,cn),cap_x(n,w,yrep));
  rep_infra_stor('%case%',rgn,cn,w,'Extr','expans',yrep)=   sum(n$map_n_cn(n,cn),d_x.l(n,w,yrep));
  rep_infra_stor('%case%',rgn,cn,w,'Extr','delmax',yrep)=   sum(n$map_n_cn(n,cn),d_x_max(n,w,yrep));
  rep_infra_stor('%case%',rgn,cn,w,'Extr','expcum',yrep)=   sum((n,y2)$(map_n_cn(n,cn) AND ORD(y2)<ORD(yrep)), d_x.l(n,w,y2));
  rep_infra_stor('%case%',rgn,cn,w,'Extr','captot',yrep)=   rep_infra_stor('%case%',rgn,cn,w,'Extr','capexog',yrep) + rep_infra_stor('%case%',rgn,cn,w,'Extr','expcum',yrep);
  rep_infra_stor('%case%',rgn,cn,w,'Extr','usage-L',yrep)=  SUM((t,n)$map_n_cn(n,cn), (F_X.l(t,n,w,'L',yrep)-F_I.l(t,n,w,'L',yrep)));
  rep_infra_stor('%case%',rgn,cn,w,'Extr','usage-H',yrep)=  SUM((t,n)$map_n_cn(n,cn), (F_X.l(t,n,w,'H',yrep)-F_I.l(t,n,w,'H',yrep)));
  rep_infra_stor('%case%',rgn,cn,w,'Extr','usage-P',yrep)=  SUM((t,n)$map_n_cn(n,cn), (F_X.l(t,n,w,'P',yrep)-F_I.l(t,n,w,'P',yrep)));
};
