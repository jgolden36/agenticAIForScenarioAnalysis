$SETGLOBAL case  %WEO%-%SETNav%          /*set the case string*/

$INCLUDE data\%last_yr%.gms              /*load the years set*/
$INCLUDE data\in_sets_parms.gms          /*define model agent sets and parameters, load Excel files into gdx*/
$INCLUDE data\in_period.gms              /*time structure and discounting*/

$INCLUDE data\in_prod.gms                /*production data*/
$INCLUDE data\in_cons.gms                /*consumption data*/
$INCLUDE data\in_arcs.gms                /*arc data, i.e. pipelines, liquefiers, shipping, regasifiers*/
$INCLUDE data\in_stor.gms                /*storage data*/
$INCLUDE data\in_market.gms              /*market power*/
;
