SETS
           n_p(n)              "Nodes with production"
           r                   "Types of production resources"
;

PARAMETERS
           cap_p(n,r,y)        "Production capacity (Mcm per day)"
           cap_p_cal           "Prod cap calibration - including the resource shares in cap_p_cal(n,r)"
           cost_p_cal          "Prod cost calibration"
           cost_pl(n,r,y)      "constant   prod cost term: cost_pl in marg = cost_pl+ cost_pq * q (EUR/kcm)"
           cost_pq(n,r,y)      "Increasing prod cost term: cost_pq in marg = cost_pl+ cost_pq * q (EUR/kcm)"
           dat_proj_eu         "EU prod cons and sector share reference projections"
           dat_proj_weo        "Rest of World prod and cons reference projections"
           is_np(n)            "Indicator for node having production"
           p_grow(n,y)         "Production cost inflator"
           ref_p(n,y)          "prod ref (Mcm per day)"
           ref_p_glob(y)       "Global reference production - needed for projections gap, see in_cons.gms ref_c_glob and c_adj"
;

*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*-*              READ PROJECTIONS VALUES
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
$gdxin gdx\%data%_%case%_proj
$load dat_proj_eu, dat_proj_weo
;

SET paux1 "Auxiliary set" /prod,cons/;

dat_n(n,cn,rgn, paux1,y)= dat_proj_weo('%WEO%',  rgn, n,cn,paux1,y);
dat_n(n,cn,'EU',paux1,y)= dat_proj_eu('%SETNav%','EU',cn,n,paux1,y);

*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*-*              LOAD CALIBRATION VALUES
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
$gdxin gdx\%data%_%case%_calib
$load    cap_p_cal, cost_p_cal
;

*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*-*              LOAD AND ASSIGN SETS AND PARAMETERS
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
$gdxin gdx\%data%
$load    r
;

n_p(n)$SUM((cn,rgn), dat_n(n,cn,rgn,'Node','P')) = n(n);        /* prod nodes */
is_np(n_p)=1;

p_grow(n,y)= power(1+cost_infl, step_y*(ORD(y)-1));

ref_p(n_p,y) = SUM((cn,rgn),dat_n(n_p,cn,rgn,'Prod',y))/.365;    /* ref prod in mcm/day */
cap_p(n_p,r,y) = ref_p(n_p,y)*cap_p_cal(n_p,r)*cap_p_cal(n_p,y);
cost_pl(n_p,r,y) = cost_p_cal(n_p,'base','cost')*cost_p_cal(n_p,r,'c')*cost_p_cal(n_p,'y',y)*p_grow(n_p,y);
cost_pq(n_p,r,y)$ref_p(n_p,y) = cost_p_cal(n_p,'base','cost')*cost_p_cal(n_p,r,'q')*cost_p_cal(n_p,'y',y)*p_grow(n_p,y)/ref_p(n_p,y)/cap_p_cal(n_p,r)/cap_p_cal(n_p,y);

*Needed to account for global losses and projections mismatch, see specification above
ref_p_glob(y)=round(sum(n_p,ref_p(n_p,y))*.365,1);
