PARAMETERS
          disc(y)                "Discount factor"
          is_pred(y,y2)          "Indicator for predecessor years: (pred,succ)"
;

*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*-*                  ASSIGNMENTS
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
disc(y) = 1/power(1+disc_rate,step_y*(ORD(y)-1));
is_pred(y,y2)$(ORD(y) < ORD(y2)) = 1;
