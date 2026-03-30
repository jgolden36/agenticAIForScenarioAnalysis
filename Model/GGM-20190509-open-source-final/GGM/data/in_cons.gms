SETS
          k                      "Demand sectors"
          n_c(n)                 "Nodes of consuming countries"
;

ALIAS (k,k2);

PARAMETERS
          c_adj(n,y)             "Adjustment to account for European trade mismatches WEO vs SET-Nav"
          dat_c(n,*)             "Consumption data in Mcm/d"
          dat_c_k(n,k,y)         "Yearly sector shares"
          dat_d                  "Relative seasonal demand load"
          dat_pr(n,d)            "Seasonal price in the base year EUR/kcm"
          dssi(n,k,d,y)          "DemSectSeasIntTunedYr:  int of sector = P_T *(1-1/elast) EUR/Mcm/d"
          dssl(n,k,d,y)          "DemSectSeasLoadTunedYr: seasonal sector consumption in Mcm/d"
          dsss(n,k,d,y)          "DemSectSeasSlpTunedYr:  slp of sector = P_T / ((-1)*elast*Q_T) EUR/Mcm/Mcm/d"
          int(n,d,y)             "Demand curve intercept (EUR/Mcm/day)"
          l_glob                 "Global loss rate because consumption is lower than production"
          pr_cal                 "Price calibration"
          pr_elast(k)            "Price-elasticity of demand"
          pr_grow(n,y)           "Price growth"
          pr_infl                "Price inflator - increase in willingness to pay"
          ref_c(n,y)             "Reference demand (Mcm/day)"
          ref_c_d(n,d,y)         "Reference demand seasonal (Mcm/day)"
          ref_c_glob(y)          "Reference global demand - needed for projections gap European trade WEO vs SET-Nav"
          ref_pr(n,d,y)          "Reference price seasonal (EUR/kcm)"
          ref_t(n,y)             "Reference trade balance"
          slp(n,d,y)             "Demand curve slope (EUR/Mcm/Mcm/day)"
;
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*-*              LOAD CALIBRATION VALUES
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
$gdxin gdx\%data%_%case%_calib
$load    pr_cal, l_glob
;
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*-*              LOAD AND ASSIGN SETS AND PARAMETERS
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
$gdxin gdx\%data%
$load    k
;

n_c(N) $SUM((cn,rgn), dat_n(n,cn,rgn,'Node','C')) = n(n);                       /* cons nodes */
*is_nc(n_c) = 1;
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*-*              SEASONS AND SECTORS
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
$gdxin gdx\%data%_%case%_proj
$load dat_d
;
dat_c_k(n,k,y)=dat_proj_eu('%SETNav%','EU',n,n,k,y);                            /*In Europe country names equal node names*/

loop{(n_c,cn,rgn)$(map_n_cn_rgn(n_c,cn,rgn) AND NOT map_n_cn_rgn(n_c,cn,'EU')),
  dat_d(n_c,d)=      dat_n(n_c,cn,rgn,'Cons',d);
  dat_c_k(n_c,k,y) = dat_n(n_c,cn,rgn,'Cons',k);
};

dat_c_k(n_c,k,y) = max(dat_c_k(n_c,k,y),0.001/0.999);
dat_c_k(n_c,k,y) = dat_c_k(n_c,k,y)/SUM(k2,dat_c_k(n_c,k2,y));                  /* ensure shares add up to 1 */

pr_elast(k) = dat_oth(k);
pr_infl = dat_oth('PriceInfl');

dat_c(n_c,y) = SUM((cn,rgn), dat_n(n_c,cn,rgn,'Cons',y))/.365;                  /* cons in mcm/d */
dat_c(n_c,y) = max(dat_c(n_c,y),0.1);

ref_c_glob(y)=round(sum((n_c),dat_c(n_c,y))*.365,1);
c_adj(n_c,y)=1;
c_adj(n_c,y)$(NOT map_n_rgn(n_c,'EU') AND NOT map_n_rgn(n_c,'ROE')) = ref_p_glob(y)/ref_c_glob(y);


dat_c(n_c,y)$(NOT map_n_rgn(n_c,'EU') AND NOT map_n_rgn(n_c,'ROE')) = (1-l_glob(y))*dat_c(n_c,y);        /* losses in global supply chain */
dat_pr(n_c,d) = pr_cal(n_c,d)*pr_cal(n_c,'price');                                                       /* seasonal price */
pr_grow(n_c,y) = pr_cal(n_c,y)*power(1 + pr_infl, step_y*(ORD(y)-1));                                    /* calibrated price growth */

*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-***
*       CALCULATION OF CALIBRATED DEMAND CURVE
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-***
ref_pr(n_c,d,y) = dat_pr(n_c,d)*pr_grow(n_c,y);              /* ref price */

*Seasonal sector load: country load * sector share * seasonality
dssl(n_c,k,d,y) = dat_c(n_c,y)*dat_c_k(n_c,k,y)*dat_d(n_c,d);
dssi(n_c,k,d,y)$dssl(n_c,k,d,y) = ref_pr(n_c,d,y)*(1-1/pr_elast(k));                        /* P * (1-1/elas) */
dsss(n_c,k,d,y)$dssl(n_c,k,d,y) = ref_pr(n_c,d,y)/(-pr_elast(k)*dssl(n_c,k,d,y));           /* P / (-elas*Q)  */

ref_c(n_c,y) = dat_c(n_c,y)*c_adj(n_c,y);                    /* ref cons */
ref_c_d(n_c,d,y) = ref_c(n_c,y)*dat_d(n_c,d);                /* ref cons by season by year*/

slp(n_c,d,y)$(ref_c_d(n_c,d,y)) = (1/SUM(k$dssl(n_c,k,d,y),1/dsss(n_c,k,d,y)));        /* slope */
int(n_c,d,y)$ref_c_d(n_c,d,y) = slp(n_c,d,y) * SUM(k$dssl(n_c,k,d,y),
                                    dssi(n_c,k,d,y)/dsss(n_c,k,d,y));                  /* intercept */
