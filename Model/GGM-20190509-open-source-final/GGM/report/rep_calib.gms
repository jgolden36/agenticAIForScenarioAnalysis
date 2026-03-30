*Create calibration reports. I.e., deviations between reference values and model outcomes.
*Relatively large deviations can be filtered out in Excel to guide calibration

*Auxiliary node level report
LOOP{(n,cn,rgn)$(map_n_cn_rgn(n,cn,rgn) AND sum((maux2,yrep),ref_cal(maux2,n,yrep))),
*Seasonal values
  rep_cal_n('%case%',rgn,cn,n,yrep,d,'cons', 'out')=         cons(n,d,yrep)*   mcmd2bcm(d);
  rep_cal_n('%case%',rgn,cn,n,yrep,d,'cons', 'ref')=         ref_c_d(n,d,yrep)*mcmd2bcm(d);
  rep_cal_n('%case%',rgn,cn,n,yrep,d,'price','out')=         price(n,d,yrep);
  rep_cal_n('%case%',rgn,cn,n,yrep,d,'price','ref')=         ref_pr(n,d,yrep);
*Annual values
  rep_cal_n('%case%',rgn,cn,n,yrep,'y','prod','out')= SUM((t,r,d),  Q_P.l(t,n,r,d,yrep)*mcmd2bcm(d));
  rep_cal_n('%case%',rgn,cn,n,yrep,'y','cons','out')= SUM(d, cons(n,d,yrep) * mcmd2bcm(d));
  rep_cal_n('%case%',rgn,cn,n,yrep,'y','price','out')$SUM(d, cons(n,d,yrep)) = SUM(d,price(n,d,yrep)*cons(n,d,yrep)*mcmd2bcm(d))/rep_cal_n('%case%',rgn,cn,n,yrep,'y','cons','out');

  rep_cal_n('%case%',rgn,cn,n,yrep,'y',maux2,'ref')=         ref_cal(maux2,n,yrep);
*Compute deviations:
  rep_cal_n('%case%',rgn,cn,n,yrep,daux,maux2,'abs')= rep_cal_n('%case%',rgn,cn,n,yrep,daux,maux2,'out')-rep_cal_n('%case%',rgn,cn,n,yrep,daux,maux2,'ref');
  rep_cal_n('%case%',rgn,cn,n,yrep,daux,maux2,'rel')$ rep_cal_n('%case%',rgn,cn,n,yrep,daux,maux2,'ref')=rep_cal_n('%case%',rgn,cn,n,yrep,daux,maux2,'abs')/rep_cal_n('%case%',rgn,cn,n,yrep,daux,maux2,'ref');
};

*Country-level
rep_cal_cn('%case%',rgn,cn,yrep,maux3,calx) =  SUM( n$map_n_cn(n,cn), rep_cal_n('%case%',rgn,cn,n,yrep,'y',maux3,calx));
rep_cal_cn('%case%',rgn,cn,yrep,'trade',calx) = rep_cal_cn('%case%',rgn,cn,yrep,'prod',calx) - rep_cal_cn('%case%',rgn,cn,yrep,'cons',calx);

*Regional & global
rep_cal_rgn('%case%',rgn,    yrep,maux3,calx) = SUM((n,cn)$map_n_cn_rgn(n,cn,rgn),     rep_cal_n('%case%',rgn,cn,n,yrep,'y',maux3,calx));
rep_cal_rgn('%case%','world',yrep,maux3,calx) = SUM((n,cn,rgn)$map_n_cn_rgn(n,cn,rgn), rep_cal_n('%case%',rgn,cn,n,yrep,'y',maux3,calx));

*Compute relative deviations:
rep_cal_cn ('%case%',rgn,cn, yrep,maux3,'rel')$rep_cal_cn ('%case%',rgn,cn,yrep,maux3,'ref') =  rep_cal_cn ('%case%',rgn,cn, yrep,maux3,'abs')/rep_cal_cn ('%case%',rgn,cn, yrep,maux3,'ref');
rep_cal_rgn('%case%',rgn,    yrep,maux3,'rel')$rep_cal_rgn('%case%',rgn,   yrep,maux3,'ref') =  rep_cal_rgn('%case%',rgn,    yrep,maux3,'abs')/rep_cal_rgn('%case%',rgn,    yrep,maux3,'ref');
rep_cal_rgn('%case%','world',yrep,maux3,'rel') = rep_cal_rgn('%case%','world',yrep,maux3,'abs')/rep_cal_rgn('%case%','world',yrep,maux3,'ref');
