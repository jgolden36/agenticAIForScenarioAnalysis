SETS
         n_w(n)                  "Set of nodes with storage"
         w                       "storages"
;
PARAMETERS
          l_i(n,w)               "stor injection loss fraction"
          cost_x(n,w,y)          "stor extr costs (EUR or USD per kcm)"
          cap_x(n,w,y)           "daily stor extraction cap Mcmd"
          cap_w(n,w,y)           "stor work gas Mcm scaled by days_d('L')/183"
          inv_x(n,w,y)           "extraction cap expansion cost (EUR or USD per kcm per year)"
          inv_w(n,w,y)           "working gas expans cost (EUR or USD per kcm)"
          d_x_max(n,w,y)         "extraction cap expans limit"
          d_w_max(n,w,y)         "working gas expans limit"
          w_grow(n,y)            "storage cost inflator"
          map_w_n(w,n)           "storage in node"
          map_w_cn(w,cn)         "storage in country"
          dat_w                  "storage excel data"
;
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*-*              LOAD AND ASSIGN SETS AND PARAMETERS
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
$gdxin gdx\%data%
$load    w
$load    dat_w
;

n_w(n) $SUM((cn,rgn), dat_n(n,cn,rgn,'Node','W'))= n(n);                        /* nodes with storage */
w_grow(n,y)= power(1+cost_infl, step_y*(ORD(y)-1));

map_w_n(w,n)$SUM((cn,y), dat_w(cn,n,w,'WG',y)) = 1;
map_w_cn(w,cn)$SUM((n,y),dat_w(cn,n,w,'WG',y)) = 1;
l_i(n,w) = SUM(cn$map_w_cn(w,cn), dat_w(cn,n,w,'inj','loss'));

LOOP{(n,cn,w)$(map_n_cn(n,cn) AND map_w_cn(w,cn)),
   cap_x (n,w,y)= dat_w(cn,n,w,'extr',y);                                       /*Daily extraction capacity*/
   cost_x(n,w,y)= dat_w(cn,n,w,'extr','oper')*w_grow(n,y);                      /*Daily extraction costs*/
   inv_x(n,w,y) = dat_oth('BIStorX')*dat_w(cn,n,w,'extr','calib')*w_grow(n,y)*(days_d('L')/183)/step_y; /* Need to scale by season length because in real life capacity can be used every day, and by num years per period*/

   cap_w(n,w,y) = dat_w(cn,n,w,'WG',y)*(days_d('L')/183);                         /* scale WG capacity with season length. */
   inv_w(n,w,y) = dat_oth('BIStorW')*dat_w(cn,n,w,'WG',  'calib')*w_grow(n,y)/step_y;  /* here you can use every cub meter one time regardless, but need to scale by num years per period*/

   d_x_max(n,w,y)$(ORD(y) > 1) = dat_w(cn,n,w,'extr','d_max');
   d_w_max(n,w,y)$(ORD(y) > 1) = dat_w(cn,n,w,'WG',  'd_max')*(days_d('L')/183);  /* scale with season length. */
};
