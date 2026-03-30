SETS
          al(a)                  "Liquefaction arcs"
          ap(a)                  "Pipeline arcs"
          ar(a)                  "Regasification arcs"
          av(a)                  "(LNG) vessel arcs"
          n_l(n)                 "Liquefaction transit nodes of liquefying countries"
          n_r(n)                 "Regasification transit nodes of regasifying countries"
;

PARAMETERS
          a_e(a,n)               "Indicator for End node of Arc"
          a_s(a,n)               "Indicator for Start node of Arc"
          cap_a(a,y)             "Arc cap Mcm per day"
          cost_a(a,y)            "Arc regulated tariff (USD/kcm)"
          cost_a_base            "Base Arc Usage Cost"
          d_a_max(a,y)           "Arc expans lim  Mcm per day"
          dat_a                  "Table for arcs data from Excel"
          dist_v                 "LNG shipping distances excel"
          dist_v_cut             "Cut off distance for LNG shipping routes to reduce solution times "
          excl_a(a)              "Remove trade option for non-economic reasons"
          inv_a(a,y)             "Arc expans cost USD per kcm"
          inv_a_base             "Base Arc Investment cost"
          is_a(n_o,n_i)          "Indicator that there is an arc between those nodes"
          is_liq(a)              "Indicator for arc being liquefaction arc: from prod node to lng node"
          is_pip(a)              "Indicator for arc being pipeline between 'normal' country nodes"
          is_reg(a)              "Indicator for arc being regasification arc: from regas node to cons node"
          is_same_cn(a)          "Are arc start and end in same country?"
          is_v(a)                "Indicator for arc being lng shipping arc"
          l_a(a)                 "Arc loss fraction"
          l_a_base               "Base Loss Arc"
          map_a_n_n(a,n_o,n_i)   "Indicator that this arc exists between those nodes"
;

*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*-*              LOAD AND ASSIGN SETS AND PARAMETERS
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
$gdxin gdx\%data%
$load    dat_a, dist_v
;

n_l(n)$SUM((cn,rgn), dat_n(n,cn,rgn,'Node','L')) = n(n);        /* liquef nodes */
n_r(n)$SUM((cn,rgn), dat_n(n,cn,rgn,'Node','R')) = n(n);        /* regasif nodes */

*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*
*                  ARC TYPES
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*
ap(a)$SUM((n_o,n_i), dat_a(a,n_o,n_i,'P')) = a(a);
al(a)$SUM((n_o,n_i), dat_a(a,n_o,n_i,'L')) = a(a);
ar(a)$SUM((n_o,n_i), dat_a(a,n_o,n_i,'R')) = a(a);
av(a)$(NOT(al(a) OR ap(a) OR ar(a))) = a(a);

is_pip(ap) = 1;
is_liq(al) = 1;
is_reg(ar) = 1;
is_v(av) = 1;

*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*
*                  ARC START AND END
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*
SET
         auxat   "auxiliary set"        /P,L,R/
;

LOOP{(a,n_o,n_i)$SUM(auxat,dat_a(a,n_o,n_i,auxat)),
   a_s(a,n_o) = 1;
   a_e(a,n_i) = 1;
   is_a(n_o,n_i) = 1;
   map_a_n_n(a,n_o,n_i) = 1;
};

PARAMETERS
         cnt_l, cnt_r, cnt_v, num_r
;

$offOrder
cnt_l(n_l) = ORD(n_l);
cnt_r(n_r) = ORD(n_r);
cnt_v(av) = ORD(av);

num_r = CARD(n_r);

is_a(n_l,n_r) = 1;
map_a_n_n(av,n_l,n_r)$(num_r*(cnt_l(n_l)-1)+ cnt_r(n_r) = cnt_v(av))= 1;

a_s(av,n_l)$SUM(n_r,map_a_n_n(av,n_l,n_r)) = 1;
a_e(av,n_r)$SUM(n_l,map_a_n_n(av,n_l,n_r)) = 1;

LOOP{(a,n_o,n_i,cn)$(map_a_n_n(a,n_o,n_i) AND map_n_cn(n_o,cn) AND map_n_cn(n_i,cn)),
   is_same_cn(a)=1;
};

dat_a(av,n_l,n_r,"len")$map_a_n_n(av,n_l,n_r) = dist_v(n_l,n_r);

*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*
*                  Transform from BCMA to MCM/D
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*
SET
         auxa "auxiliary set" /PCI20, PIC25, d_max1,d_max2,d_max3/
;

dat_a(a,n_o,n_i,y) = dat_a(a,n_o,n_i,y)/.365;                                    /*Capacities are daily, scale from BCMA to MCMD*/
dat_a(a,n_o,n_i,auxa) = dat_a(a,n_o,n_i,auxa)/.365;

*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*
*                    ARC VALUE ASSIGNMENTS
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*
cost_a_base(ap)= dat_oth('BFPipe');  inv_a_base(ap)= dat_oth('BICPipe'); l_a_base(ap)= dat_oth('BLPipe');
cost_a_base(al)= dat_oth('BFLiq');   inv_a_base(al)= dat_oth('BICLiq');  l_a_base(al)= dat_oth('BLLiq');
cost_a_base(ar)= dat_oth('BFReg');   inv_a_base(ar)= dat_oth('BICReg');  l_a_base(ar)= dat_oth('BLReg');
cost_a_base(av)= dat_oth('BFShip');                                      l_a_base(av)= dat_oth('BLShip');

dist_v_cut= dat_oth('DistCutOff');

LOOP{(a,n_o,n_i)$(map_a_n_n(a,n_o,n_i)),

   l_a(a) = l_a_base(a)*dat_a(a,n_o,n_i,"len");

   cap_a(a,y)$(NOT is_v(a)) = dat_a(a,n_o,n_i,y)/(1-l_a(a));

   cost_a(a,y) = cost_a_base(a)*(1-l_a(a))*(dat_a(a,n_o,n_i,"len") + max(1,dat_oth('BIPipeOffshMult')-1)*dat_a(a,n_o,n_i,"off"))*dat_a(a,n_o,n_i,"c_cal")*power(1+cost_infl,step_y*(ORD(y)-1));
   inv_a(a,y) = inv_a_base(a)*(1-l_a(a))*(dat_a(a,n_o,n_i,"len") + dat_a(a,n_o,n_i,"off"))*dat_a(a,n_o,n_i,"i_cal")*power(1+cost_infl,step_y*(ORD(y)-1))
              *(days_y/365)/step_y;              /* Scale with number of days that return on investment can be made and the number of years per period */

   d_a_max(a,y)$(NOT is_v(a) AND ORD(y)=1)= dat_a(a,n_o, n_i,'d_max1')/(1-l_a(a));
   d_a_max(a,y)$(NOT is_v(a) AND ORD(y)=2)= dat_a(a,n_o, n_i,'d_max2')/(1-l_a(a));
   d_a_max(a,y)$(NOT is_v(a) AND ORD(y)>2)= dat_a(a,n_o, n_i,'d_max3')/(1-l_a(a));
};

excl_a(av) = 0;

LOOP{(av,n_o,n_i)$(map_a_n_n(av,n_o,n_i)  AND (dist_v(n_o,n_i) > dist_v_cut OR is_same_cn(av))),
   excl_a(av)=1;
};

