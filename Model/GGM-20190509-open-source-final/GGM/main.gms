*GGM OPEN SOURCE VERSION - See __READ_ME.txt for the license.
*May 2019 - Ruud Egging NTNU ruud.egging@ntnu.no

$oninline $OFFSYMXREF $Offuelxref $offinclude
*$offlisting
option   reslim=         7200
         iterlim=        1E9
*The listing file gets very big when limrow larger than 0
         limrow=         0
         limcol=         0
;
*------------------------------------------------------------------------------*
*----      Scenario and horizon specification
*------------------------------------------------------------------------------*
$SETGLOBAL data          SET-Nav         /*SET-Nav*/

* Choose one combination of WEO and SET-Nav scenarios: [SDS and Vision] or [NPS and Ref] *

*$SETGLOBAL WEO 'SDS'       $SETGLOBAL SETNav  'Vision'
$SETGLOBAL WEO 'NPS'       $SETGLOBAL SETNav  'Ref'

$SETGLOBAL last_yr       2060            /*2015, 2025, 2060*/
*-------------------------------------------------------------------------------
*----                        READ INPUT DATA
*-------------------------------------------------------------------------------
$INCLUDE data\all_input_data.gms
execute_unload 'gdx\%data%_%last_yr%_INPUTS.gdx';
*-------------------------------------------------------------------------------
*----                        SET UP MODEL AND REPORTS
*-------------------------------------------------------------------------------
$INCLUDE model\all_eq_and_var.gms

option QCP= CPLEX;
SGGM.optfile = 1;
SGGM.holdfixed=1;
*Initialize the model with a previously stored solution will reduce the time needed to find a new solution.
*execute_load    'gdx\%data%_%case%_%last_yr%.gdx' D_A, D_X, D_W, Q_P, Q_S, F_A, F_I, F_X;
$INCLUDE model\solve.gms
*Store the solution from the model to provide an initialization point for next time.
execute_unload  'gdx\%data%_%case%_%last_yr%.gdx' D_A, D_X, D_W, Q_P, Q_S, F_A, F_I, F_X;
$INCLUDE report\reports.gms
