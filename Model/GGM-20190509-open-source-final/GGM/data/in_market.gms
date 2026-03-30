SETS
         t(cn)                   suppliers
;

ALIAS(t,t2);

PARAMETERS
         cour(cn,n,y)            "Indicator for the relative market power of transmitter t in market n"
         dat_mp                  "Market power data excel "
         t_acc_a(cn,a)           "Access of Supplier to arc "
         t_acc_liq(cn)           "Supplier has liquefier(s) in country"
         t_acc_n(cn,n)           "Presence / Access of Supplier on nodes n"
         t_acc_np(cn,n)          "Production node of supplier"
;

*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*-*              LOAD AND ASSIGN SETS AND PARAMETERS
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
$gdxin gdx\%data%
$load    dat_mp
;

t(cn)$SUM((n,rgn), dat_n(n,cn,rgn,'Node','P')) = cn(cn);                        /* suppliers */
t_acc_np(t,n)$SUM((rgn), dat_n(n,t,rgn,'Node','P')) = 1;
*-------------------------------------------------------------------------------
*                 Supplier MARKET ACCESS
*-------------------------------------------------------------------------------
*      Supplier ACCESS own prod nodes
*      Supplier ACCESS to all consumption nodes and regular pipelines
*-------------------------------------------------------------------------------
t_acc_n(t,n_p)=t_acc_np(t,n_p);
t_acc_n(t,n_c)= 1;
t_acc_a(t,ap)=  1;
*-------------------------------------------------------------------------------
*                Supplier ACCESS TO Own liquefaction node and arc
*Supplier gets access liquef node, if that is connected to one of his prod nodes
*-------------------------------------------------------------------------------
LOOP{(t,al,n_p,n_l)$(t_acc_np(t,n_p) AND map_a_n_n(al,n_p,n_l)),
  t_acc_liq(t) = 1;                                                             /* Supplier has liquefier */
  t_acc_n(t,n_l) = 1;                                                           /* Suppier access to liquefactoin node */
  t_acc_a(t,al) = 1;                                                            /* Supplier access to liquefaction arc */
};
*-------------------------------------------------------------------------------
*          Supplier Access Regas and Cons Node and shipping and regas arcs
* Supplier gets access regasification node and the connected consumption node
* if it has liquefactoin and consumption node is an own prod node and access is not excluded
* Note: US1 is not a production node, therefore the below assigns USA access to the US1 regasifier and arc REG_RUS1
*-------------------------------------------------------------------------------
LOOP{(t,n_l,av,n_r,ar,n_c)$(t_acc_liq(t) AND map_a_n_n(av,n_l,n_r) AND map_a_n_n(ar,n_r,n_c)
                             AND NOT t_acc_np(t,n_c)
                            ),
   t_acc_n(t,n_r) = 1;
   t_acc_a(t,av) = 1;
   t_acc_a(t,ar) = 1;
};
*-------------------------------------------------------------------------------
*                    Market power
*-------------------------------------------------------------------------------
cour(t,n_c,y)$(t_acc_n(t,n_c) AND NOT map_n_cn(n_c,t)) = dat_mp(t,'export');
cour(t,n_c,y)$map_n_cn(n_c,t) = dat_mp(t,'domestic');
cour(t,n_c,y)$dat_mp(t,n_c) = dat_mp(t,n_c);

*Market power moderation in later years
cour(t,n_c,y)=max(cour(t,n_c,y)*dat_mp(t,'ratio'),cour(t,n_c,y)*power(dat_mp(t,'factor'),ORD(y)-1));
