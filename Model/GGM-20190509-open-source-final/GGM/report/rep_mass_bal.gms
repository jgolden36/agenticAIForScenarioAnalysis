*Seasonal node level mass balance (mcm/d)
LOOP{(n,cn,rgn)$(map_n_cn_rgn(n,cn,rgn) AND rgn_rep(rgn)),
  rep_mass_bal('%case%',rgn,cn,n,yrep,d,'+','prod') = sum((t,r),            Q_P.l(t,n,r,d,yrep));
  rep_mass_bal('%case%',rgn,cn,n,yrep,d,'+','pipe') = sum((t,ap)$a_e(ap,n), F_A.l(t,ap,d,yrep)*(1-l_a(ap)));
  rep_mass_bal('%case%',rgn,cn,n,yrep,d,'+','LNG') =  sum((t,ar)$a_e(ar,n), F_A.l(t,ar,d,yrep)*(1-l_a(ar)));
  rep_mass_bal('%case%',rgn,cn,n,yrep,d,'+','stor') = sum((t,w),            F_X.l(t,n,w,d,yrep));

  rep_mass_bal('%case%',rgn,cn,n,yrep,d,'-','cons') = cons(n,d,yrep);
  rep_mass_bal('%case%',rgn,cn,n,yrep,d,'-','pipe') = sum((t,ap)$a_s(ap,n), F_A.l(t,ap,d,yrep));
  rep_mass_bal('%case%',rgn,cn,n,yrep,d,'-','LNG') =  sum((t,al)$a_s(al,n), F_A.l(t,al,d,yrep));
  rep_mass_bal('%case%',rgn,cn,n,yrep,d,'-','stor') = sum((t,w),            F_I.l(t,n,w,d,yrep));

  rep_mass_bal('%case%',rgn,cn,n,yrep,d,'0','price')= price(n,d,yrep);
  rep_mass_bal('%case%',rgn,cn,n,yrep,d,'+','TOT') = sum(maux,rep_mass_bal('%case%',rgn,cn,n,yrep,d,'+',maux));
  rep_mass_bal('%case%',rgn,cn,n,yrep,d,'-','TOT') = sum(maux,rep_mass_bal('%case%',rgn,cn,n,yrep,d,'-',maux));
  rep_mass_bal('%case%',rgn,cn,n,yrep,d,'0','MC-R3')$rep_mass_bal('%case%',rgn,cn,n,yrep,d,'+','prod')= cost_pl(n,'R3',yrep)+ cost_pq(n,'R3',yrep)*sum(t,Q_P.l(t,n,'R3',d,yrep));
};

*Yearly country level mass balance (bcm)
rep_mass_bal('%case%',rgn,cn,cn,yrep,'y','+',mauxin)= sum((n,d)$map_n_cn(n,cn),mcmd2bcm(d)*rep_mass_bal('%case%',rgn,cn,n,yrep,d,'+',mauxin));
rep_mass_bal('%case%',rgn,cn,cn,yrep,'y','-',mauxout)=sum((n,d)$map_n_cn(n,cn),mcmd2bcm(d)*rep_mass_bal('%case%',rgn,cn,n,yrep,d,'-',mauxout));

rep_mass_bal('%case%',rgn,cn,cn,yrep,'y','0','price')$rep_mass_bal('%case%',rgn,cn,cn,yrep,'y','-','cons')=sum((n,d)$map_n_cn(n,cn), price(n,d,yrep)*cons(n,d,yrep)*mcmd2bcm(d))/sum((n,d)$map_n_cn(n,cn), cons(n,d,yrep)*mcmd2bcm(d));

