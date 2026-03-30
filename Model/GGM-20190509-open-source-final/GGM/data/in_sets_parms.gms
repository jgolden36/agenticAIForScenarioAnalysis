*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*            SETS
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
SETS
          a                      Set of all arcs
          cn                     Countries
          d                      Seasons
          n                      Nodes
          rgn                    Regions
;
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*            ALIASES
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
ALIAS (cn,cno,cni);
ALIAS (n,n_o,n_i);
ALIAS (rgn,rgn_o,rgn_i);
ALIAS (y,y2);

*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*     Set up reading from Excel
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
PARAMETERS
          cost_infl              "Cost inflator, from Excel"
          dat_n                  "Help table for definition of nodes sets."
          dat_oth                "Other data, from Excel"
          days_d(d)              "Days in season"
          days_y                 "Total number of days in all seasons covered by the model. Used to adjust reported daily values to yearly values in output reports"
          disc_rate              "Discount rate from Excel"
          map_cn_rgn(cn,rgn)     "Indicator for country is in region"
          map_n_cn(n,cn)         "Indicator for node is in country"
          map_n_cn_rgn(n,cn,rgn) "Indicater for node-country-region"
          map_n_rgn(n,rgn)       "indicator for node is in region"
          step_y                 "Number of years between two stages"
;

*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*            LOAD DATA FROM EXCEL FILES
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
execute 'xlstalk.exe -E data\%data%\data.xlsx';
abort$(errorlevel <=0) "data\%data%\data.xlsx does not exist";
$call "GDXXRW data\%data%\data.xlsx O=gdx\%data% SkipEmpty=0 @data\read_data.txt"

execute 'xlstalk.exe -E data\%data%\data_proj.xlsx';
abort$(errorlevel <=0) "data\%data%\data_proj.xlsx does not exist";
$call "GDXXRW data\%data%\data_proj.xlsx O=gdx\%data%_%case%_proj SkipEmpty=0 @data\%data%\read_proj.txt"

execute 'xlstalk.exe -E data\%data%\data_calib_%case%.xlsx';
abort$(errorlevel <=0) "data\%data%\data_calib_%case%.xlsx does not exist";
execute 'xlstalk.exe -M data\%data%\data_calib_%case%.xlsx';
abort$(errorlevel >=2) "data\%data%\data_calib_%case%.xlsx has been modified but not saved.";
$call "GDXXRW data\%data%\data_calib_%case%.xlsx O=gdx\%data%_%case%_calib SkipEmpty=0 @data\read_calib.txt"
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
*            ASSIGN PARAMETERS
*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
$gdxin gdx\%data%
$load    a, cn, d, n, rgn, dat_n, dat_oth
;

SETS
         n_aux "Auxiliary set" /C,P,W,L,R,transit/
;

map_n_cn(n,cn)$SUM((rgn,n_aux), dat_n(n,cn,rgn,'Node',n_aux)) = 1;
map_n_rgn(n,rgn)$SUM((cn,n_aux), dat_n(n,cn,rgn,'Node',n_aux)) = 1;
map_cn_rgn(cn,rgn)$SUM((n,n_aux), dat_n(n,cn,rgn,'Node',n_aux)) = 1;
map_n_cn_rgn(n,cn,rgn)=map_n_cn(n,cn)*map_n_rgn(n,rgn);

cost_infl = dat_oth('CostInfl');
disc_rate = dat_oth('DiscRate');
step_y = dat_oth('YearStep');
days_d(d) = dat_oth(d);
days_y = SUM(d, days_d(d));

*------------------------------------------------------------------------------*
*            CHECKS
*------------------------------------------------------------------------------*
abort$(abs(days_y-362.5)>3) "in_sets_parms. Incorrect number of days in a year. Adjust season lengths so that total number of days in a year is 365."
