$oninline
*------------------------------------------------------------------------------*
*----      CHOOSE SCENARIO FOR WHICH TO WRITE EXCEL FILE REPORTS
*------------------------------------------------------------------------------*
$SETGLOBAL data          SET-Nav         /*SET-Nav*/

* Choose one combination of WEO and SET-Nav scenarios: [SDS and Vision] or [NPS and Ref] *

*$SETGLOBAL WEO 'SDS'       $SETGLOBAL SETNav  'Vision'
$SETGLOBAL WEO 'NPS'       $SETGLOBAL SETNav  'Ref'

$SETGLOBAL case          %WEO%-%SETNav%
$SETGLOBAL last_yr       2060            /*2060 */
*------------------------------------------------------------------------------*
*----      WRITE THE REPORTS TO EXCEL
*------------------------------------------------------------------------------^*

*Write calibration information and mass balances:
execute 'gdxxrw gdx\%data%_%case%_%last_yr%_REPORTS.gdx o=excel\%data%_%case%_%last_yr%_rep_calib.xlsx    @excel\write_calib.txt';

*Write information for IIASA platform:
execute 'gdxxrw gdx\%data%_%case%_%last_yr%_REPORTS.gdx o=excel\%data%_%case%_%last_yr%_rep_IAMC.xlsx     @excel\write_IAMC.txt';

*Write information for geo_map tool:
execute 'gdxxrw gdx\%data%_%case%_%last_yr%_REPORTS.gdx o=geo_map\%data%_%case%_%last_yr%_rep_geo_map.xlsx @geo_map\write_geo_map.txt';
