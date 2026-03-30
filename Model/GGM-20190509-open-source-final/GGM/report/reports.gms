SETS
    maux         "mass balance auxiliary index"           /prod,pipe,LNG,cons,stor,price/
    maux2        "mass balance auxiliary index-2"         /prod,cons,price/
    maux3        "mass balance auxiliary index-3"         /prod,cons/
    mauxin       "mass balance auxiliary index-sources"   /prod,pipe,LNG,stor,TOT/
    mauxout      "mass balance auxiliary index-sinks"     /cons,pipe,LNG,stor,TOT/
    calx         "calibration auxiliary index"            /ref,out,abs/
    calx2        "calibration auxiliary index-2"          /ref,out,abs,rel/
    daux         "extended 'seasons' indices"             /'y',L,H,P/
    aaux1        "arcs auxiliary index"                   /capexog,expans,expcum,captot,capnet,usage,'usage-L','usage-H','usage-P',flow/
    rgn_rep(rgn) "reporting regions - to exclude virtual regions LIQ and REG from reports"
    yrep(y)      "reporting years - to exclude the end of horizon years, 2055 and 2060 from the reports"
;

ALIAS (rgn_rep,rro,rri);
ALIAS(yrep,yrep2);

rgn_rep(rgn)=YES;
rgn_rep('LIQ')=NO;    /* Exclude artificial region LIQ from reporting regions*/
rgn_rep('REG')=NO;    /* Exclude artificial region REG from reporting regions*/

yrep(y)$(ORD(y)<=8) = YES;   /* Select first eight years as reporting years (exclude 2055 and 2060)*/

parameter
          rep_arc            "Arc infrastructure expansions and capacities in BCM and Mcm/d-equivalents - intermediate"
          rep_infra_pipe     "Arc infrastructure expansions and capacities in Mcm/d-equivalents - pipelines"
          rep_infra_liq      "Arc infrastructure expansions and capacities in Mcm/d-equivalents - liquefiers country aggregates"
          rep_infra_regas    "Arc infrastructure expansions and capacities in Mcm/d-equivalents - regasifiers country aggregates"
          rep_infra_stor     "Storage infrastructure expansions and capacities WG in MCM and Extraction in Mcm/d - country aggregates"
          rep_cal_n          "Node calibration report BCM (seasonal cons and price, yearly prod) - special purpose"
          rep_cal_cn         "Country calibration report BCM"
          rep_cal_rgn        "Region and world calib report BCM"
          rep_geo_map        "Country level data for geo maps in BCMA"
          rep_geo_trade      "Regional trade data for geo maps BCMA"
          rep_IAMC           "Country level data IAMC platform IIASA in BCMA - Annual average volumes, prices (EUR/kcm), and gross outflow and net inflow capacities"
          rep_IAMC_supply    "Regional trade data for IAMC platform BMCA"
          rep_mass_bal       "Seasonal, nodal mass balances (Mcm/d) and yearly country mass balance (BCM/A)"
          ref_cal            "Some reference values used in calibration"
          price(n,d,y)       "Market price (EUR/kcm)"
          cons(n,d,y)        "Yearly, seasonal consumption (Mcm/d)"
          mcmd2bcm(d)        "Multiplication factor from mcmd/d in a season to bcm"
;

mcmd2bcm(d)=days_d(d)*.365/days_y;

ref_cal('prod',n,y)=ref_p(n,y)*.365;
ref_cal('cons',n,y)=ref_c(n,y)*.365;
ref_cal('price',n,y)$ref_c(n,y)=sum(d,ref_pr(n,d,y)*ref_c_d(n,d,y)*mcmd2bcm(d))/ref_cal('cons',n,y);

cons(n,d,y)=SUM(t,Q_S.l(t,n,d,y));
price(n,d,y)=int(n,d,y)- slp(n,d,y)*cons(n,d,y);


$INCLUDE report\rep_mass_bal.gms
$INCLUDE report\rep_calib.gms
$INCLUDE report\rep_infra.gms
$INCLUDE report\rep_geo_map.gms
$INCLUDE report\rep_IAMC.gms

*Store reports in a gdx file - see create_excel_dumps.gms for further processing:
execute_unload 'gdx\%data%_%case%_%last_yr%_REPORTS.gdx',
   rep_cal_cn, rep_cal_rgn, rep_mass_bal
   rep_infra_pipe, rep_infra_liq, rep_infra_regas, rep_infra_stor
   rep_IAMC_supply
   rep_IAMC
   rep_geo_map, rep_geo_trade
;

*Store reports in a gdx file - see merge_gdx_files.gms for further processing
*Only for full time horizon runs
if { card(y)=10,
  execute_unload 'gdx\%case%.gdx',
   rep_cal_cn, rep_cal_rgn, rep_mass_bal
   rep_infra_pipe, rep_infra_liq, rep_infra_regas, rep_infra_stor
   rep_IAMC_supply
  ;
}
;
