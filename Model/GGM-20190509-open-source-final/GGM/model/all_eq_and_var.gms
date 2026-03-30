FREE VARIABLES
MinObj
;

POSITIVE VARIABLES
D_A(a,y)                         "Arc Capacity expansion (mcm / year)"
D_X(n,w,y)                       "Stor Extr Capacity expansion (mcm / year)"
D_W(n,w,y)                       "Stor WG Capacity expansion (mcm / year)"

Q_P(cn,n,r,d,y)                  "Quantity produced by resource (t is auxiliary) (mcm/yr)"
Q_S(cn,n,d,y)                    "Quantity sold (mcm/yr)"

F_A(cn,a,d,y)                    "Trader Arc Flow (mcm/yr)"
F_I(cn,n,w,d,y)                  "Trader Stor Injection (mcm/yr)"
F_X(cn,n,w,d,y)                  "Trader Stor Extraction (mcm/yr)"
;

EQUATIONS
*OBJECTIVE
def_obj                          "Minization objective definition"

*SUPPLIER MASS BALANCES
eq_mass_bal                      "Sum of sales + injections + exports cannot exceed purchases + extractions + loss-adjusted imports"
eq_stor_cycle                    "Extractions cannot exceed loss-adjusted injections"

*CAPACITY RESTRICTIONS
eq_cap_a                         "Arc capacity restriction"
eq_cap_p                         "Productoin capacity restriction"
eq_cap_x                         "Extraction capacity restriction"
eq_cap_w                         "Working gas capacity restriction"

*INVESTMENT RESTRICTIONS
eq_lim_a                         "Arc capacity expansion restriction"
eq_lim_x                         "Extraction capacity expansion restriction"
eq_lim_w                         "Storage working gas expansion restriction"
;

*-------------------------------------------------------------------------------
*---------------------    OBJECTIVE
*-------------------------------------------------------------------------------
*Cost function: MinObj = TC + MPA - REV - CS; Defining separate terms like this
*and adding them into an objective gives a cplex solver error.

def_obj..  MinObj =E=
* Total costs (TC):
                     (SUM(y, disc(y)*
                       (SUM((n,d), days_d(d)*
                             SUM(r, cost_pl(n,r,y)*sum(t,Q_P(t,n,r,d,y)) + 0.5*cost_pq(n,r,y)*sqr(sum(t,Q_P(t,n,r,d,y))))
                            +SUM((t,a), cost_a(a,y)*F_A(t,a,d,y))
                            +SUM((t,w), cost_x(n,w,y)*F_X(t,n,w,d,y))
                           )
                        +SUM(a,     inv_a(a,y)*D_A(a,y))
                        +SUM((n,w), inv_x(n,w,y)*D_X(n,w,y))
                        +SUM((n,w), inv_w(n,w,y)*D_W(n,w,y))
                    )))
* + market power adjustment (MPA):
                  + 0.5*SUM((t,n_c,d,y), disc(y)*days_d(d)*slp(n_c,d,y)*cour(t,n_c,y)*sqr(Q_S(t,n_c,d,y)))
* - revenues (REV):
                  - SUM((t,n_c,d,y), disc(y)*days_d(d)*(int(n_c,d,y)- slp(n_c,d,y)*SUM(t2$t_acc_n(t2,n_c), Q_S(t2,n_c,d,y)))*Q_S(t,n_c,d,y))
* - consumer surplus (CS):
                  - 0.5*SUM((n_c,d,y),  disc(y)*days_d(d)*slp(n_c,d,y)*sqr(SUM(t, Q_S(t,n_c,d,y))))
;

*-------------------------------------------------------------------------------
*----------             FREEZE ZERO VALUES
*-------------------------------------------------------------------------------
Q_P.fx(cn,n,r,d,y)$(NOT t_acc_np(cn,n))=0;
Q_S.fx(cn,n,d,y)  $(NOT t_acc_n(cn,n)) =0;
F_A.fx(cn,a,d,y)  $(NOT t_acc_a(cn,a)) =0;
F_I.fx(cn,n,w,d,y)$(NOT t_acc_n(cn,n) OR NOT map_w_n(w,n)) =0;
F_X.fx(cn,n,w,d,y)$(NOT t_acc_n(cn,n) OR NOT map_w_n(w,n)) =0;

*-------------------------------------------------------------------------------
*----------             SUPPLIER MASS BALANCES
*-------------------------------------------------------------------------------
eq_mass_bal(t,n,d,y)..
         SUM(r,                Q_P(t,n,r,d,y)) + SUM(a$a_e(a,n), F_A(t,a,d,y)*(1-l_a(a))) + SUM(w, F_X(t,n,w,d,y))
         =E=                   Q_S(t,n,d,y) + SUM(a$a_s(a,n), F_A(t,a,d,y)) + SUM(w, F_I(t,n,w,d,y))
;

eq_stor_cycle(t,n,w,y)..
             SUM(d,days_d(d)*F_I(t,n,w,d,y))*(1-l_i(n,w))
         =E= SUM(d,days_d(d)*F_X(t,n,w,d,y))
;

*-------------------------------------------------------------------------------
*-----------------       CAPACITY RESTRICTIONS
*-------------------------------------------------------------------------------
eq_cap_a(a,d,y)$(NOT is_v(a))..
         SUM(t, F_A(t,a,d,y))
         =L= cap_a(a,y)   + SUM(y2$(ORD(y2)<ORD(y)), D_A(a,y2))
;

eq_cap_p(t,n,r,d,y)..
         Q_P(t,n,r,d,y)
         =L= cap_p(n,r,y)
;

eq_cap_x(n,w,d,y)..
         SUM(t, F_X(t,n,w,d,y))
         =L= cap_x(n,w,y)   + SUM(y2$(ORD(y2)<ORD(y)), D_X(n,w,y2))
;

eq_cap_w(n,w,y)..
         SUM((t,d), days_d(d)*F_X(t,n,w,d,y))
         =L= cap_w(n,w,y)   + SUM(y2$(ORD(y2)<ORD(y)), D_W(n,w,y2))
;

*-------------------------------------------------------------------------------
*---------------------  INVESTMENT RESTRICTIONS
*-------------------------------------------------------------------------------
eq_lim_a(a,y)$(NOT is_v(a))..  D_A(a,y)   =L= d_a_max(a,y);
eq_lim_x(n,w,y)..              D_X(n,w,y) =L= d_x_max(n,w,y);
eq_lim_w(n,w,y)..              D_W(n,w,y) =L= d_w_max(n,w,y);

*-------------------------------------------------------------------------------
*---------------------             MODEL
*-------------------------------------------------------------------------------
MODEL SGGM /all/
;
